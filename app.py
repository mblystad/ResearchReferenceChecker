from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional
from io import BytesIO

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reference_checker.predatory_db import PredatoryDbProvider  # noqa: E402
from reference_checker.crossref import CrossrefMetadataProvider  # noqa: E402
from reference_checker.reference_parser import ReferenceListParser  # noqa: E402
from reference_checker.reference_types import classify_reference  # noqa: E402
from reference_checker.validation import validate_reference_completeness  # noqa: E402


STYLE_OPTIONS = {
    "APA": "apa",
    "AMA": "ama",
    "Neutral": "neutral",
}

LINK_COLUMNS = {
    "manual_check_homepage": "Homepage",
    "manual_check_doaj": "DOAJ",
    "manual_check_cope": "COPE",
    "manual_check_nlm_catalog": "NLM Catalog",
    "manual_check_pubmed_search": "PubMed",
    "manual_check_scimagojr": "ScimagoJR",
    "manual_check_kanalregister": "Kanalregister",
    "manual_check_google": "Google",
}

RISK_PRIORITY = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "unknown": 0,
}

NORWEGIAN_PRIORITY = {
    "2": 3,
    "1": 2,
    "0": 1,
    "unknown": 0,
}


def _normalize_risk(value: Optional[str]) -> str:
    if not value:
        return "Unknown"
    return value.strip().lower()


def _pick_risk(values: List[Optional[str]]) -> str:
    best = "Unknown"
    score = -1
    for value in values:
        normalized = _normalize_risk(value)
        weight = RISK_PRIORITY.get(normalized, 0)
        if weight > score:
            best = normalized
            score = weight
    return best.title() if best else "Unknown"


def _normalize_level(value: Optional[str]) -> str:
    if not value:
        return "Unknown"
    return value.strip()


def _pick_norwegian(values: List[Optional[str]]) -> str:
    best = "Unknown"
    score = -1
    for value in values:
        normalized = _normalize_level(value)
        weight = NORWEGIAN_PRIORITY.get(normalized.lower(), 0)
        if weight > score:
            best = normalized
            score = weight
    return best


def _collect_manual_links(matches) -> Dict[str, Optional[str]]:
    links: Dict[str, Optional[str]] = {key: None for key in LINK_COLUMNS}
    for match in matches:
        for key in LINK_COLUMNS:
            if links[key]:
                continue
            url = match.record.manual_links.get(key)
            if url:
                links[key] = url
    return links


def _missing_info_messages(style_key: str, reference) -> List[str]:
    issues = validate_reference_completeness(reference, style=style_key)
    messages: List[str] = []
    for issue in issues:
        if "missing" in issue.code:
            messages.append(issue.message)
    return sorted(set(messages))


def _build_rows(reference_text: str, style_key: str, use_crossref: bool):
    parser = ReferenceListParser()
    references = parser.parse(reference_text)
    if not references:
        return [], False

    if use_crossref:
        provider = CrossrefMetadataProvider()
        references = [provider.enrich(ref) for ref in references]

    for ref in references:
        ref.entry_type = classify_reference(ref)

    pred_db = PredatoryDbProvider.load_default(base_dir=ROOT)
    pred_db_loaded = pred_db is not None

    rows = []
    for ref in references:
        missing_info = _missing_info_messages(style_key, ref)
        matches = pred_db.match_reference(ref) if pred_db else []
        if pred_db_loaded:
            predatory_hit = "Yes" if matches else "No"
            risk_level = _pick_risk([m.record.risk_level for m in matches]) if matches else "Unknown"
            norwegian_level = (
                _pick_norwegian([m.record.norwegian_level for m in matches]) if matches else "Unknown"
            )
            manual_links = _collect_manual_links(matches)
        else:
            predatory_hit = "Unavailable"
            risk_level = "Unavailable"
            norwegian_level = "Unavailable"
            manual_links = {key: "" for key in LINK_COLUMNS}

        conflict = ""
        if predatory_hit == "Yes" and norwegian_level in {"1", "2"}:
            conflict = "Yes"

        row = {
            "Reference": ref.raw_text,
            "Predatory match": predatory_hit,
            "Risk level": risk_level,
            "Norwegian level": norwegian_level,
            "Predatory vs Norwegian level": conflict,
            "Predatory reason": (
                matches[0].record.warning_summary if matches and matches[0].record.warning_summary else ""
            ),
            "Missing info": ", ".join(missing_info) if missing_info else "",
        }
        row.update({LINK_COLUMNS[key]: manual_links[key] or "" for key in LINK_COLUMNS})
        rows.append(row)

    return rows, pred_db_loaded


