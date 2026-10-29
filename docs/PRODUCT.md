# Product Baseline

## Current Purpose

Cloud Transaction App is a personal financial workflow tool. It imports transaction exports, detects duplicates against a Google Sheets budget workbook, adds new transactions to the selected month sheet, and generates report/log files after each upload.

The approved product direction expands this importer into a financial planning system, beginning with Pay Calendar and Bill Funding. Expected income, actual bank movement, budget allocations, recommendations, confirmed reservations, and payment/transfer states must remain distinct. The existing importer is preserved during this expansion.

The user clarified the purpose on 2026-10-29: understand how much money is expected to come in and when, and how much is expected to go out and when. The broader direction includes tracking APRs and APYs to help decide where money is best placed. Rate inputs, calculations, comparisons, and recommendation behavior are not yet defined or approved for implementation. Separate user logins are outside the product scope; shared hosting access protection remains a separate deployment decision.

## Approved Next Slice - Manual Balances, Vaults, And Confirmed Set-Asides

Product baseline and implementation approach approved on 2026-10-29. The user narrowed today's implementation to account/vault names, types, purposes, and manual dated balances, then requested a commit/push and continuation next session. Transfers, set-asides, releases, overrides, and availability calculations remain approved unfinished foundation work. The user explicitly approved entering real local balances/vault planning records within the existing single-machine prototype. This does not approve bank connectivity, shared deployment, or production readiness.

- Enter dated balances for named accounts and vaults. Vault balances are separate from the other account balances: moving money into a vault removes it from the other balance. Do not assume the bank's main account balance includes vault funds. Account renaming must retain financial links and history. The user mentioned a possible bank limit of ten vaults but did not establish that as an app requirement.
- Record each vault's intended purpose (for example savings or a specific bill) and protect its money from unrelated funding recommendations. Money dedicated to a bill can cover that bill without being treated as generally available. The user can explicitly override protection and move money elsewhere.
- Record confirmed transfers with From, To, Amount, and Date. These record user actions; the app never initiates bank transfers. Preserve action history and prevent replay/double counting.
- Allow setting aside part of an account balance for a specific bill without transferring funds. This reduces generally available money, not the account's recorded balance. Explicit releases or overrides are supported; do not count the same money as both available and protected.
- Recommendations alone never reserve funds or make money unavailable. Only user-confirmed transfers/set-asides change recorded balances or commitments. Actual account movement and an in-account commitment remain distinct. Preserve the ability to use already-on-hand money before the next expected income date.
- Display recorded balance, protected/set-aside money, and generally available money distinctly; expected income and funding recommendations are not actual balances. No importer/bank reconciliation, payment clearance, automatic allocation, login, or APR/APY implementation is included in this foundation.

Approved implementation direction: retain account IDs and renaming; add account/vault type and purpose; preserve dated balance/correction history; record transfers atomically across both accounts; store commitments separately from balances; distinguish recorded/protected/available money without double subtraction; require confirmed protected-fund overrides; reject actions exceeding recorded funds. Use integer cents, consumed form tokens, transaction rollback, and verified backup/migration preservation. No new dependencies. The detailed transfer/commitment storage and UI remain to be designed within that approved direction.

### Implemented Account/Vault Setup Slice

`PaymentAccount` adds `kind` (account/vault) and optional purpose, required for a vault. Existing accounts retain identity/name/creation time and remain ordinary accounts with unknown balances until explicitly configured. `AccountBalance` records absolute nonnegative integer-cent amounts with as-of date, optional note, stable per-entry integer ID, and UTC creation time. No balance entry means unknown, not zero. Each vault's balance is separate; the app never adds it to a parent account's balance. Balance records are manual snapshots, not transfers, income, debits, or available-to-spend figures.

`/accounts` lists names, type, purpose, newest recorded balance/date, and detail links; creation can include an optional confirmed balance. `/accounts/<id>` edits details and records confirmed balances/corrections with visible history. The newest as-of date determines the displayed balance; the latest saved entry on that date wins. Backdating preserves later-date balances. Future-dated balances and invalid/negative amounts are rejected. Corrections append entries; no edit/delete history UI. Successful account forms consume their token and redirect, preventing ordinary replay. Existing bill/schedule links remain by ID when renamed or labeled as a vault.

