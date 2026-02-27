from __future__ import annotations

import base64
import csv
import re
import sys
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reference_checker.predatory_db import PredatoryDbMatch, PredatoryDbProvider  # noqa: E402
from reference_checker.normalization import extract_domain, normalize_text  # noqa: E402
from reference_checker.reference_parser import ReferenceListParser  # noqa: E402


BASIS_LABELS = {
    "name": "Exact name match",
    "domain": "Exact website/domain match",
    "text-name": "Name found in reference text",
    "fuzzy-name": "Similar name match",
}

BASIS_PRIORITY = {
    "name": 3,
    "text-name": 2,
    "domain": 2,
    "fuzzy-name": 1,
}

DOI_REGEX = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

CUSTOM_WATCHLIST_FILENAME = "custom_watchlist.csv"
CUSTOM_WATCHLIST_COLUMNS = [
    "name",
    "type",
    "url_domain",
    "risk_level",
    "warning_summary",
    "source",
    "source_url",
    "entry_id",
]

STARTER_WATCHLIST = [
    {
        "name": "MDPI",
        "type": "publisher",
        "url_domain": "mdpi.com",
        "risk_level": "Medium",
        "warning_summary": (
            "Finnish JUFO downgraded many MDPI journals to level 0 as part of grey-area review."
        ),
        "source": "Publication Forum (JUFO), Dec 16, 2024",
        "source_url": "https://julkaisufoorumi.fi/en/news/changes-classification",
    },
    {
        "name": "Frontiers Media",
        "type": "publisher",
        "url_domain": "frontiersin.org",
        "risk_level": "Medium",
        "warning_summary": (
            "Finnish JUFO downgraded many Frontiers journals to level 0 as part of grey-area review."
        ),
        "source": "Publication Forum (JUFO), Dec 16, 2024",
        "source_url": "https://julkaisufoorumi.fi/en/news/changes-classification",
    },
    {
        "name": "Hindawi",
        "type": "publisher",
        "url_domain": "hindawi.com",
        "risk_level": "High",
        "warning_summary": (
            "Wiley reported a publishing pause in special issues due to compromised articles."
        ),
        "source": "Wiley FY2023 Q3 results",
        "source_url": (
            "https://newsroom.wiley.com/press-releases/press-release-details/2023/"
            "Wiley-Reports-Third-Quarter-Fiscal-Year-2023-Results/default.aspx"
        ),
    },
    {
        "name": "OMICS Group",
        "type": "publisher",
        "url_domain": "omicsonline.org",
        "risk_level": "High",
        "warning_summary": (
            "FTC court ruling found deceptive claims and inadequate fee disclosure."
        ),
        "source": "US FTC press release",
        "source_url": (
            "https://www.ftc.gov/news-events/news/press-releases/2019/04/"
            "court-rules-ftcs-favor-against-predatory-academic-publisher-omics-group-"
            "imposes-501-million-judgment"
        ),
    },
    {
        "name": "iMedPub",
        "type": "publisher",
        "url_domain": "imedpub.com",
        "risk_level": "High",
        "warning_summary": (
            "Named in the FTC's OMICS case alleging deceptive claims and hidden fees."
        ),
        "source": "US FTC press release",
        "source_url": (
            "https://www.ftc.gov/news-events/news/press-releases/2019/04/"
            "court-rules-ftcs-favor-against-predatory-academic-publisher-omics-group-"
            "imposes-501-million-judgment"
        ),
    },
    {
        "name": "Conference Series",
        "type": "publisher",
        "url_domain": "conferenceeries.com",
        "risk_level": "High",
        "warning_summary": (
            "Named in the FTC's OMICS case alleging deceptive conference and journal claims."
        ),
        "source": "US FTC press release",
        "source_url": (
            "https://www.ftc.gov/news-events/news/press-releases/2019/04/"
            "court-rules-ftcs-favor-against-predatory-academic-publisher-omics-group-"
            "imposes-501-million-judgment"
        ),
    },
]

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
:root {
  --paper: #0d1218;
  --paper-deep: #151b22;
  --panel: #121a22;
  --ink: #f7fafc;
  --muted: #d5dde6;
  --accent: #cf2436;
  --accent-soft: #45232b;
  --success: #ddf6ea;
  --warning: #ffe9ec;
  --border: #445361;
  --link: #8dc7ff;
  --shadow: 0 14px 30px rgba(0, 0, 0, 0.42);
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background:
    radial-gradient(circle at 15% 0%, rgba(207, 36, 54, 0.18) 0, rgba(207, 36, 54, 0) 37%),
    radial-gradient(circle at 85% 0%, rgba(105, 131, 160, 0.12) 0, rgba(105, 131, 160, 0) 39%),
    linear-gradient(180deg, var(--paper) 0%, #101720 100%);
  color: var(--ink);
  font-family: Calibri, "Segoe UI", Tahoma, sans-serif;
}

h1, h2, h3, .headline {
  font-family: Calibri, "Segoe UI", Tahoma, sans-serif !important;
  color: var(--ink);
}

.stMarkdown,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] p,
label,
p,
li {
  color: var(--ink) !important;
}

