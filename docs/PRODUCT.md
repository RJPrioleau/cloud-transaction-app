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
- During budgeting architecture design, which payroll/allocation records belong in application storage and which should be synchronized or displayed in Google Sheets?

## Non-Goals Until Approved

- Do not add authentication.
- Do not deploy to the cloud.
- Do not redesign the UI.
- Do not introduce a database.
- Do not replace Google Sheets as the destination.
- Do not rewrite the app into another framework.

These may become approved later, but they are not current implementation requirements.

## Approved Future Budgeting Requirements

These requirements are approved inputs for future budgeting architecture design. They must not interrupt the current characterization-test work, and they should not be implemented until the budgeting/refactoring architecture has been revisited and approved.

### Pay Calendar And Pay Schedule

The budgeting system must not assume income arrives on fixed calendar dates such as the 1st and 15th. It must eventually model actual confirmed pay dates because employer pay schedules can move through the calendar while bill due dates remain relatively fixed.

The app should support importing employer-provided pay calendars from practical source formats such as PDF, XLSX, CSV, or other formats considered later. The app must not hard-code one employer's payroll schedule into Python.

Imported calendar data should follow this conceptual flow:

```text
Employer Pay Calendar
    -> Import / extraction
    -> Detected pay periods and pay dates
    -> User review
    -> User confirmation
    -> Confirmed Pay Schedule
    -> Budget / paycheck allocation engine
```

Detected pay dates must not automatically become trusted budgeting data. The user must be able to review detected dates, correct them, and confirm the schedule before it becomes active for budgeting calculations.

The future pay schedule model should leave room for:

- Pay date.
- Pay-period start and end dates, when available.
- Expected or guaranteed pay amount.
- Actual pay amount when known.
- Confirmation status.
- Source calendar reference.
- Notes or manual corrections.

The architecture must support different schedules in different years without rewriting historical schedules. If employment or pay frequency changes, a new future schedule should be able to replace future planning data without changing historical payroll records.

### Paycheck-To-Bill Allocation

The monthly budget answers: "What do I owe or plan to spend?"

The paycheck allocation system answers: "Which money should pay for it, and when should I reserve that money?"

The allocation engine should use actual confirmed pay dates to determine which paycheck or paychecks should fund upcoming bills and recurring obligations. Allocation must be based on timing rather than only the calendar month in which a bill appears.

Calendar-month boundaries must not limit the calculation. For example, a bill due June 1 may need to be funded by a paycheck received in May. The allocation logic must also work across calendar-year boundaries.

The allocation engine should operate on period-specific bill instances rather than changing recurring bill templates:

```text
Recurring Template
    -> Monthly Bill Instance
    -> Due Date / Fund-By Date
    -> Applicable Paychecks
    -> Recommended Allocation
    -> Optional Manual Override
```

Changing a paycheck allocation must not modify the recurring bill template.

### Fund-By Dates And Safety Buffer

The architecture should support a configurable funding safety buffer. Instead of treating the due date as the last acceptable funding date, the system may calculate:

```text
Fund-By Date = Due Date - Safety Buffer
```

For example, a bill due June 1 with a 3-day safety buffer has a fund-by date of May 29. The allocation engine should ensure enough money is reserved by the fund-by date.

The safety buffer must be configurable rather than hard-coded.

### Automatic Split Funding And Overrides

Automatic split funding is a desired feature. The system should be capable of recommending that a bill be funded gradually across multiple applicable paychecks instead of always assigning the full amount to the paycheck immediately before the due date.

The allocation strategy should eventually consider:

- Bill amount.
- Bill due date and fund-by date.
- Available paychecks before the deadline.
- Other obligations assigned to those paychecks.
- Expected available income.
- Existing money already reserved toward the bill.

Do not assume an equal split is always the best algorithm. Propose the allocation strategy during architecture design.

Automatic allocation is a recommendation/default, not a mandatory allocation. The user must be able to override the recommended split, including assigning all funding to one paycheck or manually distributing funding across multiple paychecks.

The system should preserve the distinction between recommended allocation and manual allocation when practical. The architecture should leave room for allocation modes such as Auto, One Paycheck, Split Across Paychecks, and Manual. Exact UI details remain a later design decision.

### Paycheck Funding View

The app should eventually provide a view organized around paychecks rather than only calendar months. For each upcoming paycheck, the user should be able to see:

- Pay date.
- Expected paycheck amount.
- Bills and obligations funded from that paycheck.
- Amount reserved toward each obligation.
- Total amount that must be reserved.
- Remaining money after required reserves.

This view should make it immediately clear what money from each paycheck is already committed.

Biweekly payroll schedules that create three-paycheck calendar months must be handled correctly. A third paycheck must not automatically be treated as extra money. The allocation engine should first look ahead to upcoming obligations and determine whether that paycheck needs to fund future bills. Only money remaining after required reserves should be treated as available for savings, debt payments, sinking funds, discretionary spending, or other financial goals.

### Google Sheets Boundary

Do not assume the employer pay calendar itself must be embedded in the existing Google Sheets workbook.

Preferred architectural direction:

- Python/Flask application: pay-calendar import, review/confirmation, pay-schedule management, paycheck-allocation calculations, and paycheck-oriented funding views.
- Google Sheets: financial storage/reporting where useful, optional output of resulting allocations, and optional budget/dashboard integration.

During architecture design, decide what payroll and allocation data belongs in application storage versus what should be synchronized or displayed in Google Sheets.

### Historical Integrity

Historical payroll schedules, bill instances, recommendations, and manual allocations should remain historically accurate.

Future changes to employer payroll schedules, recurring bill amounts, recurring due dates, allocation strategy, or safety-buffer settings must not silently rewrite completed historical periods.

The architecture must distinguish between historical records and future planning defaults.
