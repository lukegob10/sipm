# SIPM Review Ledger

Date: 2026-03-20
Mode: `full-surface review`
Pass scope: broad setup pass, system mapping, baseline validation, first ranked queue

## Validation Checkpoint

| Command | Result |
| --- | --- |
| `python3 scripts/check_requirements_lock.py` | `requirements.txt is up to date with requirements.in` |
| `python3 scripts/check_route_module_test_mapping.py` | exit `0` |
| `python3 scripts/codebase_review.py inventory` | active surface inventory uses only git-active files and excludes git-ignored noise |
| `python3 scripts/codebase_review.py stale-scripts` | only repo `scripts/` files scanned; all three current scripts are referenced |
| `pytest -q -s src/main/test/test_codebase_review_tooling.py` | `3 passed in 2.08s` |
| `python3 -c "import backend.main; print('ok')"` from `src/main` | `ok` |
| `pytest -q -s src/main/test` | `423 passed, 1 skipped in 169.14s (0:02:49)` |
| `npm run lint:ui` | pass |
| `npm run test:ui` | `5 passed` |

## Deferred Review Queue

- `docs/codebase-review/04-review-required.md` now holds medium+, DB-related, and contract-changing items that are intentionally skipped during the autonomous low-risk pass.

## Findings

| ID | Area | Severity | Priority | Status | Evidence | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `CCR-000` | Workflow / audit memory | Medium | should-fix | fixed now | No repo-tracked audit workspace existed before this pass, so broad findings would have been chat-only and easy to lose. | Added `docs/codebase-review/00-system-map.md`, `01-review-ledger.md`, `02-dependency-map.md`, and `03-fix-queue.md`. No runtime behavior changed. |
| `CCR-001` | Workflow / audit tooling | Medium | should-fix | fixed now | Raw broad inventory helpers counted `htmlcov/*` and over-classified active files as stale candidates. | Added `scripts/codebase_review.py` to inventory only git-active files and to scan only repo `scripts/` entries for stale-candidate checks. Validated with `test_codebase_review_tooling.py` and reran the existing workflow gates. |
| `CCR-002` | Frontend shell | High | should-fix | fixed now | `src/main/ui/js/app.js` was a `9003` line shell hotspot that owned route loading, DOM lookup, shared state, modal orchestration, API URL construction, and websocket wiring. | Extracted shell responsibilities into `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context,dom,modal-shell,space-switcher,topbar-create}.js`, standardized route-module `render(ctx)` entrypoints, split major route hotspots into route-local modules, and validated with focused frontend contract suites, `npm run lint:ui`, `npm run test:ui`, and a green full Python suite. |
| `CCR-003` | Planning backend | High | should-fix | fixed now | `src/main/backend/app/routes/planning.py` was a `1515` line mixed-responsibility public API hotspot that bundled legacy allocations, work-allocation board logic, summary/report flows, and mutation/cache orchestration. | Replaced it with a `planning/` route package plus `src/main/backend/app/schemas/planning.py`, and validated with the planning suite plus `test_planning_router_composition.py`. |
| `CCR-004` | Protected runtime / auth / DB / space boundary | High | must-fix | fixed now | `src/main/backend/main.py`, `deps.py`, `auth.py`, `db.py`, `runtime.py`, `services/spaces.py`, and `security.py` form a single protected seam for startup, cookies, JWTs, DB sessions, and active-space resolution. | Narrow protected-path fixes are now backed by focused auth/db/runtime tests plus route-space enforcement coverage, including active-space fail-closed behavior, startup config hardening, legacy global-admin role normalization, and CSV import authz checks. |
| `CCR-005` | Data contracts | High | must-fix | fixed now | SQLAlchemy models and Pydantic schemas are now locked against the documented Oracle contract. Oracle `VARCHAR2` compilation drift, solution/subcomponent `github_repo_url` width mismatches, stale `PasswordResetToken` metadata, and missing audit `space_id` read coverage were fixed, and the schema doc is now regression-tested against live metadata. | `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_users_space_scope.py` -> `56 passed in 45.67s` |
| `CCR-006` | Frontend route split validation | Medium | should-fix | fixed now | The route-module gate initially proved only exports/mappings, not whether the split boundaries were real or whether route-local ownership had actually moved out of the shell. | Deliverables, planning, dashboard, and PM dashboard are now split into route-local modules; shell DOM/modal/space-switcher ownership is extracted; imported stylesheet contracts are covered by focused frontend tests; and route/module coverage is backed by `scripts/check_route_module_test_mapping.py`, route export tests, `154` focused frontend contract tests, `npm run lint:ui`, `npm run test:ui`, and a green full Python suite. |
| `CCR-007` | Observability / operations | Medium | advisory | fixed now | Repo inventory initially found no observability surface beyond `/health`; no repo-visible request correlation, structured request/error logging, readiness probe, or operator docs were present. | Added request-ID middleware, structured logging, `/health/ready`, DB readiness checks, and README ops documentation. Validated with `test_observability.py`, `test_context_path_routing.py`, and `test_seed_and_db.py`. |
| `CCR-008` | Test strategy | Medium | advisory | fixed now | The repo originally had no real frontend execution gate, and much of the UI protection depended on source-text contracts alone. | Added repo-level frontend lint/unit/browser tooling (`eslint`, `vitest`, Playwright smoke harness), strengthened observability/runtime tests, and updated style-contract helpers to follow imported stylesheet partials without losing coverage. Full suite, frontend lint, and frontend unit tests are green; the remaining limitation is only that the browser smoke surface is intentionally small. |
| `CCR-009` | Audit execution context | Medium | advisory | out of scope | `git status --short` showed the worktree already dirty across backend, frontend, tests, and schema files before this pass started. | This run only added new audit artifacts and did not modify existing dirty files. |

