# Reference Checker

Reference Checker validates manuscript references **without altering body text**. It extracts reference list entries, flags issues, and optionally screens journals/publishers against local registries. A Streamlit UI lets you paste a reference list, choose a style, and view a validation table with missing info plus predatory/Norwegian flags.

## Project scope (from `PROMPT.md`)
- **Never modify manuscript body text.** Reference-only processing.
- Detect citation/reference mismatches and missing metadata.
- Fetch missing metadata from public databases (Crossref, DOI landing pages, etc.).
- Produce validation reports and updated reference lists using verified metadata.

## Current capabilities
- **UI input:** paste a reference list (one reference per line).
- **Style checks:** APA, AMA (strict), or Neutral (basic completeness).
- **Predatory screening:** match journal/publisher against local CSV registries (v6) and surface risk + Norwegian level + manual-check links.
- **Crossref enrichment (optional):** fetch journal metadata before matching to improve registry hits (requires internet).
- **Database audit (optional):** export an Excel report of entries that are both in the predatory registry and have Norwegian levels (0/1/2).
- **Missing info checks:** authors, title, year, journal/venue, volume/issue/pages, DOI/URL (style-aware).
- **Outputs:** Streamlit table view; CLI remains available for DOCX/PDF/text workflows.

## Reference type detection
The app classifies entries as journal articles, books/chapters, conference papers, preprints, websites, or datasets and applies type-aware completeness checks.
For APA/AMA validation, journal articles also require volume, issue, and page ranges when available.

## Requirements
- Python 3.11+
- pip (or another installer) to install dependencies

## Quickstart (local IDE: PyCharm / VS Code)
Think "paint-by-numbers" simple. Follow these steps in order, copy/paste the commands, and you will have the app running.

1. **Open a terminal in the project folder**  
   PyCharm: right-click the project folder -> **Open in Terminal**.  
   VS Code: View -> **Terminal** (it opens at the project root).

2. **Make a sandbox just for this project (virtual environment)**
   ```bash
   python -m venv .venv
   ```
   - Windows: run `.venv\Scripts\activate`
   - macOS/Linux: run `source .venv/bin/activate`
   Keep this terminal open while you work so the sandbox stays active.

3. **Install everything the app needs**
   ```bash
   pip install -e .
   ```

   Place `predatory_db_v7_with_norwegian_levels.csv` in the project root (or `data/`) to enable predatory/Norwegian screening.

4. **Start the Streamlit app**
   ```bash
   streamlit run app.py
   ```
   - Open your browser at <http://localhost:8501>.
   - Paste your reference list (one reference per line).
   - Choose **APA**, **AMA**, or **Neutral**.
   - Click **Analyze references** to see the table.

5. **Close and reopen later**  
   Press `Ctrl+C` in the terminal to stop the server. To start again, repeat step 4.

6. **Run the automated checks (optional but nice)**
   ```bash
   pytest -q
   ```

