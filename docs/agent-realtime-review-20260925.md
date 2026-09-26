# Agent, realtime, cache, and analytics review

Date: 2026-09-25. Mode: full-surface review within the assigned ownership boundary.
Base: `82c69be2e71faef18c1a99b5e820aac8e6a78cb4`.
Worktree: `C:/Users/Luke Goblirsch/.codex/worktrees/d973/sipm`.
Branch: `codex/review-agent-realtime`.

## Scope and sources of truth

This is the agent API, realtime/cache/coordination, mutation publication, audit,
analytics, and browser live-sync portion of a coordinated repository review.
The intended end state is bounded fixes for confirmed defects, preserved tenant
and authorization contracts, regression coverage, and measured performance claims.
Combined repository validation and deployed performance remain separate.

Sources reviewed include CONTRIBUTING.md, repository/backend READMEs, agent
contracts and architecture/security/performance docs, schemas, runtime call sites,
tests, CI, and Python/UI test configuration. The clean-code-review skill and its
safety, full-surface, language, frontend, performance, testing, and closure
references were applied. No applicable AGENTS.md was found. Repository inventory
and the stale-script helper were run. Filename heuristics marked imported modules
and test/config entrypoints as candidates; this did not establish unused code.
No stale scripts were deleted.

Three implementation subagents were explicitly configured with
`model=gpt-6-luna`, `reasoning_effort=max`, and `fork_turns=none`: agent API;
realtime/cache/reliability; analytics/audit. The parent reviewed their changes,
handled live-sync and integration regressions, and created cohesive commits.

## Findings fixed

### High / must-fix: approval entities and request status could commit separately

A fault during the final approval-status commit left a created project persisted
while its request remained pending. Whole-request and selected-operation approval
now apply the patch inside a savepoint, commit entity changes and final request
state together, and publish only after that commit. Savepoint rollback preserves
an outer transaction that can record a failed application. Regressions inject
commit and integrity failures and inspect persisted state.

Apply validation refreshes and locks target rows before optimistic timestamp
checks; cancel/reject transitions also lock the request. Integration review found
that new `first()` locking lookups generated Oracle's unsupported
`FETCH FIRST ... FOR UPDATE` combination. All five unique-ID fetch sites now use
`one_or_none()`. Eight regressions capture actual validation statements and compile
them with the Oracle dialect, covering update/archive for each entity. All eight
failed with the unsupported SQL before correction. This verifies SQL construction,
not live Oracle transaction or contention behavior.

Files: `services/agent_change_requests.py`, `services/agent_patch_plan.py` under
`src/main/backend/app`, and agent tests. Commits: `6de1473`, `d2717b8`.

### High / must-fix: Redis notifications never reached the registered callback

The Redis listener passed `(entity, space_id)` positionally, but realtime's
callback required `space_id` as a keyword. Valid notifications raised TypeError
and restarted the listener. The callback now accepts the listener's contract.
A fake PubSub integration regression invokes the actual handler and verifies
matching-space delivery. Files: `services/realtime.py`,
`test_coordination_backend.py`. Commit: `fc1c1b5`.

### High / must-fix: Redis recovery could reuse a stale cache generation

Failed Redis invalidation advanced local state, but later reads could reset or
collide with that generation. Merely choosing the maximum also allowed collisions
when Redis caught up. The backend now tracks the last remote version separately
from a local generation and advances the latter on local invalidation, first
remote observation, and subsequent remote changes. Fault/recovery tests cover
failed reads and invalidations. Files: `services/coordination.py` and its tests.
Commit: `fc1c1b5`. Cross-worker consistency still depends on Redis availability.

### High / must-fix: committed mutations could remain unpublished

ORM refresh ran between commit and cache invalidation/publication. Refresh failure
therefore hid an already committed change from other clients. Publication now runs
after successful commit even if refresh raises; failed commits still do not
publish. A focused fault regression verifies the exception and publication.
Files: `services/mutations.py`, `test_mutations_backend.py`. Commit: `64af4bf`.

### High / must-fix: obsolete browser recovery affected replacement state

Delayed auth recovery could expire a replacement session or close its socket.
Delayed space recovery could clear replacement data, report an obsolete auth
error, and reconnect after an explicit stop. Visibility refresh could restart
stopped sync. Six regressions reproduced those failures. Async continuations now
capture a connection generation and user; stop/restart invalidate recovery, and
only the matching recovery promise can clear itself.
Files: `src/main/ui/js/shell/live-sync.js` and its unit test. Commit: `79bd6fe`.

### High / must-fix: rejection handshakes bypassed retry limits

