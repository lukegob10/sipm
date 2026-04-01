# SIPM System Map

Date: 2026-03-20
Mode: `full-surface review`
Pass intent: broad setup pass with durable audit memory and no runtime-contract changes

## Baseline
- `python3 scripts/check_requirements_lock.py` -> `requirements.txt is up to date with requirements.in`
- `python3 scripts/check_route_module_test_mapping.py` -> exit `0`
- `python3 -c "import backend.main; print('ok')"` from `src/main` -> `ok`
- `pytest -q -s src/main/test` -> `423 passed, 1 skipped in 169.14s (0:02:49)`
- `npm run lint:ui` -> pass
- `npm run test:ui` -> `5 passed`

## Noise Exclusions For Active Review
- Exclude `.git/`, `.venv/`, `.pytest_cache/`, `htmlcov/`, `__pycache__/`, and `.auto-research/` from broad inventory decisions.
- Treat local `.env` and `.env.local` files as runtime inputs, not source-of-truth docs.
- Treat `find_stale_scripts.py` output as a shortlist only; in this repo it over-classifies active Python modules and tests as candidate scripts.

## Workflow And Tooling

### Workflow And Validation Spine
- Entry points: `.github/workflows/backend-tests.yml`, `scripts/check_requirements_lock.py`, `scripts/check_route_module_test_mapping.py`, `scripts/codebase_review.py`, `src/main/README.md`
- Depends on: `git`, `uv`, `pip`, `pytest`, `src/main/requirements.in`, `src/main/requirements.txt`, `src/main/ui/js/route-module-test-map.json`
- Used by: CI, local setup, every cleanup batch
- Tests: entire suite, `src/main/test/test_codebase_review_tooling.py`, `src/main/test/test_ui_route_module_test_mapping_gate.py`, `src/main/test/test_ui_route_modules_exports.py`
- Source of truth: CI workflow and `src/main/README.md`
- Risk: Medium. Repo-local review tooling now excludes git-ignored noise, but raw broad inventory helpers still need manual interpretation.
- Status: reviewed

### Repo Hygiene And Local Config Surface
- Entry points: `.gitignore`, local `.env` loading in `src/main/backend/main.py`
- Depends on: developer workstation state and environment-variable precedence
- Used by: local backend startup and tests that exercise env loading
- Tests: `src/main/test/test_db_config.py`
- Source of truth: `.gitignore`, `src/main/backend/main.py`, `src/main/test/test_db_config.py`
- Risk: Medium. Runtime behavior depends on local env files even though those files are excluded from git.
- Status: reviewed

## Backend Runtime And Shared Boundaries

### Backend Runtime Shell
- Entry points: `src/main/backend/main.py`, `/health`, SPA catch-all routes, FastAPI lifespan
- Depends on: env loader, `src/main/backend/app/paths.py`, `src/main/backend/app/routes/__init__.py`, `src/main/backend/app/auth/auth.py`, `src/main/backend/app/db/db.py`
- Used by: `uvicorn backend.main:app --reload --app-dir src/main`, import check, all API tests, frontend SPA delivery
- Tests: `src/main/test/test_seed_and_db.py`, `src/main/test/test_context_path_routing.py`, `src/main/test/test_db_config.py`
- Source of truth: `src/main/README.md`, `src/main/backend/main.py`, runtime tests
- Risk: High. Startup, context-path routing, and SPA fallback are shared failure surfaces; the test-mode AnyIO threadpool patch now restores on lifespan teardown instead of leaking mutated global state into later app contexts, runtime shell boolean env flags now parse standard truthy/falsey forms consistently, and the shell now carries request correlation plus a readiness probe instead of only a liveness endpoint.
- Status: reviewed; teardown leak and observability surface fixed on 2026-03-24