Migration `0009_account_balances` preserves every prior field and relationship, adds no real balances, and infers no vaults or purposes. A populated downgrade with vault/purpose/balance data is refused; restore a verified backup. Vault-purpose labels are recorded now, but purpose protection, commitments, transfer recording, available-to-spend calculations, and import reconciliation are not implemented yet. Local records and backups remain ignored and do not synchronize through Git. A Certificate of Deposit is entered as an Account with a descriptive purpose. Periodic contributions saved toward annual dues are transfers/set-asides for later implementation, not additional subscription charges; the subscription represents the actual annual payment. CD maturity, APY, and withdrawal restrictions are not modeled, and no current balance is claimed as available for bills.

### Agreed Direction For Subsequent Slices

These are requirements discovered during funding-preview discussion, not authorization to implement them in the manual-balance foundation:

- A funding preview considers all saved expected income sources and the selected forecast horizon (90 days by default). Recommend funding before each obligation's funding deadline while aiming for roughly equal dollar amounts left per paycheck, rather than equal percentages or placing every bill entirely on the last payday. The user values month-to-month consistency, but timing, annual charges, and changed obligations/income can affect the recommendation. No smoothing algorithm or guarantee is approved yet.
- Current expected pay is the user's reliable base-pay estimate. Do not infer overtime or per diem in projections. The user expects actual imported deposits eventually to supply the full received amount, including overtime; linking actual deposits to projected paydays is not implemented. Per diem will be added when its schedule becomes reliable and the user chooses how to enter it. Expected and received income must remain distinct.
- Obligations needing funding before the next expected payday must use eligible money already on hand, rather than be assigned to income that arrives too late. Protected-purpose funds require the appropriate purpose or an explicit override; insufficient money must not be hidden by assumed balances or future income.
- Recognize transfers from bank CSV evidence and suggest matches to manually recorded moves for user confirmation. An accepted match represents the same move and must not update balances twice. Examples supplied in screenshots include To Savings with an account suffix and To/From a named Vault, together with transaction date, signed amount, and Posted status. These are observed examples, not a complete approved parsing/matching contract. Do not commit screenshots or real transaction data.
- Roundups use a saved default destination vault, currently the user's 52-week plan vault. Reassigning the default requires an effective date, preserves recorded history, and routes older files imported later according to transaction date. No per-import destination confirmation is required by default. Destination identity must survive renaming. Imported roundup handling must preserve the existing Sheets category behavior unless separately changed.

## Monthly Bills With Historical Estimates

Product baseline, implementation approach, and implementation commit approved on 2026-10-29. Automated tests and live-response checks passed; explicit user visual acceptance is not yet recorded. This supersedes the earlier deferral of recurring regular Bills.

- Enter a Bill once with a starting estimate and monthly due date; one-time Bills remain supported. Existing entries stay one-time until explicitly enrolled.
- Generate separate monthly charge occurrences within the selected 1–365 day forecast window without duplicate generation. Preserve earlier charges, including unpaid obligations. Use the original day-of-month anchor, clipping to month end only when necessary and returning to the original day in later months.
- Estimate each target month's amount from explicitly confirmed amounts for that same bill in its previous three calendar months. Use only available confirmed months in that window; if none exist, use the manually entered starting estimate. Do not use estimates as history and do not distinguish fixed versus variable bills.
- Allow the user to enter and confirm the accurate amount for an individual month. Existing amounts remain unconfirmed until explicitly reviewed; do not infer confirmation from prior entry, dates, imports, or payment-account assignment.
- When confirmed history changes, recalculate future unconfirmed estimates, including already-generated future charges. Preserve other confirmed amounts; do not automatically rewrite unconfirmed charges due today or earlier.
- Confirmation means the monthly amount is accurate, not that the charge is paid. No payment reconciliation, bank movement, recurring subscription repricing, APR/APY logic, deletion, or separate-user login is introduced by this slice.