The server accepts a WebSocket before returning an application rejection code.
Resetting recovery state on browser `open` caused repeated auth/space recovery and
kept busy retries at their initial delay. Three regressions reproduced failures.
Recovery state now survives rejected handshakes and resets after a refresh message
or an ordinary disconnect from an opened connection. Another regression preserves
recovery for a quiet legitimate connection. Existing protocol/close codes remain.
With deterministic jitter, busy attempts changed from 0, 1, 2 seconds to 0, 1, 3
seconds; repeated auth/space rejection recovers once before its terminal state.
Files: live-sync controller and test. Commit: `79bd6fe`.

### Medium / should-fix: slow coordination delayed unrelated realtime work

Synchronous Redis publication and WebSocket authentication blocked the event
loop; serial sends let one slow recipient delay others. Publication and database
authentication now run in workers; fanout uses concurrent sends bounded to five
seconds each and bounded failed-socket closure. Authentication extracts primitive
IDs and closes the Session in its worker. Explicit shielding waits for completion
through repeated task cancellation, avoiding concurrent dependency cleanup.
The cache no longer holds its global lock during Redis version reads; deep-copy
isolation is retained. Pending connection slots are reserved before awaiting
accept, and shared connection state is guarded, closing an admission-limit race.
Files: `routes/sync.py`, `services/realtime.py`, `services/smart_cache.py`,
`services/coordination.py`, and tests. Commit: `fc1c1b5`.

### Medium / should-fix: analytics overcounted daily identities across spaces

All-space daily series counted identity rows per space instead of distinct tokens
per day. A token in two spaces counted as two. Daily aggregation now deduplicates
identities across spaces; fixtures demonstrate the corrected count of one.
Ingestion also issued a SELECT per rollup key. It now fetches existing rows in
bounded batches of 100 composite keys and reuses pending rows. Repeated ingestion
in one Session accumulates counts without duplicate identities. Concurrent first
insertion by separate Sessions remains unverified.
Files: `services/usage_analytics.py`, `test_usage_analytics.py`. Commit: `fb4297d`.

### Medium / should-fix: audit filters mishandled offset timestamps

An event stored at 12:00 UTC could disappear for a since filter of 15:00+03:00.
Aware since/until values now normalize to UTC-naive timestamps before comparison.
Tests cover positive-offset since and negative-offset until boundaries.
Files: `routes/audit.py`, `test_audit.py`. Commit: `497ddf2`.

### Medium / should-fix: agent validation allowed inconsistent requests

Bulk review rejects empty/repeated request IDs before any transition. Program
create/update validation enforces the canonical 255-character name bound with
the agent error contract. Preview accepts 255 and rejects 256 characters; invalid
submissions return 400 before storage. Files: agent change-request and patch-plan
services/tests. Commit: `6de1473`.

### Low / advisory, improved: work-graph construction repeated a program query

Already-loaded program nodes now supply program names, removing one query per
graph build. The small local benchmark did not show a latency win.
File: `services/agent_work_graph.py`. Commit: `6de1473`.

## Performance evidence and limits

These are controlled local proxies, not Oracle or deployed login measurements.
Authentication rules, password hashing, and security controls were not weakened.

| Workload | Before | After | Evidence limit |
| --- | ---: | ---: | --- |
| 100 distinct analytics events, SQLite in memory | 500 SELECTs; median SQL 16.59 ms; service 672.08 ms | 5 SELECTs; median SQL 11.35 ms; service 326.01 ms | Three runs; ingestion service only |
| Cached get while another version read is blocked | 160.4 ms | 0.020 ms | Controlled lock-contention probe |
| Eight sockets with artificial 30 ms send delay | 272.5 ms | 30.9 ms | Single controlled comparison; no real network |
| 40 work-graph calls, one program/project/solution/task | 200 queries; mean 3.381 ms | 160 queries; mean 3.926 ms | Service only; noisy timing, no latency-win claim |

Retry scheduling and obsolete-request suppression reduce repeated work. Browser
smoke confirms login/reopening behavior; it does not establish deployed latency.

## Validation

- Live-sync baseline: 14 unit tests passed. Final: 24 passed, including nine
  reproduced failures and quiet-connection characterization. Focused ESLint passed.
- `test_live_sync_session_frontend_contract.py`: 7 passed.
- Playwright `auth-and-deliverables.spec.js`, one worker, port 8775: 7 passed
  initially in 13.8 seconds and after backend changes in 15.1 seconds. Covers
  local login, bootstrap failure, project creation, and reopening three routes
  with one context request. A Windows transport-close callback emitted a
  ConnectionResetError during shutdown; all assertions passed. Suite duration is
  not a user-journey latency measurement.
- Agent API and change-request idempotency modules: 36 passed. With Oracle follow-up
  and `test_agent_patch_plan.py`: 44 passed in 34.76 seconds.