[data-testid="stCaptionContainer"] p,
.footer-note {
  color: var(--muted) !important;
}

[data-testid="stAppViewContainer"] a {
  color: var(--link);
}

[data-testid="stAppViewContainer"] a:hover {
  color: #c0e2ff;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] > div {
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  background: #0f161d !important;
  color: var(--ink) !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
  color: #cbd3dc !important;
  opacity: 1 !important;
}

div[data-baseweb="menu"] {
  background: #121a22 !important;
  border: 1px solid var(--border) !important;
}

div[data-baseweb="menu"] * {
  color: var(--ink) !important;
}

div[data-baseweb="tag"] {
  background: #243448 !important;
  border: 1px solid #3f5370 !important;
}

div[data-baseweb="tag"] span {
  color: var(--ink) !important;
}

.hero {
  background: linear-gradient(135deg, rgba(22, 30, 39, 0.96), rgba(17, 24, 33, 0.94));
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 22px 28px;
  box-shadow: var(--shadow);
  margin-bottom: 1.25rem;
  animation: fade-in 360ms ease-out;
}

.hero-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-logo {
  width: 74px;
  max-width: 18vw;
  height: auto;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px #e1e6eb;
  padding: 8px;
}

.hero p {
  color: var(--muted);
  margin: 0.35rem 0 0;
}

@media (max-width: 720px) {
  .hero-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .hero-logo {
    width: 66px;
  }
}

.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3);
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
  color: #ffecef;
  margin-right: 8px;
}

.chip-success { background: rgba(44, 105, 74, 0.42); color: var(--success); }
.chip-warning { background: rgba(157, 32, 46, 0.52); color: var(--warning); }
.chip-neutral { background: rgba(80, 99, 120, 0.46); color: var(--ink); }

.stat-card {
  background: #1a2530;
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
  background: #0f161d;
  color: var(--ink);
}

.stButton button {
  background: var(--accent);
  color: white;
  border-radius: 999px;
  padding: 0.4rem 1.4rem;
  border: 1px solid #e26e7a;
}

[data-testid="stDownloadButton"] button {
  background: #254f8a;
  color: #f8fbff;
  border-radius: 999px;
  border: 1px solid #4f7ec0;
}

.stButton button:hover {
  background: #a8192a;
  color: white;
}

[data-testid="stDownloadButton"] button:hover {
  background: #1d4377;
  color: #f8fbff;
}

[data-testid="stAlertContainer"] {
  border-radius: 12px;
}

[data-testid="stAlertContainer"] * {
  color: var(--ink) !important;
}

[data-testid="stDataFrame"] {
  border-radius: 14px;
  border: 1px solid var(--border);
  overflow: hidden;
}

[data-testid="stDataFrame"] [role="columnheader"] {
  background: #1e2a36;
  color: var(--ink);
}

[data-testid="stDataFrame"] [role="gridcell"] {
  color: #edf2f7;
}

.detail-card {
  background: #1a2530;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
}

.legend {
  display: grid;
  gap: 8px;
  margin: 0.4rem 0 1rem;
}

.legend-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 0.9rem;
  color: var(--muted);
}

.legend-badge {
  border-radius: 999px;
  padding: 3px 9px;
  font-weight: 700;
  font-size: 0.78rem;
  min-width: 178px;
  text-align: center;
}