`BillSchedule` stores a stable identity, name, original date anchor, manual starting estimate in integer cents, buffer, optional account, and UTC creation time. `BillOccurrence` links to the schedule and a canonical billing month; a database uniqueness constraint permits only one charge per schedule/month. Confirmation uses a nullable UTC timestamp and amount-basis metadata; migration `0008_monthly_bills` leaves all old fields unchanged, new metadata null, and existing bills unenrolled/unconfirmed. Schedule/date rules are shared with subscriptions through `recurring_dates.py`; `monthly_bill_repository.py` handles enrollment, exact-cent estimates, generation, confirmation, and recalculation.

The average uses only confirmed months in the preceding three calendar months for that same schedule, excluding estimates, other bills, and older confirmed amounts. Missing months do not count as zero; explicitly confirmed zero does count. Integer arithmetic rounds the average to the nearest cent, half up. Basis labels distinguish starting estimate, available history (one/two months), three-month average, and confirmed amount. No separate fixed/variable flag is used.

`/bills/<id>/monthly` enables recurrence or displays monthly history and accepts explicit confirmations/corrections, protected by a consumed session token and redirect after save. Users can add a past month's amount or explicitly link an unassigned existing regular Bill from that month; names are never automatically matched. Linking preserves the existing ID, creation time, and due date. If the month already has another charge, linking is rejected instead of merging/deleting records. Confirming an existing scheduled month updates that record. Confirmed-history writes and all future unconfirmed estimate updates commit/roll back together; estimates due today or earlier stay unchanged. A future explicitly confirmed amount can contribute to later months, but never its own month. Confirmation can be corrected explicitly; no revision-history or undo UI is introduced.

New Bill entry accepts One-time or Monthly; Subscriptions retain Monthly/Yearly behavior. The outgoing forecast generates missing monthly bill charges inside the existing selected horizon; shrinking/reopening it does not delete or duplicate records. `/bills` and the forecast display amount basis, and linked charges direct users to Monthly history rather than generic editing. Monthly schedule anchor/name/account/buffer editing, stopping schedules, deletion, payment status, and merging duplicate records remain outside this slice. A populated downgrade with bill schedules or confirmations is refused; recovery is from a verified backup. No new dependency or importer change is introduced.

## Recurring Subscriptions And External Coverage

Approved, implemented, and visually accepted by the user on 2026-10-29. These requirements supersede earlier subscription-recurrence deferrals and the requirement that every covered subscription link to a saved Bill.

- Enter a subscription once with its amount, next due date, and Monthly or Yearly recurrence. Existing subscriptions remain one-time until the user explicitly enables recurrence; do not infer schedules.
- Show future charges within the selected forecast horizon, up to the existing 365-day limit. Reopening or expanding the forecast must not duplicate charges. Keep individual charge occurrences separate and preserve older unpaid charges.
- For missing calendar days, use the month's last valid day while retaining the original schedule anchor: January 31, February 28, March 31. A yearly February 29 charge uses February 28 in non-leap years and returns to February 29 in leap years.
- Amount changes apply to all charges after today, including upcoming charges already shown. Charges due today or earlier remain unchanged.
- Inactive or Covered stops future separate charges and excludes already-shown charges after today from funding needs. Charges due today or earlier remain unchanged. Covered subscriptions remain visible even when no separate funding is needed.
- Present separate subscription sections for subscriptions paid by the user and subscriptions covered by someone or something else. External coverage accepts a descriptive label such as Girlfriend or T-Mobile without requiring a saved Bill link; existing saved-Bill coverage remains supported. This is coverage attribution, not a separate-user/login feature.
- Recurring regular Bills, payment tracking/reconciliation, and separate user logins are outside this slice. APR/APY functionality requires later requirements discovery. Subscription changes do not cancel provider services or initiate payments.

