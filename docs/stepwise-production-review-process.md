# SIPM Stepwise Production Review Process

Purpose: define a repeatable review process that improves SIPM component by component instead of trying to clean the whole project in one pass.

This document is the operating plan for future cleanup work. Each pass should produce a small patch, focused validation, and a short closure note before moving to the next pass.

## Review Principles

- Work one workflow or component at a time.
- Start from the user-facing workflow, then trace backward through frontend state, API contracts, services, models, persistence, tests, and operational behavior.
- Fix correctness before cleanup.
- Fix active-path bugs before stale code.
- Preserve public contracts unless the current contract is clearly wrong or undocumented.
- Add or strengthen regression coverage for behavior changes.
- Avoid broad rewrites unless a component is already isolated and well-covered.
- Keep every pass small enough to review, validate, and roll back.

## Standard Pass Template

Use this sequence for every workflow or component.

1. Define scope.
   - Name the workflow or component.
   - Identify the user-visible outcome.
   - Identify the backend routes, frontend modules, services, models, and tests in scope.

2. Locate source of truth.
   - Read README or docs for the workflow.
   - Read existing tests and frontend contract tests.
   - Read schemas, models, route response shapes, and UI labels.
   - Record any missing or conflicting source of truth.

3. Trace the active path.
   - Start at the route or UI entry point.
   - Follow data loading, state mutation, rendering, persistence, validation, and error handling.
   - Separate active runtime code from test-only, schema-only, or stale candidates.

4. Review correctness.
   - Check validation, authorization, space scoping, edge cases, empty states, partial failures, date handling, numeric precision, and transaction boundaries.
   - Confirm frontend and backend agree on field names, defaults, and error semantics.

5. Review performance and responsiveness.
   - Identify expensive queries, repeated fetches, unnecessary rerenders, slow route loads, duplicated transformation work, and unbounded loops.
   - Prefer measurable evidence when available.
   - Avoid adding caches unless invalidation is clear.

6. Review UI quality.
   - Check loading, empty, error, disabled, and success states.
   - Check layout stability, mobile behavior, table overflow, modal sizing, focus behavior, and accessible labels.
   - Keep UI changes consistent with the existing design language.

7. Review maintainability.
   - Remove dead code only with evidence.
   - Simplify duplicated logic when it is on the active path.
   - Avoid creating new abstractions for one-off cleanup.
   - Prefer clear local helpers over cross-cutting utility sprawl.

8. Plan the patch.
   - List findings by severity.
   - Mark each finding as `must-fix`, `should-fix`, or `advisory`.
   - Choose the smallest patch that closes the highest-risk issue.
   - Defer unrelated cleanup.

9. Implement.
   - Patch only the scoped files.
   - Add focused tests before or with behavior changes.
   - Preserve API shape unless intentionally changing it.

10. Validate.
    - Run focused tests first.
    - Run broader backend, frontend, lint, and smoke checks when the scope touches shared behavior.
    - Record any validation blocked by local environment.

11. Close the pass.
    - Document what was fixed.
    - Document what remains.
    - Decide the next component.

## Component Review Order

The order below prioritizes production risk, active user workflows, and shared infrastructure.

### 1. Analytics And Performance Statistics

Status: completed on 2026-05-14.

Goal: make usage analytics and performance metrics trustworthy.

Primary files:

- `src/main/backend/app/routes/analytics.py`
- `src/main/backend/app/services/usage_analytics.py`
- `src/main/backend/app/schemas/analytics.py`
- `src/main/backend/app/models/analytics.py`
- `src/main/ui/js/shell/telemetry.js`
- `src/main/ui/js/routes/analytics.js`
- `src/main/test/test_usage_analytics.py`
- `src/main/ui/test/unit/telemetry.test.js`

Review checks:

- Confirm route-view counts, sessions, active users, failures, medians, and p95 values use one clear definition.
- Separate cold page-load metrics from in-app route-transition metrics where the UI needs that distinction.
- Confirm incomplete samples do not distort load statistics.
- Confirm rollups and raw-table fallback produce equivalent results.
- Confirm space scoping and global-admin restrictions are enforced.
- Confirm telemetry retries and failed-batch behavior do not lose important samples.

Validation:

- `cd src/main; pytest -q test/test_usage_analytics.py`
- `npm run test:ui -- src/main/ui/test/unit/telemetry.test.js`
- `npm run lint:ui`
- `npm run test:ui:smoke`

