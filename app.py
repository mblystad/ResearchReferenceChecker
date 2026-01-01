from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reference_checker.predatory_db import PredatoryDbMatch, PredatoryDbProvider  # noqa: E402
from reference_checker.reference_parser import ReferenceListParser  # noqa: E402


BASIS_LABELS = {
    "name": "Exact name",
    "domain": "Exact domain",
    "fuzzy-name": "Fuzzy name",
}

BASIS_PRIORITY = {
    "name": 3,
    "domain": 2,
    "fuzzy-name": 1,
}


def _format_basis(basis: str | None) -> str:
    if not basis:
        return ""
    return BASIS_LABELS.get(basis, basis)


def _format_score(score: float | None) -> str:
    if score is None:
        return ""
    return f"{score:.0%}"


def _pick_best_match(matches: list[PredatoryDbMatch]) -> PredatoryDbMatch | None:
    if not matches:
        return None

    def sort_key(match: PredatoryDbMatch) -> tuple[float, int]:
        score = match.score if match.score is not None else 0.0
        priority = BASIS_PRIORITY.get(match.basis, 0)
        return score, priority

    return max(matches, key=sort_key)


def _norwegian_search_url(journal: str | None) -> str:
    if not journal:
        return ""
    query = quote_plus(journal.strip())
    if not query:
        return ""
    return f"https://kanalregister.hkdir.no/sok?option=journals&input={query}&page=1"


def _build_rows(
    reference_text: str, *, fuzzy_threshold: float, max_fuzzy_matches: int
) -> tuple[list[dict[str, str]], bool]:
    parser = ReferenceListParser()
    references = parser.parse(reference_text)
    if not references:
        return [], False

    pred_db = PredatoryDbProvider.load_default(base_dir=ROOT)
    pred_db_loaded = pred_db is not None

    rows: list[dict[str, str]] = []
    for ref in references:
        norwegian_search = _norwegian_search_url(ref.journal)
        matches = (
            pred_db.match_reference(
                ref,
                fuzzy=True,
                fuzzy_threshold=fuzzy_threshold,
                max_fuzzy_matches=max_fuzzy_matches,
            )
            if pred_db
            else []
        )
        best = _pick_best_match(matches)
        if best:
            row = {
                "Reference": ref.raw_text,
                "Match status": "Match",
                "Matched entry": best.record.name,
                "Matched on": best.matched_value,
                "Match basis": _format_basis(best.basis),
                "Match score": _format_score(best.score),
                "Risk level": best.record.risk_level or "Unknown",
                "Norwegian level": best.record.norwegian_level or "Unknown",
                "Predatory reason": best.record.warning_summary or "",
                "Norwegian registry search": norwegian_search,
                "Other matches": str(max(0, len(matches) - 1)),
            }
        else:
            row = {
                "Reference": ref.raw_text,
                "Match status": "No match",
                "Matched entry": "",
                "Matched on": "",
                "Match basis": "",
                "Match score": "",
                "Risk level": "",
                "Norwegian level": "",
                "Predatory reason": "",
                "Norwegian registry search": norwegian_search,
                "Other matches": "0",
            }
        rows.append(row)

    return rows, pred_db_loaded


def main() -> None:
    st.set_page_config(page_title="Predatory Reference Checker", layout="wide")
    st.title("Predatory Reference Checker")
    st.caption(
        "Paste references or journal/publisher names (one per line). "
        "We fuzzy-match against the predatory registry CSV."
    )

    reference_text = st.text_area(
        "Reference list",
        placeholder="Paste one reference or journal name per line...",
        height=260,
    )
    fuzzy_threshold = st.slider(
        "Fuzzy match threshold",
        min_value=0.7,
        max_value=0.98,
        value=0.88,
        step=0.01,
        help="Higher values mean stricter matching.",
    )
    max_fuzzy_matches = st.number_input(
        "Max fuzzy matches per reference",
        min_value=1,
        max_value=10,
        value=3,
        step=1,
    )

    if st.button("Check references"):
        if not reference_text.strip():
            st.warning("Paste your reference list first.")
            return
        rows, pred_db_loaded = _build_rows(
            reference_text,
            fuzzy_threshold=fuzzy_threshold,
            max_fuzzy_matches=max_fuzzy_matches,
        )
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
            "Norwegian registry search": st.column_config.LinkColumn(
                "Norwegian registry search"
            )
        }
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
        )


if __name__ == "__main__":
    main()