The user approved separate schedules and charges, idempotent generation within the selected horizon, and extending the forecast to outgoing planning. `SubscriptionSchedule` stores the original anchor date, monthly/yearly frequency, amount in cents, status, buffer, optional account, and optional covering Bill/external label. `BillOccurrence.subscription_schedule_id` links distinct saved charges; a database uniqueness constraint on schedule/date prevents duplicate generation. Existing rows remain unlinked until explicitly opted in. `subscription_repository.py` owns anchored calendar calculations, schedule changes, charge generation, and outgoing totals. Recurrence settings at `/bills/<id>/recurrence` require confirmation and session-token validation; successful submissions consume the token and redirect. General editing/status operations reject linked charges, directing users to future-only schedule settings. Schedule before/after snapshots are stored transactionally in `SubscriptionChange`.

`/income/forecast` retains the existing income calculations and 1–365 inclusive-day horizon, and now shows outgoing obligations in a separate table/total. Loading it materializes missing Active subscription charges within that window; it is no longer a wholly read-only endpoint. Shortening the horizon does not delete saved charges. Charges outside the window are excluded from its total; past unpaid charges remain visible on `/bills`. Non-active schedules do not generate new charges, but remain visible in subscription summary sections, including external coverage without a Bill link. Future previously generated rows remain as reference with zero funding need; changing the schedule anchor also retires future dates no longer on that schedule. Schedule changes preserve all charges due today or earlier. These amounts are projections, not balances, received funds, completed payments, or spendable money.

Migration `0007_subscription_schedules` preserves all prior obligation/history fields and starts with no schedules. Populated downgrade with schedules/external labels is refused rather than discarding their meaning; restore a verified backup instead. SQLite migration table rebuilds run in an explicit transaction with foreign-key enforcement temporarily disabled only on that migration connection and all references checked before commit; application connections retain enforcement. PostgreSQL integration/concurrency and shared deployment remain unverified. No new dependencies are introduced.

## Approved Architecture And First Persistence Slice

- One centrally hosted Flask application backed by PostgreSQL is the approved target for a shared desktop/Surface financial dataset. Neither computer should maintain an independently writable authoritative financial copy. SQLAlchemy and Alembic are approved for persistence and schema migrations.
- The user explicitly approved real pay dates, expected take-home amounts, and individual bill-planning records in the local SQLite planning prototype on 2026-10-27, overriding the original synthetic-only boundary for these records. This is a temporary single-machine prototype, not independently writable shared financial copies. `DATABASE_URL` selects storage; the default is ignored `instance/development.sqlite3`. No hosting, service purchase, PostgreSQL deployment, or migration of existing bank transactions is approved.
- The first implemented foundation is separate from Flask routes and importing: `database.py` manages explicit connections, transactions, and SQLite development backups; `income_models.py` defines records; `income_repository.py` supplies create/read operations; `migrations/` owns schema changes. Module imports never initialize tables.
- `IncomeSource` stores a stable ID, name, creation timestamp, and nullable default expected net pay in integer cents. `OfficialPayDate` stores a stable ID, source foreign key, official payday, optional pay-period boundaries/source reference, creation timestamp, draft status, and nullable expected-net override in cents. Nonnegative amounts are database-constrained. An override takes precedence, including zero; null inherits the default. A missing default is unknown. Changing the default changes all unoverridden Draft projections, including past dates; immutable forecast snapshots and effective-dated changes remain deferred. UTC creation timestamps are stored without an offset. These records are projections, never actual receipts, balances, or reservations.
- Names and calendar values are validated. Foreign keys and draft/period-order constraints are enforced by the database. Operations commit or roll back as a unit. Source names and source/date pairs are not automatically merged or assumed unique; input idempotency and duplicate review remain for the interface design. Expected amounts can now be edited; other record editing, deletion, historical revision tracking, recurring generation, and calendar-file extraction remain deferred.
- Migrations and backup/restore are exercised against temporary synthetic SQLite databases. PostgreSQL integration, concurrency behavior, authentication, production recovery, and shared deployment still require their own implementation/verification before real financial use.
- The approved draft interface lives in `income_routes.py` and `templates/income_calendar.html`, registered with the existing Flask application. Users create/list sources and add/view official pay dates, optional pay-period boundaries, and references. Successful submissions redirect before displaying records, avoiding refresh resubmission. Session tokens protect forms, and validation failures retain entries. The individual-date form does not deduplicate explicit repeat submissions; yearly selection skips saved dates. Expected amounts can be edited; other editing, deletion, recurring generation, and forecast calculations remain deferred. Database access is lazy and limited to calendar requests; no schema is automatically created.