## Closure Ledger
- Fixed now: `CCR-000`, `CCR-001`, `CCR-002`, `CCR-003`, `CCR-004`, `CCR-005`, `CCR-006`, `CCR-007`, `CCR-008`
- Out of scope: `CCR-009`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: shared runtime coordination and audit request correlation

- Fixed: `src/main/backend/app/services/coordination.py` now provides a shared coordination backend with `memory` and `redis` modes; `smart_cache.py` now reads scope versions through that backend, `realtime.py` now uses it for cross-worker refresh fanout, and `main.py` starts/stops the realtime listener on lifespan boundaries.
- Fixed: `src/main/backend/app/request_context.py` and `services/audit_log.py` now propagate the inbound `X-Request-ID` into audit rows by default, and bulk project/solution/subcomponent imports no longer mint unrelated UUIDs for audit correlation.
- Why it mattered: cache invalidation and websocket refresh were previously worker-local only, and audit rows from bulk writes could not be traced back to the originating request log line.
- Validation:
  - `pytest -q -s src/main/test/test_observability.py src/main/test/test_realtime_and_sync.py src/main/test/test_smart_cache.py src/main/test/test_request_audit_correlation.py src/main/test/test_coordination_backend.py` -> `30 passed, 1 skipped in 10.72s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: frontend validation tooling and dead shell-state cleanup

- Fixed: repo-level Node tooling now exists via `package.json`, `eslint.config.js`, `vitest.config.js`, `playwright.config.js`, and `scripts/run_ui_smoke_app.py`; the CI workflow now installs Node, runs frontend lint/unit checks, provisions Redis, and invokes Playwright smoke coverage.
- Fixed: `src/main/ui/js/app.js` no longer carries the dead duplicate inline live-sync retry/recovery implementation; `src/main/ui/js/shell/live-sync.js` is now the only live-sync owner.
- Why it mattered: the repo previously had no real frontend execution gate in CI, and `app.js` still carried unreachable websocket code that referenced symbols the shell no longer owned.
- Validation:
  - `npm run lint:ui`
  - `npm run test:ui`
  - `pytest -q -s src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_ui_route_modules_exports.py src/main/test/test_live_sync_session_frontend_contract.py src/main/test/test_master_frontend_contract.py` -> green

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / active-space enforcement

- Fixed: `src/main/backend/app/deps.py` no longer lets `current_space` silently fall back to another accessible space when the request explicitly sends an invalid `X-Space-Id` or `active_space_id`; it now returns `403 FORBIDDEN_SPACE` instead.
- Why it mattered: before this fix, a stale or incorrect explicit space selection could still let a write run against the wrong space, which is the wrong failure mode for a protected boundary.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_projects.py test/test_spaces.py test/test_users_space_scope.py test/test_teams_space_scope.py test/test_space_isolation_strict.py` from `src/main` -> `50 passed in 50.10s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / lifespan teardown

- Fixed: `src/main/backend/main.py` now restores the temporary AnyIO `run_sync` monkeypatch on lifespan teardown. The previous code patched global threadpool behavior for tests or `SIPM_DISABLE_THREADPOOL=true` and never restored it.
- Why it mattered: later app contexts could inherit mutated global threadpool behavior after shutdown, which is hidden shared state on the main runtime seam.
- Validation: `pytest -q -s test/test_db_config.py test/test_context_path_routing.py test/test_auth_and_deps.py` from `src/main` -> `41 passed in 25.94s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / deployment profile normalization