- Realtime/cache/coordination baseline: 35 passed, 1 skipped. Expanded suite,
  including mutation faults: 49 passed, 1 skipped. Final realtime/cache rerun
  after lifecycle adjustments: 35 passed. Counts overlap and are not additive.
- Audit, usage analytics, request audit correlation: 20 passed.
- Targeted Ruff passed; Oracle follow-up used pinned Ruff 0.15.21. Backend
  architecture boundary test and route-module test mapping check passed.
- Staged and committed whitespace checks passed. Full backend/UI suites, coverage,
  and combined browser checks belong to coordinator integration.

Tests use `F:/vault/projects/the-eco-system/sipm/.venv/Scripts/python.exe` and an
ignored node_modules junction for dependencies; source runs from this worktree.
The local runtime has SQLAlchemy 2.0.46; the coordinator reproduced the Oracle SQL
issue with pinned 2.0.51 too. Compilation tests require no live Oracle database.
Real Redis integration was skipped because SIPM_REDIS_URL is absent; coordinator
reports Docker unavailable. No original-checkout source files were edited.

## Coverage and closure ledger

| Surface | Status |
| --- | --- |
| Agent reads, graph/search, patch validation/application, review lifecycle | Reviewed; fixes in patch/review/graph paths |
| Sync, connection admission, fanout, Redis listener/publication | Reviewed and edited; lifecycle/failure regressions |
| Cache generation, invalidation, mutation commit/publication | Reviewed and edited; copy isolation preserved |
| Analytics ingestion, rollups, summaries | Reviewed and edited; concurrent first-write race unverified |
| Audit feed/logging/correlation and filters | Reviewed; filters edited; logging/correlation unchanged |
| Browser live-sync | Reviewed and edited; lifecycle, retry, request-count coverage |
| Other shell/workflow state | Cross-boundary races reported to owners; not edited here |
| Auth policy, security/dependencies, runtime/database, core routes, other UI | Owned by other coordinated tasks; excluded here |

- **Fixed now:** confirmed findings above, including the Oracle integration finding.
- **Flagged for follow-up:** obsolete shell context and Spaces approval responses
  can apply after a user/space change; coordinator forwarded both to UI owners.
  Service-account cookie/direct-write concerns belong to the auth owner.
- **Not verified:** live Oracle contention/rollback behavior and query plans;
  real Redis outage/reconnect and cross-worker behavior; analytics concurrent
  first writes; deployed login latency; combined six-task validation. Redis PubSub
  messages lost during outage are not replayed by these changes.
- **Out of scope:** schema migrations, deployments, pushes, PRs, external service
  changes, protected original-checkout my_work edits/tests and adoption document.
- **Cleanup blocked:** automatic review rejected deleting generated test-temp
  directories with `blocked by policy`. `.pytest_tmp_realtime_baseline/` remains
  untracked; `.tmp/pytest_realtime_scope/` and `.tmp/pytest_realtime_final/` remain
  ignored. They are excluded from commits. No workaround deletion was attempted.

Next validation should combine the owners' changes, then exercise real Oracle and
Redis under concurrent requests and profile deployed login. Those are the highest
value remaining gaps. This report does not claim production readiness or complete
optimization. Revert individual commits in reverse order for rollback. No schema
migration or new operator configuration is introduced.

## Commit ledger

| Commit | Change |
| --- | --- |
| `79bd6fe45e4b25a46c85d894ece10750a6a40795` | Bound rejected handshakes and discard stale recovery |
| `fb4297dd029c74c77b138185a9f4f8c296486a7f` | Deduplicate daily identities and batch rollup lookups |
| `6de1473e68621c1e9fe969b97cd2ced0f1a7ea28` | Atomic approvals, patch contracts, graph query reduction |
| `64af4bf214f72ff1533d1d19f535814936f5838d` | Publish committed changes after refresh failure |
| `fc1c1b54db0a9c79a3215d0e2395e3f14822ddc9` | Restore Redis delivery and isolate slow coordination |
| `497ddf2864e56a9d1758ffe0020313152d938136` | Normalize audit timestamp filters to UTC |
| `d2717b88a978e66c7da63cf5091ca5de205fe781` | Preserve Oracle row locking without a fetch limit |

## Primary references

- [Oracle SELECT restrictions](https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/SELECT.html):
  row limiting cannot be combined with FOR UPDATE; compilation regression added.
- [AnyIO worker threads and cancellation](https://anyio.readthedocs.io/en/stable/threads.html):
  default shielding informed lifecycle review; explicit asyncio shielding and
  repeated-cancellation tests protect this caller.
- [SQLAlchemy Session concurrency](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks):
  Session state must not be accessed concurrently, including queries and cleanup.
