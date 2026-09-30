# Roadmap

This roadmap records approved project direction and implementation milestones. The current priority is to stabilize the legacy app, triage known problems, and restructure it in small approved steps so it matches the user's newer project workflow.

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
