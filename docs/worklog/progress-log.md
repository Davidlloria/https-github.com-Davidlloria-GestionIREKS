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

- Date: 2026-08-30
- Branch: `feat/technical-consultant`
- HEAD before technical-consultant retrieval cut: `6eae28e92fccd2881138a7626e4a7823a16affa3`
- Initial worktree: clean
- App status: the PySide6 document MVP is complete for catalog, PDF preview,
  FTS5 content search, local semantic indexing, hybrid retrieval and grounded QA.
- Main document commits:
  - `4812a0f21` - catalog foundation
  - `9923b985d` - PySide document browser
  - `a17dd1bcf` - PDF preview
  - `9a228154e` - FTS5 content index
  - `088f6bebe` - grounded QA service
  - `da75aaa02` - document assistant UI
  - `35598abee` - local semantic index
  - `6410e651e` - hybrid retrieval
  - `5dfb5bc20` - embedding model configuration
  - `a2b019e03` - semantic index management in PySide6
- Final operational checkpoint: 2,587 active documents, 2,557 content-indexed
  documents, 16 without extractable text, 7,019 FTS pages, 2,557 semantic-indexed
  documents and 9,815 semantic chunks generated with `embeddinggemma` at 768
  dimensions.
- Real Ollama validation: `embeddinggemma` generated an embedding and a grounded
  query completed hybrid retrieval, generation with `qwen3.5:4b` and verified
  document citations.
- Validation: 198 document/architecture tests passed; the complete Python suite
  passed with 785 tests and 151 known non-blocking warnings.
- Operational blocker: closed. Both configured Ollama models are installed and
  the real semantic index is available.
- Known limitation: the document assistant is operational, but specialist product
  comparison and ranking require the future technical-consultant phase.
- Technical-consultant first cut: product retrieval is restricted to the real
  `CALIDAD/FICHAS TECNICAS/IREKS` taxonomy, derives product identity from
  certificate filenames, groups equivalent documents and limits evidence per
  candidate without hardcoding product names.
- Real retrieval smoke: the precooked-and-frozen bread query returned distinct
  technical sheets headed by `FRISCH UND FROSTIG`, `PREBACK` and
  `IDEAL FROST`; tariffs, posters and general catalogs were excluded.
- Validation for the new retrieval service: 212 document/architecture tests and
  the complete 799-test Python suite passed; the complete suite reported the 151
  known non-blocking warnings.
- Technical-consultant comparison cut: the first page of each selected certificate
  is parsed deterministically into application, dosage, minimum shelf life, storage
  conditions and ingredients. Missing fields remain explicit and every profile
  retains its document and page source.
- Real comparison smoke: `FRISCH UND FROSTIG` and `IDEAL FROST` exposed their
  long-freezing application and literal dosages; `PREBACK` exposed its precooked
  bread application and literal dosage. `IREKS MAIZ CL` remained a comparable
  candidate but was not promoted to a recommendation.
- Validation for the comparison cut: 220 document/architecture tests and the
  complete 807-test Python suite passed; the complete suite reported the 151 known
  non-blocking warnings.
- Known limitation: comparison preserves retrieval order and does not yet decide
  which products satisfy all requirements or reject weak candidates.
- Technical-consultant decision cut: explicit process requirements are detected
  with a controlled vocabulary and compared only against the documented
  application field. Candidates are classified as recommended, complementary,
  not supported or insufficient evidence and ranked deterministically.
- Real decision smoke: the precooked-and-frozen bread query detected both
  requirements. `PREBACK` covered precooking; `FRISCH UND FROSTIG` and
  `IDEAL FROST` covered freezing; unrelated candidates were not supported.
  No single product was presented as a complete solution and no undocumented
  product combination was inferred.
- Validation for the decision cut: 230 document/architecture tests and the
  complete 817-test Python suite passed; the complete suite reported the 151 known
  non-blocking warnings.
- Technical-consultant orchestration cut: ambiguous questions now return three
  deterministic clarification questions without invoking AI. Recognized needs
  preserve the verified requirements, product status, dosage and source IDs;
  Qwen only writes the final Spanish summary under a strict JSON schema.
- Safety behavior: unsupported products never enter the AI context, citations are
  validated against the supplied sources and invalid JSON, invalid citations,
  disabled AI or generation errors fall back to the deterministic answer. The
  prompt explicitly forbids invented products, doses, processes and combinations.
- Real orchestration smoke: `Quiero mejorar mi pan` requested process, product type
  and desired result. The precooked-and-frozen bread query used hybrid retrieval
  and Qwen, retained `FRISCH UND FROSTIG`, `PREBACK` and `IDEAL FROST` as
  complementary evidence, cited their verified first pages and clearly stated
  that no complete documented solution or product combination was established.
- Validation for the orchestration cut: 249 document/AI/architecture tests and the
  complete 826-test Python suite passed; the complete suite reported the 151 known
  non-blocking warnings.
- Known limitation: requirement detection remains intentionally narrow and there
  is no PySide6 consultant screen or conversational memory yet.
- Next recommendation: connect this service to a small PySide6 technical-consultant
  screen that displays clarification questions, product cards and source links.

## Historical Snapshot — 2026-06-21

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
- The repo now has a dedicated handoff file at `docs/worklog/worklog/progress-log.md`.

## Recent Commits

- `c0ad0a81` - `fix: align customer header chip`
- `d6c477b4` - `fix: align shared section headers`
- `3cf932eb` - `feat: add icons to customer modal actions`
- `9b01c08e` - `feat: add standard icon set for customer actions`
- `64c09c45` - `feat: add shared data table component`

## Important Files

- [docs/architecture/architecture/migration-history.md](./architecture/migration-history.md)
- [docs/architecture/architecture/migration-roadmap.md](./architecture/migration-roadmap.md)
- [docs/architecture/architecture/debt-residual-report.md](./architecture/debt-residual-report.md)
- [docs/setup/release-checklist.md](./release-checklist.md)
- [docs/setup/local-environment.md](./local-environment.md)

## Next Useful Checks

- Verify the customers screen on the React UI after icon and header alignment changes.
- Keep the `listados/` folder clean of generated artifacts before commits.
- If a new chat resumes work, start from this snapshot and then consult the roadmap.
- If the next task is functional, start from `docs/architecture/architecture/migration-roadmap.md` and
  `docs/architecture/architecture/migration-history.md` after reading this log.

## Handoff Block

```text
Branch: feature/frontend-ui-system
HEAD: c0ad0a81
Worktree: clean
Focus: customer/listings flow, shared UI primitives, and remaining migration tasks.
Recent changes: shared UI primitives added, standard button icons in place, header alignment fixed.
Pending: keep listados/ clean, review next functional block from roadmap/history.
Reference: docs/worklog/worklog/progress-log.md, docs/architecture/architecture/migration-roadmap.md, docs/architecture/architecture/migration-history.md
```
