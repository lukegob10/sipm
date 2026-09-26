# Runtime, deployment, and browser review — 2026-09-25

Mode: **full-surface review within the runtime/deployment/browser ownership boundary**. The goal is to fix reproducible runtime defects, preserve existing API/schema/route/DOM and authentication contracts, and distinguish login feedback, authentication response, and usable content. This local review does not establish production Oracle/network latency or complete the other teams' reviews.

Baseline: `82c69be`. Worktree: `C:/Users/Luke Goblirsch/.codex/worktrees/b679/sipm`; branch: `codex/runtime-browser-review-20260925`. Both requested subagents were explicitly spawned with **gpt-6-luna, reasoning effort max**: runtime/DB resource handling and browser latency/responsive accessibility coverage. The parent reviewed and integrated their patches. No original-checkout user changes, authentication strength, external services, or deployment state were changed.

## Fixed findings

| Severity / disposition | Evidence and impact | Fix |
| --- | --- | --- |
| High / should-fix | The deployment step used detached `compose up`, then reported success even if the container never became ready. The new unhealthy-container regression failed against the baseline. | Require `docker compose up -d --wait --wait-timeout 300`. Preserve the migration order and fail before startup if a migration fails. |
| Medium / should-fix | Starting from the documented `src/main` directory selected its legacy `.env` before a repo-root `.env`. The source-ancestor lookup had the same issue when invoked from outside the repo. This contradicted the documented environment source of truth. `BASE_DIR` also incorrectly appended a second `src/main`. | Correct the runtime directory and prefer the repo-root environment over its deprecated nested fallback. Synthetic trees reproduce the original failure; explicit process-env precedence stays intact. |
| Medium / should-fix | The Docker command left a shell as the main process, preventing reliable delivery of Docker's termination signal to Uvicorn. | Use shell `exec`, preserving host/port environment expansion with quoting. |
| Medium / should-fix | A realtime-stop exception skipped remaining lifespan cleanup. Application-owned pooled DB connections were never explicitly disposed. A prewarm query/commit failure leaked the most recently checked-out connection because it had not yet entered the cleanup list. | Run subsequent cleanup in `finally` blocks, dispose an initialized pool without creating one, and track each prewarm connection immediately after checkout. Startup-failure and shutdown-failure regressions verify cleanup; both prewarm SQL-failure points verify every acquired connection closes. |
| Medium / should-fix | Request-log formatting read an expired ORM `user_id`, issuing a synchronous SELECT even with INFO logging disabled. A detached expired user instead lost its ID in the record. | Read the persisted SQLAlchemy identity without loading attributes. Synthetic SQLite instrumentation changes **one logging SELECT to zero**, and preserves the ID after session detachment. This is not a claim about the password-login endpoint, which does not set `request.state.user`. |
| Medium / should-fix | An unhandled 500 response bypassed the response-header middleware: it omitted `X-Request-ID` and application security headers, contradicting the documented response contract. | Add the outer exception response handler with the same plain `Internal Server Error` body/status plus those headers. Existing exception propagation and sensitive-header redaction tests still apply. |
| Medium / should-fix | The SQLite smoke runner used `setdefault` for its isolation flags, allowing inherited deployment settings to select Redis or enable startup work. | Force the dev/memory/startup-disabled/keepalive-off/env-override-off flags before backend import, preserving configurable port and bcrypt rounds. A subprocess regression exercises conflicting synthetic caller settings without starting any services. |
| Medium / should-fix | The dependency lock included two known development-tool advisory families. The baseline npm audit reported four moderate entries. | Patch Vitest/coverage-v8 and the exact-version Vitest family to 4.1.11, and humanfs/node to 0.16.8 with its required core/types dependencies. The resulting lock audits clean; unrelated locked versions are preserved. Installation and the complete UI check against this lock are delegated to the coordinator after worker tests finish. |