Exit criteria:

- Dashboard statistics match documented definitions.
- Backend and frontend tests cover the known statistics edge cases.
- No known misleading metric remains without an explicit label or follow-up issue.

Completion ledger:

```markdown
## Pass: Analytics And Performance Statistics

Mode: contract alignment with performance-statistics correctness.

### Findings

- High / must-fix: navigation performance samples could be queued before browser navigation timing had a populated `loadEventEnd`, creating misleading zero-valued page-load samples.
- Medium / must-fix: route performance `sample_count` included samples that could not produce a load metric, overstating the statistical basis for slowest-route rows.
- Medium / should-fix: dashboard load labels mixed cold page-load samples and in-app route-transition samples under one ambiguous load metric.
- Low / should-fix: UI smoke validation assumed port 8000 was available, which made route validation fragile when a local server was already running.

### Implemented

- Delayed browser navigation performance sample collection until complete load timing is available.
- Counted only samples with usable load metrics in slowest-route statistics.
- Added additive API fields for page-load and route-transition median/p95 load metrics; no SQL migration was required because the existing schema already stores `sample_kind`.
- Updated analytics dashboard labels to distinguish combined, page-load, and route-transition load statistics.
- Added backend and frontend regression coverage for the statistics edge cases and labels.
- Made the UI smoke server port configurable through `SIPM_UI_SMOKE_PORT`.
- Follow-up Oracle-readiness pass compiled representative analytics percentile, route-performance, and rollup queries against the SQLAlchemy Oracle dialect.
- Follow-up performance cleanup made `/analytics/dashboard` reuse load-summary percentile stats across the summary and performance sections instead of recomputing them.

### Validation

- `cd src/main; pytest -q test/test_usage_analytics.py test/test_analytics_frontend_contract.py test/test_ui_route_module_test_mapping_gate.py`: 11 passed.
- `npm run test:ui -- src/main/ui/test/unit/telemetry.test.js`: 5 passed.
- `npm run lint:ui`: passed.
- `cd src/main; pytest -q`: 484 passed, 1 skipped.
- `npm run test:ui`: 32 passed.
- `$env:SIPM_UI_SMOKE_PORT='8010'; npm run test:ui:smoke`: 2 passed.
- Representative Oracle SQLAlchemy compilation for analytics percentile, route-performance, and rollup route queries: passed.

### Remaining

- No SQL migration is needed for this pass.
- Existing analytics tables still rely on external retention, as documented in `src/main/README.md`.
- Future analytics work should add visual QA screenshots for the analytics dashboard across desktop and mobile once the app has representative telemetry data.
```

### 2. Authentication, Session, And Security Boundaries

Status: completed on 2026-05-14.

Goal: make sign-in, logout, token refresh, service-account tokens, password reset, and access enforcement production-safe.

Primary files:

- `src/main/backend/app/routes/auth.py`
- `src/main/backend/app/routes/users.py`
- `src/main/backend/app/auth/auth.py`
- `src/main/backend/app/deps.py`
- `src/main/backend/app/security.py`
- `src/main/backend/app/services/api_tokens.py`
- `src/main/backend/app/services/password_reset.py`
- `src/main/ui/js/shell/session.js`
- `src/main/test/test_auth_and_deps.py`
- `src/main/test/test_global_admin_management.py`

Review checks:

- Confirm cookies, refresh flow, active-space cookie, and service-account tokens do not conflict.
- Confirm logout semantics are documented and acceptable.
- Confirm password reset invalidates old access where intended.
- Confirm service-account tokens cannot be used in unsafe locations.
- Confirm auth failures produce stable client behavior.
- Confirm admin-only operations are enforced server-side.

Validation:

- Focused auth and user tests.
- Backend full suite if dependency behavior changes.
- UI session unit tests.

Exit criteria:

- Auth behavior is documented, tested, and not dependent on client-side trust.

Completion ledger:

```markdown
## Pass: Authentication, Session, And Security Boundaries

Mode: correctness cleanup with operational hardening.

### Findings

- High / must-fix: `require_user` preferred a browser cookie over an explicit `Authorization: Bearer` service-account token, so automation requests carrying a stale or invalid cookie could fail or authenticate as the wrong credential class.
- Medium / must-fix: bearer credentials without the SIPM PAT prefix were still sent through the API-token hash lookup path, leaving bearer-token semantics less explicit than the issued-token contract.
- Medium / should-fix: frontend logout and idle logout duplicated partial local-session teardown instead of sharing the same cleanup path used by expired sessions.

### Implemented

- Made bearer service-account tokens take explicit precedence over browser cookies in `require_user`.
- Rejected non-`sipm_pat_` bearer credentials before API-token hash lookup.
- Centralized frontend local-session cleanup so session expiry, explicit logout, and idle logout all stop live sync and reset refresh state.
- Added backend regression tests for mixed cookie/bearer credentials and non-SIPM bearer tokens.
- Added frontend unit coverage for realtime teardown on session expiry and explicit logout.

### Validation

- `pytest -q src/main/test/test_auth_and_deps.py`: 38 passed.
- `pytest -q src/main/test/test_auth_and_deps.py src/main/test/test_global_admin_management.py src/main/test/test_spaces.py src/main/test/test_realtime_and_sync.py src/main/test/test_users_space_scope.py`: 79 passed.
- `npm run test:ui -- --run src/main/ui/test/unit/session.test.js`: 4 passed.
- `npm run test:ui`: 34 passed.
- `npm run lint:ui`: passed.
- `cd src/main; pytest -q`: 486 passed, 1 skipped.
- `git diff --check`: passed.

### Remaining

- No SQL migration is needed for this pass.
- Logout remains cookie-clearing only; there is no server-side refresh-token revocation list in the current schema. Password reset and admin-issued temporary passwords still invalidate old token issue times through `password_changed_at`.
- WebSocket realtime authentication remains browser-cookie based by design; service-account API tokens are limited to HTTP API use.
```

### 3. Space Governance And Isolation

Status: completed on 2026-05-14.

Goal: ensure every user-visible and API workflow respects active space boundaries.

Primary files:

- `src/main/backend/app/routes/spaces.py`
- `src/main/backend/app/services/spaces.py`
- `src/main/backend/app/deps.py`
- `src/main/ui/js/routes/spaces.js`
- `src/main/ui/js/routes/spaces/interactions.js`
- `src/main/ui/js/routes/spaces/render.js`
- `src/main/ui/js/shell/space-switcher.js`
- `src/main/test/test_spaces.py`
- `src/main/test/test_space_isolation_strict.py`
- `src/main/test/test_route_space_enforcement_gate.py`

Review checks:

- Confirm every protected route resolves space from the shared dependency.
- Confirm switching spaces refreshes all space-scoped state.
- Confirm archived, inactive, missing, and unauthorized spaces behave correctly.
- Confirm global admin behavior is explicit and tested.
- Confirm UI state does not leak records across spaces after switch.

Validation:

- Space isolation backend tests.
- Space governance frontend contract tests.
- Smoke navigation across space-sensitive routes.

Exit criteria:

- No active route can read or write cross-space data without an explicit global-admin path.

Completion ledger:

```markdown
## Pass: Space Governance And Isolation

Mode: correctness cleanup with UI/code-layout hardening.

### Findings

- High / must-fix: archived spaces were shown in the UI as read-only until reactivated, but direct backend membership mutation calls could still add, update, or delete memberships for archived spaces through global-admin access.
- Medium / should-fix: direct API calls could create or patch a space with a blank display name, leaving the backend reliant on frontend validation for a core governance object.
- Low / should-fix: the space governance renderer used non-ASCII placeholder and separator glyphs in table cells, which made the route less consistent with the rest of the codebase and more fragile under console/encoding differences.

### Implemented

- Added backend membership-mutation validation that allows archived-space membership review but rejects create, update, and delete until the space is reactivated.
- Added explicit backend validation for blank space names on create and update.
- Added regression coverage for archived-space read-only membership behavior and blank-name validation.
- Replaced space governance table placeholders/separators with ASCII text.

### Validation

- `pytest -q src/main/test/test_spaces.py src/main/test/test_space_isolation_strict.py src/main/test/test_route_space_enforcement_gate.py src/main/test/test_space_governance_frontend_contract.py`: 21 passed.
- `pytest -q src/main/test/test_auth_and_deps.py src/main/test/test_spaces.py src/main/test/test_space_isolation_strict.py src/main/test/test_route_space_enforcement_gate.py src/main/test/test_users_space_scope.py src/main/test/test_space_governance_frontend_contract.py`: 71 passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 34 passed.
- `cd src/main; pytest -q`: 488 passed, 1 skipped.
- `$env:SIPM_UI_SMOKE_PORT='8011'; npm run test:ui:smoke`: 2 passed.
- `git diff --check`: passed.

### Remaining

- No SQL migration is needed for this pass.
- Archived spaces are still available to global admins for review and reactivation; membership edits intentionally require reactivation first.
- The route enforcement gate remains the primary guard against future protected routes skipping `current_space`, `require_space_role`, or `require_global_admin`.
```

