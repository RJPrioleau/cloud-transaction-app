# Roadmap

This roadmap records approved project direction and implementation milestones. The importer/refactor baseline is verified through `22d38f3` with 45 tests. The current approved task adds obligation editing and named payment accounts alongside the income calendar and forecast, while preserving that baseline. Older phase entries below retain context; they are not an accurate summary of completed refactoring.

## Current Milestone - Income Calendar Persistence Foundation

- [x] Add approved obligation editing and named payment-account creation/renaming, optional account assignment, identity preservation, and migration/recovery coverage.
- [ ] Next separate slice: subscription inactive/covered behavior, preserving real unpaid obligations and requiring amount/date confirmation on reactivation. Implementation scope still needs approval.

- [x] Add approved Bill/Subscription classification and separate deadline-sorted sections while preserving existing obligations as Bills. Recurrence remains deferred; editing is implemented in the following slice.

- [x] Approved individual manual bill occurrences: exact-cent amounts, due dates, default/override funding buffers, deadline-sorted listing, persistence/migration/recovery tests. Real local bill-planning data approved; recurring schedules, reservations, and payments remain separate future slices.

- [x] Add approved 1–365 day forecast selection, defaulting to 90, with validated URL input and no database changes.

- [x] Add the approved read-only 90-day projected-income view across sources, with exact-cent known totals and explicit unknown amounts. No database migration or received-income behavior.

The approved yearly-selection slice adds a source/year-labeled calendar, batch Draft creation, and skipping already-saved dates. Manual selection replaces PDF importing for the current workflow. Visual browser acceptance remains pending.

Architecture approved: retain Flask and Google Sheets; use SQLAlchemy/Alembic; design toward one central PostgreSQL-backed financial dataset accessed from both computers. The user approved real local pay dates, expected-net projections, and individual bill-planning records as a limited prototype exception to synthetic-only development. Local records do not synchronize. Deployment, purchases, and existing bank-data migration are not approved.

- [x] Add nullable expected-net source defaults and per-payday overrides in integer cents, editable through the source page, with migration preservation and synthetic recovery coverage.

- [x] Define income sources and draft official pay dates with stable IDs and source relationships.
- [x] Add explicit database sessions and an initial Alembic migration; importing modules creates no database.
- [x] Add create/read operations, input validation, database constraints, and whole-operation rollback.
- [x] Verify migrations, repeat upgrades, persistence across reopen, and synthetic backup recovery.
- [x] Run all 45 baseline tests alongside persistence acceptance tests (58 total passing); committed as `ff0b6a5`.
- [x] Approved browser creation/viewing of sources and draft pay dates, with validation and redirect after saving. Interface acceptance tests added; browser visual review remains pending.
- [ ] Test PostgreSQL migrations and transactional behavior before real financial use.

## Approved Development Direction - Dependency Gates

1. Finish this persistence slice, then the small draft calendar interface.
2. Use manual yearly payday selection instead of PDF extraction for now; add occurrence exceptions, recurring schedules, and a configurable 90-day forecast in separately approved slices. Expected money is never treated as received money.
3. Connect the existing importer to shared transaction/account identity before actual-income reconciliation; preserve positive-magnitude Sheets output while retaining explicit bank movement in new records.
4. Add bill candidates/instances, funding deadlines, recommendations, and shortfall views. Bring verified balances and commitment accounting forward before confirming reservations.
5. Add payment attempts, partial payments, autopay tracking, transfers, and risk; bill-payment clearance requires user confirmation even when other matching can be automatic.
6. Complete balance/pending reconciliation, then category budgets and discipline, rollover/closing, manual splits and rule management, and the nightly check-in/dashboard. Each requires a separately approved slice.

Hosting, authentication, backup/recovery, operating costs, and shared deployment require a separate review. The external nightly reminder is not an app integration to rebuild. Detailed business decisions such as matching thresholds, holiday rules, and closing/review policies must be resolved before their respective implementations.

## Phase 0 - Repository Foundation

Status: In progress

- [x] Clone the GitHub repository under `C:\Users\Jaypr\Python-Projects`.
- [x] Confirm the repository is connected to `origin/main`.
- [x] Create a local `.venv` for development.
- [x] Record current runtime dependencies in `requirements.txt`.
- [x] Add reusable AI collaboration documentation.
- [x] Add project roadmap and changelog files.
- [ ] Review and commit the foundation updates after user approval.

## Phase 1 - Legacy App Triage

Status: In progress

Identify the current bugs and pain points before restructuring application code.

- [ ] List known bugs from user experience.
- [ ] Identify which current bugs will become obsolete because of planned features.
- [ ] Confirm the smallest set of fixes needed before restructuring.
- [x] Establish a repeatable local verification command beyond syntax checks.

## Phase 2 - Incremental Restructure

Status: Planned

Restructure the current Flask script into clearer project boundaries while preserving behavior unless a behavior change is explicitly approved.

Candidate boundaries to discuss before implementation:

- Flask routes and web UI
- Transaction parsing
- Categorization rules
- Duplicate detection
- Google Sheets access
- Reporting and logs
- Tests and sample fixtures

## Phase 3 - Feature Planning

Status: Planned

After current problems and restructuring direction are understood, define the next feature set.

- [ ] Capture the user's feature idea.
- [ ] Decide which planned features replace current buggy behavior.
- [ ] Document approved requirements before implementation.
- [ ] Build features as small verified slices.

### Reset TEST - approved slice

- [x] Add a TEST-only reset with explicit confirmation for imported constants in H, I, K, O, and P, rows 69–383.
- [x] Preserve formulas, formatting, live months, and local reports/logs; verify boundaries and confirmation with mocked tests.
- [x] User verification through the local app against TEST; a read-only follow-up confirmed no constant values remain in the reset columns within rows 69–383.
- [ ] Decide how future transaction-section row expansion is represented and how imports are prevented from overflowing into the following section. Current reset deliberately leaves rows below 383 untouched.

## Phase 4 - Budgeting Architecture Design

Status: Planned

After the current characterization-test and legacy-restructure work is complete, revisit the target budgeting architecture before implementing budgeting features. The architecture must account for the difference between the monthly budget view and paycheck-based funding decisions.

Approved future responsibilities to design before implementation:

- Recurring bill templates and period-specific bill instances.
- Pay-calendar import/parsing from employer-provided source files.
- User review, correction, and confirmation of detected pay dates.
- Pay-schedule storage that preserves historical schedules and supports future schedule changes.
- Fund-by date calculation using configurable safety buffers.
- Paycheck-to-bill allocation across calendar-month and calendar-year boundaries.
- Automatic split-funding recommendations across multiple paychecks.
- Manual allocation overrides that preserve the distinction between recommended and user-selected allocations.
- Paycheck-oriented funding views and optional Google Sheets output.

Do not implement these modules during the current characterization-test work. Use the requirements in `docs/PRODUCT.md` when architecture design resumes.

## Parking Lot

These ideas are not approved requirements yet.

- Enhanced budgeting analytics
- Spending trend visualization
- User authentication
- Cloud deployment
- Improved UI/UX
- Budget forecasting tools
