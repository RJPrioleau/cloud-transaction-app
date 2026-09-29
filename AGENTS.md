# Repository Instructions

## Project context

- Project name: `Cloud Transaction App`
- Purpose: `A personal transaction-import tool that processes bank exports, detects duplicates, categorizes transactions, writes approved rows to a Google Sheets budget workbook, and produces upload reports.`
- Primary run command: `python app.py`
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

No sessions have been recorded yet.

### Entry format

```text
### YYYY-MM-DD HH:MM TZ - Short session title

- Completed: What changed during the session, including relevant files or commits.
- Decisions and architecture: Important agreements, boundaries, reasoning, or future direction.
- Next steps: Unfinished work and the exact first task for the next session.
- Known issues: Bugs, risks, blockers, unverified assumptions, or intentionally deferred work.
- Verification: Tests, commands, manual checks, and results; state clearly what was not tested.
```