### Auth, Cookie, And Permission Boundary
- Entry points: `src/main/backend/app/auth/auth.py`, `src/main/backend/app/deps.py`, `src/main/backend/app/routes/auth.py`, `src/main/backend/app/security.py`
- Depends on: JWT settings, bcrypt, cookie path/context path, DB user lookup, audit log, space resolution
- Used by: all protected HTTP routes, websocket auth in `src/main/backend/app/routes/sync.py`
- Tests: `src/main/test/test_auth_and_deps.py`, `src/main/test/test_global_admin_management.py`, `src/main/test/test_route_space_enforcement_gate.py`
- Source of truth: route behavior, dependency helpers, auth tests
- Risk: High. This is a protected path with broad blast radius; invalid cookie SameSite configuration now fails during startup validation, `SameSite=None` now also fails fast unless secure cookies are enabled, `SIPM_SECURE_COOKIES` now parses standard boolean env values instead of silently treating `yes`/`1`/`on` as false, invalid numeric auth env values now fail with clear config errors instead of raw import-time `ValueError`s, unknown `ENV` profiles now default to non-dev auth safety instead of dev-like relaxed settings, invalid bcrypt rounds are now rejected at startup instead of failing later on the first password hash, negative auth/reset TTLs are now blocked during startup instead of producing already-expired tokens later, password-reset expiry overrides now reject out-of-range values instead of being silently clamped, password resets no longer bypass the minimum password length enforced at registration, and global-admin authz now normalizes legacy role formatting consistently instead of depending on one exact stored string.
- Status: reviewed; protected-path validation hardened and verified on 2026-03-25

### Space Resolution And Access Context
- Entry points: `src/main/backend/app/services/spaces.py`, `src/main/backend/app/deps.py`, `src/main/backend/app/routes/spaces.py`
- Depends on: `Space`, `SpaceMembership`, `User`, active space cookie/header rules
- Used by: auth active-space endpoints, all space-scoped routes, websocket space validation
- Tests: `src/main/test/test_spaces.py`, `src/main/test/test_space_isolation_strict.py`, `src/main/test/test_users_space_scope.py`, `src/main/test/test_teams_space_scope.py`
- Source of truth: service code and space-scope tests
- Risk: High. Space selection and role resolution are central to authorization semantics; explicit inaccessible space selection now fails closed instead of silently falling back to another space, and legacy global-admin role formatting now resolves through the same elevated path instead of silently downgrading access.
- Status: reviewed; fail-closed selection and global-admin normalization validated on 2026-03-25

### DB Session And TA/Oracle Runtime
- Entry points: `src/main/backend/app/runtime.py`, `src/main/backend/app/db/db.py`, `docs/sql/schema_oracle_ta.sql`
- Depends on: `ENV`, TAConnection, SQLAlchemy engine/session configuration, Oracle dialect behavior
- Used by: all non-test DB access, startup initialization, session dependency
- Tests: `src/main/test/test_db_config.py`, `src/main/test/test_seed_and_db.py`
- Source of truth: DB config code, schema docs, DB-focused tests
- Risk: High. Engine construction, pooling, and env interpretation affect every request; `ENV=local` now resolves consistently to `dev` across auth and TA/DB runtime instead of splitting profile behavior, `ENV=test` now resolves safely to `dev` on the TA side, unknown TA deployment profiles now fail explicitly instead of being passed through blindly, and invalid negative pool settings now fail fast instead of surfacing later inside SQLAlchemy pooling behavior.
- Status: reviewed; local profile mismatch fixed on 2026-03-23 and pool-range validation tightened on 2026-03-24

### Cache, Mutation, And Realtime Spine
- Entry points: `src/main/backend/app/services/smart_cache.py`, `src/main/backend/app/services/coordination.py`, `src/main/backend/app/routes/_mutations.py`, `src/main/backend/app/services/realtime.py`, `src/main/backend/app/routes/sync.py`
- Depends on: local cache payload storage, coordination backend scope versions/pub-sub, websocket registry, route mutation helpers, space IDs
- Used by: mutation endpoints across projects, solutions, spaces, teams, planning, and websocket refresh consumers
- Tests: `src/main/test/test_realtime_and_sync.py`, planning live-refresh tests in `src/main/test/test_planning_work_allocation_people.py`, cache invalidation tests in `src/main/test/test_spaces.py` and `src/main/test/test_teams_space_scope.py`
- Source of truth: service code and realtime/cache tests
- Risk: High. Shared invalidation and websocket broadcast logic can create hidden stale-state failures; websocket limit settings and smart-cache env flags are now fail-fast validated instead of silently accepting invalid runtime values, smart-cache max entries no longer silently turns `0` or negative values back into the default cache floor, idle websocket pruning now closes stale sockets with a reconnectable close code instead of silently dropping them from the server registry, and cross-worker invalidation/broadcast now depends on the runtime coordination backend.
- Status: reviewed; `BATCH-008` closed on 2026-03-25 with fail-fast cache config validation, explicit reconnectable idle websocket closure, Redis-backed coordination support for stage/prod, and a green regression pass

