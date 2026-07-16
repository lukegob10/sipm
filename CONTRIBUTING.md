# Contributing To SIPM

## Working Rules
- Preserve public API paths, schema contracts, UI routes, and DOM IDs by default.
- Keep production-review changes behavior-preserving unless the relevant review document under `docs/` explicitly records a different decision.
- Prefer small PRs that close one logical issue set at a time.
- Do not move code out of a hotspot by creating a new oversized hotspot.

## Required Checks
- Backend or shared-runtime changes:
  - `npm run test:backend`
  - `npm run test:backend:coverage`
  - `npm run test:backend:integration` (requires SIPM_REDIS_URL for the Redis coordination contract)
- Frontend structural changes:
  - `python scripts/check_route_module_test_mapping.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `npm run test:ui:coverage`
  - `npm run test:ui:smoke`
- Dependency changes:
  - `python scripts/check_requirements_lock.py`

## Production-Review Workspace Expectations
- Production-readiness reviews should record findings, implementation notes, validation, and migration status in the relevant document under `docs/`.
- Do not mark a section complete unless the relevant focused tests and full smoke path have been run or the skipped validation is explicitly recorded.

## Ownership Defaults
- Runtime, API, or operator-flow changes should update `src/main/README.md` when they materially alter deployment, readiness, or validation expectations.
- Any temporary exception to the quality bar must be recorded in the relevant review document under `docs/`.
- If a change adds a new recurring operator expectation, update `src/main/README.md` and the relevant SQL or deployment docs.