## Current Workflow

### Approved manual bill-planning slice

The approved subscription-control slice adds `subscription_state` (active/inactive/covered), explicit `charge_is_owed`, and nullable `covered_by_bill_id` to individual obligation occurrences. Existing rows remain Active/owed without altering prior fields. When a covering Bill link is supplied, its target must be an existing regular Bill; a descriptive external label can be used without a Bill link. Self-coverage and subscription targets are rejected, and a covering Bill cannot be reclassified until its links are removed. Database constraints and foreign keys enforce valid state/link combinations. Both inactive and covered entries remain visible. Non-owed entries show their amount/date as reference with zero funding need and no required deadline. A genuine unpaid charge remains owed regardless of service state. No statuses initiate/cancel payments or provider services.

`set_subscription_state` validates explicit responsibility and requires confirmation before excluding a reference-only charge. Activation requires confirmed amount/date. An inactive/covered entry with an unpaid occurrence retains it unchanged and creates a new Active occurrence for a later date; duplicate reactivation of that same date is rejected. Otherwise it activates in place. `SubscriptionChange` stores before/after JSON snapshots and UTC timestamps in the same transaction; history has no edit/delete UI. These are local confirmations, not authenticated multi-user audit claims. The UI is `/bills/<id>/subscription`, with a consumed session token and redirect after saving. Funding calculations must use `funding_needed_cents`, not blindly total recorded reference amounts. No recurring templates or payment reconciliation are introduced.

The approved editing/account slice adds named `PaymentAccount` records with stable ID and UTC creation timestamp, create/rename operations at `/accounts`, and an optional account foreign key on each obligation. Deletion is restricted by the database. Renaming updates linked labels without changing bill references. Account names are user-defined; no bank numbers, balances, connection, or automatic importer-account matching is introduced. `bill_models.py` and `account_models.py` share the existing SQLAlchemy metadata. Migration `0005_payment_accounts` preserves all existing obligation fields and starts them unassigned. Existing bills/subscriptions can now be edited (name, type, amount, date, buffer, and account) through `/bills/<id>/edit`, retaining identity and creation time. Invalid changes roll back; successful edits redirect to the list. Edit history, deletion, concurrency conflict handling, and account deletion remain deferred.

Subscription lifecycle requirements implemented in the subsequent control slice: inactive subscriptions remain listed and do not generate future funding needs; a placeholder date is not a real unpaid charge. Genuine unpaid charges remain owed. Subscriptions included in another bill (for example Netflix through T-Mobile) should remain visible without double allocation. Reactivation must require confirmation of the amount and next charge date. The controls are separate from general editing so charge-responsibility decisions require explicit confirmation. Annual subscriptions currently record the full renewal amount and date; monthly set-aside tracking is also deferred.

The user approved tracking subscriptions as the same obligation records in a separate page section. `BillOccurrence.kind` is constrained to `bill` or `subscription`, defaulting to `bill`. Migration `0004_bill_subscription_kind` labels existing obligations as Bills without changing any prior field. The entry form accepts either type; separate Bills and Subscriptions sections each retain funding-deadline order. All calculations, integer-cent handling, and default/override funding buffers are shared. Reclassification is now available through editing; recurring schedules, reservations, and payment behavior remain deferred. Subscription planning is within the approved local prototype scope.

The user approved storing real local bill-planning records on 2026-10-27. `BillOccurrence` in `bill_models.py` represents one named obligation with integer-cent amount, due date, funding buffer (default three calendar days), stable ID, and UTC creation timestamp. `bill_repository.py` validates creation and sorts by calculated funding deadline. `bill_routes.py` and `templates/bills.html` supply manual creation/listing at `/bills`. No new dependency is introduced. Migration `0003_bill_occurrences` adds only its table and preserves existing income data.

