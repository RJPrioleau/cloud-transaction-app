# Repository Instructions

## Project context

- Project name: `Cloud Transaction App`
- Purpose: `A personal transaction-import tool that processes bank exports, detects duplicates, categorizes transactions, writes approved rows to a Google Sheets budget workbook, and produces upload reports.`
- Primary local run command: `.\start_app.ps1` in PowerShell 7; use `.\start_app.ps1 -Restart` after Python/template edits. Direct `python app.py` remains a manual/deployment entry point.
- Primary verification command: `python -m unittest discover -s tests`

## Collaboration context

Read `docs/COLLABORATION.md` before beginning substantial work. It describes the user's learning goals, preferred teaching style, division of responsibilities between PyCharm and PowerShell, browser ChatGPT update workflow, and relationship between the current project and the independent Developer Playbook repository.

## Requirements discovery before architecture

When product requirements are not yet established, guide the user through requirements discovery before proposing architecture, dependencies, frameworks, tools, or project structure.

Ask one focused question at a time and work backward from the project's intended outcome. Cover the categories that apply:

- **User:** Who operates the product, and who benefits from it?
- **Outcome:** What must the first useful version accomplish?
- **Inputs:** What information drives that outcome?
- **Output:** What does the user receive?
- **Sources:** Where does the product's content or data come from?
- **Lifecycle:** What can users create, view, change, archive, or delete?
- **History:** Which changes or prior states must be preserved?
- **Scope:** What is required now, approved for later, undecided, or only a parking-lot idea?
- **Experience:** Has the user interface been decided?
- **Architecture boundary:** Which technical decisions remain intentionally open?

Do not embed unapproved technical assumptions in the questions. Do not treat parking-lot ideas as requirements or roadmap commitments.

Summarize the resulting product baseline, separate approved requirements from open decisions and non-goals, and obtain explicit user approval before documenting it or proposing implementation architecture.

## Repository documentation

Before making architectural, data-contract, or workflow changes, inspect the relevant files in `docs/` and the repository root.

- `README.md` - project purpose, setup, usage, and current behavior.
- `ROADMAP.md` - approved phases, triage direction, and planned restructuring.
- `CHANGELOG.md` - notable changes by date.
- `docs/PRODUCT.md` - current product baseline, open questions, and scope boundaries.
- `docs/COLLABORATION.md` - the preferred teaching and collaboration workflow.

When code changes introduce or alter a durable contract, workflow, architectural boundary, or user-facing behavior, update the relevant project documentation.

## Working-tree safety

Existing and uncommitted changes belong to the user unless clearly established otherwise. Preserve unrelated work, inspect overlapping changes before editing, and never discard changes without explicit approval.

Use small, conceptually focused changes when practical. Verify each meaningful change in proportion to its risk before recommending a commit.

Do not commit or push unless the user explicitly approves it.

## End-of-session workflow

When the user indicates they are finished, asks to wrap up, or says they are switching computers:

1. Summarize the work completed and note unfinished items or known issues.
2. Run relevant tests or checks when practical, and report anything that was not verified.
3. Review `git status --short` and identify the files changed during the session without altering unrelated user changes.
4. Add a concise, self-contained entry to **Handoff details and continuity log** below. It must include the local date, time, and time zone; completed work; important decisions or architectural direction; unfinished work and the exact next task; known issues; and verification performed.
5. Preserve useful information from earlier entries while avoiding repetition of unchanged details.
6. Ask whether the user wants the session changes, including the continuity entry, committed and pushed to `origin`. Never commit or push without explicit approval.
7. After an approved push, report the branch, commit hash, and whether the local branch is synchronized with its upstream.
8. Provide a short continuation note the user can use on another computer, including the latest commit and next task when work remains.

## Machine-switch handoff

The repository documents must contain the handoff context; do not rely on the user remembering details from the previous chat or carrying a separate continuation note.

Before leaving the current computer:

1. Complete the end-of-session workflow above.
2. Ensure the newest handoff entry contains the decisions, unfinished work, exact next task, known issues, and verification needed to resume without the old transcript.
3. After the user approves the commit and push, verify the active branch is synchronized with its upstream.

On the receiving computer, before beginning new work:

1. Ask the user to confirm that the latest changes have been pulled from `origin` if synchronization has not been established.
2. Read this file and `docs/COLLABORATION.md`.
3. Inspect the newest handoff entry, current branch, `git status --short`, and latest commit.
4. Briefly summarize the recovered context, repository state, and proposed next task so the user can confirm the handoff succeeded.
5. Do not overwrite uncommitted work or assume that machine-specific environments, secrets, ignored files, virtual environments, or PyCharm settings transferred through Git.

The user should only need to pull the repository and tell the receiving agent:

> Read the latest handoff details in `AGENTS.md` and continue from there.

