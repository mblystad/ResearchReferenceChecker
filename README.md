# Research Reference Checker

Research Reference Checker helps academic users review references for missing details and possible warning signals.

## For Users

If you just want to use the app, you only need the Windows release zip.

### Download and Open

1. Go to **GitHub Releases** for this repository.
2. Download the latest `ReferenceChecker-windows-x64.zip`.
3. Unzip it.
4. Double-click `ReferenceChecker.exe`.
5. The app opens in your browser on your own computer.

### Use the App

1. Paste references, one per line.
2. Click **Review references**.
3. Start with the **What to do next** column.
4. Open **Inspect reference** if you want more detail.
5. Export CSV or Excel if needed.

### Add Screenshot Here

Add your illustration or screenshot in this section so colleagues can see the app before downloading it.

You can also point users to [USER_QUICKSTART.md](./USER_QUICKSTART.md) for a shorter handout-style guide.

### Important Notes for Users

- No Python installation is needed.
- If Windows SmartScreen appears, choose **More info** -> **Run anyway** if you trust the source.
- `No registry match` does not automatically mean a source is safe.
- `Not listed in DOAJ` does not automatically mean a journal is problematic.
- The app supports review. It does not replace subject expertise or institutional policy.
- Custom watchlist entries are saved in a local `data/` folder next to the EXE.

## What the App Does

The app can:
- review references against loaded journal and publisher warning lists
- optionally check whether a parsed journal is listed in DOAJ
- optionally add a Norwegian Kanalregister search link for parsed journals
- optionally match against a local custom watchlist of journals and publishers
- expand abbreviated journal names such as `J. Clin. Oncol.` before warning-list matching and DOAJ lookup
- show a plain-language summary in a web UI
- export results to CSV or Excel

## How to Read the Results

- `Check immediately`: strong warning signal that should be reviewed first
- `Check manually`: possible concern that needs human review
- `Add missing details`: the reference looks incomplete
- `Looks OK`: no urgent issue was found in this run

Important:
- A match is a warning signal, not a verdict.
- `No registry match` means no match was found in the loaded list. It is not a clearance result.
- `Not listed in DOAJ` means the journal was not found in DOAJ during that lookup. It is not a verdict by itself.
- The Norwegian register option adds a search link only. It is a convenience feature, not a quality check by itself.

## Data Sources

The app can use these sources during a run:
- DOAJ API for journal listing checks
- warning-list data collected from `predatoryjournals.org`
- Norwegian Kanalregister search links for parsed journal titles
- your own saved custom watchlist in `data/custom_watchlist.csv`

Warning-list source details shown in the app:
- source website: `https://www.predatoryjournals.org/`
- update label used in the UI: `February 2, 2026`

## Limits to Know

- The web app expects one reference per line.
- The CLI manuscript parser expects a heading such as `References`, `Reference List`, `Bibliography`, `Works Cited`, or `Literature Cited`.
- If you disable all actual review checks, the app switches to completeness-only mode and highlights missing details such as authors, journal or venue, year, and DOI or URL.

## GitHub Project Info

### Run from Source

```powershell
.\scripts\prepare_demo.ps1
.\scripts\run_demo.ps1
```

What this does:
- creates a local Python environment (`.venv`) if needed
- installs dependencies
- builds abbreviation datasets and enriched registry data
- runs tests
- opens the app

For a presenter checklist, see [DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md).

### Create a Release Zip

```powershell
python .\zip.py
```

Output:
- `dist/ReferenceChecker-windows-x64/`
- `dist/ReferenceChecker-windows-x64.zip`

The release folder and zip include:
- `ReferenceChecker.exe`
- the packaged runtime files needed to launch the app without Python installed
- `data/` with registry CSV files and the abbreviation database
- `README.txt` and `USER_QUICKSTART.md`

### Troubleshooting

#### App does not start
- Run: `.\.venv\Scripts\python.exe run_app.py`
- If there is an error, check `ReferenceChecker.log` next to the app launcher.

#### Warning-list files not found
- Make sure the CSV files are in the project root or `data/`.

#### No references detected
- Paste one reference per line in the web app.
- For CLI parsing, make sure the manuscript uses a heading such as `References`, `Reference List`, `Bibliography`, `Works Cited`, or `Literature Cited`.

#### PowerShell script blocked

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_demo.ps1
```

### CLI (Advanced)

```powershell
.\.venv\Scripts\python.exe -m reference_checker.cli your_manuscript.docx --json-output results.json
```

Optional outputs:
- `--updated-docx`
- `--bibtex-output`
- `--ris-output`
- `--endnote-output`

### Project Structure

- `app.py`: Streamlit app UI
- `run_app.py`: local launcher for Streamlit app
- `scripts/build_journal_abbreviation_db.py`: abbreviation and enrichment builder
- `src/reference_checker/predatory_db.py`: warning-list matching engine
- `src/reference_checker/journal_abbreviations.py`: abbreviation dataset loader

### Developer Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests --ignore-glob=pytest-cache-files-*
```