## Data And Domain Contracts

### Models And Shared Schemas
- Entry points: `src/main/backend/app/models/`, `src/main/backend/app/schemas/__init__.py`, `src/main/backend/app/utils/__init__.py`
- Depends on: SQLAlchemy metadata, enum definitions, LOB/text coercion helpers, Oracle table naming helpers
- Used by: all route handlers and DB writes/reads
- Tests: `src/main/test/test_models_schema_contract.py`
- Source of truth: model definitions, read/write schemas, schema contract tests
- Risk: High. Long-text handling, enum coercion, and metadata alignment are system-wide contracts.
- Status: reviewed; Oracle string compilation now stays on `VARCHAR2`, solution/subcomponent repo URL columns now match the documented `1024` width, the dormant `PasswordResetToken` metadata surface has been removed, and schema-doc alignment is now regression-tested against live metadata

### SQL Schema And Migrations
- Entry points: `docs/sql/schema_oracle_ta.sql`, `docs/sql/migrations/*.sql`
- Depends on: Oracle deployment assumptions and migration history
- Used by: manual DB alignment, Oracle runtime expectations, model/schema contract review
- Tests: indirectly covered by `src/main/test/test_models_schema_contract.py`, `src/main/test/test_projects.py`, `src/main/test/test_solutions.py`
- Source of truth: `docs/sql/schema_oracle_ta.sql` plus migration intent comments
- Risk: High. SQL docs are a stronger deployment contract than implementation guesses.
- Status: reviewed; doc/model table, column, unique-constraint, and index alignment is now regression-tested

### Audit Log Contract
- Entry points: `src/main/backend/app/services/audit_log.py`, `src/main/backend/app/routes/audit.py`
- Depends on: `ChangeLog` model, LOB/text coercion, caller transaction behavior
- Used by: authz denials, projects, solutions, subcomponents, phases, user/password reset flows
- Tests: `src/main/test/test_audit.py`, audit-failure tolerance tests in projects and solutions
- Source of truth: audit route/service code and tests
- Risk: Medium. Best-effort logging must not corrupt primary writes.
- Status: reviewed; `ChangeLogRead` now exposes `space_id`, so `/audit?all_spaces=true` responses remain attributable, and audit writes now inherit the active `X-Request-ID` via request context instead of bulk routes minting unrelated UUIDs

## Core Backend Domains

### Deliverables Domain: Projects, Solutions, Subcomponents, Phases
- Entry points: `src/main/backend/app/routes/projects/{common,read,write,import_export}.py`, `src/main/backend/app/routes/solutions/{common,read,write,import_export}.py`, `src/main/backend/app/routes/subcomponents/{common,read,write,import_export}.py`, `src/main/backend/app/routes/phases.py`
- Depends on: shared deps, models, schemas, `audit_log`, `github_repo_urls`, `smart_cache`, mutation helpers, enums
- Used by: master view, dashboard views, import/export workflows, activity feeds
- Tests: `src/main/test/test_projects.py`, `src/main/test/test_solutions.py`, `src/main/test/test_subcomponents.py`, `src/main/test/test_phases.py`, import/export tests
- Source of truth: route contracts and domain tests
- Risk: High. This is the main operational surface and touches import/export, soft delete, audit, and multi-space behavior; solution and subcomponent mutation paths now keep `completed_at` consistent with reopened statuses across direct updates, CSV imports, and subcomponent batch updates, soft-deleted projects now consistently hide descendant solutions, subcomponents, and solution-phase surfaces instead of leaving child reads or cached child lists/details behind, solution deletion now clears descendant subcomponent caches/broadcasts instead of leaving stale child views behind until TTL expiry, CSV imports that auto-create parent projects or solutions now invalidate those parent caches instead of leaving `/projects` or `/solutions` stale until TTL expiry, solution repo URL updates/imports now refresh descendant subcomponent caches so inherited effective repo links do not stay stale until TTL expiry, subcomponent batch responses now preserve inherited repo metadata, direct solution/subcomponent status patches now audit the derived completion transition instead of dropping it from the change log, and the old route monoliths are now split into read/write/import-export/common packages so future fixes do not have to cut across thousand-line mixed-responsibility files.
- Status: reviewed; `BATCH-005` closed on 2026-03-25 after completion-state, descendant-visibility, cache-invalidation, inherited-repo, payload-shape, direct-audit, and route-package split fixes

