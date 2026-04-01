# SIPM Fix Queue

Date: 2026-03-20
Queue type: micro-batch cleanup plan for iterative `clean-code-review` passes
Status: historical record only as of 2026-03-25

## Historical Record Notice
- This file is frozen as the batch-by-batch execution history for the initial cleanup program.
- Forward-looking roadmap ownership now lives in `docs/codebase-review/05-enterprise-roadmap.md`.
- Quality policy and merge expectations now live in `docs/codebase-review/06-quality-gates.md`.
- Open architectural risks and decisions now live in `docs/codebase-review/04-review-required.md`.
- Do not add new `BATCH-*` items here unless the repo explicitly re-enters batch mode in a later review program.

## Operating Rules
- One batch equals one logical issue set or one tightly related subsystem path.
- Update `00-system-map.md`, `01-review-ledger.md`, and `02-dependency-map.md` after every completed batch.
- Preserve public routes, SQL contracts, auth behavior, and runtime semantics by default.
- Add characterization coverage before changing active behavior when the path is weakly proven.
- Run a broad rescan after every 3 completed batches, and immediately after any auth, shared-runtime, schema, cache, or realtime change.
- Medium+, DB-related, and contract-changing items go to `docs/codebase-review/04-review-required.md` and do not block low-risk execution.

## Ranked Next Batches
- none; forward planning has moved to the enterprise roadmap and this queue is intentionally frozen

## Completed Batches

### `BATCH-001` Workflow Noise Boundary And Audit-Tool Sanity
- Outcome:
  - added `scripts/codebase_review.py` for repo-local `inventory` and `stale-scripts` commands
  - filtered the review source set to git-active files instead of raw filesystem walks
  - limited stale-script scans to actual repo `scripts/` candidates
  - added `src/main/test/test_codebase_review_tooling.py` to lock the behavior
- Validation:
  - `python3 scripts/codebase_review.py inventory`
  - `python3 scripts/codebase_review.py stale-scripts`
  - `pytest -q -s src/main/test/test_codebase_review_tooling.py`
  - `python3 scripts/check_requirements_lock.py`
  - `python3 scripts/check_route_module_test_mapping.py`
- Notes:
  - no runtime or API behavior changed
  - broad rescan not due yet; only one batch is complete

### `BATCH-004` SQL / Model / Schema / Audit-Log Contract Alignment
- Outcome:
  - aligned Oracle `String` compilation to `VARCHAR2(... CHAR)` for both explicit and implicit lengths
  - sized solution and subcomponent `github_repo_url` columns to the documented `1024` characters
  - removed the dormant `PasswordResetToken` metadata/export surface that no longer matched any active Oracle table contract
  - exposed `space_id` on audit read rows so `all_spaces` results preserve attribution
  - added full schema-doc regression coverage for table sets, columns, unique constraints, and indexes
- Validation:
  - `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_users_space_scope.py`
- Notes:
  - no live DB schema changes were made
  - closure is backed by code plus an explicit schema-doc regression test

### `BATCH-006` Admin Domain: Spaces, Users, Teams, Access Control
- Outcome:
  - fixed duplicate-space conflict handling, team default-capacity precedence, and the `/users/import` global-admin authz bypass
  - kept team rename/delete mutations and cross-space shared-user updates/imports consistent with `users` cache invalidation
  - enforced the active-admin invariant across both membership edits and user deactivation, counting only actually-active admin users
  - aligned planning "people" mutations with the same protected global-admin and last-admin guards used by `/users`
- Validation:
  - `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py`
  - `pytest -q -s src/main/test`
- Notes:
  - no DB schema, migration, or live-table changes were made
  - closure is backed by focused admin-domain regression tests and a green full-suite pass

### `BATCH-002` Protected Runtime / Auth / DB / Space Boundary
- Outcome:
  - hardened startup/env/auth cookie validation across runtime, auth, and DB config parsing
  - made explicit invalid active-space selection fail closed instead of silently falling back
  - aligned TA env normalization and DB pool validation with the documented runtime contract
  - normalized legacy global-admin role values across authz and active-space resolution
  - blocked `/users/import` from letting non-global-admin actors modify or reactivate global-admin accounts
  - restored protected-route dependency coverage for the split `planning/` route package
- Validation:
  - `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_db_config.py src/main/test/test_seed_and_db.py src/main/test/test_context_path_routing.py src/main/test/test_global_admin_management.py src/main/test/test_route_space_enforcement_gate.py`
  - `pytest -q -s src/main/test/test_users_space_scope.py src/main/test/test_spaces.py`
- Notes:
  - no DB schema, migration, or live-table changes were made
  - closure is backed by focused protected-path and admin/authz regression tests

### `BATCH-003` Frontend Shell Hotspot In `app.js`
- Outcome:
  - extracted shared shell responsibilities into `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context,dom,modal-shell,space-switcher,topbar-create}.js`
  - standardized route modules on a primary `render(ctx)` entrypoint while preserving legacy exports
  - reduced `src/main/ui/js/app.js` to shell composition, wiring, and shared UI workflows instead of core routing/session/live-sync/DOM/modal/switcher ownership
