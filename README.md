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

## Local Planning Features

## Manual Bill Planning

Open **Bill planning** from the upload page or income forecast, or visit `/bills`. Add one bill name, dollar amount, and due date. An optional funding buffer defaults to **three calendar days before the due date**; zero means the due date itself. Bills are listed by earliest funding deadline, including past dates. Amounts use integer cents; blank amounts are rejected and explicit zero is permitted. No weekend/holiday adjustments are made.

These are individual planning occurrences, not recurring bill templates, reservations, payments, or income allocations. Real local bill-planning records are approved for this prototype. Editing, deletion, bill-candidate import from Sheets, payment status, recurring generation, and funding recommendations remain deferred. Refreshing after saving does not resubmit, but deliberately submitting the same bill again can create a duplicate. Records remain private/local and do not synchronize through Git. Migration `0003_bill_occurrences` adds the bill table without changing income records; back up the local database before upgrading. Downgrading this migration deletes all bill records and is not a recovery method.

## Income Calendar Usage

**Projected income forecast** is available from the upload and income-source pages at `/income/forecast`. It lists saved paydays across all sources from this computer's current date for the selected number of calendar days (today counts as day one). It uses payday overrides before source defaults and totals known amounts in integer cents. Missing amounts are shown and excluded from the known total; zero estimates remain explicit. This read-only view does not infer missing paydays, reconcile deposits, flag overdue income, or calculate spendable money. The default is 90 days; choose any whole number from 1 to 365 and click Update forecast. The selected horizon stays in the page URL as `?days=30`, so it can be bookmarked or refreshed. It is not saved as an account preference. Invalid values show an error instead of a forecast total.

The user has approved real pay dates and expected net amounts in this local planning prototype. This is a limited exception to the original synthetic-only restriction; bank-transaction migration, confirmed funding, deployment, and shared operation remain unapproved. Real local bill-planning records are also explicitly approved. The local SQLite records do not synchronize to another computer. Tests still use synthetic data only.

On a source page, **Default expected take-home pay** sets the projected net amount for every Draft date without an override, including past dates. Set a **Payday override** to change only that occurrence; clearing it restores the default. Blank default means unknown; zero is an explicit zero estimate. Enter dollars without commas, with at most two decimal places. Amounts are stored as integer cents and never count as deposits, balances, or reserved funds. These are editable projections, not immutable historical forecasts; revision history and effective-dated defaults are deferred. No deduction calculation or forecast total is introduced here.

For quick yearly entry, select an income source and click **Select pay dates for [source] for the year**. Choose a year, click the official paydays while viewing your employer calendar alongside the app, and click **Save pay dates**. Blue dates are selected; green dates are already saved. Each batch saves together as Draft and skips dates already stored for that source. This does not remove saved dates or change their optional details. The individual-date form remains available for pay-period details. PDF importing is deferred in favor of manual yearly selection; no PDF dependency is required.

The database provides create/read functions and a browser interface for income sources and **draft** official pay dates. It does not change transaction imports, Google Sheets, account balances, or funding decisions.

After database setup below, run `.\start_app.ps1 -Restart` and select **Draft Income Calendar** on the upload page (http://127.0.0.1:5000/income). Create a synthetic income source, select it, and add official dates with optional pay-period boundaries and a reference. Dates appear chronologically and remain drafts. Validation errors preserve form entries. Successful submissions redirect to a read-only GET, so refreshing the resulting page does not resubmit the form. Deliberately submitting the same values again can still create another record; duplicate review is deferred. Forms use session tokens. Restarting the server may require reopening the form.

With the project virtual environment active, run from the project root:

```powershell
python -m pip install -r .\requirements.txt
python -m alembic upgrade head
python -m alembic current
```

SQLAlchemy defines records and database operations; Alembic records and applies versioned schema changes. `upgrade head` creates the two income-calendar tables and records the migration revision. Running it again preserves existing rows. Importing the Python modules does not create a database or tables.

By default, the database is `instance/development.sqlite3`, resolved from the repository root rather than the terminal's current folder. The ignored `instance/` directory may hold the explicitly approved local pay-calendar, expected-net, and bill-planning records. `DATABASE_URL` can select another development database; check the target before migration and back up existing records. PostgreSQL remains the shared-deployment target; no PostgreSQL service or deployment is introduced here.

The repository functions in `income_repository.py` accept a SQLAlchemy session. Use `database.session_scope(engine)` around an operation: it commits all successful changes together and rolls everything back on failure. Paydays and optional pay-period boundaries are Python `date` values. Created timestamps are stored as UTC without an offset for consistent SQLite storage. Newly created pay dates can only be drafts; they do not represent received deposits. Expected amounts can be edited; editing other record details, deletion, recurring scheduling, and confirmation remain deferred. Source names and source/date pairs are not assumed unique.

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
