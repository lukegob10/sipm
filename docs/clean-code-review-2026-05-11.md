# SIPM Production Readiness Clean Code Review - 2026-05-11

Mode: full-surface review, with operational hardening emphasis for UAT migration.

No production source code was changed. This document is the only generated artifact.

## Executive Summary

SIPM is materially closer to UAT/prod readiness than the prior review implied. Several previously high-risk findings are already fixed in the current working tree: request-time space resolution no longer silently grants default-space membership, telemetry keeps failed batches, analytics has a combined dashboard endpoint, p95 rank math is fixed, `/auth/me` uses the shared auth dependency, API-token `last_used_at` writes are throttled, request logs prefer resolved space context, and analytics validates requested spaces.

The remaining production work is concentrated in UAT rehearsal and operator readiness, not basic app wiring. The first implementation pass after this review added planning-window/resource-allocation CSV coverage, dry-run support for CSV importers, duplicate SOEID protection, and lifecycle timestamp preservation for completed solutions/subcomponents.

Validation run during this review:

- `pytest -q src/main/test`: 479 passed, 1 skipped.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 8 files passed, 31 tests passed.
- `npm run test:ui:smoke`: 2 passed.
- Focused backend migration/auth/analytics/observability subset: 83 passed.
- Focused telemetry unit test: 4 passed.

Implementation validation after fixes:

- `pytest -q src/main/test`: 482 passed, 1 skipped.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 8 files passed, 31 tests passed.
- `npm run test:ui:smoke`: 2 passed.

## Production Readiness Finding

The app should not be called production-ready until the UAT migration path is validated with a real export/import rehearsal against representative data. The code now has the missing migration endpoints and safer importer semantics, but production readiness still depends on proving the runbook against the target UAT environment.

## Severity-Ordered Findings

### 1. High / must-fix / implemented: UAT CSV migration coverage was incomplete for planning data

Evidence:

- CSV import/export endpoints exist for projects, solutions, subcomponents, and users: `src/main/backend/app/routes/projects/import_export.py`, `src/main/backend/app/routes/solutions/import_export.py`, `src/main/backend/app/routes/subcomponents/import_export.py`, and `src/main/backend/app/routes/users.py`.
- Planning/work-allocation exposes JSON API endpoints for board, teams, people, tasks, allocations, planning windows, and resource allocations, for example `src/main/backend/app/routes/planning/work_allocation.py:133`, `src/main/backend/app/routes/planning/work_allocation.py:605`, `src/main/backend/app/routes/planning/legacy_allocations.py:50`, and `src/main/backend/app/routes/planning/legacy_allocations.py:260`.
- The only planning export endpoint found is the PDF report at `src/main/backend/app/routes/planning/work_allocation.py:628`; no CSV import/export endpoint exists for planning windows or allocations.

Risk:

Your stated UAT plan includes "plans/everything." The current CSV surface cannot migrate all planning state. A project/solution/subcomponent/user migration can succeed while planning windows, resource allocations, monthly work assignments, and board state are left behind or require undocumented manual API work.

Implemented fix:

- Added CSV export/import for planning windows and resource allocations.
- Allocation exports include natural project/solution/subcomponent/team/window keys so imports can resolve rows after IDs change between environments.
- Added regression coverage for planning-window CSV update and resource-allocation import by natural work-item keys.

Remaining work:

- Run a real UAT rehearsal with representative data and document the operator ordering.

### 2. High / must-fix / implemented: solution and subcomponent CSV round trips were not lossless for lifecycle timestamps

Evidence:

- Solutions export `completed_at`: `src/main/backend/app/routes/solutions/import_export.py:444` and `src/main/backend/app/routes/solutions/import_export.py:476`.
- Solution import does not read `completed_at`; it sets completed rows to `now` when `status_enum == SolutionStatus.complete`: `src/main/backend/app/routes/solutions/import_export.py:308`.
- Subcomponents export `completed_at`: `src/main/backend/app/routes/subcomponents/import_export.py:386` and `src/main/backend/app/routes/subcomponents/import_export.py:408`.
- Subcomponent import does not read `completed_at`; it sets completed rows to `now` when `status_enum == SubcomponentStatus.complete`: `src/main/backend/app/routes/subcomponents/import_export.py:286`.

Risk:

After CSV migration, completed solutions and subcomponents can have UAT import time as their completion time instead of their real completion time. That corrupts history, reporting, audit interpretation, and downstream analytics. The fact that the field is exported makes this especially risky because operators will assume it is preserved.

Implemented fix:

- Solution and subcomponent import now read ISO `completed_at` values.
- Completed rows preserve provided timestamps instead of replacing them with import time.
- Added regression coverage for solution and subcomponent import timestamp preservation.