### Admin Domain: Spaces, Users, Teams
- Entry points: `src/main/backend/app/routes/spaces.py`, `users.py`, `teams.py`
- Depends on: `SpaceContext`, `User`, `SpaceMembership`, `Team`, `TeamMember`, password reset service, cache invalidation
- Used by: admin views, active-space switching, member management, team-capacity planning setup
- Tests: `src/main/test/test_spaces.py`, `src/main/test/test_users_space_scope.py`, `src/main/test/test_teams_space_scope.py`, `src/main/test/test_global_admin_management.py`
- Source of truth: route contracts and admin tests
- Risk: High. Role changes and membership changes directly affect access control; team creation/restoration now honors explicit per-week default capacity inputs, duplicate space-name conflicts now fail with clean client errors instead of uncaught server errors, CSV user import no longer bypasses the global-admin account protection enforced by direct user-update routes, the standard `/teams` rename/delete path now keeps `User.team_tag` values in sync even for inactive space memberships and invalidates shared-user roster caches across every membership space instead of leaving hidden stale team names behind, direct user updates and CSV user imports now invalidate user-list caches across every active membership space instead of only the admin's current space, and the last-admin/global-admin deactivation guards now apply consistently across both `/users` and planning "people" mutations so planning cannot sidestep protected account rules.
- Status: reviewed; `BATCH-006` closed on 2026-03-25 and the planning crossover bypass was closed on 2026-03-25

### Planning And Work Allocation Domain
- Entry points: `src/main/backend/app/routes/planning/{common,legacy_allocations,work_allocation}.py`, `src/main/backend/app/services/planning_work_allocation.py`, `src/main/backend/app/services/planning_report_pdf.py`, `src/main/backend/app/schemas/planning.py`
- Depends on: planning models, space/user/team membership, bootstrap password hashing, mutation helpers, cache/realtime
- Used by: `#/planning`, planning windows, allocations, PDF report generation, derived board project/solution records
- Tests: `src/main/test/test_planning_work_allocation_people.py`, `src/main/test/test_planning_work_allocation_tasks.py`, `src/main/test/test_planning_work_allocation_report.py`, `src/main/test/test_planning_fte_month.py`
- Source of truth: route behavior and planning tests
- Risk: High. Planning remains a public API hotspot, but shared helpers, legacy allocation/window routes, and work-allocation board routes are now separated so future fixes do not have to cut across one monolith; planning "people" mutations now reuse the same protected global-admin and last-admin deactivation guards as `/users`, and planning team rename/delete now also repairs inactive/shared-user `team_tag` state instead of leaving stale team names latent in later roster reads.
- Status: reviewed; route/package split completed on 2026-03-24 and protected user-mutation consistency tightened on 2026-03-25

### Sync And Websocket Boundary
- Entry points: `src/main/backend/app/routes/sync.py`, `src/main/backend/app/services/realtime.py`
- Depends on: auth dependency behavior, active space resolution, websocket connection limits, refresh broadcasts
- Used by: live-refresh UI flows and cache invalidation consumers
- Tests: `src/main/test/test_realtime_and_sync.py`, live-sync frontend contract tests
- Source of truth: websocket route/service code and realtime tests
- Risk: High. Hidden state lives in process memory and is hard to reason about without a narrow pass; unexpected websocket registration failures now close with an explicit server-busy code instead of dropping out without a close reason, websocket limit settings now fail fast on invalid values instead of producing confusing runtime behavior, and idle-pruned sockets now close explicitly so the client can reconnect instead of sitting on a stale open connection.
- Status: reviewed; narrow failure-path fixes applied through 2026-03-25

## Frontend Surfaces

