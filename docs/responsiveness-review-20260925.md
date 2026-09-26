# Responsiveness and bug-hunt review

- Date: 2026-09-25 (America/New_York)
- Mode: full-surface review with login and interaction latency as the priority
- Baseline: `82c69be`
- Integration branch: `codex/responsiveness-review-20260925`
- Status: review completed; fixes integrated and locally validated

The requested end state is prompt feedback after password submission, reliable
authentication and navigation, and responsive core workflows. This pass fixes
reproduced defects and verifies the combined changes locally. Local SQLite and
browser checks do not establish deployed Oracle, Redis, network, or device
performance, and are not a claim that every possible application bug is closed.

## Review ownership

Six isolated Codex tasks each used two or three `gpt-6-luna` subagents at `max`
reasoning effort. Subagents investigated and implemented confirmed fixes in
disjoint areas; their task owners reviewed and committed the results. This task
combined the commits and performed the overall validation.

The six tasks used 15 subagents. One additional `gpt-6-luna` / `max` subagent
fixed the startup asset regression discovered by combined integration checks,
for 16 subagents in total.

| Area | Scope | Task | Subagents |
|---|---|---|---:|
| Server login | Authentication, sessions, access checks, login query path | `01a0db3a-4cfe-7700-b26c-1eff89b9d1ac` | 2 |
| Browser login | Login feedback, session restoration, shell/navigation, shared state | `01a0db3a-4cf5-78c2-b110-1d23f5bbb50e` | 2 |
| Core APIs | Domain reads/writes, reports, imports/exports, tenant boundaries | `01a0db3a-4d30-7d23-ba34-e695ed2f5f8f` | 3 |
| UI workflows | Route modules, task/planning views, dashboards, administration, responsive layouts | `01a0db3a-4d2f-7b91-8d02-1ffa919aca6d` | 3 |
| Sync and agent APIs | Live updates, caching, agent requests, audit and analytics | `01a0db3a-5dee-72f1-92ba-b8b5d0f6f2a7` | 3 |
| Runtime and validation | Startup/shutdown, database resources, deployment, browser performance harness | `01a0db3a-6011-7cc0-8085-b3ac599dfc6c` | 2 |

The repository inventory and the previous performance reports were used to map
coverage. The inventory helper also includes ignored historical `.tmp` copies;
those are not active product surface and are excluded from review claims.

Detailed findings, reproductions, scoped validation, and source commit ledgers:

- [Server authentication and sessions](auth-session-review-20260925.md)
- [Browser startup and shell](browser-shell-review-20260925.md)
- [Core APIs and domain data](domain-backend-review-20260925.md)
- [Workflow routes and responsive UI](frontend-route-review-20260925.md)
- [Agent APIs, realtime updates, cache, audit, and analytics](agent-realtime-review-20260925.md)
- [Runtime, deployment, dependencies, and browser measurements](runtime-browser-review-20260925.md)

The area reports describe their own worktrees and handoff state. This integration
report records the combined result and closes cross-team follow-ups below.

## Existing local work

The original checkout had uncommitted My Work eligibility changes and tests in
`src/main/backend/app/routes/my_work.py`, `src/main/test/test_my_work.py`, and
`src/main/test/test_my_work_personal_state.py`, plus an untracked
`docs/treasury-transformation-adoption-review-20260912.md`. These changes belong to
the user and remain intact and outside the review commits. The independent
repository-inventory fix in the same route file was integrated separately.

## Baseline and validation

- UI baseline: 317 tests passed in 34 files using `npm run test:ui -- --maxWorkers=2`.
- Backend baseline: 615 passed, 1 integration test deselected in 279.88 seconds
  using `.venv/Scripts/python.exe -m pytest -m "not integration" -q`, with the
  preexisting local changes present.
- Redis integration environment: no `SIPM_REDIS_URL` is configured and Docker's
  Linux daemon is not running. Live Redis verification is currently unavailable.
- Browser timing samples must separate submit feedback, authentication response,
  and usable content. Concurrent review workloads make absolute local CPU timing
  noisy; deterministic request/query counts and regression behavior are stronger
  evidence during this run.
- The shared Python environment does not match `requirements.txt`. An isolated
  review environment was installed from that lock for final validation, including
  FastAPI 0.139.0 and SQLAlchemy 2.0.51. The original environment was not modified.