## Project-specific instructions

Add durable rules unique to this repository here as they are discovered. Keep reusable personal workflow standards in `docs/COLLABORATION.md`, and keep session-specific state in the continuity log.

- This project predates the current AI-assisted workflow. Treat the existing app as legacy working code until each restructure step is explicitly approved.
- Do not combine bug triage, feature design, and structural refactoring in one broad change. Discuss the intended slice, verify it, then ask before committing.
- Google credentials and exported bank files are local/private inputs. Do not commit `credentials.json`, uploads, generated reports, generated logs, or real personal transaction exports.

## Handoff details and continuity log

This is the authoritative continuing handoff record for AI agents working on this repository from different computers. At every session end or computer switch, add a new entry directly below this explanation, with the newest entry first. Older entries preserve useful decision history. Keep entries concise but preserve decisions and context that cannot be recovered from the code alone. Do not use this section as a general development diary or duplicate information already clear from Git history.

### 2026-10-26 21:49 -04:00 - Live import verification and reporting checkpoint

- Completed: Extracted results/error pages into templates; added and manually verified confirmed TEST reset; configured an ignored local service-account key; fixed Sheets read-quota exhaustion by eliminating per-cell row scans; verified source/report/worksheet accuracy and repeat-upload duplicate handling. Added the Roundup category rule, managed local server lifecycle, Budget Name report column, category summary, and read-only grouped MISC review. Latest feature commit: `e57e8e3`. User requested a checkpoint push and browser ChatGPT summary to choose next work.
- Decisions and architecture: Hybrid mode continues. User approves focused commits and batches pushes. Imported amounts intentionally use positive magnitudes; category-based budget treatment distinguishes income/expense. Destination month is not a date filter: the user normally exports the desired month. MISC is an intentional fallback; additional merchant/category rules are not a current priority. Do not continue proposing category-rule expansion as the next sprint. No new feature or architecture direction is approved at this checkpoint.
- Boundaries: TEST reset clears only non-formula constants in H/I/K/O/P rows 69–383, preserving formatting, formulas, live months, and reports/logs; row 384 is the Total Transactions heading/formula and must remain. Old overflow rows were manually cleared. Future row growth/capacity handling is deferred: user attributes overflow to accumulated tests and does not want it prioritized now. Duplicate detection still reads from row 69 onward and imports do not enforce row 383 as a hard limit.
- Verified live behavior: Fresh TEST import had 295 added rows, no duplicates, and a magnitude total of $21,958.50; all rows matched the original export with no missing/extra rows or cent-rounding discrepancies. Repeat upload had zero additions/295 duplicates and left TEST unchanged. Export spanned two months intentionally for testing. After reset/reimport, all 120 Roundup entries mapped to exact workbook label `Round up Transfer`, totaling $57.12 in row-44 savings summary. TEST currently holds the imported test data. Summary/MISC calculations were reconciled with the saved export; new report UI additions have automated rendering coverage, but user visual acceptance of every new view is not recorded.
- Runtime: Use PowerShell 7 `.\start_app.ps1`, `-Restart`, `-Status`, or `-Stop`; primary URL is http://127.0.0.1:5000. Startup fingerprint catches stale Python/template code. Launcher matches only this repo's managed server command and uses exclusive Windows binding. Legacy/ad hoc servers previously survived Ctrl+C through interpreter child processes and served stale code; they were explicitly stopped. Temporary port 5001 server was retired. Do not revert to ad hoc launches or kill unrelated Python processes. `credentials.json`, uploads, reports, logs, and runtime state remain private/local and do not transfer through Git.
- Next steps: First task on return: read this entry and `docs/PRODUCT.md`, inspect branch/status, and run `.\start_app.ps1 -Status` if using the local app. Discuss the browser ChatGPT recommendations with the user and choose one concrete approved outcome before editing. Existing future pay-calendar/paycheck-allocation requirements remain design inputs only, pending architecture review. `ROADMAP.md` still has stale overall phase/status labels; do not infer they accurately describe completed refactoring.
- Known issues and limits: HTML report/detail/error rendering retains legacy unescaped behavior; only new summary/review labels are explicitly escaped. Duplicate reports show categories from the current parser, not a readback of existing worksheet categories. The bank export's Type/Status/balance columns are not currently used. Live verification covered this CSV and TEST, not all bank formats or a live-month write. Separate Developer Playbook category cleanup was pushed as `125fb40`; pre-existing Playbook IDE changes were left untouched.
- Verification: `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed 45 tests at checkpoint. Per-slice `git diff --check` passed. Live launcher checks covered idempotent start, stale fingerprint detection, restart, stop, and duplicate-listener rejection. App tree was clean before this continuity update. Push synchronization will be checked after publishing this handoff commit.

### 2026-10-22 10:53 -04:00 - Verified refactor checkpoint before short break

- Completed: Finished report HTML extraction; added report, upload-route, and download characterization coverage; extracted CSV report writing and log appending into `upload_report.py`, worksheet connection/import orchestration into `budget_sheet.py`, uploaded-file processing into `upload_processing.py`, and the home page into `templates/upload.html`. Latest implementation commit: `749b00b`. Updated `docs/PRODUCT.md` and `CHANGELOG.md` with module boundaries.
- Decisions and architecture: Hybrid mode is active: agent handles routine edits and checks, explains meaningful changes, and involves the user in scope/design decisions. Continue focused behavior-preserving slices; future budgeting features remain deferred. User approves each commit; pushes may batch multiple local commits. User explicitly requested this checkpoint push before a short break.
- Next steps: No unfinished code changes at checkpoint. First task on return: inspect branch/status and confirm this checkpoint is present. Proposed next slice, requiring discussion before implementation: extract the results-page HTML from `app.py` into a Flask template while preserving report rows, totals, download links, and current escaping behavior. Error pages remain inline. Avoid treating template extraction as approval for UI redesign.
- Known issues: Live Google Sheets access and real bank exports remain unverified; tests use synthetic inputs and mocked Google access. Local credentials were absent during environment setup. Legacy phase labels in `ROADMAP.md` lag the concrete refactor progress; the older handoff's missing-import failure is resolved. Separate Developer Playbook at `C:\Users\ridin\PycharmProjects\developer-playbook` has uncommitted `docs/COMMANDS.md` category/index cleanup and `ROADMAP.md` updates, plus pre-existing IDE changes; it is not included in this app push. Download MIME labels can vary by Windows configuration.
- Verification: `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed all 28 tests at checkpoint. Earlier per-slice whitespace checks passed, and home-page rendered output matched its original apart from whitespace. Python 3.14.6 virtual environment and dependency check were verified. No live upload or visual browser review performed. Push synchronization will be checked after publishing this handoff commit.

