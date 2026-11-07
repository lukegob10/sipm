# Code health review 2026-11-06

35 focused review agents inspected the backend, scripts, shared libraries and frontend. This full-surface review repaired bounded correctness, reliability and performance issues while preserving the directory/module layout, public API paths, database schemas, UI routes, DOM IDs and visual layout. It improves code health; it does not certify that every defect or production bottleneck has been eliminated.

The existing uncommitted workspace was snapshotted before edits. Changes in this report are relative to that snapshot, not to Git HEAD. Existing user work was preserved. The review was initially delivered without committing or deploying; the subsequent commit and merge workflow is tracked in [PR 135](https://github.com/lukegob10/sipm/pull/135).

## Highest severity repairs

- **High / must-fix:** explicit empty Bearer credentials could execute as the browser-cookie user, including creating records. `src/main/backend/app/deps.py` now keeps Bearer authentication selected and rejects the invalid token. Regression tests verify identity, exact errors and absence of writes.
- **High / must-fix:** SQL administrator guards omitted padded legacy roles that Python authorization accepted. `services/user_admin_guards.py` and `routes/spaces.py` now trim role values consistently, protecting the last active administrator.
- **High / should-fix:** frontend session refreshes, forced governance reads and My Work snapshots could reuse or apply obsolete responses. Request ownership now includes current context/generation. Failed private-note saves retain drafts and schedule the replacement read; this failure path was corrected during independent integration review.
- **High / should-fix:** the local agent benchmark could inherit deployment settings and begin external runtime work. The harness now fixes its local test settings and cleans partially initialized resources.

## Performance evidence

Measurements below use SQLite, SQL capture, ASGI dispatch counts or synthetic payloads. They demonstrate reduced work; they are not production Oracle latency claims.

| Active path | Before | After | Contract protection |
| --- | --- | --- | --- |
| My Work listing | 5 SELECTs | 1 SELECT | Own-user/space private state, missing state, hierarchy and order |
| Repository inventory | 4 SELECTs | 2 SELECTs | Grouping, effective repositories and visible hierarchy |
| Valid API token lookup | 2 SELECTs | 1 SELECT | Rejection codes, revocation/expiry and last-used throttle |
| Agent project/task detail | 2 SELECTs | 1 SELECT | Complete payload and hidden-parent boundaries |
| Phase initialization | 8 SELECTs for 7 phases | 2 SELECTs | Canonical-only updates and idempotence |
| Phase upsert, 1 / 7 / 35 input items | 6 / 18 / 74 target-model SELECTs | 4 / 4 / 4 | Duplicate ordering, validation, audits and locking |
| Task CSV, 3 rows, parent reads | 12 SELECTs | 8 SELECTs | Revalidation after commits and missing-parent row errors |
| Solution CSV export | 2 SELECTs | 1 SELECT | Scope, deleted rows and CSV content |
| Assigned-work selection | 79 columns | 26 columns | One query, pagination, hierarchy and payload |
| Graph summary synthetic string hydration | 975,193 bytes | 173 bytes | Same 4 queries and 2,421-byte response; full projection unchanged |
| Report loader, 64 solutions | 33,947,648 unused text characters | 0 unused text characters | Same 4 queries and identical report hash |
| Document download, 4,096 newline bytes | 4,097 ASGI body messages | 1 ASGI body message | Exact bytes and attachment/media headers |
| Repeated solution repository IDs | 1,201 duplicate binds | 1 bind | Same repository lookup result |
| Analytics existence probe, 50,000 rows | 150,023 SQLite VM steps | 24 VM steps | Same boolean existence result |
| Analytics initial loading render | 2 render writes | 1 render write | Same loading and result UI |

Defensive cache copies also moved outside the shared lock. Event-controlled tests verify unrelated cache hits proceed while copies run, and verify mutation isolation plus concurrent replacement/clear behavior.

## Review coverage and changes

Initial branch-local inventory: 105 backend Python files, 76 frontend JavaScript modules, 8 repository scripts, 187 backend test/support files, 99 frontend unit files and 35 browser test files. Documentation, CI, dependency declarations, configuration, SQL contracts and runtime entrypoints supplied the behavior contracts. Inventory counts describe the surface; the assigned reviews below describe inspected domains.

Paths in the backend rows are relative to `src/main/backend/app` unless a full repository prefix is shown. UI paths are relative to `src/main`. Focused test counts overlap across agents and must not be summed.

| Agent | Severity / disposition | Reviewed domain | Implemented result | Changed production paths | Focused checks |
| --- | --- | --- | --- | --- | --- |
| auth_boundaries | High / must-fix | Authentication boundary | Reject empty/malformed Bearer credentials instead of falling back to browser cookies. | `deps.py` | 39 related; 13 final focused passed |
| auth_sessions | Medium / should-fix | Sessions and API tokens | Join token/user lookup; valid PAT lookup 2 → 1 SELECT. | `services/api_tokens.py` | 119 passed |
| runtime_environment | Medium / should-fix | Startup and environment | Read UTF-8/BOM environment files; require frontend bundle paths to be files. | `environment.py; src/main/backend/main.py` | 97 related; 6 final regressions passed |
| database_layer | Medium / should-fix | Database plumbing | Close all warmed connections after any cleanup failure. | `db/db.py` | 47 passed |
| models_validation | Medium / should-fix | Models and schemas | Reject UTC overflow before reminders, token expiration or telemetry writes. | `schemas/__init__.py; schemas/analytics.py` | 68 passed |
| spaces_governance | Medium / should-fix | Space governance | Avoid deleted name/slug reservations; normalize padded administrator roles. | `routes/spaces.py` | 70 passed |
| agent_spaces_people | Low / should-fix | Agent spaces and people | Skip membership count query on empty team pages: 2 → 1 SELECT. | `services/agent_people.py` | 10 passed |
| agent_change_requests | Medium / should-fix | Agent change requests | Publish committed state changes even when response refresh fails. | `services/agent_change_requests.py` | 36 related; 13 final regressions passed |
| agent_patch_plans | Medium / should-fix | Agent patch planning | Decode LOB/bytes text before no-op comparisons. | `services/agent_patch_plan.py` | 36 passed |
| agent_work_items | Low / should-fix | Agent item detail | Use existing joins for parent metadata: 2 → 1 SELECT. | `services/agent_work_items.py` | 23 passed |
| agent_graph_search | Medium / should-fix | Agent graph and search | Load only summary columns while preserving full projections and pagination. | `services/agent_work_graph.py; services/agent_work_search.py` | 23 passed |
| agent_discovery_audit | Medium / should-fix | Agent assigned work and audit | Project 26 instead of 79 columns; reject overflowing dates and nonfinite cursors. | `services/agent_assigned_work.py; services/agent_audit.py` | 27 distinct passed |
| projects_crud | Medium / should-fix | Project CRUD | Select parent program name without unused Program CLOB/entity loading. | `routes/projects/read.py` | 25 passed |
| projects_import_export | Medium / should-fix | Project CSV | Keep lookup failures within row rollback; decode objective LOB on export. | `routes/projects/import_export.py` | 33 passed |
| solutions_crud | Low / should-fix | Solution CRUD | Select IDs for existence/conflict checks instead of full entities. | `routes/solutions/common.py; routes/solutions/write.py` | 64 passed |
| solution_documents | Medium / should-fix | Solution documents | Return materialized bytes directly instead of a per-line streaming iterator. | `routes/solutions/documents.py` | 15 passed |
| solutions_import_export | Medium / should-fix | Solution CSV | Validate disabled phases in preview; join project name directly for export. | `routes/solutions/import_export.py` | 33 passed |
| tasks_crud | Medium / should-fix | Task CRUD | Normalize batch assignees; deduplicate and narrow repository lookups. | `routes/tasks/write.py; routes/tasks/common.py` | 35 passed |
| tasks_import_export | Medium / should-fix | Task CSV | Cache scalar parent IDs across row commits; preserve locked parent revalidation. | `routes/tasks/import_export.py` | 56 passed |
| shared_mutations | No demonstrated defect | Shared mutation services | Reviewed transaction, audit, lock and publication paths; no source edits. | `services/work_items.py; services/work_item_names.py; services/mutations.py; routes/_mutations.py` | 62 passed |
| programs_phases | Medium / should-fix | Programs and phases | Batch phase upsert reads; reuse validated solution and remove unused list. | `routes/phases.py` | 27 related; 9 final regressions passed |
| users_teams | High / must-fix | User and team administration | Include padded legacy roles in final-administrator counts, locks and listings. | `services/user_admin_guards.py` | 51 passed |
| my_work_backend | Medium / should-fix | My Work and repositories | Consolidate hierarchy/private-state queries: My Work 5 → 1; inventory 4 → 2. | `routes/my_work.py` | 26 passed |
| dashboard_endpoints | Medium / should-fix | Public and PM dashboards | Omit unused task blocker-note CLOB from PM report selection. | `routes/pm_dashboard.py` | 16 passed |
| report_data | Medium / should-fix | Report data | Defer seven unused CLOB fields; preserve output and four-query budget. | `services/program_dashboard_report_data.py` | 13 passed |
| report_renderers | Medium / should-fix | PDF and XLSX renderers | Match PDF font encoding to CP1252 text, fixing accented names/punctuation. | `services/pdf_utils.py` | 33 passed |
| analytics_backend | Medium / should-fix | Usage analytics and backfill | Retain sample-only/mixed identities; preserve latest timestamps; stop existence scans early. | `services/usage_analytics.py; services/analytics_backfill.py` | 46 passed |
| realtime_coordination | Medium / should-fix | Realtime and cache | Preserve cancellation; copy outside cache lock; ignore non-object Redis payloads. | `routes/sync.py; services/smart_cache.py; services/coordination.py` | 83; 1 Redis skip passed |
| audit_helpers | Medium / should-fix | Audit and utilities | Reject overflowing audit dates; batch phase initialization from 8 → 2 reads. | `routes/audit.py; utils/__init__.py` | 31 passed |
| agent_cli_scripts | High / should-fix | Agent CLI and benchmark | Validate JSON before network work; close responses; isolate/dispose local benchmark runtime. | `skills/sipm-agent/scripts/sipm_agent.py; scripts/benchmark_agent_api.py` | 54 passed |
| developer_tooling | Medium / should-fix | Developer scripts | Clean partial SQLite setup; reject malformed route maps and mapped directories. | `scripts/run_ui_smoke_app.py; scripts/run_developer_mode_demo.py; scripts/check_route_module_test_mapping.py` | 17 passed |
| frontend_shell | High / should-fix | Frontend shell | Scope shared session refreshes to the current user/session/space generation. | `ui/js/shell/session.js` | 197 passed |
| frontend_entities_utils | Medium / should-fix | Entity editors and utilities | Reset a deleted task editor without a second discard prompt. | `ui/js/entities/tasks.js` | 72 passed |
| frontend_dashboards | High / should-fix | Dashboard and governance routes | Make forced reads fresh/latest-owned; respect explicit owner IDs; remove duplicate loading render. | `ui/js/routes/spaces/interactions.js; analytics.js; dashboard/common.js; dashboard/render.js` | 171 passed |
| frontend_workflows | High / should-fix | Task and schedule workflows | Reject pre-write My Work snapshots; retain drafts and failed-save feedback through replacement reads. | `ui/js/routes/my-work.js; ui/js/routes/my-work/shared-actions.js` | 77 after integration repair passed |

Models, database definitions, migration helpers, route package boundaries, shared mutations, public dashboard gating, password/session lifecycle and several utility/render modules were reviewed and left intact where no concrete issue was proved. HTML and relevant styles were checked for interaction/semantic context; no visual redesign or stylesheet cleanup was attempted. There is no payment/billing surface in the inspected application.

## Dependency audit repairs

The root audit found known advisories in existing dependency locks. Python lock updates are limited to `certifi` 2026.6.17 → 2026.10.23 and `dnspython` 2.8.0 → 2.9.2; `requirements.in` is unchanged. These address the upstream [certifi CA trust advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) and [dnspython decompression advisory](https://github.com/rthalley/dnspython/security/advisories/GHSA-45c3-73f7-pv4m).

Frontend tooling updates retain the existing major versions: Vitest and its coverage provider require ^4.1.12; Vite and source-map-js locks use patched compatible versions. The [Vitest advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8), [source-map-js advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q), and [Vite advisory](https://github.com/advisories/GHSA-rq7h-c2jc-7f22) support these updates. A broad audit-fix preview was discarded in favor of targeted packages. Runtime application structure and frontend build architecture remain unchanged.

`npm run audit` passes its configured high-severity threshold. The Python lock audit reports no known vulnerabilities. Npm reports three moderate package findings from one remaining [minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249) and its ESLint dependents. The patched minimatch major is outside ESLint 10's dependency range; npm proposes a breaking ESLint downgrade. This remains a tooling follow-up, with no forced downgrade or transitive major override applied. `npm ci`, Python lock regeneration and installed-package compatibility checks pass.

## Validation

- Each material behavior change was first reproduced or characterized with focused tests. Performance tests assert query, column, bind or dispatch budgets alongside response/state behavior.
- The pre-edit frontend snapshot passed 999 tests. Full pre-edit backend sweeps were interrupted to prioritize final coverage; no failures were observed in completed portions. Agent-level before/after characterization supplies baseline evidence for every repair.
- Full backend coverage: **1,737 passed**, **90.17% total coverage**, exceeding the configured 80% threshold. Final command: `npm run test:backend:coverage -- -n 8 -q --tb=short`, with the isolated locked runtime on PATH. XML output: `coverage/backend-coverage.xml`.
- Full frontend coverage after integration/dependency repairs: **1,049 passed in 103 files**. Statements 76.98%, branches 65.74%, functions 80.32%, lines 80.84%; configured coverage thresholds pass.
- Browser smoke after integration/dependency repairs: **113 passed** on Chromium using the locked Python/SQLite runtime, including responsive layout, auth/session, route startup, document actions and keyboard/focus checks.
- Python and UI lint: **passed** with the repository's pinned Ruff command and ESLint.
- Requirements lock regeneration and route-module mapping: **passed**.
- Redis integration command ran and skipped its single test because `SIPM_REDIS_URL` is absent. Docker Desktop's engine is not running; no local Redis was started.
- SQLAlchemy Oracle compilation and existing Oracle-sized query regressions passed in focused runs. No live Oracle connection or production migration was exercised.
- The full local-environment run exposed an obsolete Kanban source-string assertion that also failed in the pre-edit snapshot. Replaced it with executed option-builder coverage that checks typed/pending Kanban owner filters survive data refreshes. Product behavior is unchanged. The remaining Python Kanban contract checks pass in the locked runtime; all 10 option-builder tests pass.
- Governance module-ownership coverage now checks the refresh helper's declaration without requiring a zero-argument signature. Forced-read behavior is covered by the new stale-success/error unit cases; the nine ownership/style contract checks pass.
- Final backend validation uses a separate Python 3.12 environment installed from the exact updated requirements lock, plus the optional pytest-xdist 3.8.0 test runner. Eight workers run the full non-integration suite using the documented [pytest-xdist execution mode](https://pytest-xdist.readthedocs.io/en/stable/). The user's older `.venv` is left intact. Browser validation also uses this locked runtime.
- PDF encoding was additionally checked with PDFium/pdfminer extraction and a rendered image. The encoding follows [Adobe PDF reference, Appendix D](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.6.pdf).
- Whitespace validation respects the repository's existing CRLF/mixed-line-ending state; unrelated files were not normalized.

Local evidence, logs, before-edit bytes, query probes and synthetic benchmarks are under `.tmp/health-review-20261106/`. The local snapshot supports reviewing or reversing individual edits without reverting unrelated user work.

## Closure ledger

**Fixed now:** the bounded defects and unnecessary work listed above, with focused regression coverage. Root integration checks additionally reviewed query/transaction semantics, frontend request ownership and auth/error behavior.

**Flagged for follow-up:**

1. Project sponsor PATCH normalization and sponsor identity synchronization differ from creation. Policy and compatibility need a focused contract decision before changing linked identities.
2. `services/work_items.py` retains dormant helpers: `deleted_project_name`/its `as_utc`, `publish_project_mutation`, `publish_project_deletion`, the unused solution publication wrapper chain, and the unused task publication/import chain. Current-branch searches found no runtime callers. They were left in place to keep the cleanup bounded.
3. Three moderate npm package findings remain from the minimatch/ESLint dependency chain. Handle the incompatible dependency update as a separate tooling-maintenance change; the configured high-severity audit gate passes.

Task estimate integer bounds, other already-materialized PDF/CSV streaming endpoints, and repeat locked patch validation were identified as advisory candidates; their contracts or broader callers need additional focused evidence before edits.

**Not verified:** live Oracle execution/performance, real Redis coordination, production network behavior and deployment/rollback. Browser tests exercise the local SQLite harness. Coverage percentages are test evidence, not proof of production readiness.

**Out of scope:** architecture/file reorganization, schema/migration changes, public API redesign, visual redesign, infrastructure/deployment changes and unrelated user edits.

The next useful pass is operational validation against real Oracle and Redis, followed by a narrow contract-alignment pass for sponsor identity handling. Dormant-helper deletion can be handled as a separate low-risk cleanup after confirming external consumers.

## CI browser follow-up

For commit `13dcfe5`, the [push workflow](https://github.com/lukegob10/sipm/actions/runs/42301667568) passed all checks. The [pull request workflow](https://github.com/lukegob10/sipm/actions/runs/42301693542) passed backend, real Redis integration, lint, audit and frontend unit checks, then failed one solution-editor browser scenario: the submitted name was `Original solutionRenamed solution` rather than `Renamed solution`.

The solution and task stale-field scenarios now wait for the intended editor identity and original name, focus the name input, and verify its replacement before saving. The PATCH-body and persisted-status assertions remain intact. No production editor logic or test retries were added. Local validation passed 30 focused executions (15 per editor scenario), all 113 browser tests, frontend lint and workflow YAML parsing.

Playwright now retains traces and screenshots on the first failed attempt, and CI uploads `test-results/` with seven-day retention and an attempt-specific artifact name. CI installs the headless shell already used by the suite, avoiding the unused headed Chromium download. These settings follow the [Playwright recording options](https://playwright.dev/docs/test-use-options#recording-options), [headless-shell installation guidance](https://playwright.dev/docs/browsers#chromium-headless-shell), and [artifact upload action](https://github.com/actions/upload-artifact). Current check and merge status is available on PR 135.

For commit `510855f`, the [pull request workflow](https://github.com/lukegob10/sipm/actions/runs/42336730677) passed completely; the [push workflow](https://github.com/lukegob10/sipm/actions/runs/42336724674) failed the analogous project scenario. The retained trace showed a fully populated, clean project editor before the external status PATCH, followed by a live list refresh. Clean editors intentionally adopt fresh server values, as covered by `editor-refresh.test.js`; the scenarios had assumed the old status would remain even before a user edit. Project, solution and task scenarios now make and verify a dirty name draft before the external status update. Their exact PATCH-body and persisted-status assertions are unchanged. Program editing also waits for the intended record before creating its draft.

The corrected ordering passed 45 focused browser executions (15 per scenario), all 113 browser tests, the 15 editor-refresh/changed-field unit checks and frontend lint locally.