### 4. Planning Work Allocation Board

Status: completed on 2026-05-14.

Goal: make the planning board correct, fast, and predictable under real usage.

Primary files:

- `src/main/backend/app/routes/planning/work_allocation.py`
- `src/main/backend/app/services/planning_work_allocation.py`
- `src/main/backend/app/schemas/planning.py`
- `src/main/ui/js/routes/planning.js`
- `src/main/ui/js/routes/planning/api.js`
- `src/main/ui/js/routes/planning/render.js`
- `src/main/ui/js/routes/planning/interactions.js`
- `src/main/ui/js/routes/planning/state.js`
- `src/main/ui/js/routes/planning/storage.js`
- `src/main/test/test_planning_work_allocation_tasks.py`
- `src/main/test/test_planning_work_allocation_people.py`
- `src/main/test/test_planning_work_allocation_report.py`

Review checks:

- Confirm month scoping is correct.
- Confirm one-allocation-per-task-per-month rule is enforced.
- Confirm team/person assignment behavior is consistent.
- Confirm optimistic UI, undo, reload, and error recovery do not corrupt board state.
- Confirm capacity math and FTE-month rounding are correct.
- Confirm board loading avoids unnecessary API calls and rerenders.

Validation:

- Focused planning backend tests.
- Planning frontend contract tests.
- Smoke route test.

Exit criteria:

- Board state remains correct after create, edit, assign, unassign, delete, reload, and month switch.

Completion ledger:

```markdown
## Pass: Planning Work Allocation Board

Mode: correctness cleanup with responsiveness hardening.

### Findings

- High / must-fix: backend month parsing accepted the `YYYY-MM` shape but allowed impossible month values such as `2026-13` to escape as raw date parsing errors instead of stable 400 responses.
- Medium / must-fix: rapid month changes while the board was already loading could be dropped by the frontend loader, leaving the board with stale data for the previous month.
- Medium / should-fix: team and person update routes silently ignored blank names instead of returning clear validation errors, creating inconsistent behavior with task updates and create routes.

### Implemented

- Hardened planning month parsing so impossible months return the documented `month must use YYYY-MM` client error.
- Added shared nonblank text validation for planning team, person, and task mutation paths.
- Added a queued follow-up load in the planning board API layer so a month change during an in-flight request is applied after the active load finishes.
- Added backend regression coverage for invalid month parameters and blank team/person update names.
- Added frontend unit coverage for in-flight planning board month reload behavior.

### Validation

- `pytest -q src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_teams_space_scope.py src/main/test/test_frontend_ux_improvement_contract.py`: 87 passed.
- `pytest -q src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_teams_space_scope.py src/main/test/test_route_space_enforcement_gate.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_route_stylesheet_split_contract.py`: 93 passed.
- `npm run test:ui -- --run src/main/ui/test/unit/planning-api.test.js`: 1 passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 35 passed.
- `cd src/main; pytest -q`: 490 passed, 1 skipped.
- `$env:SIPM_UI_SMOKE_PORT='8012'; npm run test:ui:smoke`: 2 passed.
- `git diff --check`: passed.

### Remaining

- No SQL migration is needed for this pass.
- The board intentionally supports multiple assignees per task, with duplicate protection scoped to the same task, assignee, and month plus one team-level allocation per task/month.
- Future work can add deeper browser visual QA for drag/drop states, but the route smoke and unit coverage now protect the stale-month-load failure mode.
```

### 5. Projects, Solutions, And Subcomponents Core CRUD

Status: completed on 2026-05-14.

Goal: make the core work-item lifecycle robust and consistent.

Primary files:

- `src/main/backend/app/routes/projects/*`
- `src/main/backend/app/routes/solutions/*`
- `src/main/backend/app/routes/subcomponents/*`
- `src/main/backend/app/models/work.py`
- `src/main/backend/app/schemas/planning.py`
- `src/main/ui/js/entities/projects.js`
- `src/main/ui/js/entities/solutions.js`
- `src/main/ui/js/entities/subcomponents.js`
- `src/main/ui/js/routes/master/*`
- `src/main/ui/js/routes/subcomponents-workbench/*`

