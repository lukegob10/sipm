# Authentication and session review

Date: 2026-09-25. Mode: full-surface review within the assigned server authentication scope.
Base: `82c69be2e71faef18c1a99b5e820aac8e6a78cb4`.
Worktree: `C:/Users/Luke Goblirsch/.codex/worktrees/62c3/sipm`.

The target is reliable password sign-in, preserved authentication strength, and fewer avoidable database round trips. This pass fixes the confirmed local defects below. It does not establish the cause of an intermittent production delay or claim that production latency is resolved.

Two explicitly requested subagents investigated and implemented fixes: `login_hot_path` and `session_correctness`, each launched with `model=gpt-6-luna`, `reasoning_effort=max`, and `fork_turns=none`. The parent reviewed and integrated their edits, tightened reset transaction ordering and response consistency, and implemented the shared token-validation and selected-space changes.

## Fixed findings

| Severity / disposition | Finding and evidence | Change |
| --- | --- | --- |
| Critical / must-fix | Service accounts could obtain password-login cookies. Human-only and direct-write guards classified the cookie as interactive, and agent listing used the credential type to decide ownership filtering. Baseline regressions returned 200 for service password login and for a pre-conversion cookie after its user became a service account. This contradicts the documented human/service-account separation. | Reject service-account password login and refresh. Reject service-account access-session authentication centrally, including existing cookies and WebSocket callers. The successful-login SQL predicate also checks account type to prevent conversion during password verification from issuing a session. PAT authentication remains supported. |
| Critical / must-fix | Password reset relied only on `password_changed_at`; its one-second token-precision tolerance could leave tokens issued in the same second valid for their remaining lifetime. Reset completion could also leave their same-session refresh path usable. | Revoke active sessions when a temporary password is issued and when reset completes, in the same transaction as the user update and audit entry. Flush the user update before session updates to preserve lock order. Audit failures roll back both. Other users and previously revoked timestamps are preserved. |
| High / must-fix | A correct password after an expired lockout raised `TypeError: can't compare offset-naive and offset-aware datetimes`. SQLAlchemy's `synchronize_session='evaluate'` compared the ORM-loaded naive `locked_until` against aware `now`. Reproduced on both the shared and pinned SQLAlchemy versions. | Preserve the guarded SQL update, disable its Python-side predicate evaluation, and synchronize the changed ORM attributes explicitly. The response and database agree on `last_login_at` and `updated_at`; lockout and failure counters reset correctly. |
| Medium / should-fix | Login separately fetched preferences after the initial user lookup. Selected global-admin context always fetched the default lobby before querying an already valid selection. | Join the optional preference into the initial login lookup. Resolve an explicit active admin selection first and load/repair the lobby only for fallback. Existing permission decisions and fallback repair remain unchanged. |
| Medium / should-fix | Activity renewal committed its update, then triggered an implicit expired-object SELECT and an explicit SELECT merely to compute the idle deadline. | Return the deadline from the timestamp just written. The guarded update still rejects revoked or idle-expired sessions. |

The service-account restriction is an intentional correction of an authorization defect. It preserves the principal separation in [the delegated-review security contract](agent-delegated-review-security.md): automation uses API tokens; browser and delegated human sessions require a human account. The coordinator can clarify that existing operational rule in `src/main/README.md` alongside the other teams' documentation updates.

## Performance evidence

These are deterministic local SQLite statement counts, not Oracle or production latency measurements.

| Path / fixture | Before | After |
| --- | ---: | ---: |
| Member password login, new-lobby fixture, SQL statements | 7 | 6 |
| Same login: connection checkouts / commits | 1 / 1 | 1 / 1 |
| Existing valid global-admin selected-space context, SELECTs | 2 | 1 |
| Activity service after authentication, SQL statements | 3 (`UPDATE`, `SELECT`, `SELECT`) | 1 (`UPDATE`) |

The existing September 7 bootstrap and one-request login improvements were retained, not repeated. Saved preferences remain in the login response. Bootstrap continues to load current preferences and membership state on each request. The activity count excludes authentication and request logging; the runtime team separately reviewed logging-induced ORM reads.

