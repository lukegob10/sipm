# SIPM Dependency Map

Date: 2026-03-20
Scope: broad dependency map for the initial `clean-code-review` pass

## Top-Level Runtime Flow

```text
Browser
  -> src/main/ui/index.html
  -> src/main/ui/js/app.js
  -> lazy route module in src/main/ui/js/routes/*.js
  -> buildApiUrl()/buildWsUrl()
  -> /project-manager/api/*
  -> src/main/backend/app/routes/__init__.py
  -> deps/auth/space context
  -> route handler
  -> model/service/cache/realtime layer
  -> TAConnection / Oracle via SQLAlchemy
```

## Mutation And Refresh Flow

```text
HTTP mutation route
  -> DB write
  -> src/main/backend/app/routes/_mutations.py
  -> src/main/backend/app/services/smart_cache.py invalidate_space()
  -> src/main/backend/app/services/realtime.py schedule_broadcast()
  -> /api/ws websocket clients
  -> frontend refresh handlers in app.js / route modules
```

## Backend Map

### Runtime Shell
- `src/main/backend/main.py`
  - Loads `.env` and `.env.local` from `src/main/` and repo root.
  - Validates auth configuration during lifespan.
  - Initializes DB unless startup is disabled for tests.
  - Mounts API router and SPA/static file behavior.
- `src/main/backend/app/paths.py`
  - Defines `APP_CONTEXT_PATH`, `COOKIE_PATH`, `API_PREFIX`, docs paths, reset-password path.

### Router Aggregation
- `src/main/backend/app/routes/__init__.py`
  - Public router: `auth`
  - Protected router behind `require_user`: `projects`, `solutions`, `phases`, `subcomponents`, `teams`, `spaces`, `users`, `planning`, `audit`
  - Unprotected websocket router: `sync`

### Shared Dependency Chain
- `src/main/backend/app/deps.py`
  - `get_db()` -> `src/main/backend/app/db/db.py:get_session()`
  - `require_user()` -> `auth.decode_token()` + DB `User` lookup + token revocation checks
  - `current_space()` -> `services.spaces.resolve_active_space_context()`
  - `require_space_role()` and `require_global_admin()` -> audit denied access through `services.audit_log.log_changes()`
  - global-admin authz now shares normalized role matching with `services.spaces`

### Auth And Security
- `src/main/backend/app/routes/auth.py`
  - Depends on `src/main/backend/app/auth/auth.py` for hashing, token creation/decoding, cookies
  - Depends on `src/main/backend/app/services/password_reset.py` for temp/reset flows
  - Depends on `src/main/backend/app/services/spaces.py` for active-space resolution
- `src/main/backend/app/security.py`
  - Shared security-flavored `HTTPException` builder and message normalization

### DB And Environment
- `src/main/backend/app/runtime.py`
  - Maps `ENV` aliases to TA connection profiles
- `src/main/backend/app/db/db.py`
  - Builds SQLAlchemy engine with TAConnection creator
  - Owns sessionmaker singleton and optional `init_db(create_schema=True)`
- `docs/sql/schema_oracle_ta.sql`
  - External DDL contract for Oracle deployments

### Data Contracts
- `src/main/backend/app/models/base.py`
  - Common metadata, timestamp mixin, soft-delete mixin, Oracle string compiler override
- `src/main/backend/app/models/identity.py`
  - `User`, `Space`, `SpaceMembership`, `ChangeLog`, `Team`, `TeamMember`
- `src/main/backend/app/models/work.py`
  - `Project`, `Solution`, `Phase`, `SolutionPhase`, `Subcomponent`, `ResourceAllocation`, `PlanningWindow`, `SolutionWeeklySnapshot`, `ExternalRef`
- `src/main/backend/app/schemas/__init__.py`
  - Read/write contracts for API surfaces
  - Uses `src/main/backend/app/utils/read_text_value()` to coerce Oracle-style LOB values

### Route Clusters
- `projects.py`
  - Depends on: `Project`, `User`, utils parsing helpers, `safe_log_changes`, `smart_cache`, `realtime`
  - Touches: list/create/update/delete/import/export of projects, including descendant `solutions`/`subcomponents` cache invalidation and broadcasts on project delete
- `solutions.py`
  - Depends on: `Project`, `Solution`, `Phase`, `SolutionPhase`, `User`, `github_repo_urls`, `safe_log_changes`, `smart_cache`
  - Touches: solution CRUD, phase enablement, import/export, RAG behavior, and active-parent filtering so deleted projects hide child solution reads
- `subcomponents.py`
  - Depends on: `Project`, `Solution`, `Subcomponent`, `ChangeLog`, `User`, `github_repo_urls`, `log_changes`, `smart_cache`
  - Touches: subcomponent CRUD, batch actions, activity, import/export, and active-parent filtering so deleted projects hide child subcomponent reads
- `phases.py`
  - Depends on: `Phase`, `Project`, `Solution`, `SolutionPhase`, `log_changes`
  - Touches: solution-phase reads/writes, including active-parent filtering so deleted projects hide descendant phase surfaces
- `spaces.py`
  - Depends on: `Space`, `SpaceMembership`, `User`, `services.spaces`, `smart_cache`
  - Touches: space CRUD plus membership CRUD, including last-admin enforcement that now counts only active user accounts
- `users.py`
  - Depends on: `User`, `SpaceMembership`, `hash_bootstrap_password`, `password_reset`, `log_changes`, `smart_cache`
  - Touches: space-scoped roster read/update, user import/export, global-admin role management, password reset issuance, cross-membership user-cache invalidation on profile edits and CSV imports, and user-deactivation guards that prevent orphaning any admin-managed space
