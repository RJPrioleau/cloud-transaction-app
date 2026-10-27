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
- Browser-based upload report with each transaction's assigned Budget Name
- Budget Name summary with separate added/duplicate counts and totals
- Read-only MISC review grouped by description to help identify potential category rules
- Local generated CSV reports and upload logs
- Confirmed TEST-only reset of imported values in rows 69–383, preserving formulas and formatting

To start a fresh TEST import, open **Reset TEST imported transactions** from the upload page, review the scope, check the confirmation box, and submit. It clears only H, I, K, O, and P within rows 69–383. Entries below row 383 and local report/log files remain unchanged.

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

Start the local app from PowerShell 7 (activation is not required):

```powershell
.\start_app.ps1
```

After editing Python code or page templates, restart it:

```powershell
.\start_app.ps1 -Restart
```

Check the running version or stop the managed server:

```powershell
.\start_app.ps1 -Status
.\start_app.ps1 -Stop
```

The launcher prints the URL, process ID, and source fingerprint only after the app responds with the expected version. Open `http://127.0.0.1:5000`. Starting twice reuses the current server; stale code produces a restart instruction. Restart and stop affect only this repository's `local_server.py` processes. An unrelated or manually started server on port 5000 is left untouched and must be stopped separately. Local server output goes to ignored `logs/local-server.log`.

Double-clicking `start_app.bat` runs the same restart workflow using `pwsh.exe` (PowerShell 7 must be installed and available on PATH). If PowerShell blocks the script, inspect your execution policy rather than bypassing it automatically. `python app.py` remains available for manual development/deployment, but those manually started processes are not managed by the launcher; stop them before switching to the managed workflow.

Run the characterization tests:

```powershell
python -m unittest discover -s tests
```

For a quick syntax-only check:

```powershell
python -m py_compile app.py transaction_processor.py tests\test_transaction_processor.py
```

## Income Calendar Persistence - Development Only

The database provides create/read functions and a browser interface for income sources and **draft** official pay dates. It does not change transaction imports, Google Sheets, account balances, or funding decisions.

After database setup below, run `.\start_app.ps1 -Restart` and select **Draft Income Calendar** on the upload page (http://127.0.0.1:5000/income). Create a synthetic income source, select it, and add official dates with optional pay-period boundaries and a reference. Dates appear chronologically and remain drafts. Validation errors preserve form entries. Successful submissions redirect to a read-only GET, so refreshing the resulting page does not resubmit the form. Deliberately submitting the same values again can still create another record; duplicate review is deferred. Forms use session tokens. Restarting the server may require reopening the form.

With the project virtual environment active, run from the project root:

```powershell
python -m pip install -r .\requirements.txt
python -m alembic upgrade head
python -m alembic current
```

SQLAlchemy defines records and database operations; Alembic records and applies versioned schema changes. `upgrade head` creates the two income-calendar tables and records the migration revision. Running it again preserves existing rows. Importing the Python modules does not create a database or tables.

By default, the database is `instance/development.sqlite3`, resolved from the repository root rather than the terminal's current folder. The ignored `instance/` directory is for **synthetic development data only**. `DATABASE_URL` can select another development database; do not point development commands at real financial records. PostgreSQL is the approved shared-deployment target, but no PostgreSQL driver, service, or deployment is introduced in this slice.

The repository functions in `income_repository.py` accept a SQLAlchemy session. Use `database.session_scope(engine)` around an operation: it commits all successful changes together and rolls everything back on failure. Paydays and optional pay-period boundaries are Python `date` values. Created timestamps are stored as UTC without an offset for consistent SQLite storage. Newly created pay dates can only be drafts; they do not represent received deposits. There are no edit, delete, scheduling, or confirmation operations yet. Source names and source/date pairs are not assumed unique.

Run the focused acceptance tests:

```powershell
python -m unittest tests.test_income_repository tests.test_database_migrations
```

These tests use temporary synthetic databases and verify migrations, restart persistence, foreign keys, draft constraints, validation, rollback, and backup/recovery. They never connect to Google Sheets.

`database.backup_sqlite_database(engine, destination)` uses SQLite's backup API for file-based development databases. Call it outside a write transaction and choose a new destination, such as `instance/development-backup.sqlite3`; it refuses an existing destination or the source path. The recovery test deletes only its temporary source database, restores the backup to a separate file, reapplies migrations, and verifies IDs, relationships, dates, timestamps, and database integrity. Stop database users before replacing an operational database. Do not use `alembic downgrade base` as a recovery command: it drops these tables and their records. PostgreSQL migrations and production backup/recovery remain separate approval and verification gates.

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