- Validation:
  - `python3 scripts/check_route_module_test_mapping.py`
  - `pytest -q -s src/main/test/test_ui_route_modules_exports.py src/main/test/test_ui_route_module_test_mapping_gate.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_context_path_routing.py src/main/test/test_team_capacity_frontend_contract.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `pytest -q -s src/main/test` from `src/main`
- Notes:
  - no route-name, DOM-ID, or visible UX-structure change was made
  - closure is backed by frontend contract coverage plus a green full-suite pass

### `BATCH-008` Realtime, Cache, And Sync
- Outcome:
  - hardened websocket registration failure handling and limit validation
  - made smart-cache env parsing fail fast on invalid boolean, integer, and non-positive max-entry values
  - closed idle-pruned websocket connections with reconnectable code `1001` before unregistering them
  - added a shared coordination backend so cache scope versions and realtime refresh fanout can move from process-local state to Redis in stage/prod while preserving memory mode for local/test
  - aligned audit request correlation so bulk project/solution/subcomponent writes inherit the active request ID instead of generating unrelated UUIDs
  - ran the focused batch gate plus a full-suite regression pass after the shared realtime/cache changes
- Validation:
  - `pytest -q -s src/main/test/test_realtime_and_sync.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py`
  - `pytest -q -s src/main/test/test_observability.py src/main/test/test_request_audit_correlation.py src/main/test/test_coordination_backend.py`
  - `pytest -q -s src/main/test` from `src/main`
- Notes:
  - no DB schema, migration, or live-table changes were made
  - closure is backed by focused realtime/cache tests and a green full-suite pass

### `BATCH-005` Deliverables Backend: Projects, Solutions, Subcomponents, Phases
- Outcome:
  - kept solution and subcomponent completion-state metadata consistent across direct updates, CSV imports, and subcomponent batch updates
  - made soft-deleted parent projects and solutions hide descendant solution, subcomponent, and phase surfaces immediately on both cold reads and cached reads
  - fixed parent/child cache invalidation around solution delete, auto-created parents in CSV imports, and inherited repo-link changes from solutions to subcomponents
  - fixed subcomponent batch responses and direct solution/subcomponent status-patch audit entries so returned payloads and audit trails match the real derived state
  - replaced the old `solutions.py` and `subcomponents.py` route monoliths with `solutions/` and `subcomponents/` packages split into `common`, `read`, `write`, and `import_export` modules while preserving the same route contracts and package import paths
- Validation:
  - `pytest -q -s src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_phases.py src/main/test/test_audit.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py`
  - `pytest -q -s src/main/test`
- Notes:
  - no DB schema, migration, or live-table changes were made
  - closure is backed by focused deliverables regression tests and a green full-suite pass

### `BATCH-007` Planning Backend And Report Generation
- Outcome:
  - replaced the old monolithic `planning.py` route file with the `planning/{common,legacy_allocations,work_allocation}.py` package
  - moved inline planning wire schemas into `src/main/backend/app/schemas/planning.py`
  - preserved the same planning routes and report behavior while narrowing future change surfaces
  - closed the planning "people" side door around protected user-deactivation and global-admin mutation rules
- Validation:
  - `pytest -q -s src/main/test/test_planning_fte_month.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_planning_router_composition.py`
  - `pytest -q -s src/main/test` from `src/main`
- Notes:
  - no planning API contract or DB schema change was made
  - closure is backed by focused planning regression tests plus a green full-suite pass

### `BATCH-009` Frontend Route Modules, Markup, And Styles
- Outcome:
  - split `src/main/ui/js/routes/master.js` into a thin route entrypoint plus `src/main/ui/js/routes/master/table.js`
  - split `src/main/ui/js/routes/planning.js`, `dashboard.js`, and `pm-dashboard.js` into thin entrypoints plus route-local modules
  - moved shared shell DOM lookup, confirm/planning modal behavior, and the space-switcher workflow into dedicated shell modules
  - split `src/main/ui/styles.css` into imported partials under `src/main/ui/styles/{base.css,routes/*.css}` while preserving the same visible UI and selector contracts
  - preserved the same deliverables route names, DOM IDs, filters, repo-visibility behavior, and bulk-selection behavior
  - updated route-specific frontend contract tests to follow the new route-local boundary and the imported stylesheet contract
- Validation:
  - `pytest -q -s src/main/test/test_master_frontend_contract.py src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_dashboard_frontend_contract.py src/main/test/test_pm_dashboard_frontend_contract.py src/main/test/test_planning_header_compact_frontend_contract.py`
  - `pytest -q -s src/main/test/test_calendar_frontend_contract.py src/main/test/test_dark_mode_theme_contract.py src/main/test/test_deliverables_save_feedback_frontend_contract.py src/main/test/test_kanban_frontend_contract.py src/main/test/test_modal_layout_frontend_contract.py src/main/test/test_space_governance_frontend_contract.py src/main/test/test_subcomponents_workbench_frontend_contract.py src/main/test/test_view_heading_frontend_contract.py`
  - `python3 scripts/check_route_module_test_mapping.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `pytest -q -s src/main/test` from `src/main`
- Notes:
  - no route-name, DOM-ID, or visible UX-structure change was made
  - closure is backed by route-specific contract coverage and a green full-suite pass

### `BATCH-010` Test Suite Quality And Coverage Gaps
- Outcome:
  - strengthened observability regression coverage so unhandled exceptions are explicitly tested in both raising and non-raising ASGI client modes
  - closed the exact test gap that allowed the middleware exception-flow regression to slip until a late full-suite run
  - added repo-level frontend lint/unit/browser commands with Vitest router/live-sync tests and a Playwright smoke harness backed by `scripts/run_ui_smoke_app.py`
  - updated frontend contract helpers so imported stylesheet partials remain covered after the CSS split instead of pinning the suite to one monolithic file
- Validation:
  - `pytest -q -s src/main/test/test_observability.py`
  - `npm run lint:ui`
  - `npm run test:ui`
  - `pytest -q -s src/main/test` from `src/main`
- Notes:
  - this batch was test-only
  - broader frontend runtime-interaction coverage is still a longer-horizon quality opportunity, but this pass closed a concrete high-value regression gap

## Batch Details

### `BATCH-001` Workflow Noise Boundary And Audit-Tool Sanity
- Scope: inventory noise, stale-helper interpretation, generated artifact boundaries, documented exclusion list
- Entry points: repo root, `.gitignore`, `htmlcov/`, `.pytest_cache/`, `.venv/`, `scripts/check_requirements_lock.py`, `scripts/check_route_module_test_mapping.py`
- Why now: the broad audit tools are noisy enough to waste follow-up effort if left uncorrected
- Guardrails:
  - no API, schema, auth, or runtime changes
  - do not delete tracked files without proof they are generated or unused
  - treat local env files as runtime inputs, not stale artifacts
- Exit criteria:
  - audit exclusions are explicit and stable
  - stale-helper output is interpreted only after noise is filtered
  - any safe repo-hygiene edits stay outside runtime code
- Validation:
  - rerun filtered file inventory
  - rerun `python3 scripts/check_requirements_lock.py`
  - rerun `python3 scripts/check_route_module_test_mapping.py`

### `BATCH-002` Protected Runtime / Auth / DB / Space Boundary
- Scope: `src/main/backend/main.py`, `src/main/backend/app/deps.py`, `src/main/backend/app/auth/auth.py`, `src/main/backend/app/db/db.py`, `src/main/backend/app/runtime.py`, `src/main/backend/app/services/spaces.py`, `src/main/backend/app/security.py`, `src/main/backend/app/paths.py`
- Entry path to narrow first: login/refresh/me flow plus active-space resolution and startup import/lifespan behavior
- Why now: highest shared-risk seam; many later cleanups depend on it being mapped correctly
- Guardrails:
  - no cookie, token, or active-space behavior changes without strong proof
  - no DB env or TAConnection contract changes unless a defect is demonstrated
  - keep edits local and characterization-backed
- Exit criteria:
  - startup, env loading, cookie path, token TTL/revocation, space resolution, and authz denial audit paths are explicitly mapped
  - any fix stays inside one logical issue set
- Validation:
  - `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_db_config.py src/main/test/test_seed_and_db.py src/main/test/test_context_path_routing.py src/main/test/test_global_admin_management.py src/main/test/test_route_space_enforcement_gate.py`
  - rerun full suite if any file in this batch changes
- Progress:
  - 2026-03-23: fixed the fail-open active-space mismatch in `src/main/backend/app/deps.py`. Explicit inaccessible `X-Space-Id` / `active_space_id` values now return `403 FORBIDDEN_SPACE` instead of silently resolving to a different space. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_projects.py test/test_spaces.py test/test_users_space_scope.py test/test_teams_space_scope.py test/test_space_isolation_strict.py` from `src/main`.
  - 2026-03-23: fixed the lifespan teardown leak in `src/main/backend/main.py`. The temporary AnyIO threadpool bypass used for tests/sandboxed runs now restores on shutdown instead of mutating global runtime state across app contexts. Validated with `pytest -q -s test/test_db_config.py test/test_context_path_routing.py test/test_auth_and_deps.py` from `src/main`.
  - 2026-03-23: fixed deployment profile drift in `src/main/backend/app/runtime.py`. `ENV=local` now maps to `dev`, matching auth configuration and preventing local auth/runtime profile disagreement. Validated with `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py` from `src/main`.
  - 2026-03-23: fixed fail-late auth cookie config handling in `src/main/backend/app/auth/auth.py`. Invalid `SIPM_COOKIE_SAMESITE` values now fail during auth configuration validation instead of crashing later on the first auth cookie write. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-23: fixed invalid `SameSite=None` cookie mode in `src/main/backend/app/auth/auth.py`. The app now rejects `SIPM_COOKIE_SAMESITE=none` unless secure cookies are enabled, preventing startup from accepting a browser-rejected auth-cookie configuration. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-23: fixed secure-cookie env parsing in `src/main/backend/app/auth/auth.py`. `SIPM_SECURE_COOKIES` now accepts standard boolean env forms and rejects invalid ones instead of silently treating `yes`/`1`/`on` as false. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-23: fixed runtime shell boolean env parsing in `src/main/backend/main.py`. Startup/threadpool/env-override flags now accept standard boolean env forms and reject invalid ones instead of silently ignoring common truthy values. Validated with `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py test/test_context_path_routing.py` from `src/main`.
  - 2026-03-23: fixed auth numeric env parsing in `src/main/backend/app/auth/auth.py`. Invalid access/reset/bcrypt numeric settings now raise explicit runtime config errors instead of raw import-time `ValueError`s. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-24: fixed unknown deployment-profile auth defaults in `src/main/backend/app/auth/auth.py`. Non-`dev`/`test` `ENV` values now default to non-dev auth safety instead of dev-like relaxed settings. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-24: fixed fail-late bcrypt-round validation in `src/main/backend/app/auth/auth.py`. Invalid numeric bcrypt rounds are now rejected during auth startup validation instead of breaking register/reset flows later. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-24: fixed negative auth/reset TTL handling in `src/main/backend/app/auth/auth.py`. Negative duration settings now fail during auth startup validation instead of generating already-expired tokens later. Validated with `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main`.
  - 2026-03-24: tightened the TA environment contract in `src/main/backend/app/runtime.py`. `ENV=test` now normalizes to `dev`, and unknown TA profiles now fail explicitly instead of flowing into `TAConnection(env=...)` unchecked. Validated with `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py` from `src/main`.
  - 2026-03-24: fixed DB pool env range validation in `src/main/backend/app/db/db.py`. Invalid negative pool settings now fail during startup config parsing instead of surfacing later as confusing SQLAlchemy pool behavior. Validated with `pytest -q -s src/main/test/test_db_config.py`.
  - 2026-03-24: fixed password-reset expiry override validation in `src/main/backend/app/schemas/__init__.py` and `src/main/backend/app/services/password_reset.py`. Out-of-range expiry values now fail explicitly instead of being silently clamped away from the caller’s request. Validated with `pytest -q -s src/main/test/test_users_space_scope.py src/main/test/test_auth_and_deps.py`.
  - 2026-03-24: fixed password-reset minimum-length drift in `src/main/backend/app/schemas/__init__.py`. Reset passwords now enforce the same minimum length as registration instead of letting the reset flow undercut the auth contract. Validated with `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_users_space_scope.py`.
  - 2026-03-25: normalized legacy `global admin` / `global-admin` role values across `src/main/backend/app/services/spaces.py`, `src/main/backend/app/deps.py`, and `src/main/backend/app/routes/users.py`, so global-admin authz, active-space resolution, and last-admin protections stay consistent with legacy data. Also blocked non-global-admin actors from using `/users/import` to modify or reactivate global-admin accounts. Validated with `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_spaces.py`.
  - 2026-03-25: expanded `src/main/test/test_route_space_enforcement_gate.py` to scan nested route packages, restoring protected-route dependency coverage after the `planning/` split. Validated with `pytest -q -s src/main/test/test_route_space_enforcement_gate.py`.

### `BATCH-003` Frontend Shell Hotspot In `app.js`
- Scope: `src/main/ui/js/app.js` only, plus the smallest supporting route module or test file needed for one extracted responsibility slice
- Entry path to narrow first: route loader registry, shared modal orchestration, or shared API/context-path helpers
- Why now: future frontend cleanup quality depends on reducing shell responsibility without rewriting the SPA
- Guardrails:
  - no UI redesign
  - no route-name changes
  - preserve existing DOM IDs and user-visible behavior unless fixing a clear defect
  - extract one slice only
- Exit criteria:
  - one responsibility is moved or simplified with behavior preserved
  - `app.js` loses real responsibility, not just comments or wrapper indirection
  - route/shell dependency map is updated
- Validation:
  - `python3 scripts/check_route_module_test_mapping.py`
  - `pytest -q -s src/main/test/test_ui_route_modules_exports.py src/main/test/test_ui_route_module_test_mapping_gate.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_context_path_routing.py`
  - rerun full suite if shared shell code changes outside the isolated slice
- Progress:
  - 2026-03-24: extracted shared shell responsibilities into `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context}.js`, leaving `src/main/ui/js/app.js` focused on controller wiring plus shared UI workflows.
  - 2026-03-24: standardized route modules on a primary `render(ctx)` entrypoint without removing legacy named exports, which keeps lazy-loaded route contracts stable while enabling shell-side dispatch cleanup.
  - 2026-03-24: validated the shell extraction with `pytest -q -s src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_live_sync_session_frontend_contract.py src/main/test/test_team_capacity_frontend_contract.py src/main/test/test_*frontend_contract.py src/main/test/test_context_path_routing.py` -> `122 passed in 10.23s`.
  - 2026-03-25: extracted shell DOM lookup into `src/main/ui/js/shell/dom.js`, confirm/planning modal behavior into `src/main/ui/js/shell/modal-shell.js`, and the space-switcher workflow into `src/main/ui/js/shell/space-switcher.js`, reducing the shared shell contract inside `app.js` without changing route names, DOM IDs, or visible UX. Validated with `pytest -q -s src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_live_sync_session_frontend_contract.py src/main/test/test_space_governance_frontend_contract.py src/main/test/test_ui_legacy_cleanup_contract.py src/main/test/test_master_frontend_contract.py` -> `68 passed in 2.44s`, `npm run lint:ui`, and `pytest -q -s src/main/test` -> `423 passed, 1 skipped in 169.14s (0:02:49)`.

### `BATCH-004` SQL / Model / Schema / Audit-Log Contract Alignment
- Scope: `docs/sql/schema_oracle_ta.sql`, `docs/sql/migrations/*.sql`, `src/main/backend/app/models/*`, `src/main/backend/app/schemas/__init__.py`, `src/main/backend/app/services/audit_log.py`
- Entry path to narrow first: long-text/CLOB contract and stale-table removal contract
- Why now: SQL/docs alignment is a stronger production contract than implementation guesses
- Guardrails:
  - do not alter schema or migrations in the same batch unless the defect is clear and isolated
  - prefer tests and documentation alignment over speculative schema edits
- Exit criteria:
  - model/schema/DDl mismatches are either fixed safely or recorded precisely
  - stale candidates are classified as `active runtime`, `test-only`, `schema-doc-only`, or `stale candidate`
- Validation:
  - `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_projects.py src/main/test/test_solutions.py`
  - rerun full suite if shared models or schemas change
- Progress:
  - 2026-03-24: aligned Oracle string compilation in `src/main/backend/app/models/base.py` so explicit and implicit SQLAlchemy `String` columns both emit `VARCHAR2(... CHAR)`, matching the documented Oracle DDL contract instead of mixing `VARCHAR` and `VARCHAR2`.
  - 2026-03-24: fixed solution and subcomponent `github_repo_url` width drift in `src/main/backend/app/models/work.py`. Both columns now compile to the documented `VARCHAR2(1024 CHAR)` width instead of the default `255`.
  - 2026-03-24: removed the dormant `PasswordResetToken` model from `src/main/backend/app/models/identity.py` and `src/main/backend/app/models/__init__.py`. No in-branch runtime callers or Oracle DDL contract remained, so keeping it in metadata only made a stale table look supported.
  - 2026-03-24: fixed audit read-contract drift in `src/main/backend/app/schemas/__init__.py`. `ChangeLogRead` now includes `space_id`, so `/audit?all_spaces=true` responses preserve per-row space attribution.
  - 2026-03-24: validated the narrow contract batch with `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_users_space_scope.py` -> `42 passed in 41.97s`.

### `BATCH-005` Deliverables Backend: Projects, Solutions, Subcomponents, Phases
- Scope: `src/main/backend/app/routes/projects.py`, `solutions.py`, `subcomponents.py`, `phases.py`, and only the directly supporting shared helpers they use
- Entry path to narrow first: one import/export path or one CRUD + audit + cache path, not the whole domain at once
- Why now: core operational surface with import/export, audit, soft delete, and multi-space semantics
- Guardrails:
  - preserve import/export formats
  - preserve audit-write failure tolerance
  - preserve space scoping and soft-delete semantics
- Exit criteria:
  - one concrete issue set is closed with focused tests
  - no opportunistic refactor across unrelated routes
- Validation:
  - choose the smallest relevant subset from `test_projects.py`, `test_solutions.py`, `test_subcomponents.py`, `test_phases.py`, `test_import_export_projects.py`, `test_import_export_solutions.py`, `test_import_export_subcomponents.py`
  - rerun full suite if shared helpers or models are touched
- Progress:
  - 2026-03-24: fixed reopen-state drift in `src/main/backend/app/routes/solutions.py`. Direct updates and CSV import updates now clear `completed_at` when a solution moves back out of `complete`, preserving consistency between status, exports, and filtered list views. Validated with `pytest -q -s src/main/test/test_solutions.py src/main/test/test_import_export_solutions.py`.
  - 2026-03-24: fixed reopen-state drift in `src/main/backend/app/routes/subcomponents.py`. Direct updates, CSV import updates, and batch status updates now clear `completed_at` when a subcomponent is reopened instead of leaving stale completion metadata behind. Validated with `pytest -q -s src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py`.
  - 2026-03-25: fixed soft-deleted parent visibility drift in `src/main/backend/app/routes/projects.py`, `solutions.py`, `subcomponents.py`, and `phases.py`. Project deletes now invalidate and broadcast descendant `solutions`/`subcomponents` namespaces, and shared solution/subcomponent/phase lookup paths now require an active parent project so deleted projects no longer leave child reads or cached child lists/details behind. Validated with `pytest -q -s src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_phases.py` -> `44 passed in 45.38s`, `pytest -q -s src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `12 passed in 13.31s`, and `pytest -q -s src/main/test` from repo root -> `404 passed in 153.54s (0:02:33)`.
  - 2026-03-25: fixed solution-delete descendant cache drift in `src/main/backend/app/routes/solutions.py`. Soft-deleting a solution now invalidates and broadcasts descendant `subcomponents`, so cached `/subcomponents`, solution-scoped subcomponent lists, and subcomponent detail views do not stay visible until TTL expiry after the parent solution is deleted. Validated with `pytest -q -s src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py` -> `32 passed in 36.19s`.
  - 2026-03-25: fixed import-created parent cache drift in `src/main/backend/app/routes/solutions.py` and `subcomponents.py`. When CSV imports auto-create parent projects or solutions, they now invalidate and broadcast those parent namespaces instead of only the imported child namespace, so primed `/projects` and `/solutions` lists refresh immediately after import. Validated with `pytest -q -s src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py` -> `43 passed in 48.56s`.
  - 2026-03-25: fixed inherited subcomponent repo-cache drift in `src/main/backend/app/routes/solutions.py`. When an existing solution's `github_repo_url` changes through direct update or CSV import, the route now invalidates and broadcasts descendant `subcomponents` so cached effective repo links do not stay stale until TTL expiry. Validated with `pytest -q -s src/main/test/test_subcomponents.py src/main/test/test_solutions.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `45 passed in 50.37s` and `pytest -q -s src/main/test` -> `411 passed in 160.36s (0:02:40)`.
  - 2026-03-25: fixed subcomponent batch-response repo metadata in `src/main/backend/app/routes/subcomponents.py`. `/subcomponents/actions/batch` now resolves parent solution repo URLs before serializing rows, so inherited `effective_github_repo_url` and `repo_source` match the single-row detail/update paths. Validated with `pytest -q -s src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py` -> `19 passed in 21.75s`.
  - 2026-03-25: fixed direct completion-audit drift in `src/main/backend/app/routes/solutions.py` and `subcomponents.py`. Direct status patches now audit derived `completed_at`, and direct solution status patches also audit status-driven `current_phase`, matching the state transitions already recorded by the import and batch paths. Validated with `pytest -q -s src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_audit.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `51 passed in 55.52s` and `pytest -q -s src/main/test` -> `413 passed in 157.83s (0:02:37)`.

### `BATCH-006` Admin Domain: Spaces, Users, Teams, Access Control
- Scope: `src/main/backend/app/routes/spaces.py`, `users.py`, `teams.py`, plus only directly involved shared helpers
- Entry path to narrow first: one membership/role mutation path or one admin-only user operation
- Why now: access-control and membership correctness affect all space-scoped behavior
- Guardrails:
  - no role semantic changes without direct test proof
  - preserve last-admin protections and active-space repair behavior
- Exit criteria:
  - one access-control issue set is closed or explicitly deferred with proof
- Validation:
  - `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py`
  - rerun full suite if shared deps or models change
- Progress:
  - 2026-03-24: fixed team default-capacity precedence in `src/main/backend/app/routes/teams.py`. Team creation and soft-delete restoration now respect explicit `default_capacity_per_week` input when `default_capacity_fte_month` is omitted, instead of letting schema defaults erase the caller’s requested hours. Validated with `pytest -q -s src/main/test/test_teams_space_scope.py`.
  - 2026-03-24: fixed fail-late duplicate-space handling in `src/main/backend/app/routes/spaces.py`. Duplicate space names and slugs now return explicit `400` conflicts instead of raw server errors when the DB unique constraints fire. Validated with `pytest -q -s src/main/test/test_spaces.py`.
  - 2026-03-25: fixed a CSV import authz bypass in `src/main/backend/app/routes/users.py`. Non-global-admin actors can no longer use `/users/import` to modify or reactivate global-admin accounts, and the path now returns a row-level import error instead. Validated with `pytest -q -s src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py`.
  - 2026-03-25: fixed stale user-team linkage in `src/main/backend/app/routes/teams.py`. Standard team rename/delete mutations now keep active-space `User.team_tag` values in sync and invalidate both `teams` and `users` cache scopes, matching the behavior already enforced by the planning team-management path. Validated with `pytest -q -s src/main/test/test_teams_space_scope.py` and `pytest -q -s src/main/test/test_planning_work_allocation_people.py`.
  - 2026-03-25: tightened the same team-tag repair in `src/main/backend/app/routes/teams.py`. Team rename/delete now also updates inactive space memberships and invalidates `/users` caches across every membership space for affected shared users, so stale team names do not survive into later reactivations or other-space roster caches. Validated with `pytest -q -s src/main/test/test_teams_space_scope.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py` -> `28 passed in 29.55s` and `pytest -q -s src/main/test` -> `419 passed in 168.93s (0:02:48)`.
  - 2026-03-25: fixed cross-space user-roster cache invalidation in `src/main/backend/app/routes/users.py`. Direct user profile updates now invalidate every active membership space for the target user instead of only the admin's current space, so shared users do not leave stale `/users` and roster-export data behind in other spaces. Validated with `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `31 passed in 31.67s`.
  - 2026-03-25: fixed the same stale-cache class in `src/main/backend/app/routes/users.py` for `/users/import`. CSV imports now invalidate every active membership space for each imported user instead of only the admin's current space, so shared users do not leave stale roster data behind in other spaces after import-based edits. Validated with `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `32 passed in 32.53s`.
  - 2026-03-25: fixed the active-admin invariant in `src/main/backend/app/routes/spaces.py` and `src/main/backend/app/routes/users.py`. Last-admin checks now count only active user accounts, and user deactivation now refuses to orphan any space where the target is the last active `space_admin`, including cross-space cases. Validated with `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `34 passed in 35.19s` and `pytest -q -s src/main/test` -> `406 passed in 160.63s (0:02:40)`.
  - 2026-03-25: fixed the planning crossover bypass in `src/main/backend/app/routes/planning/work_allocation.py` by moving protected global-admin and last-admin mutation checks into `src/main/backend/app/services/user_admin_guards.py` and reusing them from both planning "people" routes and `/users`. Planning can no longer modify global-admin accounts as a non-global-admin actor, nor deactivate the last active global admin or `space_admin`. Validated with `pytest -q -s src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_spaces.py src/main/test/test_route_space_enforcement_gate.py` -> `30 passed in 30.91s` and `pytest -q -s src/main/test` -> `416 passed in 165.42s (0:02:45)`.

### `BATCH-007` Planning Backend And Report Generation
- Scope: `src/main/backend/app/routes/planning/{common,legacy_allocations,work_allocation}.py`, `src/main/backend/app/services/planning_work_allocation.py`, `src/main/backend/app/services/planning_report_pdf.py`, and the smallest necessary model/test surface
- Entry path to narrow first: one live work-allocation create/update/delete path or one planning-window path
- Why now: large mixed-responsibility hotspot with derived board objects and report generation
- Guardrails:
  - no planning API contract changes by default
  - keep derived board project/solution behavior intact unless a defect is proven
  - avoid mixing report cleanup with allocation mutation cleanup unless inseparable
- Exit criteria:
  - one planning issue set is fixed with focused validation
  - queue is updated to reflect what remains inside the `planning/` package
- Validation:
  - `pytest -q -s src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_planning_fte_month.py`
 - Progress:
 - 2026-03-25: fixed a protected user-mutation bypass in `src/main/backend/app/routes/planning/work_allocation.py`. Planning "people" update/delete now reuse shared guards in `src/main/backend/app/services/user_admin_guards.py`, so the planning surface can no longer modify global-admin accounts as a non-global-admin actor or deactivate the last active global admin / `space_admin`. Validated with `pytest -q -s src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_spaces.py src/main/test/test_route_space_enforcement_gate.py` -> `30 passed in 30.91s` and `pytest -q -s src/main/test` -> `416 passed in 165.42s (0:02:45)`.
  - 2026-03-25: fixed stale planning team-tag repair in `src/main/backend/app/routes/planning/work_allocation.py`. Planning team rename/delete now also repair inactive users' `team_tag` state and invalidate `/users` caches across every membership space for affected shared users, so planning no longer leaves latent team-name drift behind the standard `/teams` path. Validated with `pytest -q -s src/main/test/test_teams_space_scope.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py` -> `28 passed in 29.55s` and `pytest -q -s src/main/test` -> `419 passed in 168.93s (0:02:48)`.
  - rerun full suite if shared mutation/cache/runtime code changes
- Progress:
  - 2026-03-24: replaced `src/main/backend/app/routes/planning.py` with `src/main/backend/app/routes/planning/{common,legacy_allocations,work_allocation}.py`, preserving the same router export and public planning paths while splitting shared helpers from route groups.
  - 2026-03-24: moved work-allocation request/response models into `src/main/backend/app/schemas/planning.py` so the route package no longer embeds API schema definitions inline.
  - 2026-03-24: added `src/main/test/test_planning_router_composition.py` to lock the package-exported route surface, and validated with `pytest -q -s src/main/test/test_planning_fte_month.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_planning_router_composition.py` -> `14 passed in 15.62s`.

### `BATCH-008` Realtime, Cache, And Sync
- Scope: `src/main/backend/app/services/realtime.py`, `src/main/backend/app/services/smart_cache.py`, `src/main/backend/app/routes/_mutations.py`, `src/main/backend/app/routes/sync.py`
- Entry path to narrow first: one invalidation + websocket refresh path
- Why now: hidden in-memory state creates stale-data and cleanup risks that are easy to miss in later batches
- Guardrails:
  - no protocol changes without explicit test updates
  - preserve per-user/per-space connection limit behavior
- Exit criteria:
  - one cache or broadcast issue set is closed, and invalidation boundaries are explicit
- Validation:
  - `pytest -q -s src/main/test/test_realtime_and_sync.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py`
  - rerun full suite after any behavior change here
- Progress:
  - 2026-03-24: fixed unexpected websocket registration failure handling in `src/main/backend/app/routes/sync.py`. The route now closes with the existing server-busy code instead of returning without a close reason when `register()` fails unexpectedly. Validated with `pytest -q -s test/test_realtime_and_sync.py` from `src/main`.
  - 2026-03-24: fixed websocket limit config validation in `src/main/backend/app/services/realtime.py`. Invalid or non-positive websocket limit settings now fail explicitly instead of causing confusing live-sync runtime behavior. Validated with `pytest -q -s test/test_realtime_and_sync.py` from `src/main`.
  - 2026-03-24: fixed smart-cache env validation in `src/main/backend/app/services/smart_cache.py`. `SIPM_SMART_CACHE_ENABLED` now accepts standard boolean env forms and rejects invalid values, and `SIPM_SMART_CACHE_MAX_ENTRIES` now fails explicitly on non-integer values instead of silently falling back. Validated with `pytest -q -s src/main/test/test_smart_cache.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py`.
  - 2026-03-25: tightened smart-cache max-entry validation in `src/main/backend/app/services/smart_cache.py`. Non-positive `SIPM_SMART_CACHE_MAX_ENTRIES` values now fail explicitly instead of being silently coerced back to the cache floor. Validated with `pytest -q -s src/main/test/test_smart_cache.py src/main/test/test_teams_space_scope.py src/main/test/test_planning_work_allocation_people.py`.
  - 2026-03-25: fixed idle websocket pruning in `src/main/backend/app/services/realtime.py`. Stale sockets are now closed with reconnectable code `1001` before being removed from the registry, so the client can recover instead of holding an apparently-open dead connection. Validated with `pytest -q -s src/main/test/test_realtime_and_sync.py` and `pytest -q -s src/main/test/test_live_sync_session_frontend_contract.py`.
  - 2026-03-25: closed the batch with `pytest -q -s src/main/test/test_realtime_and_sync.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py` -> `31 passed in 18.58s`, followed by `pytest -q -s src/main/test` from `src/main` -> `397 passed in 139.28s (0:02:19)`.

### `BATCH-009` Frontend Route Modules, Markup, And Styles
- Scope: one route module at a time plus the smallest necessary shared shell or `index.html` / `styles.css` surface
- Entry path to narrow first: the largest route module that directly benefits from prior `app.js` cleanup
- Why now: after shell reduction, route modules can be normalized without fighting hidden global state
- Guardrails:
  - preserve established UI language
  - no sweeping CSS rewrite
  - keep route-module boundaries real, not cosmetic
- Exit criteria:
  - one route module becomes smaller, clearer, or less coupled with test-backed safety
- Validation:
  - route-specific frontend contract tests
  - `python3 scripts/check_route_module_test_mapping.py`
  - rerun full suite if shared shell or markup changes materially
- Progress:
  - 2026-03-25: split the deliverables route so `src/main/ui/js/routes/master.js` is now a thin route entrypoint and `src/main/ui/js/routes/master/table.js` owns deliverables table rendering and route-local bindings. Validated with `pytest -q -s src/main/test/test_master_frontend_contract.py src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py` -> `59 passed in 1.60s`, `python3 scripts/check_route_module_test_mapping.py`, and `pytest -q -s src/main/test` from `src/main` -> `398 passed in 138.29s (0:02:18)`.
  - 2026-03-25: split the planning, dashboard, and PM dashboard route monoliths into thin wrappers plus route-local modules, preserving the same route names and render-entry contracts. Validated with `pytest -q -s src/main/test/test_planning_header_compact_frontend_contract.py src/main/test/test_dashboard_frontend_contract.py src/main/test/test_pm_dashboard_frontend_contract.py src/main/test/test_pm_dashboard_space_scope_contract.py src/main/test/test_ui_route_modules_exports.py` -> green, `npm run lint:ui`, and `npm run test:ui`.
  - 2026-03-25: split `src/main/ui/styles.css` into imported partials under `src/main/ui/styles/{base.css,routes/*.css}` and updated the frontend contract harness to resolve imported CSS. Validated with `pytest -q -s src/main/test/test_calendar_frontend_contract.py src/main/test/test_dark_mode_theme_contract.py src/main/test/test_dashboard_frontend_contract.py src/main/test/test_deliverables_save_feedback_frontend_contract.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_kanban_frontend_contract.py src/main/test/test_master_frontend_contract.py src/main/test/test_modal_layout_frontend_contract.py src/main/test/test_planning_header_compact_frontend_contract.py src/main/test/test_pm_dashboard_frontend_contract.py src/main/test/test_space_governance_frontend_contract.py src/main/test/test_subcomponents_workbench_frontend_contract.py src/main/test/test_view_heading_frontend_contract.py` -> `154 passed in 7.45s`.

### `BATCH-010` Test Suite Quality And Coverage Gaps
- Scope: tests only, after structural hotspots have settled
- Entry path to narrow first: replace or supplement brittle string-contract coverage for the most changed surfaces
- Why now: test cleanup should follow behavior cleanup, not precede it blindly
- Guardrails:
  - do not churn stable tests without a clear value gain
  - preserve CI runtime where possible
- Exit criteria:
  - one meaningful coverage gap is closed or one noisy pattern is reduced without losing protection
- Validation:
  - run the touched test subset, then the full suite if shared fixtures or helpers change
- Progress:
  - 2026-03-25: expanded `src/main/test/test_route_space_enforcement_gate.py` to recurse into nested route packages, so the planning route split does not leave those protected endpoints outside the dependency-enforcement test.
  - 2026-03-25: expanded `src/main/test/test_observability.py` so the observability boundary is covered in both ASGI client modes: the default client still raises unhandled endpoint exceptions, and a non-raising client still exercises the logged `500` path. Validated with `pytest -q -s src/main/test/test_observability.py` -> `7 passed in 6.73s` and `pytest -q -s src/main/test` from `src/main` -> `399 passed in 138.93s (0:02:18)`.
  - 2026-03-25: updated the frontend contract harness to resolve imported stylesheet partials through `ui_style_contract.py`, keeping CSS contract tests meaningful after the stylesheet split instead of forcing styles back into one file. Validated with the `154`-test frontend contract slice plus `pytest -q -s src/main/test` -> `423 passed, 1 skipped in 169.14s (0:02:49)`.

## Rescan Checkpoints
- After `BATCH-003`, rerun the broad inventory, refresh the hotspot ranking, and update the top three queued batches.
- After `BATCH-006`, rerun the broad inventory and the stale-candidate classification for any files touched so far.
- Immediately rerun a broad rescan after any change in shared runtime, auth, schema, cache, or websocket behavior.