7. **Use the CLI for DOCX/PDF workflows (optional)**
   Create a sample DOCX (or point to your own manuscript) and run validation:
   ```bash
   python - <<'PY'
from pathlib import Path
from reference_checker.app import ReferenceCheckerApp

PARAGRAPHS = [
    "Dummy Manuscript for Reference Checker",
    "This short document includes dummy text with in-text citations [1] and [2] to support testing of the reference checker workflow. It also mentions an author-based citation (Doe, 2021) and highlights the importance of consistent metadata [3]. Additional filler sentences ensure the content spans roughly one page when rendered in a standard word processor.",
    "Methodologically, the sample text outlines a hypothetical pipeline with preprocessing, citation detection, reference parsing, metadata enrichment, and validation reporting [1,3]. The details are intentionally lightweight so that automated tools can focus on references without modifying the surrounding narrative.",
    "Another paragraph adds variety by discussing limitations, potential error cases, and logging needs [2]. It hints at uncited references and dangling citations to see how the checker flags missing links.",
    "References",
    "[1] Doe J. Sample article title. Journal of Testing. 2021;10(2):123-130. doi:10.1234/jt.2021.456.",
    "[2] Smith A, Lee B. Another study on testing. Proceedings of the Reference Checking Conference; 2020. Available from: https://example.com/testing.",
    "[3] Patel R. Data validation handbook. Testing Press; 2019.",
    "[4] Adams K. Preprint example on reference integrity. bioRxiv; 2023. doi:10.1101/2023.12345.",
]

Path("sample_manuscript.docx").write_bytes(
    ReferenceCheckerApp._build_minimal_docx(PARAGRAPHS)  # type: ignore[attr-defined]
)
PY

   reference-checker sample_manuscript.docx \
     --json-output results.json \
     --updated-docx updated.docx \
     --bibtex-output refs.bib \
     --ris-output refs.ris \
     --endnote-output refs.xml \
     --style vancouver
   ```
   Add `--check-links` to perform HTTP reachability checks for DOIs/URLs (requires network access). The CLI prints the same validation report shown in the UI and writes optional JSON/BibTeX/RIS/EndNote/updated DOCX outputs when paths are provided.
   Add `--web-metadata` to scrape public URL/DOI landing pages for missing authors, titles, years, and page ranges when references are incomplete.
   Add `--crossref-metadata` to fill gaps using Crossref's API without overwriting existing fields.
   Add `--verify-online` to compare each reference's title/author/year against Crossref and flag mismatches.
   Add `--predatory-db path/to.csv` (repeatable) to point at local predatory-journal registries, or `--no-predatory-db` to disable screening.

## Programmatic usage
```python
from reference_checker.app import ReferenceCheckerApp
from reference_checker.link_checker import LinkVerifier
from reference_checker.web_metadata import WebPageMetadataProvider

checker = ReferenceCheckerApp(
    link_verifier=LinkVerifier(), metadata_provider=WebPageMetadataProvider()
)
extraction, issues = checker.process_file("sample_manuscript.docx", check_links=True)
report = checker.validation_report(extraction.body_text + "\nReferences\n" + extraction.references_text)
updated_docx_bytes = checker.build_updated_docx(extraction, issues)
```
`updated_docx_bytes` can be written to disk to share an updated reference list copy.

To fill missing fields or cross-check accuracy programmatically, combine providers and verifiers:

```python
from reference_checker.crossref import CrossrefMetadataProvider, OnlineReferenceVerifier

checker = ReferenceCheckerApp(
    metadata_provider=CrossrefMetadataProvider(),
    online_verifier=OnlineReferenceVerifier(),
)
_, online_issues = checker.process_file("sample_manuscript.docx", verify_online=True)
```

## Sample data
To avoid storing binaries in the repository, use the snippet above (or the `sample_docx_path` pytest fixture) to generate the one-page dummy manuscript on demand. The text includes numbered citations [1], [2], an author citation (Doe, 2021), and a four-entry reference list with one intentionally uncited entry for negative checks.

## Repository map (key modules)
- `app.py`: Streamlit UI for reference-list validation.
- `scripts/merge_norwegian_levels.py`: Merge Norwegian levels into predatory registry (creates `predatory_db_v7_with_norwegian_levels.csv`).
- `src/reference_checker/app.py`: Orchestrates extraction, validation, enrichment, reporting.
- `src/reference_checker/reference_parser.py`: Reference list parsing heuristics.
- `src/reference_checker/citation_extractor.py`: In-text citation detection.
- `src/reference_checker/reference_types.py`: Reference type classification heuristics.
- `src/reference_checker/validation.py`: Issue detection rules.
- `src/reference_checker/web_metadata.py`: DOI/URL landing-page scraping.
- `src/reference_checker/crossref.py`: Crossref metadata and verification.
- `src/reference_checker/exporters.py`: JSON/BibTeX/RIS/EndNote export helpers.
- `src/reference_checker/predatory_db.py`: Predatory journal/publisher CSV matching.
- `src/reference_checker/normalization.py`: Shared normalization helpers for matching.
