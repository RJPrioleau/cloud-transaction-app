# Product Baseline

## Current Purpose

Cloud Transaction App is a personal financial workflow tool. It imports transaction exports, detects duplicates against a Google Sheets budget workbook, adds new transactions to the selected month sheet, and generates report/log files after each upload.

## Current Workflow

1. The user opens the local Flask app.
2. The user selects a month sheet.
3. The user uploads one or more `.csv` or `.xlsx` bank export files.
4. The app detects the account from the uploaded filename.
5. The app parses transactions, assigns a budget category, and sorts by date.
6. The app checks existing Google Sheets rows for duplicates.
7. The app writes new transactions to the sheet and skips duplicates.
8. The app shows an upload report and writes a CSV report/log locally.

## Current Inputs

- Bank transaction exports in `.csv` or `.xlsx` format.
- Filename text that identifies the account.
- A local Google service account credentials file.
- A Google Sheets budget workbook with month-named worksheets.

## Current Outputs

- New rows written to the selected worksheet.
- A browser report showing added and duplicate transactions.
- Generated CSV report files.
- Generated upload log entries.

## Known Technical Shape

- The app is currently a small Flask application.
- Most route and Google Sheets workflow code lives in `app.py`.
- Transaction parsing and category matching live in `transaction_processor.py`.
- Generated uploads, reports, logs, virtual environments, and credentials are local-only files.

## Open Decisions

- Which current bugs should be fixed before restructuring?
- Which current bugs will be replaced by planned features and should not receive duplicate effort?
- What should the next feature set look like?
- Should category rules remain in Python code, move to a config file, or move into a user-editable interface?
- How should account detection work when filename patterns change?
- What test fixtures can safely represent bank exports without exposing personal data?
- What should the long-term UI look like?

## Non-Goals Until Approved

- Do not add authentication.
- Do not deploy to the cloud.
- Do not redesign the UI.
- Do not introduce a database.
- Do not replace Google Sheets as the destination.
- Do not rewrite the app into another framework.

These may become approved later, but they are not current implementation requirements.
