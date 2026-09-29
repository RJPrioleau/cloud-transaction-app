# Cloud Transaction App

Cloud Transaction App is a local Flask application for importing personal bank transaction exports into a Google Sheets budget workbook.

The current app processes CSV/XLSX files, detects duplicate transactions, assigns basic budget categories, writes new rows to the selected month sheet, and produces local upload reports.

## Status

This project predates the current Developer Playbook workflow. The repository is being brought up to the same structure as the user's newer projects before deeper bug triage and feature work.

Current priority:

1. Preserve the working legacy behavior.
2. Triage the current bugs with the user.
3. Skip fixes that will be made obsolete by approved new features.
4. Restructure the code in small verified steps.

## Current Features

- Multi-file CSV/XLSX upload support
- Account detection from export filenames
- Transaction parsing and sorting
- Rule-based budget category assignment
- Duplicate detection against existing Google Sheets rows
- Google Sheets write workflow
- Browser-based upload report
- Local generated CSV reports and upload logs

## Documentation

- [Product baseline](docs/PRODUCT.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Collaboration workflow](docs/COLLABORATION.md)

## Development Setup

Create and activate a local virtual environment, then install the recorded dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

Run the Flask development server:

```powershell
python app.py
```

Open the app:

```text
http://127.0.0.1:5000
```

Verify the current Python files compile:

```powershell
python -m py_compile app.py transaction_processor.py
```

## Local Files

The app expects Google service account credentials locally. By default it looks for:

```text
credentials.json
```

You can also point to another credentials file by setting:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\credentials.json"
```

Generated uploads, reports, logs, credentials, virtual environments, and IDE settings are local-only and should not be committed.

Read `AGENTS.md` and the repository documentation before making implementation or architectural decisions.
