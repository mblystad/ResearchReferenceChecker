from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
import re

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

DOI_REGEX = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

SAMPLE_TEXT = """Doe J. Sample article title. Journal of Testing. 2021;10(2):123-130. doi:10.1234/jt.2021.456.
Smith A, Lee B. Another study on testing. Proceedings of the Reference Checking Conference; 2020. Available from: https://example.com/testing.
Patel R. Data validation handbook. Testing Press; 2019.
Adams K. Preprint example on reference integrity. bioRxiv; 2023. doi:10.1101/2023.12345."""

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Source+Sans+3:wght@400;600&display=swap');

:root {
  --paper: #f6f1e7;
  --paper-deep: #efe4d4;
  --panel: #fffaf1;
  --ink: #2b2a28;
  --muted: #6e645b;
  --accent: #7b5a3a;
  --accent-soft: #e9dccb;
  --success: #3b6b4f;
  --warning: #a3613f;
  --border: #e1d4c2;
  --shadow: 0 12px 32px rgba(67, 54, 41, 0.12);
}

html, body, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 25% 15%, rgba(255, 250, 238, 0.8) 0, rgba(255, 250, 238, 0) 45%),
    radial-gradient(circle at 75% 10%, rgba(246, 232, 214, 0.7) 0, rgba(246, 232, 214, 0) 48%),
    linear-gradient(180deg, var(--paper) 0%, #f9f4ec 100%);
  color: var(--ink);
  font-family: "Source Sans 3", sans-serif;
}

h1, h2, h3, .headline {
  font-family: "Merriweather", serif !important;
  color: var(--ink);
}

.hero {
  background: linear-gradient(135deg, rgba(255,250,238,0.9), rgba(239,228,212,0.85));
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 22px 28px;
  box-shadow: var(--shadow);
  margin-bottom: 1.25rem;
}

.hero p {
  color: var(--muted);
  margin-top: 0.4rem;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: 0 8px 20px rgba(67, 54, 41, 0.08);
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent);
  margin-right: 8px;
}

.chip-success { background: rgba(59, 107, 79, 0.12); color: var(--success); }
.chip-warning { background: rgba(163, 97, 63, 0.12); color: var(--warning); }
.chip-neutral { background: rgba(110, 100, 91, 0.12); color: var(--muted); }

.stat-card {
  background: #fbf7ef;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.stat-value {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--ink);
}

.stTextArea textarea {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fffdfa;
}

.stButton button {
  background: var(--accent);
  color: white;
  border-radius: 999px;
  padding: 0.4rem 1.4rem;
  border: none;
}

.stButton button:hover {
  background: #6a4c31;
  color: white;
}