- The independently integrated repository-inventory fix passes all 11 combined
  My Work tests on locked dependencies. The original user diff remains identical
  except for the expected index blob hashes after committing the separate fix.

### Combined validation

The complete backend unit run was performed with coverage enabled, so the same
775 tests satisfy the unit and coverage checks without a duplicate full run.

| Check | Combined result |
|---|---|
| Backend unit tests with coverage | **775 passed**, 1 integration test deselected; 342.53 seconds |
| Backend coverage | **85.01%**, above the 80% gate; XML in `coverage/backend-coverage.xml` |
| Redis integration selection | **1 skipped**, 775 deselected; `SIPM_REDIS_URL` is not configured |
| Full Python lint | Passed with Ruff 0.15.21 |
| Requirements lock | Matches `requirements.in` |
| Python dependency audit | No known vulnerabilities |
| Installed npm dependency audit | 0 vulnerabilities at the moderate threshold after `npm ci` |
| Complete UI unit tests with coverage | **428 passed** in 43 files; 24.75 seconds |
| UI coverage | 58.45% statements, 47.01% branches, 61.13% functions, 61.82% lines; existing gates passed |
| Final UI lint and route/test mapping | Passed |
| Frontend Python contracts after lazy import integration | **41 passed**; changed Python contract also passes Ruff |
| Complete browser smoke after final integration | **34 passed** in 56.2 seconds; Chromium, one worker, bcrypt cost 12 |
| Whitespace and preservation check | `git diff --check` passed; original user patch and file hashes preserved |

The first complete browser smoke run passed **34 cases in 58.2 seconds**,
including a 250 ms upper bound for visible busy feedback under a deliberately
held login request. The first complete UI run passed 423 of 424 cases; its single
failure exposed the startup-asset budget overrun. The final UI run above includes
the corrected lazy imports and four additional regressions, with all 428 passing.
The final browser run also passed after the lazy import change. Windows Python
logged socket-close `WinError 10054` callbacks during browser teardown; these did
not fail requests asserted by the suite or any test. No remaining test failure is
being waived.

Local verification artifacts are retained under
`.tmp/responsiveness-review-20260925/`: `backend-coverage.log`, `ui-coverage.log`,
and `browser-smoke.log`. Backend coverage XML is in
`coverage/backend-coverage.xml`. These generated files are not committed.

The original user test/document SHA-256 values match their saved pre-review
values. The preserved My Work patch matches after removing only Git index blob
hash lines. Full backend validation includes those existing uncommitted changes.

## Closure ledger

### Fixed now

- Medium / should-fix: task-name sorting reconstructed locale options during
  every comparison. Reusing one collator per sort preserves natural numeric,
  case-insensitive ordering and removes repeated initialization. Focused tests
  cover equivalent names, missing names, both directions, and input preservation.
  Source: `src/main/ui/js/utils/task-sort.js`.
- Critical / must-fix: service-account browser cookies bypassed human-session
  boundaries, and password resets could leave very recently issued sessions valid
  for their remaining lifetime. Browser admission is now restricted to interactive
  users and reset operations revoke sessions in the same transaction. High /
  must-fix: valid login after lockout expiry could return 500 from a naive/aware
  datetime comparison in ORM synchronization. See
  [auth review](auth-session-review-20260925.md) for the reproductions and 117
  passing focused tests on locked dependencies.
- High / should-fix: blocked browser storage could halt startup; obsolete sync
  recovery could affect a replacement session, and rejected WebSocket handshakes
  reset retry bounds. Targeted browser/unit regressions accompany the fixes in
  `shell/activity-session.js` and `shell/live-sync.js`.
- High / should-fix: unrelated background refreshes could overwrite unsaved
  Project, Solution, and Task edits. Shared editor restoration and select rebuilding
  now preserve dirty fields; context/session generations discard obsolete
  workspace completions. Real browser refresh reproductions pass.
- High / must-fix: concurrent administrator removal could leave no global
  administrator. The guard now serializes removals and refreshes decision fields.
  Concurrent SQLite tests and Oracle SQL compilation validate the bounded fix;
  live Oracle locking remains unverified.
