# Login and session restoration performance implementation

Date: 2026-09-07. Baseline: `3e77295`. Mode: performance optimization.
Scope: PERF-02 / package 2, in the isolated `ec58/sipm` worktree.

## Result and evidence

Valid-session reopening now calls the additive `GET /project-manager/api/auth/bootstrap` endpoint. It returns the same user, preferences, accessible spaces, and active-space schema as local login. Both endpoints use one payload builder. `/auth/me`, login, refresh, active-space, and preferences retain their public contracts.

Deterministic request and SQL counts, rather than deployed latency, establish the improvement:

| Journey / measurement | Before | After |
| --- | ---: | ---: |
| Valid reopening: authenticated context requests | 4 | 1 |
| Valid reopening: sequential context network stages | 2 | 1 |
| Valid reopening: regular-user SQL statements | 11 | 4 |
| Valid reopening: DB connection checkouts | 4 | 1 |
| Expired-access recovery: context/auth requests | 5 | 3 |
| Expired-access recovery: sequential network stages | 3 | 3 |
| Explicit login: context/auth requests after form submit | 1 | 1 |
| Explicit login: redundant follow-up context requests | 0 | 0 |
| Regular-user login: SQL statements, existing new-lobby fixture | 8 | 7 |
| Regular-user login: checkouts / commits | 1 / 1 | 1 / 1 |
| Reopening: newly created sessions / changed activity timestamps | 0 / 0 | 0 / 0 |

The independent, nonblocking `/auth/session-policy` request remains present in both versions and is excluded from the context-request counts above. Initial signed-out startup still makes one unsuccessful discovery request and at most one refresh request. Session reopening does not extend the idle timeout.

The old valid path was `/auth/me` followed by concurrent preferences, spaces, and active-space reads. Each protected endpoint authenticated the same user/session again. The new regular-user path performs four SQL reads: user, auth session, active memberships joined to spaces, and preferences. The same membership rows supply active-space selection and the spaces list. No authorization data is retained beyond the request.

The old expired-access path was `/auth/me` -> `/auth/refresh` -> the three context reads. The new path is `/auth/bootstrap` -> the existing shared `/auth/refresh` -> one bounded retry of `/auth/bootstrap`. This reduces request count but not recovery network stages.

The existing login SQL test was run unchanged before implementation: eight statements, one checkout, one commit. After implementation the same fixture records seven statements, one checkout, one commit. The removed statement was a second membership/space-list query. Global-admin selection/listing and default-lobby repair retain the existing service paths; their query tuning is deferred.

## Behavior and security preservation

- The bootstrap endpoint uses `require_interactive_user`, which delegates authentication to `require_user` and preserves the interactive-user restriction already applied by `/users/me/preferences`. API tokens can still use `/auth/me`; bootstrap does not expose preferences to them.
- Bcrypt, dummy verification, lockout updates/race protection, password-reset requirements, token revocation, idle expiry, and session issuance remain unchanged. Bootstrap never calls `_issue_session` or changes access/refresh cookies. It repairs the active-space cookie by the same rules as `/auth/active-space`.
- Regular-user membership filters, space ordering, role normalization, default selection, and inaccessible/stale selection fallback reuse the existing selection implementation. Suspended membership changes are visible on the next request. Global-admin behavior remains the same.
- The session controller retains its existing callbacks and default `/auth/me` behavior for `fetchCurrentUser()`. Startup opts into the consolidated response and applies it through the existing `applyAuthBootstrap` callback. Explicit login continues using its original consolidated response.
- A startup generation and active-space check discard late bootstrap responses after logout, a superseding authentication, or a space change. Shared refresh has a separate session-lifetime generation plus user/space check, so an ordinary refresh cannot resurrect a logged-out user and a newer bootstrap can consume the same valid refresh. An obsolete refresh cannot clear a replacement refresh promise. Existing API cancellation stays in place.
- Routing, developer-mode preferences, theme application, notices, focus, selection, drafts, scrolling, and visible controls use the existing controller callbacks and UI. No app.js, router, data-store, style, or filtering edits are included.
- The auth browser test's 503 interception changed from `/auth/me` to `/auth/bootstrap`. Any external harness that mocks startup discovery should make the same endpoint update; `/auth/me` remains supported as a public endpoint.

