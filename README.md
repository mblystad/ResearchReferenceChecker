# Reference Checker

Reference Checker validates manuscript references without altering body text. It parses citations and reference lists, flags mismatches, fills missing metadata, and can export refreshed reference lists and reports. A FastAPI UI lets you upload DOCX files or paste text, view the validation report, and download an updated DOCX with highlighted missing details.

## Requirements
- Python 3.11+
- pip (or another installer) to install dependencies

## Quickstart (local IDE: PyCharm / VS Code)
Think “paint-by-numbers” simple. Follow these steps in order, copy/paste the commands, and you will have the app running.

1. **Open a terminal in the project folder**  
   PyCharm: right-click the project folder → **Open in Terminal**.  
   VS Code: View → **Terminal** (it opens at the project root).

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
   You should see messages about FastAPI, uvicorn, and other packages being installed. If you ever see an error, rerun the same command.

4. **Start the web app (the friendly interface)**
   ```bash
   uvicorn reference_checker.web:app --reload
   ```
   - Leave this running.
   - Open your browser at <http://localhost:8000>.
   - Click **Upload DOCX** or **Paste text**, then **Validate references**.
   - After processing a DOCX, click the **Download updated DOCX** link to get a copy with missing details noted.
   - Toggle “scrape web pages for missing details” to let the app visit DOIs/URLs and pull citation meta tags.
   - Toggle “Query Crossref to complete references” to fetch authoritative metadata from Crossref.
   - Toggle “Check cited metadata against Crossref” to verify that the provided title/author/year match the online record.

5. **Close and reopen later**  
   Press `Ctrl+C` in the terminal to stop the server. To start again, repeat step 4 (no need to reinstall unless you deleted the `.venv`).

6. **Run the automated checks (optional but nice)**
   ```bash
   pytest -q
   ```
   This confirms DOCX loading, the validation pipeline, and the web upload/download flow all behave as expected (FastAPI-dependent tests skip themselves if the framework is missing).

7. **Use the CLI for quick checks**
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

   reference-checker sample_manuscript.docx \\
     --json-output results.json \\
     --updated-docx updated.docx \\
     --bibtex-output refs.bib
   ```
   Add `--check-links` to perform HTTP reachability checks for DOIs/URLs (requires network access). The CLI prints the same validation report shown in the web UI and writes optional JSON/BibTeX/updated DOCX outputs when paths are provided.
   Add `--web-metadata` to scrape public URL/DOI landing pages for missing authors, titles, years, and page ranges when references are incomplete.
   Add `--crossref-metadata` to fill gaps using Crossref’s API without overwriting existing fields.
   Add `--verify-online` to compare each reference’s title/author/year against Crossref and flag mismatches.

## Programmatic usage
```python
from reference_checker.app import ReferenceCheckerApp
from reference_checker.link_checker import LinkVerifier
from reference_checker.web_metadata import WebPageMetadataProvider

checker = ReferenceCheckerApp(
    link_verifier=LinkVerifier(), metadata_provider=WebPageMetadataProvider()
)
extraction, issues = checker.process_docx("sample_manuscript.docx", check_links=True)
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
_, online_issues = checker.process_docx("sample_manuscript.docx", verify_online=True)
```

## Sample data
To avoid storing binaries in the repository, use the snippet above (or the `sample_docx_path` pytest fixture) to generate the one-page dummy manuscript on demand. The text includes numbered citations [1], [2], an author citation (Doe, 2021), and a four-entry reference list with one intentionally uncited entry for negative checks.