- Medium / should-fix: project reads and repository inventory admitted hidden or
  cross-space parent data. Explicit live-parent scope joins close these cases.
- Medium / should-fix: malformed phase updates and nonfinite roster capacities
  could reach server/database failure paths. They now produce input errors.
- Medium / should-fix: telemetry flushing could duplicate batches, discard newer
  events, and exceed the API batch limit. Daily analytics could count one identity
  more than once across spaces. Batch reservation and distinct counts correct the
  behavior, while batched rollup reads remove repeated lookups.
- High / should-fix: runtime failures could leak pooled connections or skip later
  cleanup, and deployment reported success before readiness. Cleanup now runs
  through failures; deployment waits for health checks; Uvicorn receives shutdown
  signals directly. Deployment execution was not performed.
- Medium / should-fix: request logging could trigger an ORM SELECT, and unhandled
  errors lacked the normal request/security headers. Logging now uses persisted
  identity metadata and error responses retain the required headers.
- Medium / should-fix: two confirmed development-tool advisory families are
  patched through narrow Vitest/coverage and humanfs lock updates. The updated
  lock was installed with `npm ci` after the worker browser tests finished.
  The installed dependency audit reports zero vulnerabilities at the moderate
  threshold. The pinned Python dependency audit reports no known vulnerabilities.
- High / must-fix: editable names and option values could create unintended
  option/datalist markup. Both shell and task-workbench builders now escape them;
  actual renderer tests verify literal values, labels, and assignee propagation.
- Medium / should-fix: entity saves could submit twice, overwrite newer drafts,
  or apply old results after a workspace/session change. Per-editor and context
  guards preserve current edits. Approvals and analytics now scope cached data
  and in-flight work to the current identity and space.
- Medium / should-fix: My Work and Repositories searches lost caret position on
  render. Calendar day controls and Kanban phase changes lacked equivalent native
  keyboard actions. Caret, focus, and responsive browser checks cover the fixes.
- High / should-fix: approved entity changes and change-request status could
  commit separately. They now share one transaction with rollback regressions.
  Optimistic version checks lock the target rows before applying a plan.
- High / should-fix: a Redis listener callback signature mismatch prevented
  refresh delivery, and fallback cache versions could alias a later remote value.
  Callback and generation fixes have regression coverage. Slow socket clients
  now have bounded concurrent sends, and synchronous coordination/authentication
  work runs outside the websocket event loop.
- Medium / should-fix: moving a solution left child task project IDs stale, soft
  deletion retained conflicting unique names, malformed CSV inputs reached error
  paths, and metadata lists loaded full document BLOBs. Scoped write/import/read
  fixes preserve parent relationships, reusable names, and download contents.

### Integration findings and cross-team closure

- The shell task-delete marker and all four caller removals are integrated
  together. Cancelling confirmation no longer consumes an unrelated refresh.
- A held task-delete confirmation or batch could continue under a replacement
  account/space. Three new regressions failed before the root fix; all four helper
  cases pass afterward. Pending batches stop, and obsolete completions return a
  cancelled result before callers can change the current UI. Already committed
  deletes remain committed in their original space.
- Held Program, Project, Solution, and Task deletions could close/reset a newer
  editor or show the old operation's error there. Revision guards now preserve
  the newer editor while updating the successfully deleted record and lists.
  Failed Task deletions keep the original draft available for retry.
- The Task workbench also refilled dirty fields and reselected a previously saved
  task after its request completed. Draft baselines preserve edited fields while
  allowing untouched fields to refresh; selection/session guards keep late saves
  and notices in their original editor. Deferred-request unit tests and two
  Chromium reproductions verify task switching and edits during a pending save.
- The Team aggregate fix now locks the scoped parent before member writes and
  recomputation. A single commit alone did not prevent lost totals under Oracle
  READ COMMITTED. Tests verify lock ordering and actual Oracle SQL compilation;
  SQLite concurrency checks are not a substitute for live Oracle contention.
- Unique-ID agent locking queries initially used `.first()`, which emitted
  `FETCH FIRST ... FOR UPDATE`. Oracle forbids combining those clauses. The
  corrected queries use `.one_or_none()`; all eight update/archive compilation
  regressions fail before and pass after the correction. See the
  [Oracle SELECT reference](https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/SELECT.html).
