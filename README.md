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

## Accounts, Vaults, and Recorded Balances

Open **Manage payment accounts** from Bill planning, or visit `/accounts`. Existing names remain linked to their bills. Add an **Account** or **Vault**, enter its purpose (required for a vault), and optionally record its balance and as-of date. Enter each vault separately; exclude its funds from other account balances so the same money is not counted twice. Blank balance means **Not recorded**, while zero is an explicit balance.

Use **Details / balance history** to rename an entry, change its type/purpose, or record another balance/correction. Enter the full balance, not an amount to add/subtract. Entries remain in history; the newest date wins, with the latest saved entry correcting the same date. Future-dated or negative balances are rejected. Names, purposes, and balances are private local records; they do not transfer on Git pull.

These are manual recorded balances, not bank-synced or available-to-spend amounts. Transfers, protected-fund enforcement, bill set-asides, releases/overrides, import matching, and paycheck funding recommendations come in subsequent slices. Migration `0009_account_balances` preserves existing records and leaves balances unknown; back up before migrating and recover from a verified backup rather than discarding populated balance history with a downgrade.

## Manual Bills and Subscriptions

For regular Bills, choose **Monthly** when adding a new entry, or **Enable monthly bill** beside an existing one. Enter a starting estimate once. The selected 1–365 day forecast generates separate monthly charges without duplicates, using the same original-day/month-end rule as subscriptions. Existing Bills stay one-time until you explicitly enroll them.

Use **Monthly history / confirm amount** to record an accurate amount for a specific billing month, including past months. Confirmed amounts from the previous three calendar months determine that month's future estimate. Available confirmed months are averaged (nearest cent, half up); estimates never count as history, missing months are excluded, and zero counts when explicitly confirmed. With no confirmed history in that window, the starting estimate is used. The list/forecast labels the amount's basis.

Confirming or correcting history updates future unconfirmed estimates in the same transaction. Other confirmed amounts and unconfirmed charges due today or earlier stay unchanged. Confirmation means the amount is accurate, **not that it is paid**. Existing entries remain unconfirmed until reviewed. To reuse a past one-time Bill, explicitly select that same bill/month in the history form; the app does not guess names or merge existing records. Monthly schedule editing/stopping, deletion, and payment tracking are not part of this slice.

Migration `0008_monthly_bills` preserves existing financial fields and starts with no monthly schedules or confirmations. Back up before upgrading; restore a verified backup rather than downgrading a database containing monthly schedules or confirmations.

Choose **One-time**, **Monthly**, or **Yearly** when adding a Subscription. Existing entries stay one-time until you use **Enable recurrence**. Set the amount and first/next due date once, then open the incoming/outgoing forecast and choose 1–365 days. The forecast saves missing active subscription charges within that period without repeating a scheduled date. Monthly dates retain the original day: January 31 becomes February 28 and then March 31; yearly February 29 returns in leap years. Regular Bills support One-time or Monthly, with confirmed-history estimates as described above.

Use **Recurrence settings** for a recurring subscription's amount, schedule, name, account, buffer, and Active/Inactive/Covered status. Changes apply only to charges after today, including those already shown. Older charges, including today's, remain unchanged. Keep the schedule starting date when changing only the amount; enter a new next charge date when resuming on a different schedule. Inactive/Covered stops new separate charges and excludes existing future charges from funding needs without deleting them. No provider cancellation or payment occurs.

Subscriptions paid by you and those covered by someone/something else have separate sections. Covered entries remain visible; enter a label such as **Girlfriend** or **T-Mobile**, optionally linking a saved Bill. No separate login is needed. Outgoing totals include only funding needed for dates in the selected window; earlier unpaid charges remain on Bill planning and are not included in that window's total. Incoming estimates and outgoing obligations remain separate from actual money movement.

Migration `0007_subscription_schedules` adds schedules without enrolling or changing existing financial records. Back up before upgrading. A populated downgrade with schedules/external coverage is refused; recover from a verified backup instead. The forecast now writes missing recurring charge records when opened, while its income calculations remain read-only.

Use **Subscription settings** beside a subscription for **Active**, **Inactive / paused**, or **Covered by another bill**. Status does not cancel or restart a provider service. When pausing or covering an entry, explicitly choose whether its recorded charge is still owed. A real unpaid charge retains its amount and funding deadline. To exclude a placeholder/included charge, choose **No — only a placeholder or included charge** and confirm no separate unpaid amount is owed. The recorded amount/date remain as reference, but funding needed is zero and no deadline is presented as required.

For coverage, enter a person/provider label or select an existing Bill (not another subscription). Its name stays linked if renamed; it cannot be reclassified while it covers subscriptions. A covered entry with no separate unpaid charge shows **Via [bill]** instead of suggesting a separate withdrawal. If an old separate charge is still owed, it remains an obligation even while future service is covered.

Selecting Active requires explicit confirmation of the amount and next charge date. A placeholder reactivates in place. If an inactive/covered occurrence still has a real unpaid charge, the old occurrence remains and a distinct active occurrence is created for a later charge date; repeat confirmation for that same next date is rejected. Confirmation history is stored privately in the database; no history-editing UI is provided. Status forms use consumed session tokens and redirect after saving. No recurring generation, bank payment, cancellation, or automatic reservation occurs.

Migration `0006_subscription_controls` preserves all existing fields, labeling entries Active with their recorded charge still owed. Classification requires your action; no subscription names are guessed. Downgrade preserves old obligation fields but discards status, responsibility, coverage links, and confirmation history, so it is not a recovery method. Verified backups are required before upgrading real records.

Use **Edit** beside an obligation to correct its name, type, amount, due date, funding buffer, or payment account. Saving updates the same ID and creation timestamp, recalculates its funding deadline, and moves it between Bills and Subscriptions when its type changes. Cancel returns without changes. Edit history and deletion are not implemented yet.

**Manage payment accounts** opens `/accounts`, where you can add names you choose and rename them later. Obligations reference an account ID, so renaming updates every linked label. Select an account when adding or editing a bill; **Unassigned** is allowed and clears the reference. Accounts now support manual dated balances and vault purposes as described above; they have no credentials or bank connection. Duplicate names are not automatically merged. Migration `0005_payment_accounts` preserves existing obligations and leaves their account unassigned. Back up before migrating; downgrading removes account records and assignments. Subscription controls are available through Subscription settings, as described above.

Select **Bill** or **Subscription** when adding an occurrence. Both types share the same amounts and funding rules, but appear in separate sections, each ordered by funding deadline. Existing records become Bills under migration `0004_bill_subscription_kind`; no existing amounts, dates, IDs, or buffers are changed. The classification is not a recurring schedule and does not create future occurrences. Reclassification is now available through Edit. Downgrading this migration preserves obligations but removes their type labels.

Open **Bill planning** from the upload page or income forecast, or visit `/bills`. Add one bill name, dollar amount, and due date. An optional funding buffer defaults to **three calendar days before the due date**; zero means the due date itself. Bills are listed by earliest funding deadline, including past dates. Amounts use integer cents; blank amounts are rejected and explicit zero is permitted. No weekend/holiday adjustments are made.

These are individual planning occurrences, not recurring bill templates, reservations, payments, or income allocations. Real local bill-planning records are approved for this prototype. Deletion, bill-candidate import from Sheets, payment status, recurring generation, and funding recommendations remain deferred. Refreshing after saving does not resubmit, but deliberately submitting the same bill again can create a duplicate. Records remain private/local and do not synchronize through Git. Migration `0003_bill_occurrences` adds the bill table without changing income records; back up the local database before upgrading. Downgrading this migration deletes all bill records and is not a recovery method.

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