- `teams.py`
  - Depends on: `Team`, `TeamMember`, `SpaceMembership`, `User`, `smart_cache`
  - Touches: team CRUD, team-member CRUD, active-space user team-tag synchronization on rename/delete
- `planning/`
  - Depends on: `PlanningWindow`, `ResourceAllocation`, `SpaceMembership`, `Subcomponent`, `Team`, `User`
  - Depends on: `planning_work_allocation`, `planning_report_pdf`, `_mutations`, `smart_cache`, `hash_bootstrap_password`
  - Touches: legacy resource allocations, planning windows, work-allocation teams/people/tasks/allocations, report PDF
- `audit.py`
  - Depends on: `ChangeLog`
- `sync.py`
  - Depends on: `authenticate_access_token()`, `resolve_active_space_context()`, `services.realtime`

### Shared Services
- `src/main/backend/app/services/audit_log.py`
  - Called by authz helpers and most write paths
  - Offers nested-transaction-safe `safe_log_changes()`
- `src/main/backend/app/services/spaces.py`
  - Owns default-space creation, space membership repair, active-space selection
- `src/main/backend/app/services/smart_cache.py`
  - In-memory scoped cache keyed by endpoint, params, space, user, role, and scope versions
- `src/main/backend/app/services/realtime.py`
  - In-memory websocket registry, broadcast refresh, connection limits, idle pruning, and reconnectable closure of stale sockets
- `src/main/backend/app/services/planning_work_allocation.py`
  - Planning-specific derived board project/solution, month parsing, user/team lookup, SOEID generation
- `src/main/backend/app/services/planning_report_pdf.py`
  - Planning PDF rendering boundary
- `src/main/backend/app/services/password_reset.py`
  - Temp-password reset orchestration via `User.temp_password_*` fields; no separate reset-token table is active in runtime metadata
- `src/main/backend/app/services/github_repo_urls.py`
  - URL normalization/validation for solution and subcomponent repo links

## Frontend Map

### Shell
- `src/main/ui/index.html`
  - Declares the authenticated shell, modal shells, auth screens, shared IDs, and view containers.
- `src/main/ui/styles.css`
  - Global styling for shell, modals, tables, dashboards, planning, auth, and admin views.
- `src/main/ui/js/app.js`
  - Bootstraps the shell, shared DOM lookup table, route-module lazy loading, and shared UI workflows.
  - Delegates context-path/API/WS URL building, routing, session/auth, live sync, and shared data loading to `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context}.js`.
- `src/main/ui/js/routes/master/table.js`
  - Route-local helper for deliverables table markup and filter/select-all bindings used by `src/main/ui/js/routes/master.js`

### Lazy Route Registry In `app.js`
- `master` -> `src/main/ui/js/routes/master.js`
- `subcomponents-workbench` -> `src/main/ui/js/routes/subcomponents-workbench.js`
- `dashboard` -> `src/main/ui/js/routes/dashboard.js`
- `pm-dashboard` -> `src/main/ui/js/routes/pm-dashboard.js`
- `kanban` -> `src/main/ui/js/routes/kanban.js`
- `calendar` -> `src/main/ui/js/routes/calendar.js`
- `planning` -> `src/main/ui/js/routes/planning.js`
- `team-capacity` -> `src/main/ui/js/routes/team-capacity.js`
- `spaces` -> `src/main/ui/js/routes/spaces.js`
- `access` -> `src/main/ui/js/routes/access.js`

### Route Module Contract
- `src/main/ui/js/route-module-test-map.json`
  - Maps every route module to at least one test file
- `scripts/check_route_module_test_mapping.py`
  - Fails CI if a route module lacks mapped tests or the map points at missing files
- `src/main/test/test_ui_route_modules_exports.py`
  - Verifies exported entrypoints and loader registry presence
- `src/main/test/test_master_frontend_contract.py`
  - Verifies the deliverables route entrypoint still delegates to its route-local table helper and preserves name-link/repo/filter contracts

## SQL And Migration Touchpoints
- `docs/sql/schema_oracle_ta.sql`
  - Current Oracle schema contract
- `docs/sql/migrations/2026-03-13_solution_subcomponent_github_repo_url.sql`
  - Added GitHub repo URL support
- `docs/sql/migrations/2026-03-17_reassert_long_text_clob_columns.sql`
  - Reasserted audit/project/solution long-text columns as CLOB
- `docs/sql/migrations/2026-03-18_drop_stale_document_digest_tables.sql`
  - Removed stale document digest tables
- `src/main/test/test_models_schema_contract.py`
  - Confirms stale digest models/tables are absent from SQLAlchemy metadata

## Validation And Workflow Dependencies
- CI uses `.github/workflows/backend-tests.yml`
  - `python scripts/check_requirements_lock.py`
  - install from `src/main/requirements.txt`
  - import check from `src/main`
  - `python scripts/check_route_module_test_mapping.py`
  - `pytest -q -s src/main/test`
- `scripts/codebase_review.py`
  - `inventory` -> repo-local active surface inventory based on `git ls-files --cached --others --exclude-standard`
  - `stale-scripts` -> repo-local stale-script scan limited to actual `scripts/` candidates
- Local run path in `src/main/README.md`
  - `python3 -m venv .venv`
  - `pip install -r src/main/requirements.txt`
  - `uvicorn backend.main:app --reload --app-dir src/main`

## Dependency Hotspots To Prioritize
- `src/main/ui/js/app.js` (`8246` lines)
- `src/main/ui/js/routes/planning.js` (`1960` lines)
- `src/main/ui/js/routes/dashboard.js` (`1415` lines)
- `src/main/ui/js/routes/pm-dashboard.js` (`1072` lines)
- `src/main/backend/app/routes/subcomponents.py` (`1014` lines)
- `src/main/backend/app/routes/solutions.py` (`1001` lines)