- The websocket blocking-auth follow-up from the auth report is closed by the
  realtime package. The session/context and approval follow-ups from that package
  are closed by the shell and workflow packages.
- Agent program-write name bounds reported by the domain team are closed by the
  agent package. Administrator mutations refresh active/role fields after waiting
  for locks and revalidate current same-space membership where required.

Combined validation caught a stale source-text test and excess startup assets.
The obsolete assertions are replaced with actual DOM checks for description and
canonical/legacy acceptance criteria. Workbench controls and its editor now load
through the lazy Tasks route. Shared form helpers use one module. The initial
static graph is **34 modules / 407,128 bytes** (LF normalized), inside the
unchanged limits of 37 modules and less than 425,000 bytes. A held-import browser
test verifies that the search draft survives while the Tasks route is loading;
the input listener remains bound once. The solution-filter option renderer also
escapes untrusted IDs and names, with a DOM regression covering both.

## Performance evidence

These are local query counts or controlled browser measurements, not production
latency guarantees.

| Path / fixture | Before | After |
|---|---:|---:|
| Member login SQL statements | 7 | 6 |
| Activity service SQL statements | 3 | 1 |
| Administrator selected-space lookup SELECTs | 2 | 1 |
| Task-list SELECTs | 2 | 1 |
| PM report SELECTs | 4 | 3 |
| List 12 teams SELECTs | 13 | 2 |
| List 12 access requests SELECTs | 25 | 3 |
| Rollup lookup SELECTs for 100 distinct events | 500 | 5 |
| Logging an expired persisted user SELECTs | 1 | 0 |
| Agent work graph SELECTs | 5 | 4 |

Login retains one connection checkout and one commit in the measured fixture.
Password hashing strength and lockout protections remain intact. A bcrypt-12
SQLite browser probe delivered visible feedback before the authentication
response, including a synthetic 700 ms request delay, and issued one login request
under duplicate submission. Single samples varied with host contention; the
reported intermittent deployed delay has not been reproduced or timed here.

Final combined Chromium run, on local SQLite with bcrypt cost 12:

| Scenario | Visible busy feedback | Authentication response | Usable content | Login requests |
|---|---:|---:|---:|---:|
| Local sign-in | 11.9 ms | 205.3 ms | 257.2 ms | 1 |
| Added 700 ms request hold | 13.6 ms | 914.4 ms | 987.2 ms | 1 |

These are individual shared-host observations, not percentiles or a before/after
production comparison. The runtime package contains independent measurements and
reproduction instructions. Both runs passed the 250 ms visible-feedback bound
under the held request. The login path also fixes the reproduced post-lockout
500 response and reduces database queries without weakening password hashing.

### Flagged for follow-up

- Capture a delayed deployed sign-in with request correlation, Oracle query/wait
  times, pool checkout, worker contention, and browser phase timings. The local
  bug fixes do not prove the intermittent production delay has been eliminated.
- The existing global-admin exception for explicitly selecting another owner's
  personal space differs from listing behavior. Intended policy is ambiguous;
  this review preserves it. Refresh-token rotation and absolute session lifetime
  are separate policy questions, not confirmed regressions in this pass.
- The manual developer-demo script has no repository references but no confirmed
  replacement. It remains available pending a maintainer usage decision.
- CSV exports retain literal user text, including formula-like strings. Changing
  that behavior needs a spreadsheet-safety versus round-trip contract decision;
  generated XLSX reports already write those values as strings.
- Historical task/project inconsistencies caused by earlier solution moves need
  a scoped deployed-data audit before repair. This change prevents new ones and
  does not infer or rewrite existing production records.

### Not verified

- Deployed Oracle execution plans and connection latency.
- Production Redis and multi-instance behavior.
- Corporate-network and real-device login distributions.
- Container build, real SIGTERM delivery, and deployed health transitions because
  the Docker daemon was unavailable. Workflow shell behavior is tested locally.
- Concurrent first inserts into analytics rollups. Existing Redis PubSub outage
  drops still have no replay; this review does not add durable messaging.

### Out of scope

- Deploying the application or changing live data.
- Pushing branches or opening a pull request.
- Broad architecture rewrites and speculative performance tuning.