.badge-immediate { background: #7c1f2a; color: #fff5f7; }
.badge-manual { background: #5b4720; color: #fff6d8; }
.badge-details { background: #4f6072; color: #f8fbff; }
.badge-ok { background: #2c5b48; color: #eefbf3; }
.badge-flag { background: #2a3542; color: #f1f5f9; }

*:focus-visible {
  outline: 2px solid #ffd447 !important;
  outline-offset: 2px !important;
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


def _build_excel_bytes(df: pd.DataFrame) -> bytes:
    from openpyxl.utils import get_column_letter

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reference Check Results")
        worksheet = writer.sheets["Reference Check Results"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for col_idx, column_name in enumerate(df.columns, start=1):
            sample_series = df[column_name].fillna("").astype(str).head(250)
            longest_sample = max([len(str(column_name)), *[len(value) for value in sample_series]], default=12)
            worksheet.column_dimensions[get_column_letter(col_idx)].width = min(
                max(longest_sample + 2, 12),
                58,
            )
    return output.getvalue()


def _custom_watchlist_path() -> Path:
    return ROOT / "data" / CUSTOM_WATCHLIST_FILENAME


def _empty_custom_watchlist_df() -> pd.DataFrame:
    return pd.DataFrame(columns=CUSTOM_WATCHLIST_COLUMNS)


def _load_custom_watchlist_df(path: Path | None = None) -> pd.DataFrame:
    target = path or _custom_watchlist_path()
    if not target.exists():
        return _empty_custom_watchlist_df()
    try:
        df = pd.read_csv(target)
    except Exception:
        return _empty_custom_watchlist_df()

    for column in CUSTOM_WATCHLIST_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[CUSTOM_WATCHLIST_COLUMNS].fillna("")
    df["name"] = df["name"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip().replace("", "publisher")
    df["url_domain"] = df["url_domain"].astype(str).str.strip().map(lambda val: extract_domain(val) or "")
    df["entry_id"] = df["entry_id"].astype(str).str.strip()
    missing_ids = df["entry_id"] == ""
    if missing_ids.any():
        df.loc[missing_ids, "entry_id"] = df[missing_ids].apply(
            lambda row: _watchlist_entry_id(str(row["name"]), str(row["url_domain"])),
            axis=1,
        )
    df = df[df["name"] != ""].drop_duplicates(subset=["entry_id"], keep="first").reset_index(drop=True)
    return df


def _save_custom_watchlist_df(df: pd.DataFrame, path: Path | None = None) -> None:
    target = path or _custom_watchlist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = df.copy()
    for column in CUSTOM_WATCHLIST_COLUMNS:
        if column not in clean.columns:
            clean[column] = ""
    clean = clean[CUSTOM_WATCHLIST_COLUMNS].fillna("")
    clean.to_csv(target, index=False, encoding="utf-8")


def _watchlist_entry_id(name: str, domain: str) -> str:
    norm_name = normalize_text(name)
    norm_domain = extract_domain(domain) or ""
    return f"custom:{norm_name}:{norm_domain}"


def _watchlist_display_label(row: pd.Series) -> str:
    name = str(row.get("name", "")).strip()
    domain = str(row.get("url_domain", "")).strip()
    concern = str(row.get("risk_level", "")).strip()
    pieces = [name]
    if domain:
        pieces.append(f"({domain})")
    if concern:
        pieces.append(f"[{concern}]")
    return " ".join(pieces).strip()


def _append_watchlist_rows(existing: pd.DataFrame, rows: list[dict[str, str]]) -> tuple[pd.DataFrame, int]:
    if not rows:
        return existing, 0
    incoming = pd.DataFrame(rows)
    for column in CUSTOM_WATCHLIST_COLUMNS:
        if column not in incoming.columns:
            incoming[column] = ""
    incoming = incoming[CUSTOM_WATCHLIST_COLUMNS].fillna("")
    incoming["name"] = incoming["name"].astype(str).str.strip()
    incoming["type"] = incoming["type"].astype(str).str.strip().replace("", "publisher")
    incoming["url_domain"] = incoming["url_domain"].astype(str).str.strip().map(lambda val: extract_domain(val) or "")
    incoming["entry_id"] = incoming.apply(
        lambda row: _watchlist_entry_id(str(row["name"]), str(row["url_domain"])),
        axis=1,
    )
    incoming = incoming[incoming["name"] != ""]
    if incoming.empty:
        return existing, 0

    merged = pd.concat([existing, incoming], ignore_index=True)
    merged = merged.drop_duplicates(subset=["entry_id"], keep="first").reset_index(drop=True)
    added = len(merged) - len(existing)
    return merged, max(added, 0)


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
    if row.get("Custom watchlist warning") == "Match":
        if "high" in risk:
            return "Check immediately"
        return "Check manually"
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
    custom_db: PredatoryDbProvider | None = None,
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
        custom_matches = (
            custom_db.match_reference(
                ref,
                fuzzy=True,
                scan_raw_text=True,
                fuzzy_threshold=fuzzy_threshold,
                max_fuzzy_matches=max_fuzzy_matches,
            )
            if custom_db
            else []
        )
        best = _pick_best_match(matches)
        best_custom = _pick_best_match(custom_matches)
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
        if best_custom:
            row["Custom watchlist warning"] = "Match"
            row["Custom watchlist entry"] = best_custom.record.name
            row["Custom matched text"] = best_custom.matched_value
            row["Custom match method"] = _format_basis(best_custom.basis)
            row["Custom confidence"] = _format_score(best_custom.score)
            row["Custom note"] = best_custom.record.warning_summary or ""
            row["Custom source"] = best_custom.record.source or "Custom watchlist"
            row["Custom source URL"] = best_custom.record.source_url or ""
            if not row.get("Risk level"):
                row["Risk level"] = best_custom.record.risk_level or "Medium"
            if not row.get("Registry note"):
                row["Registry note"] = best_custom.record.warning_summary or ""
        else:
            row["Custom watchlist warning"] = "No match"
            row["Custom watchlist entry"] = ""
            row["Custom matched text"] = ""
            row["Custom match method"] = ""
            row["Custom confidence"] = ""
            row["Custom note"] = ""
            row["Custom source"] = ""
            row["Custom source URL"] = ""
        row["Recommended next step"] = _action_needed(row)
        rows.append(row)

    return rows, pred_db_loaded


def _style_match_status(value: str) -> str:
    value_norm = str(value or "").strip().lower()
    if value_norm in {"match", "flagged"}:
        return "background-color: #7c1f2a; color: #fff5f7; font-weight: 700;"
    return "background-color: #2a3542; color: #f1f5f9; font-weight: 600;"


def _style_custom_status(value: str) -> str:
    value_norm = str(value or "").strip().lower()
    if value_norm in {"match", "flagged"}:
        return "background-color: #7c1f2a; color: #fff5f7; font-weight: 700;"
    return "background-color: #2a3542; color: #f1f5f9; font-weight: 600;"


def _style_risk_level(value: str) -> str:
    if not value or value == "Unknown":
        return "color: #d5dde6;"
    value_norm = value.lower()
    if "high" in value_norm:
        return "background-color: #7c1f2a; color: #fff5f7; font-weight: 700;"
    if "medium" in value_norm:
        return "background-color: #4f6072; color: #f8fbff; font-weight: 700;"
    if "low" in value_norm:
        return "background-color: #2c5b48; color: #eefbf3; font-weight: 700;"
    return ""


def _style_norwegian_level(value: str) -> str:
    if not value or value == "Unknown":
        return "color: #d5dde6;"
    if str(value).strip() in {"0", "1", "2"}:
        return "background-color: #2a3542; color: #f1f5f9; font-weight: 700;"
    return ""


def _style_missing_fields(value: str) -> str:
    if not value or value == "OK":
        return "color: #f1f5f9; font-weight: 700;"
    return "background-color: #7c1f2a; color: #fff5f7; font-weight: 700;"


def _style_action(value: str) -> str:
    if value == "Check immediately":
        return "background-color: #7c1f2a; color: #fff5f7; font-weight: 700;"
    if value in {"Check manually", "Add missing details"}:
        return "background-color: #5b4720; color: #fff6d8; font-weight: 700;"
    return "color: #f1f5f9; font-weight: 700;"


def _short_text(value: str, max_len: int = 110) -> str:
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def _view_options() -> list[str]:
    return [
        "Needs attention",
        "All references",
        "Registry-flagged",
        "Watchlist-flagged",
        "Not found in registry",
        "Missing details",
    ]


def _pick_view() -> str:
    options = _view_options()
    default_option = "Needs attention"
    label = "Quick filter"
    if hasattr(st, "segmented_control"):
        try:
            return st.segmented_control(label, options=options, default=default_option)  # type: ignore[attr-defined]
        except TypeError:
            return st.segmented_control(label, options=options)  # type: ignore[attr-defined]
    return st.radio(label, options=options, horizontal=True, index=options.index(default_option))


def _filter_rows(df: pd.DataFrame, view_name: str) -> pd.DataFrame:
    if view_name == "Needs attention":
        return df[df["Recommended next step"].isin(["Check immediately", "Check manually"])]
    if view_name == "Registry-flagged":
        return df[df["Registry warning"] == "Match"]
    if view_name == "Watchlist-flagged":
        return df[df["Custom watchlist warning"] == "Match"]
    if view_name == "Not found in registry":
        return df[df["Registry warning"] == "No match"]
    if view_name == "Missing details":
        return df[df["Reference check"] != "OK"]
    return df


def _sort_for_review(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    action_rank = {
        "Check immediately": 0,
        "Check manually": 1,
        "Add missing details": 2,
    }
    risk_rank = {
        "high": 0,
        "medium": 1,
        "low": 2,
        "unknown": 3,
        "": 3,
    }
    ranked = df.assign(
        _action_rank=df["Recommended next step"].map(action_rank).fillna(9).astype(int),
        _risk_rank=df["Risk level"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .map(risk_rank)
        .fillna(9)
        .astype(int),
    )
    return (
        ranked.sort_values(by=["_action_rank", "_risk_rank", "Reference"], ascending=[True, True, True])
        .drop(columns=["_action_rank", "_risk_rank"])
        .reset_index(drop=True)
    )


def _logo_data_uri() -> str:
    logo_path = ROOT / "reflogo.png"
    if not logo_path.exists():
        return ""
    try:
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{encoded}"


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
    if "custom_watchlist_df" not in st.session_state:
        st.session_state.custom_watchlist_df = _load_custom_watchlist_df()

    logo_uri = _logo_data_uri()
    logo_html = f'<img class="hero-logo" src="{logo_uri}" alt="Reference Checker logo" />' if logo_uri else ""
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-head">
            {logo_html}
            <div class="headline" style="font-size:2.1rem; font-weight:700;">Predatory Reference Checker</div>
          </div>
          <p>Check reference lists for missing details and possible registry matches.</p>
          <p><strong>Important:</strong> review flagged entries before making a final decision.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.44, 0.56], gap="large")
    pred_db = PredatoryDbProvider.load_default(base_dir=ROOT)
    custom_watchlist_path = _custom_watchlist_path()
    custom_watchlist_df = st.session_state.custom_watchlist_df

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("1. Add references")
        st.caption(
            "Paste your references, load a sample, or upload a TXT/CSV file. "
            "Supports APA and compact formats like `Journal. 2015, 182, 189-190. [Google Scholar]`."
        )

        sample_col, clear_col = st.columns([0.5, 0.5])
        with sample_col:
            if st.button("Load sample", key="use_sample_data"):
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
                "Registry files are not loaded. This run can still check reference completeness."
            )

        with st.expander("Custom watchlist filter", expanded=False):
            st.caption(
                "Add publishers or journals your institution wants to manually review. "
                "Saved to `data/custom_watchlist.csv`."
            )
            st.info(
                "Why this helps: public registries are useful but never complete. "
                "A custom watchlist adds your local policy context, helps catch known concerns early, "
                "and reduces false confidence when something is simply not found in a registry."
            )

            starter_labels = {
                entry["name"]: f"{entry['name']} ({entry['risk_level']})"
                for entry in STARTER_WATCHLIST
            }
            selected_starters = st.multiselect(
                "Starter entries from current research scan",
                options=[entry["name"] for entry in STARTER_WATCHLIST],
                format_func=lambda name: starter_labels.get(name, name),
                key="starter_watchlist_selection",
            )
            if st.button("Add selected starters", key="add_starter_watchlist"):
                starter_rows = [
                    {**entry, "entry_id": _watchlist_entry_id(entry["name"], entry["url_domain"])}
                    for entry in STARTER_WATCHLIST
                    if entry["name"] in selected_starters
                ]
                updated_df, added_count = _append_watchlist_rows(custom_watchlist_df, starter_rows)
                if added_count:
                    _save_custom_watchlist_df(updated_df)
                    st.session_state.custom_watchlist_df = updated_df
                    custom_watchlist_df = updated_df
                    st.success(f"Added {added_count} starter entr{'y' if added_count == 1 else 'ies'}.")
                else:
                    st.info("No new starter entries were added.")

            with st.form("manual_watchlist_form", clear_on_submit=True):
                watch_name = st.text_input("Publisher or journal name")
                watch_domain = st.text_input("Domain (optional)")
                watch_concern = st.selectbox(
                    "Concern level",
                    options=["Medium", "High", "Low"],
                    index=0,
                )
                watch_note = st.text_input("Short note (optional)")
                watch_source = st.text_input("Source label (optional)", value="Institution watchlist")
                watch_source_url = st.text_input("Source URL (optional)")
                add_manual = st.form_submit_button("Add custom entry")

            if add_manual:
                manual_row = {
                    "name": watch_name.strip(),
                    "type": "publisher",
                    "url_domain": extract_domain(watch_domain) or "",
                    "risk_level": watch_concern,
                    "warning_summary": watch_note.strip(),
                    "source": watch_source.strip() or "Institution watchlist",
                    "source_url": watch_source_url.strip(),
                    "entry_id": _watchlist_entry_id(watch_name.strip(), watch_domain.strip()),
                }
                updated_df, added_count = _append_watchlist_rows(custom_watchlist_df, [manual_row])
                if added_count:
                    _save_custom_watchlist_df(updated_df)
                    st.session_state.custom_watchlist_df = updated_df
                    custom_watchlist_df = updated_df
                    st.success("Custom entry added.")
                else:
                    st.info("Entry was blank or already exists.")

            if not custom_watchlist_df.empty:
                st.caption(f"{len(custom_watchlist_df)} custom entr{'y' if len(custom_watchlist_df) == 1 else 'ies'} loaded.")
                display_df = custom_watchlist_df[
                    ["name", "url_domain", "risk_level", "warning_summary", "source"]
                ].rename(
                    columns={
                        "name": "Name",
                        "url_domain": "Domain",
                        "risk_level": "Concern",
                        "warning_summary": "Note",
                        "source": "Source",
                    }
                )
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                removal_options = [
                    f"{idx}|{_watchlist_display_label(custom_watchlist_df.iloc[idx])}"
                    for idx in range(len(custom_watchlist_df))
                ]
                selected_remove = st.selectbox(
                    "Remove entry",
                    options=removal_options,
                    index=0,
                    key="watchlist_remove_selection",
                )
                if st.button("Remove selected entry", key="remove_watchlist_entry"):
                    remove_idx = int(selected_remove.split("|", 1)[0])
                    updated_df = custom_watchlist_df.drop(index=remove_idx).reset_index(drop=True)
                    _save_custom_watchlist_df(updated_df)
                    st.session_state.custom_watchlist_df = updated_df
                    custom_watchlist_df = updated_df
                    st.success("Entry removed.")
            else:
                st.info("No custom watchlist entries yet.")

        uploaded = st.file_uploader(
            "Upload TXT or CSV",
            type=["txt", "csv"],
        )

        if uploaded is not None:
            name = (uploaded.name or "").lower()
            if name.endswith(".csv"):
                separator_label = st.selectbox(
                    "CSV separator",
                    options=["Auto detect", "Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"],
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
                            "Reference column",
                            options=[str(column) for column in csv_df.columns],
                        )
                        st.caption("Preview")
                        st.dataframe(csv_df.head(5), use_container_width=True, hide_index=True)
                        if st.button("Load column", key="load_csv_column"):
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
                st.caption("Preview")
                st.code(preview_lines or "(File is empty)", language="text")
                if st.button("Load text", key="load_text_upload"):
                    st.session_state.reference_text = preview_text
                    st.session_state.analysis_ran = False

        simple_mode = st.toggle(
            "Standard matching",
            value=True,
            help="Recommended for most reference lists.",
        )

        if simple_mode:
            fuzzy_threshold = 0.88
            max_fuzzy_matches = 3
        else:
            st.caption("Adjust only if matching looks too broad or too strict.")
            fuzzy_threshold = st.slider(
                "Match strictness",
                min_value=0.7,
                max_value=0.98,
                value=0.88,
                step=0.01,
            )
            max_fuzzy_matches = st.number_input(
                "Suggestions per reference",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
            )

        with st.form("analysis_form", clear_on_submit=False):
            st.subheader("2. Run check")
            st.caption("Use standard matching unless results look too broad or too strict.")
            reference_text = st.text_area(
                "Reference list",
                placeholder="One full reference per line",
                height=260,
                key="reference_text",
            )
            action = st.form_submit_button("Run check")

        if action:
            st.session_state.analysis_error = ""
            if not reference_text.strip():
                st.session_state.analysis_rows = []
                st.session_state.analysis_pred_db_loaded = pred_db is not None
                st.session_state.analysis_ran = True
                st.session_state.analysis_notice = "Add at least one reference."
            else:
                try:
                    latest_custom_df = st.session_state.custom_watchlist_df
                    latest_custom_db = (
                        PredatoryDbProvider.from_csv_paths([custom_watchlist_path])
                        if not latest_custom_df.empty and custom_watchlist_path.exists()
                        else None
                    )
                    with st.status("Running checks...", expanded=True) as status_box:
                        status_box.write("1/3 Reading references")
                        progress = st.progress(15)
                        status_box.write("2/3 Matching against registry data")
                        rows, pred_db_loaded = _build_rows(
                            reference_text,
                            fuzzy_threshold=float(fuzzy_threshold),
                            max_fuzzy_matches=int(max_fuzzy_matches),
                            pred_db=pred_db,
                            custom_db=latest_custom_db,
                        )
                        progress.progress(75)
                        status_box.write("3/3 Preparing results")
                        progress.progress(100)
                        status_box.update(
                            label=f"Done: {len(rows)} references processed",
                            state="complete",
                            expanded=False,
                        )
                    st.session_state.analysis_rows = rows
                    st.session_state.analysis_pred_db_loaded = pred_db_loaded
                    st.session_state.analysis_ran = True
                    if rows:
                        st.session_state.analysis_notice = ""
                        if hasattr(st, "toast"):
                            st.toast("Check complete.")
                    else:
                        st.session_state.analysis_notice = (
                            "No references found. Add one reference per line."
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
        st.subheader("3. Review results")
        st.caption("Start with items that need attention, then inspect details.")
        st.markdown(
            """
            <div class="legend">
              <div class="legend-item"><span class="legend-badge badge-immediate">❗ Check immediately</span><span>High-priority risk signal. Review first.</span></div>
              <div class="legend-item"><span class="legend-badge badge-manual">⚠ Check manually</span><span>Possible concern. Verify before use.</span></div>
              <div class="legend-item"><span class="legend-badge badge-details">🛠 Add missing details</span><span>Reference is incomplete and needs fixing.</span></div>
              <div class="legend-item"><span class="legend-badge badge-ok">✓ Looks OK</span><span>No urgent warning found in this run.</span></div>
              <div class="legend-item"><span class="legend-badge badge-flag">🏷 Registry/Watchlist flagged</span><span>Matched a loaded registry entry or your custom watchlist.</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not st.session_state.analysis_ran:
            st.info("Run the check to view results.")
        elif st.session_state.analysis_error:
            st.error(f"Could not complete the check: {st.session_state.analysis_error}")
        else:
            rows = st.session_state.analysis_rows or []
            if not rows:
                st.warning(st.session_state.analysis_notice or "No results available.")
            else:
                if not st.session_state.analysis_pred_db_loaded:
                    st.warning(
                        "Registry files were not found. Only reference completeness was checked."
                    )

                df = pd.DataFrame(rows)
                total = len(df)
                matches = int((df["Registry warning"] == "Match").sum())
                custom_matches = int((df["Custom watchlist warning"] == "Match").sum())
                no_match = total - matches
                needs_review = int(df["Recommended next step"].isin(["Check immediately", "Check manually"]).sum())
                score_series = df["Match confidence"].fillna("").astype(str).str.rstrip("%")
                avg_score = score_series.replace("", "0").astype(float).mean()

                stats = st.columns(6)
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
                      <div class="stat-label">Registry-flagged</div>
                      <div class="stat-value">{matches}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                stats[2].markdown(
                    f"""
                    <div class="stat-card">
                      <div class="stat-label">Watchlist-flagged</div>
                      <div class="stat-value">{custom_matches}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                stats[3].markdown(
                    f"""
                    <div class="stat-card">
                      <div class="stat-label">Not found</div>
                      <div class="stat-value">{no_match}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                stats[4].markdown(
                    f"""
                    <div class="stat-card">
                      <div class="stat-label">Needs review</div>
                      <div class="stat-value">{needs_review}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                stats[5].markdown(
                    f"""
                    <div class="stat-card">
                      <div class="stat-label">Avg. confidence</div>
                      <div class="stat-value">{avg_score:.0f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.caption(
                    "`Not found` means no matching entry was found in the loaded registry data."
                )

                view_name = _pick_view()
                filtered_df = _sort_for_review(_filter_rows(df, view_name).reset_index(drop=True))
                st.caption(f"Showing {len(filtered_df)} of {len(df)} references in this view.")
                if filtered_df.empty:
                    st.info("No references match this filter. Try another quick view.")
                    filtered_df = _sort_for_review(df.reset_index(drop=True))

                display_columns = [
                    "Reference",
                    "Recommended next step",
                    "Registry warning",
                    "Custom watchlist warning",
                    "Risk level",
                    "Registry record",
                    "Matched text",
                    "Source URL",
                    "Norwegian registry search",
                ]
                display_df = filtered_df[display_columns].copy()
                display_df["Registry warning"] = display_df["Registry warning"].replace(
                    {"Match": "Flagged", "No match": "Not found in loaded registry"}
                )
                display_df["Custom watchlist warning"] = display_df["Custom watchlist warning"].replace(
                    {"Match": "Flagged", "No match": "Not found in custom watchlist"}
                )

                column_config = {
                    "Norwegian registry search": st.column_config.LinkColumn(
                        "Search Norwegian register"
                    ),
                    "Source URL": st.column_config.LinkColumn("Source URL"),
                    "Registry warning": st.column_config.TextColumn("Registry flag"),
                    "Custom watchlist warning": st.column_config.TextColumn("Watchlist flag"),
                    "Recommended next step": st.column_config.TextColumn(
                        "What to do next",
                    ),
                }

                styled = display_df.style
                style_rules = [
                    ("Registry warning", _style_match_status),
                    ("Custom watchlist warning", _style_custom_status),
                    ("Risk level", _style_risk_level),
                    ("Norwegian level", _style_norwegian_level),
                    ("Reference check", _style_missing_fields),
                    ("Recommended next step", _style_action),
                ]
                for column_name, style_fn in style_rules:
                    if column_name in display_df.columns:
                        styled = styled.applymap(style_fn, subset=[column_name])
                st.dataframe(
                    styled,
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config,
                )

                detail_options = [
                    _short_text(row["Reference"])
                    for idx, row in filtered_df.iterrows()
                ]
                if detail_options:
                    selected_option = st.selectbox(
                        "Inspect reference",
                        options=detail_options,
                        index=0,
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
                    details_cols[0].write(selected_row["Registry record"] or "Not found in loaded registry")
                    details_cols[1].markdown("**Reference check**")
                    details_cols[1].write(selected_row["Reference check"])
                    st.markdown("**Registry note**")
                    st.write(selected_row["Registry note"] or "No additional note")
                    st.markdown('</div>', unsafe_allow_html=True)

                full_export_df = _sort_for_review(df.reset_index(drop=True))
                csv_data = full_export_df.to_csv(index=False).encode("utf-8")
                excel_data = _build_excel_bytes(full_export_df)
                download_cols = st.columns(2)
                with download_cols[0]:
                    st.download_button(
                        "Download CSV",
                        data=csv_data,
                        file_name="reference_check_results.csv",
                        mime="text/csv",
                    )
                with download_cols[1]:
                    st.download_button(
                        "Download Excel (.xlsx)",
                        data=excel_data,
                        file_name="reference_check_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="footer-note">Keep registry files updated for the most complete matching.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