- Fixed: `src/main/backend/app/runtime.py` now normalizes `ENV=local` to `dev`, matching `src/main/backend/app/auth/auth.py`.
- Why it mattered: auth and DB runtime were interpreting the same deployment profile differently, which could make local auth behavior and TA connection environment selection diverge.
- Validation: `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py` from `src/main` -> `34 passed in 18.61s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / auth cookie config validation

- Fixed: `src/main/backend/app/auth/auth.py` now validates `SIPM_COOKIE_SAMESITE` during auth configuration checks and rejects values outside `lax`, `strict`, or `none`.
- Why it mattered: a bad SameSite config previously survived startup and only failed later when login or refresh tried to write auth cookies.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `35 passed in 16.55s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / SameSite none secure coupling

- Fixed: `src/main/backend/app/auth/auth.py` now rejects `SIPM_COOKIE_SAMESITE=none` unless `SIPM_SECURE_COOKIES=true`.
- Why it mattered: browsers reject `SameSite=None` cookies without `Secure`, so the previous config path could still pass startup validation while leaving auth cookies unusable at runtime.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `36 passed in 16.25s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / secure-cookie boolean parsing

- Fixed: `src/main/backend/app/auth/auth.py` now parses `SIPM_SECURE_COOKIES` with standard boolean env semantics (`1/true/yes/on`, `0/false/no/off`) and rejects invalid values explicitly.
- Why it mattered: the previous `== "true"` parsing silently treated common truthy values like `yes` or `1` as false, which could disable secure auth cookies or trigger a false non-dev startup failure.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `38 passed in 17.10s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / runtime shell boolean env parsing

- Fixed: `src/main/backend/main.py` now parses `SIPM_DISABLE_STARTUP`, `SIPM_DISABLE_THREADPOOL`, `SIPM_KEEPALIVE_TASK`, and `SIPM_ENV_OVERRIDE` with standard boolean env semantics and rejects invalid values explicitly.
- Why it mattered: the previous `== "true"` checks silently ignored common truthy values like `1`, `yes`, or `on`, which could leave startup, threadpool, or env-override behavior in the wrong mode.
- Validation: `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py test/test_context_path_routing.py` from `src/main` -> `50 passed in 25.00s`

## Incremental Update

Date: 2026-03-23
Mode: `follow-up audit`
Issue set: protected runtime / auth numeric env parsing

- Fixed: `src/main/backend/app/auth/auth.py` now validates numeric auth env variables such as `SIPM_ACCESS_MINUTES`, `SIPM_RESET_MINUTES`, and `SIPM_BCRYPT_ROUNDS` with explicit runtime config errors instead of raw import-time `ValueError`s.
- Why it mattered: invalid auth numeric config previously failed noisily and inconsistently during module import, which is the wrong failure shape for a protected startup boundary.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `44 passed in 17.09s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / unknown deployment profile safety

- Fixed: `src/main/backend/app/auth/auth.py` now treats any non-`dev`/`test` deployment profile as non-dev for auth defaults, so unknown values like `stage` no longer inherit dev-like relaxed auth settings.
- Why it mattered: unknown `ENV` values previously defaulted to insecure auth behavior (`SECURE_COOKIES=false`, self-registration enabled), which is the wrong failure mode on a protected startup boundary.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `45 passed in 17.31s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / bcrypt rounds startup validation

- Fixed: `src/main/backend/app/auth/auth.py` now validates `SIPM_BCRYPT_ROUNDS` during auth configuration checks instead of letting invalid numeric rounds survive until the first password hash operation.
- Why it mattered: bad bcrypt round values previously produced a fail-late auth break on register/reset flows rather than a clean startup config failure.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `46 passed in 16.12s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / negative auth TTL validation

- Fixed: `src/main/backend/app/auth/auth.py` now rejects negative access, refresh, and reset TTL settings during auth configuration validation.
- Why it mattered: negative duration settings previously survived startup and only surfaced later as immediately expired auth or reset tokens.
- Validation: `pytest -q -s test/test_auth_and_deps.py test/test_db_config.py` from `src/main` -> `48 passed in 15.68s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / TA environment contract

- Fixed: `src/main/backend/app/runtime.py` now normalizes `ENV=test` to `dev` for TA usage and rejects unknown TA environments explicitly instead of passing them through.
- Why it mattered: the TA runtime contract already documented only `dev/local`, `uat`, and `prod`, but the old code still let arbitrary values like `stage` or `qa` flow into `TAConnection(env=...)` without validation.
- Validation: `pytest -q -s test/test_db_config.py test/test_auth_and_deps.py` from `src/main` -> `50 passed in 17.33s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: realtime / websocket registration failure path

- Fixed: `src/main/backend/app/routes/sync.py` now closes websocket clients with the existing server-busy close code when an unexpected registration failure occurs.
- Why it mattered: the old path swallowed unexpected registration errors and returned without giving the client a close reason, which is the wrong failure shape for a live-sync boundary.
- Validation: `pytest -q -s test/test_realtime_and_sync.py` from `src/main` -> `10 passed in 0.24s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: realtime / websocket limit config validation

