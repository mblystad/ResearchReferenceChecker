# Reference Checker

Reference Checker validates manuscript references without altering body text. It parses citations and reference lists, flags mismatches, fills missing metadata, and can export refreshed reference lists and reports. A FastAPI UI lets you upload DOCX files or paste text, view the validation report, and download an updated DOCX with highlighted missing details.

## Requirements
- Python 3.11+
- pip (or another installer) to install dependencies

## Quickstart (local IDE: PyCharm / VS Code)
1. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
   ```

2. **Install the package and dependencies**
   ```bash
   pip install -e .
   ```
   This installs FastAPI, uvicorn, and multipart upload support defined in `pyproject.toml`.

3. **Run the web app (FastAPI + Tailwind)**
   ```bash
   uvicorn reference_checker.web:app --reload
   ```
   Then open http://localhost:8000 in your browser. Upload a DOCX or paste text to view the validation report. After processing a DOCX you will see a download link for the updated copy with refreshed references.

4. **Run the automated tests**
   ```bash
   pytest -q
   ```
   Tests include DOCX loading, validation pipeline behavior, and the web upload/download flow (FastAPI-dependent tests are skipped automatically if the framework is missing).

5. **Use the CLI for quick checks**
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

## Programmatic usage
```python
from reference_checker.app import ReferenceCheckerApp
from reference_checker.link_checker import LinkVerifier

checker = ReferenceCheckerApp(link_verifier=LinkVerifier())
extraction, issues = checker.process_docx("sample_manuscript.docx", check_links=True)
report = checker.validation_report(extraction.body_text + "\nReferences\n" + extraction.references_text)
updated_docx_bytes = checker.build_updated_docx(extraction, issues)
```
`updated_docx_bytes` can be written to disk to share an updated reference list copy.

## Sample data
To avoid storing binaries in the repository, use the snippet above (or the `sample_docx_path` pytest fixture) to generate the one-page dummy manuscript on demand. The text includes numbered citations [1], [2], an author citation (Doe, 2021), and a four-entry reference list with one intentionally uncited entry for negative checks.
