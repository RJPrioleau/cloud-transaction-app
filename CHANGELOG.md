# Changelog

## Unreleased

- Added a read-only 90-day projected-income page across saved income sources. Uses per-payday overrides before defaults, lists dates chronologically, totals known amounts in integer cents, and flags missing amounts. No database migration or actual-income/balance changes.

- Added expected take-home pay defaults and per-payday overrides, stored as integer cents with nonnegative constraints. Blank amounts mean unknown/inherit; zero is explicit. Added amount forms, projected displays, migration preservation, validation, and backup recovery tests. User approved real local pay-calendar/expected-net planning data; shared deployment and other financial workflows remain gated.

- Added a yearly payday selector labeled with the income source and year. Users click dates and save them together as Draft; saved dates are marked and skipped on repeated submission. Includes leap-year, validation, persistence, source-isolation, and batch-rollback coverage. PDF calendar importing is deferred.

- Added the synthetic-data Draft Income Calendar interface: create/list sources, add/view chronological draft dates, optional periods/references, validation, session form tokens, and redirect-after-save behavior. Database access occurs only on calendar requests; importer behavior is preserved.

- Added the synthetic-development income-calendar persistence foundation using SQLAlchemy/Alembic: income sources, draft official pay dates, create/read operations, validation, database constraints, transaction rollback, and SQLite backup/recovery tests. Existing importer and Flask routes remain unchanged.
- Added an expandable MISC review in browser reports, grouped by exact description with separate added/duplicate counts and decimal totals; no automatic category changes.
- Added a browser Budget Name summary with separate added and duplicate counts and decimal amount totals above the detailed transaction tables.
- Added `Budget Name` to newly generated browser and CSV transaction reports for both added and duplicate entries; existing report files remain unchanged.
- Added a managed local start/restart/status/stop workflow with an exclusive localhost listener and startup source fingerprint, avoiding stale overlapping app processes. Updated the batch launcher to use it.
- Categorized descriptions beginning with `Roundup ` as `Round up Transfer`, matching the savings-summary label instead of falling back to `MISC`.
- Fixed upload read-quota exhaustion by finding the destination row from already-fetched worksheet values, eliminating per-cell reads and skipping the search for duplicate-only uploads.
- Added a confirmed TEST-only reset for imported constant values in H/I/K/O/P rows 69–383, preserving formulas, formatting, and other workbook content. Added boundary, live-month rejection, and one-use confirmation tests.
- Extracted missing-credentials and general upload-error pages into templates, preserving messages, return links, HTTP status codes, and legacy escaping behavior.
- Moved the results-page layout into `templates/report.html`, preserving summary formatting, transaction HTML, download links, styling, and legacy escaping behavior.
- Moved the home-page upload form into `templates/upload.html`, preserving its content, styling, and default month selection.
- Moved Google service-account authentication and workbook/month selection into `budget_sheet.py`; the Flask route retains configuration and its missing-credentials response.
- Extracted uploaded-file processing into `upload_processing.py`, preserving validation messages, file-save order, account detection, and combined transaction sorting.
- Consolidated worksheet duplicate checking and transaction writes in `budget_sheet.py`, preserving the row-69 start and writable columns.
- Moved upload-log file appending into `upload_report.py`, preserving existing entries and the header-on-file-creation behavior.
- Moved CSV report file writing into `upload_report.py`, preserving UTF-8 encoding, CSV formatting, and overwrite behavior; verified with report-file and upload-route tests.
- Added initial transaction processor characterization tests for CSV and XLSX parsing.
- Added project collaboration instructions and continuity workflow.
- Added roadmap for legacy triage, incremental restructuring, and later feature planning.
- Added a product baseline document for current behavior and open decisions.
- Documented future pay-calendar and paycheck-allocation requirements for later budgeting architecture design.
- Updated setup documentation to match the newer project workflow.

## 2026-09-29

- Stabilized transaction upload workflow in commit `45b66c0`.
- Cloned the GitHub-backed repository into the standard `Python-Projects` workspace.
