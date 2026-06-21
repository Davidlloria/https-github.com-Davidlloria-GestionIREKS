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
- Branch: `feature/frontend-ui-system`
- HEAD: `c0ad0a81`
- Worktree: clean
- App status: FastAPI + React customer/listings flow is working.
- Recent state: shared button, card, chip, state box, section header and data table components are in place.
- Current UI note: standard action buttons use Lucide icons; customer activity icons remain custom SVG.
- Last published commit: `c0ad0a81` (`fix: align customer header chip`).

## What Was Completed Recently

- Shared UI primitives were added for buttons, cards, chips, state boxes, section headers and data tables.
- Customer listing PDF export now comes from the backend and produces a real PDF.
- Customer listing Excel export now comes from the backend and produces a real `.xlsx`.
- Customer action buttons and modal actions now use standard Lucide icons.
- A local `listados/` folder exists in the repo for test artifacts, with `.gitkeep` tracked.
- The repo now has a dedicated handoff file at `docs/progress-log.md`.

## Recent Commits

- `c0ad0a81` - `fix: align customer header chip`
- `d6c477b4` - `fix: align shared section headers`
- `3cf932eb` - `feat: add icons to customer modal actions`
- `9b01c08e` - `feat: add standard icon set for customer actions`
- `64c09c45` - `feat: add shared data table component`

## Important Files

- [docs/migration-history.md](./migration-history.md)
- [docs/migration-roadmap.md](./migration-roadmap.md)
- [docs/debt-residual-report.md](./debt-residual-report.md)
- [docs/release-checklist.md](./release-checklist.md)
- [docs/local-environment.md](./local-environment.md)

## Next Useful Checks

- Verify the customers screen on the React UI after icon and header alignment changes.
- Keep the `listados/` folder clean of generated artifacts before commits.
- If a new chat resumes work, start from this snapshot and then consult the roadmap.
- If the next task is functional, start from `docs/migration-roadmap.md` and
  `docs/migration-history.md` after reading this log.

## Handoff Block

```text
Branch: feature/frontend-ui-system
HEAD: c0ad0a81
Worktree: clean
Focus: customer/listings flow, shared UI primitives, and remaining migration tasks.
Recent changes: shared UI primitives added, standard button icons in place, header alignment fixed.
Pending: keep listados/ clean, review next functional block from roadmap/history.
Reference: docs/progress-log.md, docs/migration-roadmap.md, docs/migration-history.md
```
