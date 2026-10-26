# Changelog

## Unreleased

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
