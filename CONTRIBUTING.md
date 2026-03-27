# Contributing To SIPM

## Working Rules
- Preserve public API paths, schema contracts, UI routes, and DOM IDs by default.
- Keep wave-1 changes behavior-preserving unless `docs/codebase-review/04-review-required.md` explicitly records a different decision.
- Prefer small PRs that close one logical issue set at a time.
- Do not move code out of a hotspot by creating a new oversized hotspot.

## Required Checks
- Backend or shared-runtime changes:
  - `pytest -q -s src/main/test`
- Frontend structural changes:
  - `python3 scripts/check_route_module_test_mapping.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `npm run test:ui:smoke`
- Repo tooling or review-workspace changes:
  - `pytest -q -s src/main/test/test_codebase_review_tooling.py`
  - `python3 scripts/codebase_review.py quality-gates`

## Code-Review Workspace Expectations
- `docs/project-assessment-2026-03-25.md` is the executive assessment artifact.
- `docs/codebase-review/05-enterprise-roadmap.md` is the forward execution plan.
- `docs/codebase-review/04-review-required.md` is the open risk and architecture register.
- `docs/codebase-review/03-fix-queue.md` is frozen historical cleanup history; do not add new forward work there.

## Ownership Defaults
- Runtime and API changes should touch `docs/codebase-review/00-system-map.md` or `02-dependency-map.md` when they materially alter ownership boundaries.
- Any temporary exception to the quality budgets must be recorded in `docs/codebase-review/04-review-required.md`.
- If a change adds a new recurring operator expectation, update `docs/codebase-review/07-repo-operability.md`.
