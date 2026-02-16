from __future__ import annotations

import csv
import re
import sys
from html import escape
from io import StringIO
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
    "name": "Exact name match",
    "domain": "Exact website/domain match",
    "fuzzy-name": "Similar name match",
}

BASIS_PRIORITY = {
    "name": 3,
    "domain": 2,
    "fuzzy-name": 1,
}

DOI_REGEX = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

SAMPLE_TEXT = """Nashif, S., Raihan, M. R., Islam, M. R., & Imam, M. H. (2018). Heart disease detection by using machine learning algorithms and a real-time cardiovascular health monitoring system. World Journal of Engineering and Technology, 6, 854–873. https://doi.org/10.4236/wjet.2018.64057

Grudniewicz, A., Moher, D., Cobey, K. D., Bryson, G. L., Cukier, S., Allen, K., … Moher, D. (2019, December 11). Predatory journals: No definition, no defence. Nature. https://www.nature.com/articles/d41586-019-03759-y

Cukier, S., Lalu, M. M., Bryson, G. L., Cobey, K. D., Grudniewicz, A., & Moher, D. (2020). Defining predatory journals and responding to the threat they pose: A modified Delphi consensus process. BMJ Open, 10(2), e035561. https://doi.org/10.1136/bmjopen-2019-035561

Christopoulou, M., Lakioti, A., Pezirkianidis, C., Karakasidou, E., & Stalikas, A. (2018). The role of grit in education: A systematic review. Psychology, 9, 2951–2971. https://doi.org/10.4236/psych.2018.915171

Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. Numerische Mathematik, 1, 269–271. https://doi.org/10.1007/BF01386390

Hastie, T., Tibshirani, R., & Friedman, J. (2009). The elements of statistical learning: Data mining, inference, and prediction (2nd ed.). Springer. https://doi.org/10.1007/978-0-387-84858-7

Shannon, C. E. (1948). A mathematical theory of communication. Bell System Technical Journal, 27, 379–423, 623–656. https://doi.org/10.1002/J.1538-7305.1948.TB01338.X

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., & Polosukhin, I. (2017). Attention is all you need. In I. Guyon, U. V. Luxburg, S. Bengio, H. Wallach, R. Fergus, S. Vishwanathan, & R. Garnett (Eds.), Advances in Neural Information Processing Systems (Vol. 30, pp. 5998–6008). Curran Associates. https://arxiv.org/abs/1706.03762

Watson, J. D., & Crick, F. H. C. (1953). Molecular structure of nucleic acids: A structure for deoxyribose nucleic acid. Nature, 171, 737–738. https://doi.org/10.1038/171737a0"""

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
  animation: fade-in 360ms ease-out;
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
  animation: rise-in 380ms ease-out;
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