- Fixed: `src/main/backend/app/services/realtime.py` now validates websocket limit and idle-timeout settings with explicit runtime config errors instead of raw import failures or confusing runtime behavior.
- Why it mattered: invalid or non-positive websocket limit values previously survived startup and only showed up later as broken live-sync behavior.
- Validation: `pytest -q -s test/test_realtime_and_sync.py` from `src/main` -> `12 passed in 0.29s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: data contracts / Oracle string and audit-read alignment

- Fixed: `src/main/backend/app/models/base.py` now compiles Oracle `String` columns as `VARCHAR2` whether or not a length is explicit; `src/main/backend/app/models/work.py` now sizes solution and subcomponent `github_repo_url` columns to the documented `1024` characters; `src/main/backend/app/models/identity.py` and `src/main/backend/app/models/__init__.py` no longer carry the dormant `PasswordResetToken` metadata/export surface; and `src/main/backend/app/schemas/__init__.py` now exposes `space_id` on `ChangeLogRead`.
- Why it mattered: the Oracle DDL contract and runtime metadata had drifted apart, and `/audit?all_spaces=true` results could not tell callers which space a row belonged to.
- Validation: `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_users_space_scope.py` -> `42 passed in 41.97s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: data contracts / schema-doc regression closure

- Fixed: `src/main/test/test_models_schema_contract.py` now performs a full Oracle schema-doc regression against live SQLAlchemy metadata, covering table sets, column definitions, unique constraints, and index names for the documented Oracle contract.
- Why it mattered: without a whole-surface regression, `CCR-005` would stay partially manual and could drift back silently even after the direct fixes landed.
- Validation: `pytest -q -s src/main/test/test_models_schema_contract.py src/main/test/test_audit.py src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_users_space_scope.py` -> `56 passed in 45.67s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / DB pool config validation

- Fixed: `src/main/backend/app/db/db.py` now validates DB pool env values by range instead of only parsing integers. `SIPM_DB_POOL_SIZE` must be `>= 0`, `SIPM_DB_MAX_OVERFLOW` must be `-1` or `>= 0`, `SIPM_DB_POOL_TIMEOUT_SECONDS` must be `>= 0`, and `SIPM_DB_POOL_RECYCLE_SECONDS` must be `-1` or `>= 0`.
- Why it mattered: invalid negative pool settings previously survived startup parsing and could produce confusing or fail-late behavior inside SQLAlchemy’s pooling layer instead of a clean runtime config error.
- Validation: `pytest -q -s src/main/test/test_db_config.py` -> `25 passed in 1.06s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / password-reset expiry contract

- Fixed: `src/main/backend/app/schemas/__init__.py` now validates `PasswordResetIssueRequest.expires_minutes` within `5..1440`, and `src/main/backend/app/services/password_reset.py` now rejects out-of-range values instead of silently clamping them.

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: protected runtime / admin authz normalization and gate closure

- Fixed: `src/main/backend/app/services/spaces.py`, `src/main/backend/app/deps.py`, and `src/main/backend/app/routes/users.py` now normalize legacy `global admin` / `global-admin` role values consistently across global-admin authz checks, active-space resolution, global-admin listing/counting, and the CSV user-import path. Non-global-admin actors can no longer use `/users/import` to modify or reactivate global-admin accounts. `src/main/test/test_route_space_enforcement_gate.py` now scans nested route packages, so the `planning/` split no longer leaves those protected routes outside the dependency gate.
- Why it mattered: legacy role formatting could incorrectly strip global-admin access or weaken last-admin protections, and the CSV import path bypassed the explicit global-admin account protection already enforced by direct user update endpoints. The route-space enforcement gate also regressed when `planning.py` became a package.
- Validation:
  - `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_route_space_enforcement_gate.py` -> `45 passed in 31.34s`
  - `pytest -q -s src/main/test/test_spaces.py` -> `7 passed in 7.19s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: admin domain / team-tag consistency and user-cache invalidation

- Fixed: `src/main/backend/app/routes/teams.py` now updates active-space `User.team_tag` values when a team is renamed and clears them when a team is deleted. The route also invalidates both `teams` and `users` cache scopes for those mutations instead of only the team cache.
- Why it mattered: the standard `/teams` path had drifted from the planning team-management path and could leave users pointing at stale or deleted team names. That leaked into `/users` responses, planning person-team mapping, and cached roster views.
- Validation:
  - `pytest -q -s src/main/test/test_teams_space_scope.py` -> `8 passed in 8.38s`
  - `pytest -q -s src/main/test/test_planning_work_allocation_people.py` -> `3 passed in 3.80s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: realtime/cache / smart-cache max-entry validation

