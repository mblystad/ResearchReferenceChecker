# Research Reference Checker

Research Reference Checker is a local review tool for academic reference lists.
It helps you spot incomplete references, warning-list matches, missing journal details,
and other issues before submission, supervision, or internal review.

## What it does

The app can:
- review one reference per line in a Streamlit interface
- flag matches against bundled journal and publisher warning lists
- expand abbreviated journal titles before matching
- optionally check whether a parsed journal is listed in DOAJ
- optionally add a Norwegian register search link
- let users keep a local custom watchlist in `data/custom_watchlist.csv`
- export review results to CSV or Excel

Important:
- a match is a warning signal, not a verdict
- `No registry match` is not a clearance result
- `Not listed in DOAJ` is not a verdict by itself
- the tool supports review and does not replace subject expertise or policy

## For end users

This repository is the source version of the project.
If you publish a packaged Windows release separately, end users do not need Python or an IDE.

See [USER_QUICKSTART.md](./USER_QUICKSTART.md) for the short handout version.

## Run from source

Requirements:
- Windows
- Python 3.11+

Quick setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe run_app.py
```

The app opens in your browser and runs locally on your machine.

## Demo helpers

The repo includes helper scripts for demo prep:

```powershell
.\scripts\prepare_demo.ps1
.\scripts\run_demo.ps1
```

`prepare_demo.ps1`:
- creates `.venv` if missing
- installs the project in editable mode
- rebuilds abbreviation data
- runs tests unless `-SkipTests` is used

`run_demo.ps1` launches the local app, or prints the launch command with `-NoLaunch`.

For a presenter checklist, see [DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md).

## CLI usage

The project also includes a CLI entrypoint for manuscript files:

```powershell
.\.venv\Scripts\python.exe -m reference_checker.cli your_manuscript.docx --json-output results.json
```

Optional outputs include:
- `--updated-docx`
- `--bibtex-output`
- `--ris-output`
- `--endnote-output`

Supported manuscript parsing depends on the file containing a references section such as:
- `References`
- `Reference List`
- `Bibliography`
- `Works Cited`
- `Literature Cited`

## Data and local files

Bundled project data includes:
- warning-list CSVs in the project root and `data/`
- abbreviation datasets in `data/abbr_to_full.json` and `data/abbr_to_full.sqlite`
- an enriched registry file in `data/predatory_db_v7_with_norwegian_levels_enriched.csv`

User-generated local data:
- custom watchlist entries are stored in `data/custom_watchlist.csv`

External data/services used by the project:
- DOAJ API for journal listing checks
- warning-list data collected from `predatoryjournals.org`
- abbreviation sources used by `scripts/build_journal_abbreviation_db.py`

## Project structure

- `app.py`: Streamlit user interface
- `run_app.py`: local launcher for the web app
- `src/reference_checker/`: core parsing, matching, validation, export, and CLI logic
- `scripts/build_journal_abbreviation_db.py`: abbreviation/enrichment data builder
- `data/`: generated and bundled data assets
- `tests/`: automated tests

## Developer validation

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests --ignore-glob=pytest-cache-files-*
```

Rebuild abbreviation/enrichment data:

```powershell
.\.venv\Scripts\python.exe scripts\build_journal_abbreviation_db.py
```

## Troubleshooting

App does not start:
- run `.\.venv\Scripts\python.exe run_app.py`
- if a packaged build fails, check `ReferenceChecker.log` next to the launcher

Warning-list files not found:
- keep the bundled `data/` folder next to `ReferenceChecker.exe`

No references detected:
- use one full reference per line in the web app
- for CLI parsing, make sure the manuscript includes a references heading

PowerShell script blocked:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_demo.ps1
```