.detail-card {
  background: #fbf7ef;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes rise-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
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


def _chip(text: str, tone: str = "neutral") -> str:
    class_map = {
        "neutral": "chip-neutral",
        "success": "chip-success",
        "warning": "chip-warning",
    }
    css_class = class_map.get(tone, "chip-neutral")
    return f'<span class="chip {css_class}">{escape(text)}</span>'


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


def _decode_uploaded_text(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1", errors="ignore")


def _guess_csv_separator(text: str) -> str:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _load_uploaded_csv(raw_bytes: bytes, separator: str = "auto") -> pd.DataFrame:
    decoded = _decode_uploaded_text(raw_bytes)
    chosen_separator = _guess_csv_separator(decoded) if separator == "auto" else separator
    return pd.read_csv(StringIO(decoded), sep=chosen_separator)


def _extract_reference_text_from_upload(
    uploaded,
    *,
    csv_separator: str = "auto",
    csv_column: str | None = None,
) -> str | None:
    if uploaded is None:
        return None
    name = (uploaded.name or "").lower()
    raw_bytes = uploaded.getvalue()
    if name.endswith(".csv"):
        df = _load_uploaded_csv(raw_bytes, separator=csv_separator)
        if df.empty:
            return ""
        if csv_column and csv_column in df.columns:
            column = csv_column
        else:
            column = str(df.columns[0])
        lines = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
        return "\n".join(lines)
    return _decode_uploaded_text(raw_bytes)


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


def _has_year(raw_text: str, parsed_year: str | None) -> bool:
    if parsed_year:
        return True
    if not raw_text:
        return False
    return bool(re.search(r"(19|20)\d{2}", raw_text))


def _has_url(raw_text: str, parsed_url: str | None) -> bool:
    if parsed_url:
        return True
    if not raw_text:
        return False
    return "http://" in raw_text.lower() or "https://" in raw_text.lower()


def _has_publisher(raw_text: str, parsed_publisher: str | None) -> bool:
    if parsed_publisher:
        return True
    if not raw_text:
        return False
    return bool(re.search(r"\b(press|publishing|publisher)\b", raw_text, re.IGNORECASE))


def _has_conference(raw_text: str, parsed_conference: str | None, parsed_journal: str | None) -> bool:
    if parsed_conference or parsed_journal:
        return True
    if not raw_text:
        return False
    return bool(re.search(r"\b(proceedings|conference|symposium|workshop)\b", raw_text, re.IGNORECASE))


def _has_preprint_server(raw_text: str, parsed_server: str | None) -> bool:
    if parsed_server:
        return True
    if not raw_text:
        return False
    return bool(re.search(r"\b(arxiv|biorxiv|medrxiv|ssrn|research square)\b", raw_text, re.IGNORECASE))


def _has_locator(raw_text: str, parsed_doi: str | None, parsed_url: str | None) -> bool:
    return _has_doi(raw_text, parsed_doi) or _has_url(raw_text, parsed_url)


def _missing_field_summary(ref) -> str:
    raw_text = ref.raw_text or ""
    ref_type = (ref.entry_type or "unknown").lower()
    missing = []

    if ref_type == "journal":
        if not _has_authors(raw_text, ref.authors):
            missing.append("authors")
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_journal(raw_text, ref.journal):
            missing.append("journal")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
        if not _has_locator(raw_text, ref.doi, ref.url):
            missing.append("doi/url")
    elif ref_type == "book":
        if not _has_authors(raw_text, ref.authors):
            missing.append("authors")
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_publisher(raw_text, ref.publisher):
            missing.append("publisher")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
    elif ref_type == "conference":
        if not _has_authors(raw_text, ref.authors):
            missing.append("authors")
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_conference(raw_text, ref.conference_name, ref.journal):
            missing.append("conference/venue")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
        if not _has_locator(raw_text, ref.doi, ref.url):
            missing.append("doi/url")
    elif ref_type == "preprint":
        if not _has_authors(raw_text, ref.authors):
            missing.append("authors")
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_preprint_server(raw_text, ref.preprint_server):
            missing.append("server")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
        if not _has_locator(raw_text, ref.doi, ref.url):
            missing.append("doi/url")
    elif ref_type == "website":
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_url(raw_text, ref.url):
            missing.append("url")
    elif ref_type == "dataset":
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
        if not _has_locator(raw_text, ref.doi, ref.url):
            missing.append("doi/url")
    else:
        if not _has_authors(raw_text, ref.authors):
            missing.append("authors")
        if not _has_title(raw_text, ref.title):
            missing.append("title")
        if not _has_year(raw_text, ref.year):
            missing.append("year")
        if not _has_locator(raw_text, ref.doi, ref.url):
            missing.append("doi/url")

    if not missing:
        return "OK"
    return "Missing: " + ", ".join(missing)


def _action_needed(row: dict[str, str]) -> str:
    risk = (row.get("Risk level") or "").lower()
    completeness = row.get("Reference check") or ""
    if "high" in risk:
        return "Check immediately"
    if "medium" in risk:
        return "Check manually"
    if completeness != "OK":
        return "Add missing details"
    if row.get("Registry warning") == "No match":
        return "No warning found"
    return "Looks OK"


def _build_rows(
    reference_text: str,
    *,
    fuzzy_threshold: float,
    max_fuzzy_matches: int,
    pred_db: PredatoryDbProvider | None = None,
) -> tuple[list[dict[str, str]], bool]:
    parser = ReferenceListParser()
    references = parser.parse(reference_text)
    if not references:
        return [], False

    provider = pred_db or PredatoryDbProvider.load_default(base_dir=ROOT)
    pred_db_loaded = provider is not None

    rows: list[dict[str, str]] = []
    for ref in references:
        norwegian_search = _norwegian_search_url(ref.journal)
        matches = (
            provider.match_reference(
                ref,
                fuzzy=True,
                fuzzy_threshold=fuzzy_threshold,
                max_fuzzy_matches=max_fuzzy_matches,
            )
            if provider
            else []
        )
        best = _pick_best_match(matches)
        if best:
            row = {
                "Reference": ref.raw_text,
                "Registry warning": "Match",
                "Registry record": best.record.name,
                "Matched text": best.matched_value,
                "Match method": _format_basis(best.basis),
                "Match confidence": _format_score(best.score),
                "Risk level": best.record.risk_level or "Unknown",
                "Norwegian level": best.record.norwegian_level or "Unknown",
                "Registry note": best.record.warning_summary or "",
                "Source": best.record.source or "",
                "Source URL": best.record.source_url or "",
                "Norwegian registry search": norwegian_search,
                "Reference check": _missing_field_summary(ref),
            }
        else:
            row = {
                "Reference": ref.raw_text,
                "Registry warning": "No match",
                "Registry record": "",
                "Matched text": "",
                "Match method": "",
                "Match confidence": "",
                "Risk level": "",
                "Norwegian level": "",
                "Registry note": "",
                "Source": "",
                "Source URL": "",
                "Norwegian registry search": norwegian_search,
                "Reference check": _missing_field_summary(ref),
            }
        row["Recommended next step"] = _action_needed(row)
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


def _style_action(value: str) -> str:
    if value == "Check immediately":
        return "background-color: rgba(163, 97, 63, 0.2); color: #7a3f1d; font-weight: 700;"
    if value in {"Check manually", "Add missing details"}:
        return "background-color: rgba(123, 90, 58, 0.14); color: #6a4c31; font-weight: 600;"
    return "color: #3b6b4f; font-weight: 600;"


def _short_text(value: str, max_len: int = 110) -> str:
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def _view_options() -> list[str]:
    return [
        "All references",
        "Needs attention",
        "Registry matches",
        "No registry match",
        "Missing details",
    ]


def _pick_view() -> str:
    options = _view_options()
    label = "Quick view"
    if hasattr(st, "segmented_control"):
        try:
            return st.segmented_control(label, options=options, default=options[0])  # type: ignore[attr-defined]
        except TypeError:
            return st.segmented_control(label, options=options)  # type: ignore[attr-defined]
    return st.radio(label, options=options, horizontal=True)


def _filter_rows(df: pd.DataFrame, view_name: str) -> pd.DataFrame:
    if view_name == "Needs attention":
        return df[df["Recommended next step"].isin(["Check immediately", "Check manually"])]
    if view_name == "Registry matches":
        return df[df["Registry warning"] == "Match"]
    if view_name == "No registry match":
        return df[df["Registry warning"] == "No match"]
    if view_name == "Missing details":
        return df[df["Reference check"] != "OK"]
    return df


def main() -> None:
    st.set_page_config(
        page_title="Predatory Reference Checker",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)

    if "reference_text" not in st.session_state:
        st.session_state.reference_text = ""
    if "analysis_rows" not in st.session_state:
        st.session_state.analysis_rows = None
    if "analysis_ran" not in st.session_state:
        st.session_state.analysis_ran = False
    if "analysis_error" not in st.session_state:
        st.session_state.analysis_error = ""
    if "analysis_pred_db_loaded" not in st.session_state:
        st.session_state.analysis_pred_db_loaded = False
    if "analysis_notice" not in st.session_state:
        st.session_state.analysis_notice = ""

    st.markdown(
        """
        <div class="hero">
          <div class="headline" style="font-size:2.1rem; font-weight:700;">Predatory Reference Checker</div>
          <p>Paste references and flag possible predatory journal/publisher warnings with Norwegian registry context.</p>
          <p><strong>Important:</strong> this is a screening tool. Always make a final manual decision.</p>
          <div style="margin-top: 0.6rem;">
            <span class="chip">One reference per line</span>
            <span class="chip">Fuzzy matching</span>
            <span class="chip">Registry aware</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        _chip("Built for non-coders", "success")
        + _chip("Fast screening workflow", "neutral")
        + _chip("Manual decision always required", "warning"),
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.44, 0.56], gap="large")
    pred_db = PredatoryDbProvider.load_default(base_dir=ROOT)

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Step 1: Add References")
        st.caption("Paste references directly or import from a file.")

        sample_col, clear_col = st.columns([0.5, 0.5])
        with sample_col:
            if st.button("Use sample data", key="use_sample_data"):
                st.session_state.reference_text = SAMPLE_TEXT
                st.session_state.analysis_ran = False

        with clear_col:
            if st.button("Clear input", key="clear_input"):
                st.session_state.reference_text = ""
                st.session_state.analysis_rows = None
                st.session_state.analysis_ran = False
                st.session_state.analysis_error = ""
                st.session_state.analysis_notice = ""

        if pred_db is None:
            st.warning(
                "Registry data is not loaded. Place "
                "`predatory_db_v7_with_norwegian_levels.csv`, `pred_pub_list.csv`, and/or "
                "`pred_jour_list.csv` "
                "in the project root or `data/` to enable predatory matching."
            )

        uploaded = st.file_uploader(
            "Import from file",
            type=["txt", "csv"],
            help="TXT: one reference per line. CSV: choose separator and the correct column below.",
        )

        if uploaded is not None:
            name = (uploaded.name or "").lower()
            if name.endswith(".csv"):
                separator_label = st.selectbox(
                    "CSV separator",
                    options=["Auto detect", "Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"],
                    help="If parsing looks wrong, choose the delimiter manually.",
                )
                separator_map = {
                    "Auto detect": "auto",
                    "Comma (,)": ",",
                    "Semicolon (;)": ";",
                    "Tab": "\t",
                    "Pipe (|)": "|",
                }
                try:
                    csv_df = _load_uploaded_csv(
                        uploaded.getvalue(),
                        separator=separator_map[separator_label],
                    )
                except Exception as exc:
                    st.error(f"Could not read CSV file: {exc}")
                else:
                    if csv_df.empty:
                        st.info("The uploaded CSV has no rows.")
                    else:
                        selected_column = st.selectbox(
                            "Which column contains references?",
                            options=[str(column) for column in csv_df.columns],
                            help="Choose the column that contains one reference per row.",
                        )
                        st.caption("Preview (first 5 rows)")
                        st.dataframe(csv_df.head(5), use_container_width=True, hide_index=True)
                        if st.button("Load this column", key="load_csv_column"):
                            try:
                                uploaded_text = _extract_reference_text_from_upload(
                                    uploaded,
                                    csv_separator=separator_map[separator_label],
                                    csv_column=selected_column,
                                )
                                st.session_state.reference_text = uploaded_text or ""
                                st.session_state.analysis_ran = False
                            except Exception as exc:
                                st.error(f"Could not load references from CSV: {exc}")
            else:
                preview_text = _decode_uploaded_text(uploaded.getvalue())
                preview_lines = "\n".join(preview_text.splitlines()[:8]).strip()
                st.caption("Text preview")
                st.code(preview_lines or "(File is empty)", language="text")
                if st.button("Load this text file", key="load_text_upload"):
                    st.session_state.reference_text = preview_text
                    st.session_state.analysis_ran = False

        simple_mode = st.toggle(
            "Simple mode (recommended)",
            value=True,
            help="Use default matching settings suitable for most users.",
        )

        if simple_mode:
            fuzzy_threshold = 0.88
            max_fuzzy_matches = 3
            st.caption("Using standard matching settings.")
        else:
            st.caption("Use advanced settings only if results look too strict or too broad.")
            fuzzy_threshold = st.slider(
                "Match strictness",
                min_value=0.7,
                max_value=0.98,
                value=0.88,
                step=0.01,
                help="Higher values are stricter and reduce possible false positives.",
            )
            max_fuzzy_matches = st.number_input(
                "Maximum suggestions per reference",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
            )

        with st.form("analysis_form", clear_on_submit=False):
            reference_text = st.text_area(
                "Reference list",
                placeholder="Paste one full reference per line...",
                height=260,
                key="reference_text",
            )
            action = st.form_submit_button("Step 2: Run Check")

        if action:
            st.session_state.analysis_error = ""
            if not reference_text.strip():
                st.session_state.analysis_rows = []
                st.session_state.analysis_pred_db_loaded = pred_db is not None
                st.session_state.analysis_ran = True
                st.session_state.analysis_notice = "Please paste references first."
            else:
                try:
                    with st.status("Running reference checks...", expanded=True) as status_box:
                        status_box.write("Step 1/3: Reading and parsing references")
                        progress = st.progress(15)
                        status_box.write("Step 2/3: Matching journals/publishers to registry data")
                        rows, pred_db_loaded = _build_rows(
                            reference_text,
                            fuzzy_threshold=float(fuzzy_threshold),
                            max_fuzzy_matches=int(max_fuzzy_matches),
                            pred_db=pred_db,
                        )
                        progress.progress(75)
                        status_box.write("Step 3/3: Building prioritized review table")
                        progress.progress(100)
                        status_box.update(
                            label=f"Check complete: {len(rows)} references processed",
                            state="complete",
                            expanded=False,
                        )
                    st.session_state.analysis_rows = rows
                    st.session_state.analysis_pred_db_loaded = pred_db_loaded
                    st.session_state.analysis_ran = True
                    if rows:
                        st.session_state.analysis_notice = ""
                        if hasattr(st, "toast"):
                            st.toast("Reference check complete.")
                    else:
                        st.session_state.analysis_notice = (
                            "No references were detected. Add one full reference per line."
                        )
                except Exception as exc:
                    st.session_state.analysis_rows = []
                    st.session_state.analysis_pred_db_loaded = pred_db is not None
                    st.session_state.analysis_ran = True
                    st.session_state.analysis_error = str(exc)
                    st.session_state.analysis_notice = ""

        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Step 3: Review Results")
        st.caption("Use the recommended next step column first, then inspect details.")
        if hasattr(st, "popover"):
            with st.popover("Quick guide"):
                st.markdown(
                    "1. Start with `Needs attention` view.\n"
                    "2. Open one reference in `Reference spotlight`.\n"
                    "3. Resolve `Check immediately` first, then `Check manually`.\n"
                    "4. Export CSV for records or sharing."
                )

        if not st.session_state.analysis_ran:
            st.info("Run the check to see possible warnings and missing details.")
        elif st.session_state.analysis_error:
            st.error(f"Could not complete the check: {st.session_state.analysis_error}")
        else:
            rows = st.session_state.analysis_rows or []
            if not rows:
                st.warning(st.session_state.analysis_notice or "No analysis output available yet.")
            else:
                if not st.session_state.analysis_pred_db_loaded:
                    st.warning(
                        "Registry file not found. This run only checks reference completeness, not predatory registry matches."
                    )

                df = pd.DataFrame(rows)
                total = len(df)
                matches = int((df["Registry warning"] == "Match").sum())
                no_match = total - matches
                needs_review = int(df["Recommended next step"].isin(["Check immediately", "Check manually"]).sum())
                score_series = df["Match confidence"].fillna("").astype(str).str.rstrip("%")
                avg_score = score_series.replace("", "0").astype(float).mean()

                stats = st.columns(5)
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
                      <div class="stat-label">Needs review</div>
                      <div class="stat-value">{needs_review}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                stats[4].markdown(
                    f"""
                    <div class="stat-card">
                      <div class="stat-label">Avg. confidence</div>
                      <div class="stat-value">{avg_score:.0f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _chip(f"{needs_review} need attention", "warning")
                    + _chip(f"{matches} registry matches", "neutral")
                    + _chip(f"{no_match} no-match entries", "success"),
                    unsafe_allow_html=True,
                )

                st.caption(
                    "No match does not prove a journal is safe. It only means no match was found in the loaded registry file."
                )
                with st.expander("How to interpret results", expanded=False):
                    st.markdown(
                        "1. Start with `Recommended next step`.\n"
                        "2. If it says `Check immediately` or `Check manually`, review `Risk level`, `Registry note`, and links.\n"
                        "3. If it says `Add missing details`, improve that reference before submission.\n"
                        "4. Use `Norwegian registry search` for manual confirmation."
                    )

                view_name = _pick_view()
                filtered_df = _filter_rows(df, view_name).reset_index(drop=True)
                st.caption(f"Showing {len(filtered_df)} of {len(df)} references in this view.")
                if filtered_df.empty:
                    st.info("No references match this filter. Try another quick view.")
                    filtered_df = df.reset_index(drop=True)

                column_config = {
                    "Norwegian registry search": st.column_config.LinkColumn(
                        "Norwegian registry search"
                    ),
                    "Source URL": st.column_config.LinkColumn("Source URL"),
                    "Recommended next step": st.column_config.TextColumn(
                        "Recommended next step",
                        help="Fastest way to prioritize what to review first.",
                    ),
                    "Reference check": st.column_config.TextColumn(
                        "Reference check",
                        help="Quick check for missing core details by reference type.",
                    ),
                }

                styled = (
                    filtered_df.style.applymap(_style_match_status, subset=["Registry warning"])
                    .applymap(_style_risk_level, subset=["Risk level"])
                    .applymap(_style_norwegian_level, subset=["Norwegian level"])
                    .applymap(_style_missing_fields, subset=["Reference check"])
                    .applymap(_style_action, subset=["Recommended next step"])
                )
                st.dataframe(
                    styled,
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config,
                )

                detail_options = [
                    f"{idx + 1}. {_short_text(row['Reference'])}"
                    for idx, row in filtered_df.iterrows()
                ]
                if detail_options:
                    selected_option = st.selectbox(
                        "Reference spotlight",
                        options=detail_options,
                        index=0,
                        help="Pick one reference to inspect all details in one place.",
                    )
                    selected_idx = detail_options.index(selected_option)
                    selected_row = filtered_df.iloc[selected_idx]
                    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
                    top = st.columns(4)
                    top[0].markdown(f"**Next step**\n\n{selected_row['Recommended next step']}")
                    top[1].markdown(f"**Risk level**\n\n{selected_row['Risk level'] or 'Unknown'}")
                    top[2].markdown(f"**Norwegian level**\n\n{selected_row['Norwegian level'] or 'Unknown'}")
                    top[3].markdown(f"**Match confidence**\n\n{selected_row['Match confidence'] or 'N/A'}")
                    st.markdown("**Reference text**")
                    st.code(selected_row["Reference"], language="text")
                    details_cols = st.columns(2)
                    details_cols[0].markdown("**Registry record**")
                    details_cols[0].write(selected_row["Registry record"] or "No registry match")
                    details_cols[1].markdown("**Reference check**")
                    details_cols[1].write(selected_row["Reference check"])
                    st.markdown("**Registry note**")
                    st.write(selected_row["Registry note"] or "No additional note")
                    st.markdown('</div>', unsafe_allow_html=True)

                st.download_button(
                    "Download results (CSV)",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="reference_check_results.csv",
                    mime="text/csv",
                )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="footer-note">Tip: keep registry files (`predatory_db_v7_with_norwegian_levels.csv`, `pred_pub_list.csv`, and `pred_jour_list.csv`) up to date for the most complete matching.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