Review checks:

- Confirm create, update, delete, import, export, and batch update semantics match across entity types.
- Confirm lifecycle timestamps are preserved.
- Confirm status, RAG, priority, blocked, due-date, sponsor, assignee, and repository URL fields are validated.
- Confirm UI forms do not submit stale or hidden values.
- Confirm tables and workbench views remain responsive with larger datasets.

Validation:

- Project, solution, and subcomponent backend tests.
- Import/export tests.
- Master and workbench frontend contract tests.

Exit criteria:

- Entity behavior is consistent across backend, frontend, import/export, and tests.

Completion ledger:

```markdown
## Pass: Projects, Solutions, And Subcomponents Core CRUD

Mode: lifecycle-route hardening with import/export parity review.

### Findings

- High / must-fix: JSON create and update routes accepted whitespace-only project, solution, and subcomponent names even though CSV import rejected blank identifiers.
- Medium / must-fix: solution updates accepted a whitespace-only version, which could create records that are difficult to target consistently by import/export and UI filters.
- Medium / should-fix: subcomponents could remain unblocked while retaining a stale blocker note, making blocked-state reporting and workbench review misleading.

### Implemented

- Normalized required project names on JSON create/update and rejected blank names before persistence.
- Normalized required solution names and versions on JSON create/update, while preserving the existing `0.1.0` create default when version is omitted.
- Normalized required subcomponent names on JSON create/update and rejected blank names before persistence.
- Cleared blocker notes automatically when a subcomponent is saved as not blocked.
- Added focused backend regression tests for identifier normalization, blank rejection, version rejection, and stale blocker-note cleanup.

### Validation

- `cd src/main; pytest -q test/test_projects.py test/test_solutions.py test/test_subcomponents.py`: 47 passed.
- `cd src/main; pytest -q test/test_import_export_projects.py test/test_import_export_solutions.py test/test_import_export_subcomponents.py`: 20 passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 35 passed.
- `cd src/main; pytest -q`: 493 passed, 1 skipped.

### Remaining

- No SQL migration is needed for this pass.
- The reviewed CRUD queries remain Oracle-compatible through SQLAlchemy ORM expressions; no SQLite-only SQL was introduced.

## Follow-up: Frontend Entity Contract Layer

Mode: JavaScript entity contract alignment and refresh-state cleanup.

### Findings

- Medium / must-fix: solution payload construction could copy a display-name assignee into `assignee_user_soeid` when the SOEID field was blank, corrupting user-key semantics across backend filters and dashboards.
- Medium / should-fix: solution and subcomponent entity payloads sent unsupported FTE alias fields that the CRUD schemas ignore, creating noisy route-to-JavaScript contract drift.
- Medium / should-fix: `restoreSelections` maintained a stale second copy of project, solution, and subcomponent form population logic, missing newer fields such as repository URLs and increasing refresh-state fragility.
- Low / should-fix: entity payload builders were nested inside controllers, which made contract testing harder and let route payload drift go untested.

### Implemented

- Exported focused project, solution, and subcomponent payload builders from the entity modules.
- Trimmed identifier, URL, and SOEID fields before submit while preserving long-text body fields where user spacing can be intentional.
- Removed unsupported `capacity_fte_months` and `estimate_fte_months` keys from solution/subcomponent CRUD payloads.
- Removed display-name fallback for `solution.assignee_user_soeid`; the field now submits only an explicit SOEID or `null`.
- Made subcomponent payloads clear `blocker_note` client-side when `blocked` is false, matching the backend route behavior.
- Changed refresh selection restore to delegate to the entity controllers instead of duplicating form-field assignment in `app.js`.
- Removed the now-unused `updateSubcomponentSolutionOptions` helper.
- Added UI unit tests for entity payload normalization and route-contract shape.

### Validation

- `npm run test:ui -- src/main/ui/test/unit/entities.test.js`: 3 passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 38 passed.
- `cd src/main; pytest -q test/test_projects.py test/test_solutions.py test/test_subcomponents.py`: 47 passed.
- `cd src/main; pytest -q test/test_frontend_ux_improvement_contract.py test/test_deliverables_save_feedback_frontend_contract.py`: 72 passed.
- `cd src/main; pytest -q`: 493 passed, 1 skipped.
- `$env:SIPM_UI_SMOKE_PORT='8014'; npm run test:ui:smoke`: 2 passed.

### Remaining

- No SQL migration is needed for this pass.
- This pass covered entity modules, their `app.js` wiring, workbench save payloads, backend CRUD route contracts, and existing frontend contract tests. It did not do a visual redesign pass on the modal layouts.
```