def _build_overlap_report() -> tuple[pd.DataFrame | None, str | None]:
    csv_path = ROOT / "predatory_db_v7_with_norwegian_levels.csv"
    if not csv_path.exists():
        csv_path = ROOT / "predatory_db_v6_manual_check_links.csv"
    if not csv_path.exists():
        csv_path = ROOT / "data" / "predatory_db_v6_manual_check_links.csv"
    if not csv_path.exists():
        return None, "Predatory registry CSV not found."

    df = pd.read_csv(csv_path)
    df["norwegian_level"] = df["norwegian_level"].astype(str).str.strip()
    df["risk_level"] = df.get("risk_level", df.get("risk", "")).astype(str).str.strip()

    overlap = df[
        df["norwegian_level"].isin(["0", "1", "2"])
        & df["risk_level"].str.len().gt(0)
    ].copy()

    if overlap.empty:
        return overlap, None

    columns = [
        "type",
        "name",
        "risk_level",
        "norwegian_level",
        "warning_summary",
        "url",
        "manual_check_homepage",
        "manual_check_google",
        "manual_check_google_predatory_query",
        "manual_check_doaj",
        "manual_check_cope",
        "manual_check_nlm_catalog",
        "manual_check_pubmed_search",
        "manual_check_scimagojr",
        "manual_check_kanalregister",
    ]
    existing = [col for col in columns if col in overlap.columns]
    overlap = overlap[existing]
    return overlap, None


def main() -> None:
    st.set_page_config(page_title="Reference Checker", layout="wide")
    st.title("Reference Checker")
    st.caption(
        "Paste a reference list to flag missing details, predatory-journal matches, and Norwegian levels."
    )

    style_label = st.selectbox("Reference style", list(STYLE_OPTIONS.keys()), index=0)
    style_key = STYLE_OPTIONS[style_label]
    use_crossref = st.checkbox(
        "Use Crossref to enrich metadata (requires internet)",
        value=False,
        help="Uses DOI or title to fetch journal details before matching predatory/Norwegian levels.",
    )

    reference_text = st.text_area(
        "Reference list",
        placeholder="Paste one reference per line...",
        height=260,
    )

    if st.button("Analyze references"):
        if not reference_text.strip():
            st.warning("Paste your reference list first.")
            return
        rows, pred_db_loaded = _build_rows(reference_text, style_key, use_crossref)
        if not rows:
            st.info("No references detected. Add one reference per line.")
            return
        if not pred_db_loaded:
            st.warning(
                "Predatory registry CSV not found. Place "
                "`predatory_db_v7_with_norwegian_levels.csv` in the project root or `data/`."
            )

        df = pd.DataFrame(rows)
        column_config = {
            "Homepage": st.column_config.LinkColumn("Homepage"),
            "DOAJ": st.column_config.LinkColumn("DOAJ"),
            "COPE": st.column_config.LinkColumn("COPE"),
            "NLM Catalog": st.column_config.LinkColumn("NLM Catalog"),
            "PubMed": st.column_config.LinkColumn("PubMed"),
            "ScimagoJR": st.column_config.LinkColumn("ScimagoJR"),
            "Kanalregister": st.column_config.LinkColumn("Kanalregister"),
            "Google": st.column_config.LinkColumn("Google"),
        }

        st.dataframe(
            df,
            use_container_width=True,
            column_config=column_config,
            hide_index=True,
        )

    st.divider()
    st.subheader("Database audit: predatory + Norwegian overlap")
    st.caption(
        "Generate a spreadsheet of entries that appear in the predatory registry and also "
        "have a Norwegian level (0/1/2)."
    )
    if st.button("Build overlap report"):
        overlap, error = _build_overlap_report()
        if error:
            st.warning(error)
            return
        if overlap is None or overlap.empty:
            st.info("No overlap entries found.")
            return

        buffer = BytesIO()
        overlap.to_excel(buffer, index=False)
        buffer.seek(0)
        st.download_button(
            "Download overlap report (Excel)",
            data=buffer,
            file_name="predatory_norwegian_overlap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