### 3. Medium / should-fix / implemented: CSV imports allowed partial success without a dry-run or batch preflight

Evidence:

- Project import commits inside the row loop: `src/main/backend/app/routes/projects/import_export.py:157`.
- Solution and subcomponent imports commit per created/updated entity through `commit_session`: `src/main/backend/app/routes/solutions/import_export.py:293`, `src/main/backend/app/routes/solutions/import_export.py:377`, `src/main/backend/app/routes/subcomponents/import_export.py:278`, and `src/main/backend/app/routes/subcomponents/import_export.py:329`.
- Each importer returns row-level `errors` alongside created/updated counts, for example `src/main/backend/app/routes/projects/import_export.py:162`, `src/main/backend/app/routes/solutions/import_export.py:391`, and `src/main/backend/app/routes/subcomponents/import_export.py:350`.

Risk:

Partial success is useful for day-to-day bulk editing, but it is dangerous for environment migration. An operator can import hundreds of rows, get a few errors, and now own a mixed database state that needs manual cleanup before retrying. That is how UAT data drift starts.

Implemented fix:

- Added `dry_run=true` support to projects, solutions, subcomponents, users, planning windows, and resource allocations imports.
- Planning-window and resource-allocation importers also accept `atomic=true` to avoid writes when validation errors are present.
- Default partial-success behavior is preserved for existing admin bulk-edit workflows.

Remaining work:

- Document dry-run-first UAT migration steps in the runbook.

### 4. Medium / should-fix / implemented: users CSV import lacked the duplicate-row guard used by other importers

Evidence:

- Projects, solutions, and subcomponents each maintain a `seen` set and reject duplicate CSV keys: `src/main/backend/app/routes/projects/import_export.py:63`, `src/main/backend/app/routes/solutions/import_export.py:52`, and `src/main/backend/app/routes/subcomponents/import_export.py:56`.
- Users import loops through rows at `src/main/backend/app/routes/users.py:533` and commits at `src/main/backend/app/routes/users.py:586`, but has no `seen` guard for duplicate `soeid` rows.

Risk:

In a migration CSV, duplicated SOEIDs can be applied multiple times with last-row-wins behavior. That makes import results order-dependent and inconsistent with the strict-first policy used by the other importers.

Implemented fix:

- Added duplicate-SOEID rejection with strict-first semantics.
- Added `total_rows` and `dry_run` response fields for consistency.
- Added regression coverage for duplicate SOEID rows.

### 5. Medium / advisory: logout remains cookie-only and does not revoke minted sessions server-side

Evidence:

- `logout` clears cookies only: `src/main/backend/app/routes/auth.py:278`.
- Token validation checks password-change invalidation through `ensure_token_not_revoked`, but there is no per-session revocation table or session version check beyond password reset/change.

Risk:

This is an acceptable working model if the team explicitly accepts "logout clears this browser, stolen tokens remain valid until expiry." It should not block UAT if refresh TTLs remain short and secrets/cookies are configured correctly, but it must be documented as the current security model.

Smallest reasonable fix:

- Document logout semantics in the production runbook.
- Keep refresh TTL short in UAT/prod.
- When the reverse proxy/header-auth model returns, decide whether app-minted refresh tokens remain in scope.

### 6. Medium / advisory: large active modules still make future changes expensive to reason about

Evidence:

- `src/main/ui/js/app.js`: 4003 lines.
- `src/main/backend/app/services/usage_analytics.py`: 1198 lines.
- `src/main/backend/app/routes/planning/work_allocation.py`: 878 lines.
- `src/main/ui/styles/base.css`: 1693 lines.

Risk:

Large files are not automatically broken, but these files mix orchestration, rendering, data transformation, state, and route-specific behavior. The risk is not aesthetic; it raises review cost and makes small UI/action changes more likely to have hidden coupling.

Smallest reasonable fix:

- Do not start a broad rewrite before UAT.
- Continue extracting only active, well-tested route-specific pieces.
- Prioritize migration/import code and planning work-allocation code before stylistic frontend splitting.

### 7. Low / should-fix: visual robustness still needs a targeted UAT screenshot pass

Evidence:

- Playwright smoke validates navigation and a basic auth/deliverables flow, but not every admin/migration/control surface.
- Existing tests cover route contracts and smoke paths; they do not visually exercise space action menus, CSV upload menus, analytics tables, or planning board edge states across desktop and mobile.

Risk:

Minor "does not exactly look right" issues are still most likely in table actions, admin menus, and data-heavy route states. These are not release blockers if the business workflow works, but they are the visible polish risks before UAT stakeholders see the app.

Smallest reasonable fix:

