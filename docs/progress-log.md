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
- HEAD: `87975c3`
- Worktree: clean
- App status: FastAPI + React customer/listings flow is working.
- Recent state: PDF export was moved to backend and Excel export now generates a real `.xlsx`.
- Current UI note: the customers action buttons were tweaked for contrast, and the latest text-color change is committed.

## What Was Completed Recently

- Customer listing PDF export now comes from the backend and produces a real PDF.
- Customer listing Excel export now comes from the backend and produces a real `.xlsx`.
- Customer list actions were visually refined, including button contrast.
- A local `listados/` folder exists in the repo for test artifacts, with `.gitkeep` tracked.

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