### Frontend Shell And Shared State
- Entry points: `src/main/ui/index.html`, `src/main/ui/js/app.js`, `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context,dom,modal-shell,space-switcher,topbar-create}.js`, `src/main/ui/styles.css`, `src/main/ui/styles/base.css`, `src/main/ui/styles/routes/*.css`
- Depends on: DOM IDs defined in `index.html`, context-path derivation, route lazy-loader registry, shared modals, API and websocket URLs
- Used by: every SPA screen
- Tests: `src/main/test/test_frontend_ux_improvement_contract.py`, `src/main/test/test_context_path_routing.py`, multiple frontend contract tests
- Source of truth: SPA shell files and frontend contract tests
- Risk: High. Shared shell state still exists, but path/routing/session/live-sync/data-loading responsibilities are now split into dedicated shell modules instead of being concentrated in one file; DOM lookup, confirm/planning modal orchestration, and the space-switcher workflow are now also isolated in shell-local modules, and the dead duplicate inline live-sync implementation has been removed so `shell/live-sync.js` is the single authority.
- Status: reviewed; shell extraction continued through 2026-03-25 with dedicated `dom.js`, `modal-shell.js`, `space-switcher.js`, and `topbar-create.js` modules, while `styles.css` now serves as a compatibility import surface over split base/route partials instead of one monolithic stylesheet

### Frontend Route Modules
- Entry points: `src/main/ui/js/routes/*.js`, `src/main/ui/js/route-module-test-map.json`
- Depends on: lazy import registry in `src/main/ui/js/app.js`, shared DOM/state helpers, route-specific markup already present in `index.html`
- Used by: deliverables, planning, dashboards, spaces, access, calendar, kanban, team-capacity views
- Tests: `src/main/test/test_ui_route_modules_exports.py`, `src/main/test/test_ui_route_module_test_mapping_gate.py`, route-specific frontend contract tests
- Source of truth: route modules, export/mapping tests, route-specific contract tests
- Risk: Medium. Route modules still depend on shared shell state and static view roots, but the main route hotspots are now split into route-local modules: deliverables (`master/table.js`), planning (`planning/{state,common,storage,selection,api,render,interactions}.js`), dashboard (`dashboard/{common,prefs,modal,interactions,render}.js`), and PM dashboard (`pm-dashboard/{analytics,storage,interactions,render}.js`).
- Status: reviewed; wrapper/route-local ownership completed through 2026-03-25 with focused frontend contract validation and a green full-suite pass

## Validation Surfaces

### Test Harness
- Entry points: `src/main/test/conftest.py`, `src/main/test/*.py`
- Depends on: FastAPI app overrides, in-memory test DB setup, route-module mapping script, repo-level Node toolchain for frontend lint/unit/browser validation
- Used by: all validation during cleanup
- Tests: Python suite plus `npm run lint:ui`, `npm run test:ui`, and Playwright smoke coverage
- Source of truth: test files, `package.json`, and CI workflow
- Risk: Medium. The suite is stronger now that frontend lint/unit/smoke entrypoints exist, route/style contract tests can resolve imported stylesheet partials, and the route split surfaces are covered by focused contracts; local browser execution still depends on Playwright system libraries and the smoke surface remains intentionally small compared to the Python contract suite.
- Status: reviewed; Node/Vitest/Playwright tooling and the imported-stylesheet contract harness were in place by 2026-03-25

## Not Present Or Minimal
- Infra/deploy surface: not present in repo
- Observability surface: lightweight only; request-ID logging and `/health/ready` now exist, but no repo-visible metrics or tracing setup was found

## Remaining Enterprise Gaps
- Hotspot concentration remains the main maintainability risk. The highest-leverage files are still `src/main/ui/js/app.js`, `src/main/ui/styles/routes/workbench-planning-admin.css`, `src/main/backend/app/routes/planning/work_allocation.py`, and `src/main/ui/js/routes/pm-dashboard/render.js`.
- Repo governance is still thin. The codebase now has durable audit memory, but it still needs explicit contribution rules, ownership defaults, environment templates, and documented quality gates so repo expectations are not tribal knowledge.
- The code-review workspace needs a forward-looking operating layer. `01-review-ledger.md` and `03-fix-queue.md` preserve cleanup history well, but enterprise-quality execution now depends on an epic roadmap, a quality-gates definition, and an architecture-decision register.
- Observability remains repo-light. Request correlation, readiness, and structured logs exist, but there is still no repo-visible metrics, tracing, or production-grade incident documentation surface.
- Branding drift remains minor but real until the remaining `Jira-lite` metadata/comments are removed from the backend runtime shell.