### 6. Dashboards, Calendar, Gantt, Kanban, And Team Capacity

Status: completed on 2026-05-14.

Goal: ensure read-heavy operational views are accurate, crisp, and fast.

Primary files:

- `src/main/ui/js/routes/dashboard*`
- `src/main/ui/js/routes/pm-dashboard*`
- `src/main/ui/js/routes/calendar*`
- `src/main/ui/js/routes/gantt*`
- `src/main/ui/js/routes/kanban*`
- `src/main/ui/js/routes/team-capacity*`
- `src/main/ui/styles/routes/*.css`

Review checks:

- Confirm views share the same source data and do not duplicate business rules incorrectly.
- Confirm date and status filtering is consistent.
- Confirm charts, tables, lanes, cards, and capacity bars handle empty and overflow states.
- Confirm route transitions and filter interactions are snappy.
- Confirm rendering does not do avoidable expensive work on every keystroke.

Validation:

- Frontend route contract tests.
- UI unit tests for affected utilities.
- Playwright smoke tests.

Exit criteria:

- Each operational view loads, filters, and updates without visible jank or stale data.

Completion ledger:

```markdown
## Pass: Dashboards, Calendar, Gantt, Kanban, And Team Capacity

Mode: read-heavy route correctness and polish pass.

### Findings

- High / must-fix: Kanban cards inserted backend-provided owner, assignee, priority, phase, due-date, status, and phase-group text directly into `innerHTML`, while only the solution/project links were escaped.
- Medium / must-fix: Calendar modal opening treated restored month state as a `Date` object even though persisted month state can be restored as a string.
- Medium / must-fix: Calendar month parsing used `new Date("YYYY-MM")`, which can resolve to the previous local month in eastern time because JavaScript parses that shape as UTC.

### Implemented

- Escaped all Kanban backend text rendered in card metadata and phase-group headings.
- Added Kanban unit coverage that verifies hostile backend text remains text instead of becoming live DOM.
- Added a shared calendar month normalizer that parses persisted `YYYY-MM` and date-only strings as local calendar months.
- Added calendar unit coverage for modal opening from restored string month state.

### Validation

- `npm run test:ui -- src/main/ui/test/unit/kanban.test.js`: 1 passed.
- `npm run test:ui -- src/main/ui/test/unit/calendar.test.js src/main/ui/test/unit/kanban.test.js src/main/ui/test/unit/gantt.test.js src/main/ui/test/unit/router.test.js`: 18 passed.
- `pytest -q src/main/test/test_calendar_frontend_contract.py src/main/test/test_gantt_frontend_contract.py src/main/test/test_kanban_frontend_contract.py src/main/test/test_team_capacity_frontend_contract.py src/main/test/test_dashboard_frontend_contract.py src/main/test/test_pm_dashboard_frontend_contract.py src/main/test/test_pm_dashboard_space_scope_contract.py src/main/test/test_ui_route_modules_exports.py`: 73 passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 40 passed.
- `cd src/main; pytest -q`: 493 passed, 1 skipped.
- `$env:SIPM_UI_SMOKE_PORT='8015'; npm run test:ui:smoke`: 2 passed.
- `git diff --check`: passed with existing CRLF normalization warnings.

### Remaining

- No SQL migration is needed for this pass.
- Team capacity remains intentionally backed by the existing space-scoped users and allocation loader; no route or schema changes were needed.
- A future visual QA pass can still inspect dense dashboard/card overflow in a real browser with representative production data.
```

### 7. Data Store, Router, Live Sync, And Shell

Goal: make shared frontend infrastructure predictable and low-waste.

Primary files:

- `src/main/ui/js/app.js`
- `src/main/ui/js/shell/router.js`
- `src/main/ui/js/shell/data-store.js`
- `src/main/ui/js/shell/live-sync.js`
- `src/main/ui/js/shell/context.js`
- `src/main/ui/js/shell/dom.js`
- `src/main/ui/js/shell/modal-shell.js`
- `src/main/ui/test/unit/data-store.test.js`
- `src/main/ui/test/unit/router.test.js`
- `src/main/ui/test/unit/live-sync.test.js`