- Fixed: `src/main/backend/app/services/smart_cache.py` now rejects `SIPM_SMART_CACHE_MAX_ENTRIES <= 0` instead of silently coercing invalid values like `0` or `-5` back to the default floor of `256`.
- Why it mattered: this was another fail-open config path on shared runtime state. A clearly broken cache-size setting could survive startup and mask the operator error instead of failing fast.
- Validation:
  - `pytest -q -s src/main/test/test_smart_cache.py src/main/test/test_teams_space_scope.py src/main/test/test_planning_work_allocation_people.py` -> `17 passed in 13.10s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: realtime / idle websocket pruning

- Fixed: `src/main/backend/app/services/realtime.py` now actively closes idle-pruned websocket clients with the reconnectable `1001` close code before unregistering them from the in-memory registry.
- Why it mattered: the old prune path silently dropped stale sockets from server state without closing them, which could leave a client tab sitting on an apparently-open websocket until some later failure path cleaned it up.
- Validation:
  - `pytest -q -s src/main/test/test_realtime_and_sync.py` -> `13 passed in 0.30s`
  - `pytest -q -s src/main/test/test_live_sync_session_frontend_contract.py` -> `3 passed in 0.37s`
- Why it mattered: the admin password-reset API could accept one expiry value and quietly execute another, which is the wrong failure shape for a protected auth path and contradicted the UI contract.
- Validation: `pytest -q -s src/main/test/test_users_space_scope.py src/main/test/test_auth_and_deps.py` -> `37 passed in 22.53s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: protected runtime / password-reset minimum-length enforcement

- Fixed: `src/main/backend/app/schemas/__init__.py` now enforces the same minimum password length on `ResetPasswordRequest` that registration already enforced.
- Why it mattered: the reset-password path previously let callers set passwords that were shorter than the minimum accepted by the registration flow, weakening the auth contract on a protected path.
- Validation: `pytest -q -s src/main/test/test_auth_and_deps.py src/main/test/test_users_space_scope.py` -> `38 passed in 23.80s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: realtime / smart-cache env validation

- Fixed: `src/main/backend/app/services/smart_cache.py` now parses `SIPM_SMART_CACHE_ENABLED` with standard boolean env semantics and rejects invalid values, and `SIPM_SMART_CACHE_MAX_ENTRIES` now fails explicitly on non-integer values instead of silently falling back.
- Why it mattered: cache settings live on a shared stale-state boundary; invalid env values previously downgraded into hidden defaults instead of producing a clear startup/config error.
- Validation: `pytest -q -s src/main/test/test_smart_cache.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py` -> `13 passed in 8.99s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: admin domain / team default-capacity precedence and space conflict handling

- Fixed: `src/main/backend/app/routes/teams.py` now honors `default_capacity_per_week` when callers omit `default_capacity_fte_month`, including the soft-delete restore path; `src/main/backend/app/routes/spaces.py` now converts duplicate space-name and duplicate slug DB conflicts into explicit `400` responses instead of uncaught `500`s.
- Why it mattered: team creation/restoration could silently discard a caller’s per-week capacity request because schema defaults looked like explicit FTE input, and duplicate space names were still falling through as raw server errors on an admin path.
- Validation: `pytest -q -s src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py` -> `13 passed in 12.70s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: deliverables domain / reopen completion-state consistency

- Fixed: `src/main/backend/app/routes/solutions.py` now clears `completed_at` when a solution is reopened through direct updates or CSV import updates, and `src/main/backend/app/routes/subcomponents.py` now does the same for direct updates, CSV import updates, and batch status updates.
- Why it mattered: reopened solutions and subcomponents could keep a stale completion timestamp, which left status and completion metadata contradicting each other and polluted downstream exports and filtered views.
- Validation: `pytest -q -s src/main/test/test_solutions.py src/main/test/test_import_export_solutions.py src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py` -> `38 passed in 40.85s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: observability / runtime shell correlation and readiness