- Add a short UAT screenshot checklist for: space governance, CSV upload/download menu, users import/export, analytics dashboard, planning board, and subcomponents workbench.
- Add one Playwright visual/smoke assertion around the CSV menu and planning board if these are expected to be demo-critical.

## Resolved Since Prior Review

These were previously material risks but are fixed or materially improved in the current working tree:

- Request-time space resolution no longer auto-adds non-global users to the default space; no-membership users now get `NO_ACTIVE_SPACE`. Evidence: `src/main/backend/app/services/spaces.py:183` and `src/main/test/test_spaces.py:103`.
- Telemetry flush now checks `response.ok` and retains failed retryable batches. Evidence: `src/main/ui/js/shell/telemetry.js:177` and `src/main/ui/test/unit/telemetry.test.js:79`.
- Analytics UI now calls one `/analytics/dashboard` endpoint instead of three separate endpoint refreshes. Evidence: `src/main/ui/js/routes/analytics.js:89` and `src/main/backend/app/routes/analytics.py:191`.
- P95 rank math now uses floating-point arithmetic and has a 101-sample regression test. Evidence: `src/main/backend/app/services/usage_analytics.py:661` and `src/main/test/test_usage_analytics.py:525`.
- API-token `last_used_at` updates are throttled. Evidence: `src/main/backend/app/services/api_tokens.py:10` and `src/main/backend/app/services/api_tokens.py:61`.
- `/auth/me` uses `require_user`, so bearer-token HTTP API clients are supported. Evidence: `src/main/backend/app/routes/auth.py:284` and `src/main/test/test_auth_and_deps.py:629`.
- Request logs prefer resolved `request.state.space_context` before header/cookie fallback. Evidence: `src/main/backend/main.py:197`.
- Analytics validates requested `space_id` before returning scoped results. Evidence: `src/main/backend/app/routes/analytics.py:137`, `src/main/backend/app/routes/analytics.py:160`, `src/main/backend/app/routes/analytics.py:184`, and `src/main/backend/app/routes/analytics.py:207`.

## Strengths

- CI has a clear path: dependency lock check, import check, route-module mapping gate, backend tests, UI lint, Vitest, and Playwright smoke.
- Non-dev auth config validates secret key, secure cookies, self-registration, SameSite, token durations, and bcrypt rounds.
- UAT/prod coordination requires Redis through `SIPM_COORDINATION_BACKEND=redis` and `SIPM_REDIS_URL`.
- Readiness includes auth config, frontend bundle verification, and DB connectivity.
- Space-scoped project/solution/subcomponent/user export tests exist.
- Import/export tests cover auto-created parent rows, cache invalidation, bad statuses, duplicate project/solution/subcomponent keys, and rollback on phase enablement failure for nested imports.
- Usage analytics has server-side user/space binding, batch limits, detail sanitization, rollups, and dashboard tests.

## Coverage Ledger

Reviewed:

- FastAPI app wiring, readiness, startup validation, request logging, context path behavior.
- Auth/session/API-token paths, excluding a redesign of the current auth model by request.
- Space resolution, membership, global admin handling, and route-space enforcement tests.
- CSV import/export for projects, solutions, subcomponents, and users.
- Planning/work-allocation API surface and PDF report surface.
- Analytics ingest, rollups, dashboard reads, telemetry client, and analytics tests.
- Frontend shell routing, route module structure, smoke tests, and obvious client-side safety patterns.
- CI, dependency lock workflow, README operations notes, and test commands.

Flagged for follow-up:

- Document logout/session revocation semantics.
- Add targeted UAT screenshot checks for admin/data-heavy surfaces.
- Execute and record a real UAT CSV migration rehearsal.

Not verified:

- Real Oracle execution plans, table volumes, and cross-environment export/import performance.
- External deployment platform: ingress, TLS/HSTS, secret injection, dashboards, alert routing, backup/restore, and rollback.
- Full visual regression across every route and viewport.
- Penetration testing beyond static source review.

Out of scope by request:

- Code changes.
- Auth redesign.
- Schema migrations.
- Reverse proxy/header-auth implementation.
- PR/commit generation.

## Recommended Implementation Order

1. Build or run the migration rehearsal: export CSVs from source, import into a blank target DB, and compare counts/relationships/timestamps.
2. Document the UAT migration runbook, including dry-run-first import order.
3. Document logout/session revocation semantics.
4. Add targeted screenshot checks for admin/data-heavy UAT surfaces.

After those changes, rerun:

- `pytest -q src/main/test/test_import_export_projects.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py src/main/test/test_users_space_scope.py`
- Planning migration tests once added.
- `pytest -q src/main/test`
- `npm run lint:ui`
- `npm run test:ui`
- `npm run test:ui:smoke`