Password hash cost, password preprocessing, dummy verification, rate limits, cookie settings, token lifetimes, and idle policy are unchanged. Login is already a synchronous `def` route, so FastAPI runs it in a worker thread; this pass did not change thread or pool settings. See the [FastAPI execution model](https://fastapi.tiangolo.com/async/#path-operation-functions), [SQLAlchemy synchronization strategies](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#selecting-a-synchronization-strategy), and [committed attribute synchronization](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.attributes.set_committed_value).

## Validation

Before the fixes, focused tests reproduced service-cookie admission, the expired-lockout exception, seven login statements, and two selected-space statements. A separate in-memory baseline capture from the original source recorded all three activity statements.

After the fixes:

- Shared environment: 114 auth, session, space-selection, space-administration, and onboarding tests passed in 79.47 seconds. This environment used FastAPI 0.128.6, SQLAlchemy 2.0.46, and pytest 9.0.2.
- Pinned review environment: 117 tests passed in 86.68 seconds using FastAPI 0.139.0, SQLAlchemy 2.0.51, and pytest 9.1.1. This rerun added three focused agent authentication, direct-write denial, and delegated-human review tests.
- Independent pinned-version reproduction: the original successful-login update still raised the naive/aware `TypeError`; the fixed update succeeded and cleared the expired lock.
- Ruff 0.15.21 passed on every changed Python file. `git diff --check` passed. Unchanged mixed line endings were preserved to keep the logical diff small.

The pinned invocation used `F:/vault/projects/the-eco-system/sipm/.tmp/responsiveness-review-20260925/venv/Scripts/python.exe` and:

```text
-m pytest
  src/main/test/test_auth_and_deps.py
  src/main/test/test_auth_login_performance.py
  src/main/test/test_auth_session_regressions.py
  src/main/test/test_auth_space_resolution.py
  src/main/test/test_spaces.py
  src/main/test/test_space_onboarding.py
  src/main/test/test_agent_api.py::test_agent_auth_requires_bearer_service_account_and_space
  src/main/test/test_agent_api.py::test_service_account_cannot_bypass_agent_approval_on_normal_solution_write
  src/main/test/test_agent_api.py::test_human_delegated_review_requires_session_token_and_exact_request_version
  -q --basetemp=.pytest_tmp_auth_pinned
```

New regressions cover saved preference payloads and query counts, expired-lockout success and response timestamps, service-account conversion while bcrypt verification is in progress, failed bootstrap rollback, existing cookies after account conversion, session revocation and isolation, reset rollback on audit failure, update ordering, same-second access/delegated tokens, and rejected revoked/expired activity.

The coordinating task owns the required combined full backend/coverage, Redis integration, UI, and browser checks after cherry-picking all teams' fixes. They were deliberately not repeated here. No browser server was started by this task.

## Coverage and closure ledger

| Surface | Status |
| --- | --- |
| Password verification, admission, failed-attempt/lockout races, bootstrap and session issuance | Reviewed; confirmed defects fixed and focused tests passed |
| Access/refresh/delegated token validation, service-account separation, cookie and session policy | Reviewed; service-cookie admission corrected; existing contracts retained |
| Reset issuance/completion, audit atomicity and session invalidation | Reviewed and fixed |
| Activity, idle expiry and logout | Reviewed; activity reads reduced; expiry/revocation tests passed |
| API-token hashing, expiry, user eligibility, revocation and last-used behavior | Reviewed without edits; focused lifecycle and agent tests passed |
| Space selection used by login/refresh/bootstrap and dependencies | Reviewed; redundant default lookup removed; permission/fallback tests passed |
| `auth/`, `security.py`, auth models/schema and Oracle SQL shape | Reviewed without schema changes; existing hash/cookie/config tests and Oracle compilation checks passed |
| Inventory/stale-script helpers | Run; no script deletion justified in this scope. Old one-time-reset helper functions have no current in-repository callers and remain untouched. |
| Frontend, domain routes, DB engine, runtime middleware/coordination, deployments | Out of scope; separate teams own them |
| Deployed Oracle waits, production pool/worker contention, Redis and production tail latency | Not verified here |

Fixed now: the five findings above. No public route, schema, DOM contract, hash policy, or external service was changed. No original-checkout user files were edited.

Flagged for follow-up:

1. Measure actual delayed production sign-ins with request phases, Oracle round trips/waits, and pool/worker contention. Local query reductions and a fixed 500 do not by themselves establish production latency closure.
2. Clarify global-admin personal-space access: listing hides other owners' personal spaces, while explicit selection permits them. Existing permissions were preserved because the intended administrative exception is ambiguous.
3. Refresh continues to issue tokens for the same session without per-token rotation/reuse tracking, and the documented server-side session limit is idle expiry. Treat rotation/absolute lifetime as a separate policy/design review, not a confirmed regression in this pass.

The async WebSocket handshake's direct calls to synchronous DB authentication/space helpers were reported to the runtime team; no `sync.py` edit is included here. Review that team's integrated result before assigning remaining work.

Rollback is by reverting the isolated auth/session/space commits; no migration is required. The security corrections should be assessed explicitly before rollback because reverting them reopens the documented session/principal gaps.