- Fixed: `src/main/backend/main.py` now adds request-ID middleware, structured request/error logging, and `/health/ready`, while `src/main/backend/app/db/db.py` now exposes a lightweight DB connectivity check for readiness and `src/main/README.md` documents the operator surface.
- Why it mattered: the runtime previously had only `/health` and no request correlation, which made startup/runtime failures harder to diagnose and gave operators no shallow readiness signal.
- Validation: `pytest -q -s src/main/test/test_observability.py src/main/test/test_context_path_routing.py src/main/test/test_seed_and_db.py` -> `18 passed in 14.20s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: planning backend decomposition

- Fixed: the monolithic `src/main/backend/app/routes/planning.py` was replaced by `src/main/backend/app/routes/planning/{common,legacy_allocations,work_allocation}.py`, and inline work-allocation schemas were moved into `src/main/backend/app/schemas/planning.py`.
- Why it mattered: planning changes were previously trapped inside one large public-API file, which made targeted fixes and contract review harder than necessary.
- Validation: `pytest -q -s src/main/test/test_planning_fte_month.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_planning_router_composition.py` -> `14 passed in 15.62s`

## Incremental Update

Date: 2026-03-24
Mode: `follow-up audit`
Issue set: frontend shell decomposition

- Fixed: `src/main/ui/js/app.js` now delegates path building, routing, session/auth, live-sync, and shared data loading to `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context}.js`, and route modules now expose a primary `render(ctx)` entrypoint.
- Why it mattered: the frontend shell hotspot previously concentrated shared state, navigation, API, and websocket behavior in one file, which raised regression risk on every UI change.
- Validation: `pytest -q -s src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_live_sync_session_frontend_contract.py src/main/test/test_team_capacity_frontend_contract.py src/main/test/test_*frontend_contract.py src/main/test/test_context_path_routing.py` -> `122 passed in 10.23s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: realtime/cache batch closure and full-suite regression gate

- Fixed: the shared realtime/cache/sync seam is now closed for the low-risk pass. The batch added fail-fast smart-cache config validation, reconnectable idle websocket closure, and full batch regression coverage over websocket, cache invalidation, planning live-refresh, and team/user cache consumers.
- Why it mattered: hidden in-memory state was still the easiest place for stale data or dead websocket behavior to hide after the shell/runtime refactors.
- Validation:
  - `pytest -q -s src/main/test/test_realtime_and_sync.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_spaces.py src/main/test/test_teams_space_scope.py` -> `31 passed in 18.58s`
  - `pytest -q -s src/main/test` from `src/main` -> `397 passed in 139.28s (0:02:19)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: frontend route module / deliverables route-local split

- Fixed: `src/main/ui/js/routes/master.js` now acts as a small route entrypoint while deliverables table rendering and binding moved into `src/main/ui/js/routes/master/table.js`.
- Why it mattered: the deliverables route still carried rendering, filter binding, and cross-view refresh wiring in one file even after the shell split, which made it harder to test route-local changes without reading through unrelated behavior.
- Validation:
  - `pytest -q -s src/main/test/test_master_frontend_contract.py src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py` -> `59 passed in 1.60s`
  - `python3 scripts/check_route_module_test_mapping.py` -> exit `0`
  - `pytest -q -s src/main/test` from `src/main` -> `398 passed in 138.29s (0:02:18)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: test strategy / observability exception-flow coverage

- Fixed: `src/main/test/test_observability.py` now covers both sides of the unhandled-exception contract: the default ASGI client still raises endpoint exceptions, and a non-raising ASGI client still exercises the logged `500` path.
- Why it mattered: the earlier observability middleware regression only surfaced because the full suite happened to include a test that expected the raising-client path. The boundary now has direct regression coverage instead of relying on incidental fallout.
- Validation:
  - `pytest -q -s src/main/test/test_observability.py` -> `7 passed in 6.73s`
  - `pytest -q -s src/main/test` from `src/main` -> `399 passed in 138.93s (0:02:18)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: admin domain / cross-space user-roster cache invalidation

- Fixed: `src/main/backend/app/routes/users.py` now invalidates user caches across every active membership space when a direct user update changes shared profile fields, instead of only invalidating the admin's current space.
- Why it mattered: `display_name` and `is_active` live on the global `User` row, so a shared user could be edited from one space while `/users` in another space kept serving stale cached roster data.
- Validation: `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `31 passed in 31.67s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: admin domain / cross-space user-import cache invalidation

- Fixed: `src/main/backend/app/routes/users.py` now invalidates user caches across every active membership space after `/users/import` updates a shared user, instead of only invalidating the admin's current space.
- Why it mattered: CSV imports can update the same shared `User` fields as direct edits, so a shared user imported from one space could still leave stale `/users` cache entries behind in other spaces.
- Validation: `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `32 passed in 32.53s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / soft-deleted parent descendant visibility

- Fixed: `src/main/backend/app/routes/projects.py` now invalidates and broadcasts descendant `solutions` and `subcomponents` namespaces when a project is soft-deleted, and the shared lookup/query helpers in `src/main/backend/app/routes/solutions.py`, `subcomponents.py`, and `phases.py` now require an active parent project before exposing child solution, subcomponent, or solution-phase data.
- Why it mattered: soft-deleting a project previously hid the project row itself but could still leave child deliverables reachable on cold reads, and cached child lists/details could remain visible until TTL expiry because project delete only invalidated the `projects` namespace.
- Validation:
  - `pytest -q -s src/main/test/test_projects.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_phases.py` -> `44 passed in 45.38s`
  - `pytest -q -s src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `12 passed in 13.31s`
  - `pytest -q -s src/main/test` from repo root -> `404 passed in 153.54s (0:02:33)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / route monolith decomposition

- Fixed: `src/main/backend/app/routes/solutions.py` and `src/main/backend/app/routes/subcomponents.py` were replaced by `solutions/{common,read,write,import_export}.py` and `subcomponents/{common,read,write,import_export}.py`, while preserving the same package import path, `router` export, HTTP routes, response shapes, and the package-level `enable_all_phases` monkeypatch target used by the current tests.
- Why it mattered: both deliverables route files were still around a thousand lines and mixed read paths, write paths, CSV import/export, cache publication, audit logging, and derived-state helpers in one place. That made every future change harder to reason about and raised the risk of accidental cross-path regressions.
- Validation:
  - `pytest -q -s src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `47 passed in 54.40s`
  - `pytest -q -s src/main/test` from repo root -> `423 passed, 1 skipped in 170.17s (0:02:50)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: admin domain / active space-admin invariant

- Fixed: `src/main/backend/app/routes/spaces.py` now counts only active user accounts when enforcing the last-`space_admin` guard, and `src/main/backend/app/routes/users.py` now blocks deactivating a user if that would orphan any space where they are the last active `space_admin`, including cross-space cases.
- Why it mattered: the old guard counted active memberships but not whether the underlying user account was active, so membership edits could treat an inactive admin as sufficient coverage, and a space admin in one space could deactivate a shared user who was the only real admin in another space.
- Validation:
  - `pytest -q -s src/main/test/test_spaces.py src/main/test/test_users_space_scope.py src/main/test/test_teams_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_space_isolation_strict.py` -> `34 passed in 35.19s`
  - `pytest -q -s src/main/test` from repo root -> `406 passed in 160.63s (0:02:40)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / solution-delete descendant cache invalidation

