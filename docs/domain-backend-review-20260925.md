# Domain backend review — 2026-09-25

Mode: **full-surface review within the assigned non-auth domain backend**. This pass fixes bounded, reproduced defects and avoids schema, public route, and authentication-strength changes. It does not certify production performance or complete the coordinating review's full-system validation.

Worktree: `C:/Users/Luke Goblirsch/.codex/worktrees/2821/sipm`; branch: `codex/domain-backend-review`; base: `82c69be`.

Three requested subagents ran with **gpt-6-luna / max**: read/query paths; write/import/document paths; programs/public/reports. The root agent integrated their changes and reviewed users, teams, spaces, phases, domain helpers/models, and the authorized independent repository-inventory hunk.

## Sources and coverage

Read `CONTRIBUTING.md`, root/runtime READMEs, package/pytest/ruff entrypoints, relevant route/schema/model/test contracts, canonical Oracle DDL, and the clean-code-review safety, comprehensive-audit, Python, testing, performance, and end-state references. No nonempty applicable `AGENTS.md` was found. The skill's surface and stale-script inventories ran; heuristic stale hits were not treated as proof and no scripts were removed.

| Surface | Closure status |
| --- | --- |
| Projects, solutions, tasks: reads/writes/import/export and domain tests | Reviewed; bounded correctness and query fixes |
| Solution documents | Reviewed; metadata projections exclude the BLOB; existing size, filename, tenant, deletion, and download checks retained |
| Programs, public dashboards, PM/report data and PDF/XLSX generation | Reviewed; scoped report/input/query fixes |
| Users, teams, spaces, phases and relevant domain helpers/models | Reviewed; administration, transactions, input validation, and query fixes |
| My Work | Existing dirty eligibility changes read only; separately authorized repository-inventory hunk committed independently |
| UI, login/session/auth/deps/security, agent/sync/audit/analytics/coordination, runtime/DB configuration | Out of scope; owned by other coordinating tasks |
| Redis integration, complete backend coverage, browser smoke, live Oracle | Not verified in this task; coordinating validation required |

## Fixed now

| Severity | Finding and repair | Evidence |
| --- | --- | --- |
| P1 / high | Concurrent role revocations or deactivations could remove every active global administrator. Role/activation checks now serialize on ordered administrator row locks and refresh stale role/active fields, with permission rechecks. | Before: three two-session cases returned two successes and zero admins. After: one success and one HTTP 400; stale promotion/authorization and Oracle SQL regressions. SQLite local concurrency, not live Oracle. |
| P1 / high | Administrator actors loaded before lock waits could retain stale role, active status, or space authority. | Fresh actor fields and same-space membership/permission checks reject revoked authority before mutation. Tests cover demotion/deactivation, absent/member-only membership, membership revocation, and continued authority for a real space admin. |
| P1 / high | Project list could expose a Program name from another tenant through a mismatched parent link. | Explicit parent-space filter and cross-space regression. Deleted program labels are also omitted from project detail. |
| P2 / medium | Moving a solution left dependent tasks assigned to the former project. | Atomic same-space task propagation/cache invalidation; regression also deletes the former project and confirms the moved work remains available. |
| P2 / medium | Team-member changes committed before capacity recomputation, so aggregate failure left a partial write. | Failure injection for create/update/delete; member and team capacity remain unchanged after rollback. |
| P2 / medium | Independent team-member transactions could compute stale aggregate capacity under row-level concurrency. | Team mutations now acquire a scoped active Team lock before member writes, then aggregate and commit once. The actual evaluated lock compiles without Oracle row limits; mutation-order/no-autoflush checks and a two-session SQLite proxy pass. The Oracle race was identified by transaction analysis, not reproduced against a live Oracle instance. |
| P2 / medium | Deleted work-item names still occupied database unique keys, blocking recreation, rename, or import. | Bounded tombstone names release keys in the same transaction; create/rename/import regressions include legacy deleted rows. |
| P2 / medium | Repository inventory included solution/task repositories under deleted or cross-space projects. | Two reproductions returned hidden repository entries before the fix; both now omit them. Original eligibility edits are preserved. |
| P2 / medium | Invalid phase-list items raised unhandled Pydantic exceptions. | Four malformed-item cases now return HTTP 422 with item locations and no partial phase update. |
| P2 / medium | Nonfinite roster capacity and solution confidence values were accepted or crashed imports. | NaN/infinity/overflow cases rejected per row; roster preview and import agree. |
| P2 / medium | CSV rows with extra values silently dropped data; unknown task booleans became false and malformed CSV could raise an unhandled error. | Row-width and boolean validation plus strict CSV parsing produce import errors; preview/import regressions. |
| P2 / medium | Program names longer than the canonical 255-character Oracle column reached database errors. | Create/update validation and unchanged-row regression. |
| P2 / medium | Program report filters could exceed older Oracle versions' 1,000-expression `IN` limit. | Batched predicates compile to `[1000, 1]` for 1,001 IDs; public/private PDF/XLSX selected-space regressions. |
| P2 / medium | Team and access-request lists performed per-row related-record queries; tasks and PM reports repeated or loaded unused data. | Query-count regressions and existing domain/report tests; measurements below. |
| P2 / medium | Document metadata reads loaded document BLOB contents unnecessarily. | SQL projection assertions exclude the content column without lazy follow-up queries; a 1,040,000-byte download still matches exactly. |