### 2026-09-30 22:52 -04:00 - Phase 3 characterization refactor handoff

- Completed: Confirmed `C:\Users\Jaypr\Python-Projects\cloud-transaction-app` is the canonical repo; deleted old/archive app copies after verifying their paths; committed and pushed incremental Phase 3 characterization/refactor slices through `984ec68`. New helper boundaries include duplicate-key creation and duplicate splitting in `transaction_processor.py`, Google Sheets payload and first-empty-row helpers in `budget_sheet.py`, and report/log row helpers in `upload_report.py`. Documented future pay-calendar/paycheck-allocation requirements in `docs/PRODUCT.md` and `ROADMAP.md`.
- Decisions and architecture: Continue current Phase 3 characterization-test work before future budgeting architecture. Teaching Focused mode means the user writes meaningful syntax unless they explicitly pass implementation to the agent; the agent should coach, run verification, and help debug. Future budgeting architecture must account for confirmed pay calendars, paycheck allocation, fund-by dates, split funding, manual overrides, paycheck views, Google Sheets boundaries, and historical integrity, but those features must not be implemented yet.
- Next steps: Resume the in-progress `build_transaction_report_html()` extraction. Exact first task: in `tests/test_upload_report.py`, add `build_transaction_report_html` to the `from upload_report import (...)` block. Then rerun `.\.venv\Scripts\python.exe -m unittest tests.test_upload_report`. After that, split the HTML assertions into their own test if desired, import `build_transaction_report_html` in `app.py`, and replace the remaining inline `report_html` construction block with `build_transaction_report_html(new_transactions, duplicate_transactions)`.
- Known issues: The repository is intentionally being handed off with a failing test because the user needed to shut down quickly. Current failure is `NameError: name 'build_transaction_report_html' is not defined` in `tests/test_upload_report.py`; the function exists in `upload_report.py` but has not been imported in the test. `upload_report.py` also needs style cleanup with two blank lines around the new top-level function.
- Verification: Last clean pushed commit before the current WIP was `984ec68`, where `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed with 12 tests. After the current WIP, `.\.venv\Scripts\python.exe -m unittest discover -s tests` ran 12 tests and failed with the known `NameError` above. Working files at handoff are `upload_report.py`, `tests/test_upload_report.py`, and this `AGENTS.md` continuity entry.

### Entry format

```text
### YYYY-MM-DD HH:MM TZ - Short session title

- Completed: What changed during the session, including relevant files or commits.
- Decisions and architecture: Important agreements, boundaries, reasoning, or future direction.
- Next steps: Unfinished work and the exact first task for the next session.
- Known issues: Bugs, risks, blockers, unverified assumptions, or intentionally deferred work.
- Verification: Tests, commands, manual checks, and results; state clearly what was not tested.
```
