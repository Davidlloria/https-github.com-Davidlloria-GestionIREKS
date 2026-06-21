# Progress Log

This document is the short, living handoff for the current migration work.
Use it to resume work in a fresh chat or by another person without reading the
entire migration history first.

## How to use

- Update this file at the end of each meaningful block.
- Keep entries short and factual.
- Record only what is needed to continue the work safely.
- Do not store secrets, exports, backups, or database files here.

## Current Snapshot

- Date: 2026-06-21
- Branch: `main`
- HEAD: `0dee56f`
- Worktree: clean
- App status: FastAPI + React customer/listings flow is working.
- Recent state: PDF export is backend-driven and the Excel export now generates a real `.xlsx`.
- Current UI note: the customers action buttons have a contrast fix committed and the button styling is stable.
- Last published commit: `0dee56f` (`docs: add progress log for handoff context`).

## What Was Completed Recently

- Customer listing PDF export now comes from the backend and produces a real PDF.
- Customer listing Excel export now comes from the backend and produces a real `.xlsx`.
- Customer list actions were visually refined, including button contrast.
- A local `listados/` folder exists in the repo for test artifacts, with `.gitkeep` tracked.
- The repo now has a dedicated handoff file at `docs/progress-log.md`.
- Documentation links now point readers from README, AGENTS, roadmap and history into this log.

## Recent Commits

- `0dee56f` - `docs: add progress log for handoff context`
- `011a436` - `fix: improve customers button contrast`
- `750ff04` - `fix: export customer listings as xlsx`
- `d232bcf` - `fix: stretch customer listing pdf table`
- `ad40d22` - `fix: align listing pdf left and keep test folder`

## Important Files

- [docs/migration-history.md](./migration-history.md)
- [docs/migration-roadmap.md](./migration-roadmap.md)
- [docs/debt-residual-report.md](./debt-residual-report.md)
- [docs/release-checklist.md](./release-checklist.md)
- [docs/local-environment.md](./local-environment.md)

## Next Useful Checks

- Verify the customers listing export buttons on the React UI.
- Keep the `listados/` folder clean of generated artifacts before commits.
- If a new chat resumes work, start from this snapshot and then consult the roadmap.
- If the next task is functional, start from `docs/migration-roadmap.md` and
  `docs/migration-history.md` after reading this log.