Zero amounts and zero-day buffers are explicit allowed values; blank amounts are rejected. Funding deadlines use calendar days without holiday/weekend adjustment and cannot precede the supported calendar. This slice has no recurring defaults, deletion, payment lifecycle, confirmed reservations, funding allocation, or Sheets bill import. Past obligations remain visible. Refresh after save does not repeat a submission; explicit repeated bill submissions are not deduplicated. Bill records now reference optional named payment accounts, but are not connected to imported transaction identity or account balances. Local data does not synchronize across machines.

The approved read-only income forecast at `/income/forecast` shows saved paydays across all sources, sorted chronologically, for a selectable 1–365 day horizon (90 by default). Today is day one; the last included date is today + horizon - 1. The selection is a validated URL parameter, not a stored preference. The current date comes from the local computer. Expected net uses individual overrides before source defaults; known amounts are summed in integer cents. Unknown amounts are explicitly counted and excluded from the known total; zero is distinct from unknown. Empty periods display an empty state. It neither writes records nor represents deposits, balances, or funds available. Missing calendar dates, overdue deposits, reconciliation, and recurring generation remain deferred.

1. The user opens the local Flask app.
2. The user selects a month sheet.
3. The user uploads one or more `.csv` or `.xlsx` bank export files.
4. The app detects the account from the uploaded filename.
5. The app parses transactions, assigns a budget category, and sorts by date.
6. The app checks existing Google Sheets rows for duplicates.
7. The app writes new transactions to the sheet and skips duplicates.
8. The app shows an upload report and writes a CSV report/log locally.

### Amount And Month Conventions

- Descriptions beginning with `Roundup ` map to the workbook category `Round up Transfer`, whose savings-summary entry is at row 44 in the current template. The existing summary formula totals matching imported amounts; the app does not write directly into that summary cell. Existing imported categories are not automatically updated when rules change.
- Imported amounts intentionally use positive magnitudes. Category-based budget treatment determines whether a transaction contributes as income or expense; preserving the source bank's amount sign is not the current import contract.
- The report's amount totals sum transaction magnitudes and may combine income and expenses. They are not spending-only totals or signed net cash flow.
- The selected worksheet is the import destination, not a date filter. The user normally exports the current month's transactions before uploading. A cross-month export is imported in full to the selected worksheet; the past-30-days export used for TEST was intentional.
- A manual source-file audit on 2026-10-26 confirmed that all 295 rows in the tested export matched the initial upload report after the intended absolute-value conversion, with no omitted or extra rows and no cent-rounding discrepancies. A repeat upload produced 295 duplicates and no additions. This verifies the tested export, not every possible bank format.

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

### Report Columns

- The browser report includes a read-only, expandable MISC Review grouped by exact parsed description, with separate added/duplicate counts and decimal totals. Case differences remain distinct; description text is escaped for display. Only transactions assigned exactly `MISC` appear. No rules are inferred or changed, and no worksheet data is modified by this view.
- The browser report includes an alphabetically ordered Budget Name Summary above the detailed tables. Each category shows separate added/duplicate counts and amount totals, calculated with decimal arithmetic. Empty uploads show a no-transactions message. Totals use transaction magnitudes and are not spending-only totals.
- New CSV reports use `Status`, `Date`, `Amount`, `Account`, `Description`, and `Budget Name`, in that order. Browser report tables show the same transaction fields, with added/duplicate status represented by separate sections.
- `Budget Name` shows the category assigned while parsing this upload, including for skipped duplicates. It does not read back or change an existing worksheet row's category. Reports generated before this column was added retain their original contents.

## Reset TEST

