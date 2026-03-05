# Demo Runbook

## 1. Prepare (once before demo)

```powershell
.\scripts\prepare_demo.ps1
```

This installs dependencies, builds data, and runs tests.

## 2. Launch app

```powershell
.\scripts\run_demo.ps1
```

## 3. Demo flow (recommended)

1. Paste 5 to 10 references (one per line).
2. Include at least one abbreviated journal name.
3. Click **Analyze references**.
4. Explain columns:
- `Recommended next step`
- `Registry warning`
- `Risk level`
- `Expanded journal title`
- `Abbreviation candidates`
5. Open one flagged row in **Inspect reference**.
6. Export CSV.

## 4. Quick fallback commands

If scripts are blocked:

```powershell
.\.venv\Scripts\python.exe scripts\build_journal_abbreviation_db.py
.\.venv\Scripts\python.exe run_app.py
```
