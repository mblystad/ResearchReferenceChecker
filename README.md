# Research Reference Checker

Reference Checker validates manuscript references **without changing the manuscript body text**. It extracts in-text citations and reference list entries, flags missing or inconsistent metadata, optionally enriches references using public sources, and can screen journals/publishers against local predatory and Norwegian registry CSVs.

This repository also includes a **Streamlit UI** that is focused on **predatory registry matching for a pasted reference list** (one reference per line). The full validation workflow is available via the CLI and the Python API.

---

## What you can do with this project

### 1) Streamlit UI (fast, non-coder friendly)
- Paste a reference list (one reference per line) or upload a `.txt` or `.csv` file.
- Match journal/publisher names against a local predatory registry CSV.
- See risk level, Norwegian level, and a direct Norwegian registry search link.
- See a simple missing-field flag for authors, title, journal, and DOI (local regex/heuristics).
- Tune fuzzy matching sensitivity.
- Download results as a CSV.

### 2) CLI (full reference validation)
- Parse `.docx`, `.pdf`, or `.txt` manuscripts.
- Detect missing or uncited references, duplicates, and broken citation markers.
- Run completeness checks (authors, title, year, DOI/URL, and type-specific fields).
- Optionally:
  - Check DOI/URL reachability (HTTP HEAD)
  - Enrich missing metadata from web pages or Crossref
  - Verify references against Crossref
  - Screen journals/publishers against local predatory registries
- Export:
  - Updated DOCX (references only, body text preserved as plain text)
  - JSON report
  - BibTeX, RIS, EndNote XML

---

## Quickstart (Streamlit UI - easiest)

This is the quickest way to try the predatory registry matcher.

1. **Open a terminal in this project folder**
   - Windows File Explorer: right-click the folder and choose **Open in Terminal**.

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   ```
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

3. **Install the dependencies**
   ```bash
   pip install -e .
   ```

4. **(Recommended) Place the predatory registry CSV**
   Put `predatory_db_v7_with_norwegian_levels.csv` in the project root or in `data/`.

5. **Run the Streamlit app**
   ```bash
   streamlit run app.py
   ```

6. **Use the UI**
   - Paste one reference per line, or upload a `.txt`/`.csv` file.
   - Click **Analyze references**.
   - Download the results CSV if needed.

---

## Quickstart (CLI - full validation)

1. **Install and activate the virtual environment** (same as above).
2. **Run the CLI on a manuscript file**
   ```bash
   reference-checker your_manuscript.docx --json-output results.json
   ```

3. **Add optional outputs**
   ```bash
   reference-checker your_manuscript.docx \
     --json-output results.json \
     --updated-docx updated.docx \
     --bibtex-output refs.bib \
     --ris-output refs.ris \
     --endnote-output refs.xml
   ```

4. **Enable optional online checks (requires internet)**
   ```bash
   reference-checker your_manuscript.docx \
     --check-links \
     --web-metadata \
     --crossref-metadata \
     --verify-online
   ```

5. **Control formatting style for exported references**
   ```bash
   reference-checker your_manuscript.docx --style vancouver
   ```
   Supported styles: `apa`, `vancouver`, `ieee`, `harvard`, `chicago`.

---

## Inputs supported

### Streamlit UI
- **Paste text**: one reference per line.
- **Upload**:
  - `.txt` (one reference per line)
  - `.csv` (first column is treated as references)

### CLI / Python API
- `.docx`
- `.pdf`
- `.txt` / `.md`

**Important:** For `.docx`, `.pdf`, and `.txt` files, the parser looks for a line that is exactly `References` or `Bibliography` (case-insensitive). Everything after that heading is treated as the reference list. If the heading is missing, the reference list may be empty.

---

## Outputs

### Streamlit UI
- Interactive results table
- Downloadable CSV

### CLI
- Printed validation report to the terminal
- Optional output files:
  - `--json-output` structured data (citations, references, issues)
  - `--updated-docx` rebuilt DOCX with updated reference list
  - `--bibtex-output`, `--ris-output`, `--endnote-output`

**Note on updated DOCX:** The updated DOCX is a minimal, clean document created from extracted text and formatted references. It preserves **text content** but does **not preserve original Word formatting**. The reference section also includes explicit "Missing details" lines when issues are detected.

---

## Predatory registry matching

### Where the CSV is loaded from
The predatory matcher automatically searches for these files (first match wins):
- `predatory_db_v7_with_norwegian_levels.csv`
- `predatory_db_v6_manual_check_links.csv`
- `predatory_db_v5_norwegian_levels.csv`
- `predatory_db_v5_norwegian_matches.csv`

It checks both the project root and a `data/` folder.

### Minimum useful CSV columns
The matcher works best with these columns (extra columns are ignored):
- `name` and `type` (required for name matching)
- `url`, `url_domain`, or `url_root` (enables domain matching)
- `risk_level` (or `risk`), `norwegian_level`, `warning_summary`
- `manual_check_*` columns for optional manual-review links
- Optional pre-normalized fields like `name_norm` or `abbr_norm` if your CSV already includes them

### Matching logic (high level)
- **Exact name match** on normalized `name`/`abbr` (or pre-normalized fields if present).
- **Domain match** if a reference contains a URL and the domain matches a registry entry.
- **Fuzzy match** (enabled in the UI with threshold control) using token overlap + similarity score.

### What gets reported
- Match status (Match / No match)
- Match basis (Exact name / Exact domain / Fuzzy name)
- Risk level (from the registry)
- Norwegian level (from the registry)
- Warning summary and manual-check links (if present in the CSV)

**Important:** These are **warning signals**, not legal or academic determinations. Always verify with the provided manual-check links.

### CLI options for predatory screening
The CLI will load default registry CSVs automatically if they exist. You can override or disable this behavior:
- `--predatory-db path/to/registry.csv` (repeatable, add more than one)
- `--no-predatory-db` (disable screening)

Example:
```bash
reference-checker your_manuscript.docx \
  --predatory-db data/predatory_db_v7_with_norwegian_levels.csv \
  --json-output results.json