- The upload page links to a separate Reset TEST confirmation page. A confirmed POST with a one-use session token clears constant values only in H, I, K, O, and P, rows 69–383, on the worksheet named exactly `TEST`.
- Formula cells, formatting, headings, other columns and rows, live-month worksheets, and local reports/logs are preserved. Missing/invalid confirmation never connects to Sheets. An empty section requires no clear request.
- The current template's imported section ends at row 383; row 384 contains the Total Transactions heading and formula. Reset leaves that total row and all lower rows untouched. Old overflow entries below the total row were cleared manually before the fresh TEST verification. The upload writer currently does not enforce the section's ending row.
- Future use may require adding transaction rows at the bottom of the imported section. How the app discovers and enforces an expanded section boundary remains an open decision; this reset does not assume all lower worksheet rows are safe to clear.

## Known Technical Shape

- The app is currently a small Flask application.
- Flask routes and upload workflow coordination live in `app.py`.
- `start_app.ps1` manages the local-only `local_server.py` process on 127.0.0.1:5000. It checks the running source fingerprint, supports restart/status/stop, and leaves unrelated processes untouched. The launcher-only status route reports the startup version; credentials, uploads, and logs are excluded from the fingerprint. Local server binding is exclusive on Windows to prevent overlapping listeners. The batch launcher uses the same restart workflow; direct `python app.py` remains a separate manual entry point.
- The home-page upload form and styling live in `templates/upload.html`; the results-page layout, styling, summary totals, and download link live in `templates/report.html`. Missing-credentials and general upload-error pages live in `templates/missing_credentials.html` and `templates/upload_error.html`. Flask renders these templates. The report and error templates deliberately preserve legacy unescaped rendering during extraction; transaction-table HTML still comes from `upload_report.py`. Validation responses remain plain text.
- Transaction parsing and category matching live in `transaction_processor.py`.
- Uploaded-file validation, safe filename storage, account detection, parser calls, and combined date sorting live in `upload_processing.py`. Its helper returns transactions plus an optional validation message; storage/parser exceptions propagate to the route. The route handles missing file selection and creates output folders. Files are still saved before account detection, and earlier saved uploads remain if a later file fails validation.
- Google authentication, worksheet selection, and worksheet import orchestration live in `budget_sheet.py`: it checks duplicates against rows starting at row 69, finds the first empty transaction row from the same fetched values without per-cell network reads, writes new transactions to columns H, I, K, O, and P, and returns added and duplicate lists. Duplicate-only imports skip the destination-row search and worksheet write. The route supplies the credentials path, workbook name, and month, and handles the missing-credentials response.
- Report row/HTML construction, CSV report writing, and upload-log appending live in `upload_report.py`. The Flask route chooses file paths and supplies report data and log rows to the writers. The log writer adds a header when the log file does not yet exist.
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
- Real local pay dates, expected-net projections, and individual bill-planning records are explicitly approved. Other real financial workflows remain gated on PostgreSQL migration/recovery, access controls, shared-operation verification, and user approval. Local planning data must not be treated as synchronized across computers.
- Do not replace Google Sheets as the destination.
- Do not rewrite the app into another framework.

These may become approved later, but they are not current implementation requirements.

## Approved Future Budgeting Requirements

These requirements remain inputs for incremental financial-system development. The shared-dataset architecture and initial income-calendar persistence are approved; later financial services require separately scoped milestones. The broader product vision also includes income reconciliation, bill/payment lifecycles, transfers, balances, pending activity, category budgets, month-end closing, manual splits, rule management, and nightly check-in; this first persistence slice does not implement those services.

### Pay Calendar And Pay Schedule

The budgeting system must not assume income arrives on fixed calendar dates such as the 1st and 15th. It must eventually model actual confirmed pay dates because employer pay schedules can move through the calendar while bill due dates remain relatively fixed.

The current approved workflow is manual selection on one yearly calendar labeled with the income source and year, such as "Select pay dates for WSP — 2026". Selected dates save together as Draft; dates already stored for that source are marked and skipped. This route checks for existing dates within its transaction; concurrent multi-writer uniqueness is not yet guaranteed and must be addressed before shared deployment. The individual-date form remains available and does not deduplicate repeated entries. No schema changes or new dependencies are needed. PDF extraction is deferred. Future source-file import may be reconsidered; the app must not hard-code one employer's payroll schedule into Python.

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