## Validation

Environment: Windows, Node 20.19.2, Python 3.12.2, SQLite temporary databases, Vitest/jsdom and Playwright. The coordinating checkout's existing `.venv` and `node_modules` were reused; backend imports, UI source, config, and smoke server came from this worktree. `node_modules` is an ignored local junction. No shared source was edited.

Before implementation:

- `python -m pytest src/main/test/test_auth_and_deps.py -q --basetemp=.pytest_tmp_login_baseline`: 60 passed.
- `node node_modules/vitest/vitest.mjs run src/main/ui/test/unit/session.test.js`: 20 passed.

After implementation:

- `python scripts/check_route_module_test_mapping.py`: passed.
- After the final session-only race fix, `python -m pytest src/main/test/test_live_sync_session_frontend_contract.py -q --basetemp=.pytest_tmp_login_contract`: seven passed.
- `npm run lint:ui`: passed.
- `npm run test:ui`: 214 passed, including 34 session-controller tests.
- `npm run test:ui:coverage`: passed; statements 45.92%, branches 36.04%, functions 52.27%, lines 48.92%.
- `npm run test:backend`: 613 passed, one integration test deselected.
- `npm run test:backend:coverage`: 613 passed; 82.61% coverage (80% gate).
- `npm run test:backend:integration`: one skipped because `SIPM_REDIS_URL` is not configured; Redis coordination was not verified.
- `SIPM_UI_SMOKE_PORT=8771 npm run test:ui:smoke`: all 14 passed, including responsive/theme/navigation tests and new one-request reopen tests for Deliverables, a deep link, and developer-mode My Work. Session cookies remain identical across reopening.
- `uvx --offline ruff==0.15.21 check src/main/backend/app/routes/auth.py src/main/backend/app/services/spaces.py src/main/test/test_auth_and_deps.py`: passed.
- `git -c core.autocrlf=false diff --check`: passed.

The new backend tests compare the consolidated payload against all four existing endpoints for both a regular user and a global admin, count SQL/checkouts, and verify no new sessions or activity updates. They cover expired-access recovery, invalid/expired/revoked sessions, locked/inactive users, password-change revocation, missing memberships, cookie repair, fresh membership reads, user isolation, and API-token restrictions. Session tests cover bounded retries, failures, single-flight refresh, no redundant context loads, routing preferences, and stale-response rejection.

Use the existing Python runtime in PATH for npm backend/smoke scripts. Each backend run used a unique worktree-local `PYTEST_ADDOPTS=--basetemp=...`. The default shared Windows temp directory was inaccessible under the sandbox. Node/npm commands needed execution outside the sandbox to resolve the worktree path; no dependency installation was needed. The first smoke attempt exposed an incorrect selector in the new Deliverables test (`view-deliverables`); correcting it to the existing `view-master` made all tests pass. The final smoke run logged Windows socket-close callbacks during browser disconnects but all assertions passed.

## Limits and integration

This patch closes the measured redundant-request issue, not the plan's production latency budgets. No Oracle execution plans, deployed network timings, p50/p75/p95 journey samples, corporate-network profiles, or Redis integration results are claimed. Browser test durations include setup and assertions and are not journey latency measurements. Startup asset work, duplicate data collection loading, and navigation scheduling belong to the coordinating sibling changes.

The endpoint is additive and needs no schema migration, configuration change, or operator procedure. Deploy it with the corresponding session-controller change; roll back those pieces together. All changes remain unpushed and undeployed for parent-task integration.