```

---

## Merging Norwegian levels into the registry CSV

If you have:
- `predatory_db_v6_manual_check_links.csv`
- `2025-12-23 Scientific Journals and Series.csv`

You can generate a merged file with Norwegian levels:
```bash
python scripts/merge_norwegian_levels.py
```
This writes `predatory_db_v7_with_norwegian_levels.csv` in the project root.

---

## Python API (programmatic use)

```python
from reference_checker.app import ReferenceCheckerApp
from reference_checker.link_checker import LinkVerifier
from reference_checker.web_metadata import WebPageMetadataProvider

checker = ReferenceCheckerApp(
    metadata_provider=WebPageMetadataProvider(),
    link_verifier=LinkVerifier(),
)

extraction, issues = checker.process_file(
    "sample_manuscript.docx",
    check_links=True,
)
print(len(issues))
```

You can also add Crossref verification:
```python
from reference_checker.crossref import CrossrefMetadataProvider, OnlineReferenceVerifier

checker = ReferenceCheckerApp(
    metadata_provider=CrossrefMetadataProvider(),
    online_verifier=OnlineReferenceVerifier(),
)
extraction, issues = checker.process_file(
    "sample_manuscript.docx",
    verify_online=True,
)
```

---

## Project layout (key files)

- `app.py`: Streamlit UI for registry matching
- `src/reference_checker/app.py`: Main orchestration logic for extraction and validation
- `src/reference_checker/cli.py`: Command-line interface
- `src/reference_checker/reference_parser.py`: Reference parsing heuristics
- `src/reference_checker/citation_extractor.py`: In-text citation detection
- `src/reference_checker/validation.py`: Completeness and consistency checks
- `src/reference_checker/formatter.py`: Reference formatting (APA/Vancouver/IEEE/Harvard/Chicago)
- `src/reference_checker/web_metadata.py`: DOI/URL metadata scraping
- `src/reference_checker/crossref.py`: Crossref metadata + verification
- `src/reference_checker/predatory_db.py`: Predatory registry matching
- `scripts/merge_norwegian_levels.py`: Registry merge helper

---

## Troubleshooting

- **"Predatory registry CSV not found" in UI**
  Place `predatory_db_v7_with_norwegian_levels.csv` in the project root or in `data/`.

- **No references detected**
  For text files, add a line that says `References` before the reference list. For the UI, use one reference per line.

- **PDF extraction looks wrong**
  PDF text extraction quality depends on the file. Try a DOCX version if possible.

- **Online checks fail**
  The `--check-links`, `--web-metadata`, `--crossref-metadata`, and `--verify-online` flags require internet access.

---

## Running tests

```bash
pytest -q
```

---

## Notes about other scripts

This repo includes a `scripts/poller.py` and an `src/award_planner` package used for unrelated Seats.aero polling. They are not required for the reference checker. If you want to use them, install extra dependencies from `requirements.txt` and configure `.env.example`.