- Fixed: `src/main/backend/app/routes/solutions.py` now invalidates and broadcasts descendant `subcomponents` when a solution is soft-deleted, instead of only invalidating `solutions`.
- Why it mattered: subcomponent reads already hide deleted parents on cold queries, but the old delete path left cached `/subcomponents`, solution-scoped subcomponent lists, and subcomponent detail views visible until TTL expiry after the parent solution was deleted.
- Validation: `pytest -q -s src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py` -> `32 passed in 36.19s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / import-created parent cache invalidation

- Fixed: `src/main/backend/app/routes/solutions.py` and `subcomponents.py` now invalidate and broadcast parent `projects` and `solutions` namespaces when CSV imports auto-create those parent records, instead of only publishing the imported child namespace.
- Why it mattered: a successful import could create a new project or solution while cached `/projects` or `/solutions` responses still returned the old empty/stale list until TTL expiry, which is the wrong behavior for an import that just materially expanded the deliverables tree.
- Validation: `pytest -q -s src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py src/main/test/test_solutions.py src/main/test/test_subcomponents.py` -> `43 passed in 48.56s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / inherited subcomponent repo-cache invalidation

- Fixed: `src/main/backend/app/routes/solutions.py` now invalidates and broadcasts descendant `subcomponents` when a solution update or CSV import changes `github_repo_url` on an existing solution. That closes the inherited repo-link cache gap for `SubcomponentRead.effective_github_repo_url` and `repo_source`, which derive from the parent solution when a subcomponent has no override.
- Why it mattered: cached `/subcomponents`, solution-scoped subcomponent lists, and subcomponent detail responses could keep showing the old inherited repo URL until TTL expiry after a solution repo-link change, even though the parent solution already reflected the new link.
- Validation:
  - `pytest -q -s src/main/test/test_subcomponents.py src/main/test/test_solutions.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `45 passed in 50.37s`
  - `pytest -q -s src/main/test` -> `411 passed in 160.36s (0:02:40)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / subcomponent batch-response repo metadata

- Fixed: `src/main/backend/app/routes/subcomponents.py` now resolves parent solution repo URLs before returning rows from `/subcomponents/actions/batch`, so inherited `effective_github_repo_url` and `repo_source` stay consistent with the single-row create/update/detail paths.
- Why it mattered: the bulk-update route returned subcomponent payloads without the parent solution repo context, which could make inherited repo links disappear or come back wrong in the immediate batch response even though the stored data was unchanged.
- Validation: `pytest -q -s src/main/test/test_subcomponents.py src/main/test/test_import_export_subcomponents.py` -> `19 passed in 21.75s`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: deliverables domain / direct completion audit coverage