Review checks:

- Confirm route module loading and prefetching do not duplicate fetches.
- Confirm shared state is reset on auth and space changes.
- Confirm refresh fanout, websocket sync, and manual reloads do not race.
- Confirm modal and drawer state cannot leak between routes.
- Confirm `app.js` still has clear ownership boundaries or identify extraction candidates.

Validation:

- UI unit tests.
- Route module export tests.
- Playwright navigation smoke.

Exit criteria:

- Shared shell behavior is stable enough that route-specific work does not need defensive workarounds.

### 8. Backend Runtime, Database, Readiness, And Observability

Goal: make the server operationally predictable.

Primary files:

- `src/main/backend/main.py`
- `src/main/backend/app/runtime.py`
- `src/main/backend/app/db/db.py`
- `src/main/backend/app/db/table_names.py`
- `src/main/backend/app/request_context.py`
- `src/main/test/test_observability.py`
- `src/main/test/test_db_config.py`
- `src/main/test/test_runtime_path_resolution.py`
- `docs/sql/schema_oracle_ta.sql`

Review checks:

- Confirm startup and readiness fail for real production blockers.
- Confirm request IDs and logs are consistent.
- Confirm DB configuration is explicit and non-mutating at startup.
- Confirm Oracle schema and SQLAlchemy models remain aligned.
- Confirm environment variables are documented and validated.

Validation:

- Runtime, DB config, observability, and schema contract tests.
- Focused readiness checks.

Exit criteria:

- Operators can reason about startup, readiness, logs, and schema requirements without tribal knowledge.

### 9. Import, Export, Migration, And UAT Rehearsal

Goal: make environment migration repeatable and low-risk.

Primary files:

- Project, solution, subcomponent, user, planning import/export routes.
- `docs/sql/first_deploy_reference_data.sql`
- `docs/sql/first_time_global_admin.sql`
- `docs/sql/schema_oracle_ta.sql`
- `README.md`
- `src/main/README.md`

Review checks:

- Confirm dry-run behavior exists where migration needs it.
- Confirm imports reject duplicate natural keys.
- Confirm partial success and atomic mode are documented.
- Confirm migration ordering is explicit.
- Confirm exported fields are re-imported losslessly where intended.

Validation:

- Import/export backend tests.
- Manual rehearsal checklist against representative data.

Exit criteria:

- UAT migration can be rehearsed, repeated, and verified without manual guessing.

### 10. Tests, CI, Scripts, And Developer Workflow

Goal: make validation obvious and fast enough to run frequently.

Primary files:

- `.github/workflows/*`
- `package.json`
- `playwright.config.js`
- `scripts/check_requirements_lock.py`
- `scripts/check_route_module_test_mapping.py`
- `scripts/run_ui_smoke_app.py`
- `requirements.in`
- `requirements.txt`
- `README.md`

Review checks:

- Confirm documented commands match CI.
- Confirm smoke tests can run when port 8000 is occupied.
- Confirm route module test mapping stays enforced.
- Confirm dependency lock checks are clear.
- Confirm stale scripts are either deleted or documented.

Validation:

- Backend tests.
- UI lint and unit tests.
- UI smoke tests.
- CI-equivalent command set.

Exit criteria:

- A new maintainer can run the same validation path locally and in CI.

## Per-Pass Output Format

Each component pass should end with this short ledger.

```markdown
## Pass: <component name>

Mode: <correctness cleanup | contract alignment | performance optimization | operational hardening | follow-up audit>

### Findings

- <Severity> / <must-fix|should-fix|advisory>: <finding>

### Implemented

- <change>

### Validation

- `<command>`: <result>

### Remaining

- <remaining risk or next step>
```

## Initial Working Sequence

Start here:

1. Analytics and performance statistics.
2. Auth, session, and security boundaries.
3. Space governance and isolation.
4. Planning work allocation board.
5. Data store, router, live sync, and shell.

Rationale: these areas carry the highest production risk because they affect trust, access, cross-space data safety, and the most active user workflows.

## Review Backlog Rules

- Promote an item to `must-fix` only when it affects correctness, security, data integrity, production operability, or core UX.
- Keep `should-fix` for real maintainability or performance issues that are not immediate blockers.
- Keep `advisory` for cleanup that is useful but not production-blocking.
- Do not start a new component until the current pass has validation results and a remaining-risk note.
- If a pass discovers a larger architectural issue, document it and finish the current narrow patch first.
