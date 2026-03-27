# SIPM Quality Gates

Date: 2026-03-25
Status: report-only in wave 1

## Purpose
- define the structural, process, and validation rules required for enterprise-quality changes
- keep the first wave behavior-preserving while hotspot reduction is still in progress
- make repo expectations explicit before CI enforcement begins

## Command

```bash
python3 scripts/codebase_review.py quality-gates
```

Current mode is report-only. The command must surface violations but return success unless run with a future strict/blocking mode.

## File-Size Budgets

| Surface | Budget |
| --- | --- |
| `src/main/ui/js/app.js` | `<= 4000` LOC |
| Any route-local JS module | `<= 700` LOC |
| Any backend route module | `<= 500` LOC |
| Any route stylesheet | `<= 900` LOC |

Budget exceptions are not implicit. Any temporary exception must be recorded in `docs/codebase-review/04-review-required.md`.

## Required Repo Artifacts
- `.editorconfig`
- `.env.example`
- `CONTRIBUTING.md`
- `.github/CODEOWNERS`
- `docs/codebase-review/05-enterprise-roadmap.md`
- `docs/codebase-review/06-quality-gates.md`
- `docs/codebase-review/07-repo-operability.md`

## Required Validation By Change Type
- Docs/tooling-only changes:
  - `pytest -q -s src/main/test/test_codebase_review_tooling.py`
- Frontend structural changes:
  - `python3 scripts/check_route_module_test_mapping.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `npm run test:ui:smoke`
  - focused frontend contract tests for the touched route
- Backend structural changes:
  - focused backend suites for the touched domain
  - `pytest -q -s src/main/test`
- Shared runtime, cache, auth, schema, or route-composition changes:
  - focused suites first
  - full Python suite required before closing the slice

## Merge Rules
- No intentional API route, schema, SQL contract, UI route, or DOM ID changes in wave 1 unless the architecture register explicitly approves them.
- Any hotspot decomposition must update the relevant roadmap or register entry when scope, risk, or target boundaries change.
- New route-local files must respect the target budgets; do not move code out of a hotspot by creating another oversized hotspot.
- New shared code must prove cross-route reuse; otherwise keep ownership route-local.
- Keep the history artifacts (`01-review-ledger.md`, `03-fix-queue.md`) append-only or frozen according to their stated role.

## Soft Then Hard Rollout
- Wave 1:
  - `quality-gates` is report-only
  - CI does not fail on budget violations
  - violations are expected and tracked while the epics are still queued
- Promotion criteria:
  - Epics 1-4 are compliant with the stated budgets
  - the repo passes `quality-gates` locally and in CI twice in a row
  - the rollout decision in `04-review-required.md` is closed

## Current Report-Only Violations
- `src/main/backend/app/routes/planning/work_allocation.py`

These are not merge blockers until the rollout criteria are met.