The deployment changes follow Docker's documented [health wait](https://docs.docker.com/reference/cli/docker/compose/up/) and [main-process signal behavior](https://docs.docker.com/reference/build-checks/json-args-recommended/). The logging fix uses SQLAlchemy's [inspection API](https://docs.sqlalchemy.org/en/20/core/inspection.html) and [persistent instance identity](https://docs.sqlalchemy.org/en/20/orm/internals.html#sqlalchemy.orm.InstanceState.identity).

## Login and browser evidence

The added `login-performance.spec.js` runs real username/password login against a disposable SQLite smoke app on isolated port **8776**, with memory coordination and explicit bcrypt cost **12**. It records the first submit only, a busy-feedback animation frame, the completed login resource, and an animation frame with visible active Deliverables content, the seeded program, and its enabled filter. Usable content is measured inside the browser rather than after Playwright assertion scheduling.

The delayed case adds 700 ms before forwarding the login request and attempts both Enter and `requestSubmit()` while the request is pending. The browser suite also checks labels, autocomplete, tab order, description references, and horizontal containment at 320×568. No production UI or auth code was modified.

The focused browser run passed all three cases. The following single samples were collected with the locked backend environment; all times start at the first form submit, except the request-duration column.

| Scenario | Busy feedback frame | Auth response | Request duration | Usable content | Login requests |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normal local login | 10.5 ms | 242.3 ms | 241.0 ms | 347.1 ms | 1 |
| Synthetic 700 ms forwarding delay | 11.4 ms | 940.5 ms | 939.6 ms | 1037.8 ms | 1 |

Timing varied across shared-host runs with concurrent reviews; these samples cannot establish a p95, improvement over production, or stable CPU performance. Request counts and state-transition assertions are stronger evidence. The delayed case covers the pending-auth interval: after a successful auth response, the auth screen hides even if a route module is still loading, so its keyboard submit is no longer available. The old September 7 measurements are retained in `performance-integration-20260907.md`; this fixture is smaller and is not a like-for-like replacement for that benchmark.

## Validation

The locked backend environment passed **79 focused tests** across `test_db_config.py`, `test_seed_and_db.py`, `test_runtime_path_resolution.py`, `test_observability.py`, `test_request_audit_correlation.py`, `test_frontend_bundle_operability.py`, `test_context_path_routing.py`, and `test_deployment_workflow.py`. The separate smoke-isolation subprocess regression passed **one test**, bringing focused backend validation to **80 passed**. The three browser cases cover normal login phase instrumentation, a held request with duplicate submit attempts, and mobile sign-in accessibility/layout. The final run also verifies that timing collection waits for the browser animation-frame mark and preserves the first feedback timestamp.

Browser reproduction from the repository root, with the locked backend venv on `PATH`:

```powershell
$env:SIPM_BCRYPT_ROUNDS = '12'
$env:SIPM_UI_SMOKE_PORT = '8776'
npm run test:ui:smoke -- --grep 'bcrypt 12 login|held login|mobile sign-in'
```

Targeted Ruff and ESLint checks, JavaScript syntax checking, requirements-lock consistency, route-module test mapping, and `git diff --check` pass. The deployment regression executes the workflow shell with a fake Docker command and verifies unhealthy startup, migration failure, and the healthy path; it does not contact a Docker daemon. The final browser run released port 8776. No production service was started or changed.

## Coverage and closure ledger

| Status | Surface |
| --- | --- |
| Fixed now | Environment resolution; DB/lifespan resource cleanup; request-log query and 500-response correlation; Docker process launch; deployment readiness acknowledgment; smoke-runner isolation; the two dev-tool advisory families in the lock; regression coverage for delayed/duplicate login and narrow mobile sign-in. |
| Reviewed | Runtime/startup, engine options, environment/paths/request context, static serving and context routing, liveness/readiness/observability, Docker/Compose/CI/operator docs, dependency locks, eight operator/benchmark/skill scripts, existing browser tests. Static route, cache-header, and missing-bundle behavior remain covered by focused tests. |
| Flagged for follow-up | Unreferenced developer demo entrypoint; production login stage profiling. |
| Not verified | Production Oracle/TAConnection/Redis/network timing, Docker image build and actual container SIGTERM/health behavior (local Docker daemon unavailable), full combined coverage/integration/browser suite and UI validation against the patched tooling lock (coordinator owns combined validation). |
| Out of scope | Auth-route and production-UI fixes; domain APIs/schema/migrations; coordination/smart-cache/realtime implementation; protected user-edited My Work files and adoption-review document. |
| Not present in repo | Production ingress, secret delivery, log shipping, dashboards, and alert routing. These remain platform responsibilities. |

The skill inventory helper and stale-script helper were run. The stale helper initially classified 295 executable-looking files on Windows, including imported modules and automatically discovered tests; those are not evidence of staleness. Restricting the shortlist to actual scripts yielded eight. `scripts/run_developer_mode_demo.py` lacks repository references, but it is a functioning manual entrypoint with no confirmed replacement; retain it pending a maintainer usage decision. The benchmark scripts have documented invocation paths. No scripts were deleted.

## Dependency and performance boundaries

`check_requirements_lock.py` and the route-module test mapping gate pass. `uvx pip-audit==2.10.1 -r requirements.txt` reports **no known vulnerabilities**. The baseline `npm audit --audit-level=high` passed its high-severity gate but reported **four moderate entries from two advisory families**: `@humanfs/node` 0.16.7 ([symlink-copy advisory](https://github.com/humanwhocodes/humanfs/security/advisories/GHSA-p498-v437-472g), fixed in 0.16.8), and Vitest/@vitest/mocker 4.1.8 ([redirect-mock advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9), fixed in 4.1.11). The latter requires access to the affected development-server mock registration surface; this repository uses `vitest run` with jsdom. Production exposure was not demonstrated.

The separate dependency commit updates the package constraints and locks those patched versions, including humanfs/core 0.19.2 and its new types 0.15.0 dependency. The final `npm audit --package-lock-only --audit-level=moderate` reports **zero vulnerabilities**. A package-lock-only npm resolution check accepts the resulting graph. Unrelated dependencies, including Vite 8.0.16 and Rolldown 1.0.3, remain at their original versions. The shared installed `node_modules` junction target still has Vitest/coverage-v8 4.1.8 and humanfs/node 0.16.7; no install was performed against it. The coordinator will install the final lock and run the full UI validation after parallel workers finish.

Default DB pool settings remain five pooled connections plus ten overflow, a 30-second pool wait, pre-ping enabled, and optional prewarm/keepwarm disabled. Pool wait is not a network connection deadline; pre-ping and cold connection creation can contribute round trips. These are investigation candidates, not measured production bottlenecks, and the settings were not tuned speculatively. See the [SQLAlchemy pooling contract](https://docs.sqlalchemy.org/en/20/core/pooling.html).

Canceling an async keepwarm task cannot forcibly cancel an already-running synchronous DB operation in its worker thread. Pool disposal closes idle connections; checked-out connections remain owned by their operation. Production driver timeouts and interrupted-operation behavior still require infrastructure validation.

Initial focused tests used the existing shared venv: FastAPI 0.128.6, Starlette 0.52.1, SQLAlchemy 2.0.46, Uvicorn 0.40.0, bcrypt 4.0.1, pytest 9.0.2. Final validation used the coordinator's separate venv installed from `requirements.txt` (including FastAPI 0.139.0 and SQLAlchemy 2.0.51), leaving the shared environment untouched.

Next useful passes are production login stage profiling on the real Oracle/network path, container lifecycle validation on a Docker runner, and combined application/tooling validation by the coordinator. None requires weakening bcrypt, rate limits, or session checks.