The global-admin locking follows the existing space-admin locking approach. Oracle documents that `SELECT FOR UPDATE` waits on conflicting row locks; the application rechecks state after acquiring them. [Oracle locking documentation](https://docs.oracle.com/en/database/oracle/oracle-database/21/adfns/sql-processing-for-application-developers.html). Lock queries must also avoid row-limiting clauses; the Oracle SQL reference prohibits combining them with `FOR UPDATE`. [Oracle SELECT reference](https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/SELECT.html). No live Oracle contention experiment was performed.

## Performance evidence

All numbers are **local SQLite SELECT counts with test authentication dependencies**, measured on uncached route/data loads. They are round-trip proxies, not production latency claims. Password hashing, rate limits, and authentication were unchanged.

| Path / fixture | Before | After |
| --- | ---: | ---: |
| Team list, 12 teams | 13 | 2 |
| Access-request list, 12 requests | 25 | 3 |
| Access-request list, 501 requests | Not rebenchmarked | 5; batch-boundary regression |
| All-task list | 2 | 1 |
| Tasks for one solution | 3 | 2 |
| PM command report with project/solution/task | 4 | 3 |
| Program report with one project and no solutions | 4 | 3 |

The PM report also selects only consumed columns and groups solutions by project once instead of rescanning the solution list for every project. No timing claim is attached to those changes.

Document list reads retain two SELECTs but omit BLOB data and issue no lazy content query; download still loads the original bytes. This is projection evidence, not a production bandwidth or latency measurement.

## Validation

- Root admin/scoping/input group: **73 passed** on the coordinator's freshly installed locked dependencies.
- Program/public/report group: **21 passed** on locked dependencies.
- Team transaction, team scope, read-review, and PM report follow-up: **19 passed** on locked dependencies.
- Final Team lock/atomicity group: **7 passed** on locked dependencies; actual evaluated Oracle SQL, no pre-lock autoflush, Team-before-member mutation order, and two-session local capacity totals are covered.
- Final existing team-scope and administrative read group: **16 passed** on locked dependencies after the Team lock follow-up.
- Document list/delete/download group: **5 passed** on locked dependencies.
- Final administrator authority/management/user-scope group: **41 passed** on locked dependencies after same-space authority revalidation.
- Affected project/solution/task write/import routes: **97 passed** on locked dependencies; final review cases after legacy rename additions: **21 passed**.
- Administrative read batch boundaries: **7 passed** on locked dependencies.
- Extra-column roster cases: **2 passed** on locked dependencies.
- Earlier project/solution/task/read/PM regression group: **61 passed** on the original shared environment; relevant focused checks repeated with locked dependencies and full combined validation remains with the coordinator.
- XLSX formula-like text was inspected in generated XML and is already written as string cells; no XLSX sanitizer change was required.
- Final `uvx ruff==0.15.21 check` passed for every changed Python file; `git diff --check` passed.
- All three workers and their test processes finished. The root's final Team test process also exited successfully. No npm, browser, or background service was started by this task.

These groups overlap and must not be summed into a unique test total. The locked Python environment was `F:/vault/projects/the-eco-system/sipm/.tmp/responsiveness-review-20260925/venv/Scripts/python.exe`.

The final concurrency checks were `pytest -q src/main/test/test_team_concurrency_review.py src/main/test/test_team_transactions_review.py`, `pytest -q src/main/test/test_teams_space_scope.py src/main/test/test_domain_admin_reads_review.py`, and `pytest -q src/main/test/test_global_admin_concurrency_review.py src/main/test/test_global_admin_management.py src/main/test/test_users_space_scope.py`. The task worktree was checked clean after the report commit; the coordinator integrates the code commits into the original worktree while preserving its existing user edits.

No deployment, push, PR, external-service mutation, or live database data repair was performed. Full backend/coverage/Redis/UI/browser runs from `CONTRIBUTING.md` are explicitly left to the coordinator to avoid duplicate full suites.

## Flagged for follow-up

1. CSV exports preserve formula-like user text. Spreadsheet-safe escaping needs an explicit export/round-trip contract; this pass does not silently alter exported text. XLSX reports already disable formula parsing.
2. Historical tasks left inconsistent by earlier solution moves require a scoped data audit/repair decision. The new move transaction prevents new inconsistencies; no production rows were changed.
3. Equivalent name-length validation in agent program-write paths is outside this task's ownership and was reported to the coordinator.

Follow-up mode: **operational hardening** on Oracle concurrency and query plans, then **contract alignment** on CSV spreadsheet safety and historical task-parent consistency. The remaining validation and external surfaces prevent a whole-repository closure claim.

## Commit inventory

Apply in this order. The first commit is the separately authorized My Work repository-inventory hunk; it does not include or replace the original worktree's user edits.

| Commit | Change |
| --- | --- |
| `4a5f345d64f8e86de53f31572210ad4875735dfd` | Repository inventory requires an available same-space project |
| `eea5ef5848e9af3c551ce2637ddcf68d1058d1d3` | Scoped project reads and task/PM query reductions |
| `29952ce7b97f4229e9674195a032fd59aa4ff58d` | Malformed phase updates return validation errors |
| `14dde9d7fc4d22a4ca61631d2e0961c8279ec343` | Nonfinite roster capacity rejected |
| `47aea51681e47cb437798712e2e45ac683877d75` | Final-global-admin mutation serialization |
| `0bf69e4f2a624fcf293542fa9f14f2742d6abdfe` | Team/access-request read batching |
| `bb616e12b5cd75b560e83c50b069ff23a887c8e8` | Program name and Oracle report-filter bounds |
| `4320d125caf8b79e96afd77559a3857bda10fbf6` | Atomic member/capacity transactions |
| `9693f8fa48c91d726d3daa7c51a0e6d96966213f` | Deleted program labels omitted |
| `c8c0dd6efe877364d2f4dce495d586d5015258e3` | Document metadata reads exclude content |
| `fce387bd4251c1f641d52d8d69d08b527b3bdfd6` | Actor authority refreshed after lock waits |
| `e52f71048072d928634e97c2ece47a5cde60a792` | Work-item lifecycle and CSV import corrections |
| `98f1d97627d62aae5c44cedd1a59287d215aee16` | Team lock before member writes and capacity aggregation |
| `64f54255242b7c14768b165b1fbec728b82a7184` | Same-space authority revalidated after lock waits |