[data-testid="stDataFrame"] {
  border-radius: 14px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.footer-note {
  color: var(--muted);
  font-size: 0.85rem;
}
</style>
"""


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


def _extract_reference_text_from_upload(uploaded) -> str | None:
    if uploaded is None:
        return None
    name = (uploaded.name or "").lower()
    raw_bytes = uploaded.getvalue()
    if name.endswith(".csv"):
        try:
            df = pd.read_csv(StringIO(raw_bytes.decode("utf-8")))
        except UnicodeDecodeError:
            df = pd.read_csv(StringIO(raw_bytes.decode("latin-1")))
        if df.empty:
            return ""
        column = df.columns[0]
        lines = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
        return "\n".join(lines)
    return raw_bytes.decode("utf-8", errors="ignore")


def _has_authors(raw_text: str, parsed_authors: list[str]) -> bool:
    if parsed_authors:
        return True
    if not raw_text:
        return False
    first_segment = raw_text.split(".", 1)[0]
    if "et al" in first_segment.lower():
        return True
    if "," in first_segment:
        return True
    if re.search(r"\b[A-Z][a-zA-Z'-]+\s+[A-Z][a-zA-Z'-]+\b", first_segment):
        return True
    return False


def _has_title(raw_text: str, parsed_title: str | None) -> bool:
    if parsed_title:
        return True
    if not raw_text:
        return False
    if re.search(r"\(\s*(19|20)\d{2}\s*\)\.\s*[^.]{3,}\.", raw_text):
        return True
    segments = [seg.strip() for seg in raw_text.split(".") if seg.strip()]
    if len(segments) >= 2:
        candidate = segments[1]
        if not candidate.lower().startswith("available from"):
            return True
    return False


def _has_journal(raw_text: str, parsed_journal: str | None) -> bool:
    if parsed_journal:
        return True
    if not raw_text:
        return False
    match = re.search(r"\.\s*([^\.]+)\.\s*(19|20)\d{2}", raw_text)
    if match:
        candidate = match.group(1).strip()
        if candidate and not candidate.lower().startswith("available from"):
            return True
    return False


def _has_doi(raw_text: str, parsed_doi: str | None) -> bool:
    if parsed_doi:
        return True
    if not raw_text:
        return False
    return DOI_REGEX.search(raw_text) is not None


def _missing_field_summary(raw_text: str, ref) -> str:
    missing = []
    if not _has_authors(raw_text, ref.authors):
        missing.append("authors")
    if not _has_title(raw_text, ref.title):
        missing.append("title")
    if not _has_journal(raw_text, ref.journal):
        missing.append("journal")
    if not _has_doi(raw_text, ref.doi):
        missing.append("doi")
    if not missing:
        return "OK"
    return "Missing: " + ", ".join(missing)


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
                "Source": best.record.source or "",
                "Source URL": best.record.source_url or "",
                "Norwegian registry search": norwegian_search,
                "Missing fields": _missing_field_summary(ref.raw_text, ref),
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
                "Source": "",
                "Source URL": "",
                "Norwegian registry search": norwegian_search,
                "Missing fields": _missing_field_summary(ref.raw_text, ref),
            }
        rows.append(row)

    return rows, pred_db_loaded


def _style_match_status(value: str) -> str:
    if value == "Match":
        return "background-color: rgba(59, 107, 79, 0.12); color: #2f5d42; font-weight: 600;"
    return "background-color: rgba(163, 97, 63, 0.12); color: #7a3f1d; font-weight: 600;"


def _style_risk_level(value: str) -> str:
    if not value or value == "Unknown":
        return "color: #6e645b;"
    value_norm = value.lower()
    if "high" in value_norm:
        return "background-color: rgba(163, 97, 63, 0.16); color: #7a3f1d; font-weight: 600;"
    if "medium" in value_norm:
        return "background-color: rgba(123, 90, 58, 0.14); color: #6a4c31; font-weight: 600;"
    if "low" in value_norm:
        return "background-color: rgba(59, 107, 79, 0.12); color: #2f5d42; font-weight: 600;"
    return ""


def _style_norwegian_level(value: str) -> str:
    if not value or value == "Unknown":
        return "color: #6e645b;"
    if str(value).strip() in {"0", "1", "2"}:
        return "background-color: rgba(110, 100, 91, 0.12); color: #5d534c; font-weight: 600;"
    return ""


def _style_missing_fields(value: str) -> str:
    if not value or value == "OK":
        return "color: #3b6b4f; font-weight: 600;"
    return "background-color: rgba(163, 97, 63, 0.12); color: #7a3f1d; font-weight: 600;"


def main() -> None:
    st.set_page_config(page_title="Predatory Reference Checker", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    if "reference_text" not in st.session_state:
        st.session_state.reference_text = ""

    st.markdown(
        """
        <div class="hero">
          <div class="headline" style="font-size:2.1rem; font-weight:700;">Predatory Reference Checker</div>
          <p>Paste references, tune matching sensitivity, and surface potential predatory journal flags with
          Norwegian registry context.</p>
          <div style="margin-top: 0.6rem;">
            <span class="chip">One reference per line</span>
            <span class="chip">Fuzzy matching</span>
            <span class="chip">Registry aware</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.44, 0.56], gap="large")

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Input")

        sample_col, upload_col = st.columns([0.45, 0.55])
        with sample_col:
            if st.button("Use sample data"):
                st.session_state.reference_text = SAMPLE_TEXT

        with upload_col:
            uploaded = st.file_uploader(
                "Upload .txt or .csv",
                type=["txt", "csv"],
                help="CSV: first column will be treated as references.",
            )
            uploaded_text = _extract_reference_text_from_upload(uploaded)
            if uploaded_text is not None:
                st.session_state.reference_text = uploaded_text

        reference_text = st.text_area(
            "Reference list",
            placeholder="Paste one reference or journal name per line...",
            height=260,
            key="reference_text",
        )

        with st.expander("Advanced matching", expanded=False):
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

        action = st.button("Analyze references")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Results")
        st.caption("Matches, flags, and quick links to the Norwegian registry.")

        if action:
            if not reference_text.strip():
                st.warning("Paste your reference list first.")
                st.markdown('</div>', unsafe_allow_html=True)
                return

            rows, pred_db_loaded = _build_rows(
                reference_text,
                fuzzy_threshold=fuzzy_threshold,
                max_fuzzy_matches=max_fuzzy_matches,
            )
            if not rows:
                st.info("No references detected. Add one reference per line.")
                st.markdown('</div>', unsafe_allow_html=True)
                return

            if not pred_db_loaded:
                st.warning(
                    "Predatory registry CSV not found. Place "
                    "`predatory_db_v7_with_norwegian_levels.csv` in the project root or `data/`."
                )

            df = pd.DataFrame(rows)
            total = len(df)
            matches = int((df["Match status"] == "Match").sum())
            no_match = total - matches
            score_series = df["Match score"].fillna("").astype(str).str.rstrip("%")
            avg_score = score_series.replace("", "0").astype(float).mean()

            stats = st.columns(4)
            stats[0].markdown(
                f"""
                <div class="stat-card">
                  <div class="stat-label">References</div>
                  <div class="stat-value">{total}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            stats[1].markdown(
                f"""
                <div class="stat-card">
                  <div class="stat-label">Matches</div>
                  <div class="stat-value">{matches}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            stats[2].markdown(
                f"""
                <div class="stat-card">
                  <div class="stat-label">No Match</div>
                  <div class="stat-value">{no_match}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            stats[3].markdown(
                f"""
                <div class="stat-card">
                  <div class="stat-label">Avg. score</div>
                  <div class="stat-value">{avg_score:.0f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            column_config = {
                "Norwegian registry search": st.column_config.LinkColumn(
                    "Norwegian registry search"
                ),
                "Source URL": st.column_config.LinkColumn("Source URL"),
            }

            styled = (
                df.style.applymap(_style_match_status, subset=["Match status"])
                .applymap(_style_risk_level, subset=["Risk level"])
                .applymap(_style_norwegian_level, subset=["Norwegian level"])
                .applymap(_style_missing_fields, subset=["Missing fields"])
            )
            st.dataframe(
                styled,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )

            st.download_button(
                "Download results (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="reference_check_results.csv",
                mime="text/csv",
            )

        else:
            st.info("Run an analysis to see matches and registry details.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="footer-note">Tip: add the latest registry CSV to the project root for the most complete matching.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