- Fixed: `src/main/backend/app/routes/solutions.py` and `subcomponents.py` now include derived completion fields in direct `PATCH` audit entries. Solution status updates now audit `completed_at` and any status-driven `current_phase` change, and subcomponent status updates now audit `completed_at`.
- Why it mattered: the direct patch paths already changed completion state in the database and response payload, but the audit trail dropped that derived transition even though the import and batch paths already recorded it.
- Validation:
  - `pytest -q -s src/main/test/test_solutions.py src/main/test/test_subcomponents.py src/main/test/test_audit.py src/main/test/test_import_export_solutions.py src/main/test/test_import_export_subcomponents.py` -> `51 passed in 55.52s`
  - `pytest -q -s src/main/test` -> `413 passed in 157.83s (0:02:37)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: planning/admin crossover / protected user-mutation guards

- Fixed: planning "people" mutations in `src/main/backend/app/routes/planning/work_allocation.py` now reuse a shared guard service in `src/main/backend/app/services/user_admin_guards.py`, and `src/main/backend/app/routes/users.py` now uses the same shared helper. Non-global-admin actors can no longer modify global-admin accounts through the planning surface, and planning can no longer deactivate the last active global admin or the last active `space_admin`.
- Why it mattered: the standard `/users` routes already enforced those protections, but planning "people" update/delete was a side door that could still modify or deactivate protected accounts because it changed `User.is_active` directly without the same checks.
- Validation:
  - `pytest -q -s src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py src/main/test/test_global_admin_management.py src/main/test/test_spaces.py src/main/test/test_route_space_enforcement_gate.py` -> `30 passed in 30.91s`
  - `pytest -q -s src/main/test` -> `416 passed in 165.42s (0:02:45)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: admin/planning team-tag sync and shared-user cache repair

- Fixed: `src/main/backend/app/routes/teams.py` and `src/main/backend/app/routes/planning/work_allocation.py` now repair `User.team_tag` for all non-deleted space memberships during team rename/delete, not just currently active users. Both paths also now invalidate `/users` caches across every membership space for affected shared users instead of only invalidating the team's current space.
- Why it mattered: team rename/delete was only fixing the visible active-user slice. Inactive users and inactive memberships could keep a stale team name hidden on the shared `User` row, and shared users could still leave stale `/users` caches behind in other spaces because `team_tag` is global per user rather than per space.
- Validation:
  - `pytest -q -s src/main/test/test_teams_space_scope.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_users_space_scope.py` -> `28 passed in 29.55s`
  - `pytest -q -s src/main/test` -> `419 passed in 168.93s (0:02:48)`

## Incremental Update

Date: 2026-03-25
Mode: `follow-up audit`
Issue set: frontend shell ownership and stylesheet contract closure

- Fixed: `src/main/ui/js/app.js` now delegates DOM lookup, confirm/planning modal behavior, and the space-switcher workflow to `src/main/ui/js/shell/{dom,modal-shell,space-switcher}.js`, and `styles.css` now imports split partials from `src/main/ui/styles/{base.css,routes/*.css}` instead of carrying one giant stylesheet directly.
- Fixed: route-local frontend ownership is now real across deliverables, planning, dashboard, and PM dashboard, and the frontend contract tests now resolve imported stylesheet partials through `ui_style_contract.py` instead of pinning everything to one file.
- Why it mattered: the shell still owned raw DOM lookup and shared modal/switcher internals, and the single `styles.css` file kept CSS ownership coupled to one global contract even after the JS route splits landed.
- Validation:
  - `pytest -q -s src/main/test/test_calendar_frontend_contract.py src/main/test/test_dark_mode_theme_contract.py src/main/test/test_dashboard_frontend_contract.py src/main/test/test_deliverables_save_feedback_frontend_contract.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_kanban_frontend_contract.py src/main/test/test_master_frontend_contract.py src/main/test/test_modal_layout_frontend_contract.py src/main/test/test_planning_header_compact_frontend_contract.py src/main/test/test_pm_dashboard_frontend_contract.py src/main/test/test_space_governance_frontend_contract.py src/main/test/test_subcomponents_workbench_frontend_contract.py src/main/test/test_view_heading_frontend_contract.py` -> `154 passed in 7.45s`
  - `npm run lint:ui`
  - `npm run test:ui` -> `5 passed`
  - `pytest -q -s src/main/test` -> `423 passed, 1 skipped in 169.14s (0:02:49)`

## Next Highest-Leverage Focus
1. broad rescan only if new product requirements or regressions surface, because the ranked cleanup queue is closed on current evidence.
2. expand the Playwright smoke surface if future UI work starts touching cross-route interaction flows more often.
3. keep shrinking `src/main/ui/js/app.js` opportunistically when route-specific workflows move, but there is no active review blocker waiting on that work now.
