# SIPM Production Readiness Enhancements

Date: 2026-05-01
Mode: full-surface clean-code review
Scope: backend, frontend, schema, tests, and code-owned operational behavior

## Scope Boundary
- This backlog is limited to changes owned by the SIPM codebase.
- CI/CD deployment mechanics, production manifests, environment injection, deployment-time secret management, and platform-owned reverse-proxy files are handled outside this repo and are intentionally out of scope here.
- Codebase work can still define and test integration contracts, but it should not require SIPM to own deployment packaging or platform configuration.

## Purpose
- Capture the production-readiness improvement backlog from the clean-code review pass.
- Separate concrete implementation work from general observations.
- Keep the list actionable with owners, severity, affected surfaces, and expected outcomes.

## Current Strengths
- Runtime auth configuration contains safeguards for non-dev auth and cookie behavior.
- `/health` and `/health/ready` exist and readiness checks auth, proxy auth, frontend files, and DB connectivity.
- Request IDs are generated, propagated, and logged for HTTP requests.
- Space isolation has a route-level enforcement gate in `src/main/test/test_route_space_enforcement_gate.py`.
- Schema/model drift is covered by `src/main/test/test_models_schema_contract.py`.
- Existing automated checks cover backend tests, frontend lint, frontend unit tests, frontend smoke tests, route-module mapping checks, Redis-backed tests, and dependency lock consistency.
- The new Gantt view is covered by route/module contract tests and follows the lazy route-module pattern.

## Priority 1: Must Fix Before Production

### PRD-001: Remove WebSocket Token Auth From Query Strings
- Severity: High
- Owner: backend/security
- Surface: `src/main/backend/app/routes/sync.py`
- Issue: The WebSocket endpoint accepts `?token=...` as an access-token source. Query tokens can leak through browser history, proxy logs, referrers, tracing systems, and support screenshots.
- Implementation:
  - Stop reading `query_params.get("token")`.
  - Prefer the existing `access_token` HTTP-only cookie for browser sockets.
  - Keep personal access tokens scoped to HTTP API routes only; do not accept API tokens or JWTs in WebSocket URLs.
  - Add tests proving query-token auth is rejected and cookie auth still works.
- Exit criteria:
  - No production WebSocket path accepts reusable access tokens in the URL.
  - Existing browser socket behavior still works after login.

### PRD-002: Remove Or Test-Gate Anonymous WebSocket Fallback
- Severity: High
- Owner: backend/security
- Surface: `src/main/backend/app/routes/sync.py`
- Issue: The WebSocket endpoint registers anonymous sockets when the injected session lacks `query`. That looks like a test shim, but it lives in production route code.
- Implementation:
  - Gate this branch behind a test-only runtime check, or move the behavior into test-only dependency overrides.
  - Add a production-mode test proving a malformed/non-query session cannot register anonymously.
- Exit criteria:
  - Production route execution always requires authenticated socket identity.

### PRD-003: Add Formal Database Migration Discipline
- Severity: High
- Owner: backend/database
- Surface: `docs/sql/migrations/`, `src/main/backend/app/db/db.py`
- Issue: Startup intentionally avoids schema mutation, which is right for the production runtime, but migrations are currently loose SQL files without a repo-owned ledger or verification workflow.
- Implementation:
  - Document the `schema_migrations` ledger expectation for the external deployment migration process.
  - Require each migration to be ordered, documented, and tied to an application version.
  - Add feature-specific SQL migration files when code changes require schema changes.
  - Keep production startup non-mutating.
- Exit criteria:
  - Operators can determine which migrations have run.
  - Code-owned schema changes include matching SQL migration notes/files.

### PRD-004: Document Code-Owned Runtime Contracts
- Severity: High
- Owner: backend/platform
- Surface: `src/main/README.md`, `docs/codebase-review/`
- Issue: The codebase has important runtime assumptions around auth flow, health checks, context path routing, static frontend serving, DB startup behavior, Redis-backed coordination, and migration ordering. Those assumptions need to be captured as code-owned contracts without duplicating external CI/CD deployment mechanics.
- Implementation:
  - Document which behaviors the application guarantees directly: auth bootstrap path, cookie-backed sessions, context-path routing, `/health` vs `/health/ready`, startup schema non-mutation, and WebSocket refresh behavior.
  - Document which integration boundaries are externally owned: proxy ingress, CI/CD packaging, deployment-time configuration injection, and platform healthcheck wiring.
  - Add or update tests when a documented contract maps to application behavior.
- Exit criteria:
  - A maintainer can tell which readiness guarantees are enforced by SIPM code and which are intentionally delegated to the deployment platform.

## Priority 2: Should Fix Before Broad Rollout

### PRD-005: Finish Frontend Core Decomposition
- Severity: Medium-high
- Owner: frontend
- Surface: `src/main/ui/js/app.js`
- Issue: `app.js` remains a large shell/state module. Route extraction is underway, but more modal wiring, state persistence, route loaders, repository helpers, and entity orchestration still belong in focused modules.
- Implementation:
  - Defer broad `app.js` decomposition for this readiness pass.
  - Extract only small shared utilities needed by security and date-stability work.
  - Keep future route/module extraction as normal roadmap work.
- Exit criteria:
  - `app.js` stays within the quality-gate budget.
  - New views do not add route-local behavior back to the shell.

### PRD-006: Add Application Security Headers
- Severity: Medium-high
- Owner: backend/platform
- Surface: `src/main/backend/main.py`, backend tests
- Issue: The app logs request metadata and validates auth config, but production browser hardening headers are not enforced in app code.
- Implementation:
  - Add code-owned response headers for `Content-Security-Policy`, `frame-ancestors` or `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` where SIPM can safely enforce them.
  - If a header must remain platform-owned, document that as an explicit integration boundary instead of adding proxy config here.
  - Add tests for the application-owned header contract.
  - Keep CSP compatible with the current static frontend.
- Exit criteria:
  - SIPM responses have a tested browser security-header contract for the portions owned by app code.

### PRD-007: Normalize Frontend Date Parsing
- Severity: Medium
- Owner: frontend
- Surface: `src/main/ui/js/routes/calendar.js`, `src/main/ui/js/routes/gantt.js`
- Issue: Gantt uses UTC date-only parsing, while calendar has local `Date` fallback behavior. Date-only fields can shift by timezone if parsing remains inconsistent.
- Implementation:
  - Add a shared date-only utility for `YYYY-MM-DD` parsing, formatting, range overlap, and day-number math.
  - Use it in Gantt, Calendar, Kanban due-date filtering, dashboards, and any date-window storage.
  - Add timezone-stable frontend tests for due dates and range bars.
- Exit criteria:
  - The same stored date appears on the same logical day across all views and time zones.

### PRD-008: Validate External Links In The Frontend
- Severity: Medium
- Owner: frontend/security
- Surface: `src/main/ui/js/app.js`, `src/main/ui/js/routes/master/table.js`
- Issue: Backend validation protects persisted repository URLs, but frontend previews and table rendering should also reject unsafe schemes before creating anchors.
- Implementation:
  - Add a shared `safeExternalUrl()` helper.
  - Only render external anchors for approved `https://github.com/...` style URLs.
  - Render invalid or unsupported values as plain escaped text or a validation message.
  - Add tests for `javascript:`, malformed, relative, and valid GitHub URLs.
- Exit criteria:
  - No UI path renders an executable or untrusted external URL into an `href`.

### PRD-009: Document Or Harden Multi-Instance WebSocket Behavior
- Severity: Medium
- Owner: backend/platform
- Surface: `src/main/backend/app/services/realtime.py`, `src/main/backend/app/services/coordination.py`, backend tests
- Issue: Redis coordinates refresh broadcasts, but socket connection state and connection limits remain per process. This needs an explicit application-level scaling contract.
- Implementation:
  - Make the application-level scaling contract explicit in code comments, service docs, or tests: refresh fanout can cross instances through Redis, while live socket accounting is currently process-local.
  - If horizontal scaling is required, move connection accounting or fanout semantics to Redis-backed primitives.
  - Add code-level metrics or inspectable snapshots for open sockets, rejected sockets, idle timeouts, and broadcast failures.
- Exit criteria:
  - SIPM's WebSocket behavior is explicit, tested where practical, and observable from app-owned code.

### PRD-010: Keep Proxy Auth Boundary Explicit In Application Code
- Severity: Medium
- Owner: backend/security
- Surface: `src/main/backend/app/auth/proxy_auth.py`, `src/main/backend/app/routes/auth.py`, auth tests
- Issue: Reverse-proxy identity is intentionally trusted only after the platform proxy has authenticated the user and stripped spoofed headers. The app should keep that boundary narrow and testable without owning platform configuration files.
- Implementation:
  - Keep proxy identity parsing centralized in `proxy_auth.py`.
  - Prove only the expected auth bootstrap path provisions proxy users and mints SIPM cookies.
  - Add tests for missing identity, malformed identity, inactive users, and stale-cookie fallback through `/auth/me`.
  - Document that header spoofing protection is an external ingress responsibility while SIPM owns the in-app trust boundary.
- Exit criteria:
  - Proxy-auth behavior is constrained, regression-tested, and not spread across unrelated routes.

## Priority 3: Production Hardening And Maintainability

### PRD-011: Add Code-Owned Security Regression Tests
- Severity: Medium
- Owner: repo-quality/security
- Surface: `src/main/test/`, `src/main/ui/test/`
- Issue: Several important security expectations are currently implicit in implementation rather than captured as durable regression tests.
- Implementation:
  - Add focused tests for auth-cookie handling, WebSocket auth rejection, external-link rendering, route-level space isolation, and admin-only endpoints.
  - Prefer contract tests around high-risk behavior over broad deployment or dependency scanning concerns.
  - Keep external dependency vulnerability management in the separate CI/CD/security process.
- Exit criteria:
  - Code-owned security assumptions fail fast during the repository's normal test suite.

### PRD-012: Add Operational Observability Beyond Request Logs
- Severity: Medium
- Owner: backend/platform
- Surface: `src/main/backend/main.py`, analytics services, realtime services
- Issue: Request IDs and key-value request logs exist, but the app can expose richer code-owned telemetry without taking over platform dashboards or alert routing.
- Implementation:
  - Emit structured JSON logs with request ID, route, status, latency, user/space identifiers where safe, and error category.
  - Keep this pass to structured logs only.
  - Keep dashboard, alert routing, retention jobs, and log shipping mechanics platform-owned.
- Exit criteria:
  - SIPM emits enough structured signals for the external observability platform to detect and localize application failures.

### PRD-013: Keep Startup Behavior Explicit And Non-Mutating
- Severity: Medium
- Owner: backend/database
- Surface: `src/main/backend/main.py`, `src/main/backend/app/db/db.py`, backend tests
- Issue: Production startup intentionally avoids schema mutation, but that guarantee should remain explicit and covered as the app evolves.
- Implementation:
  - Add or strengthen tests proving startup does not create or alter schema unless explicitly invoked through a controlled helper.
  - Keep readiness DB checks separate from migration application.
  - Document the code-level startup sequence and the non-mutating DB invariant.
- Exit criteria:
  - Application startup cannot accidentally become a schema-changing path.

### PRD-014: Add Coverage And Quality Thresholds
- Severity: Medium-low
- Owner: repo-quality
- Surface: tests
- Issue: The repo has strong suites, but no coverage threshold or explicit quality trend gate for critical code paths.
- Implementation:
  - Add focused contract checks for backend-critical paths and frontend utility behavior.
  - Do not add percentage coverage thresholds in this pass.
- Exit criteria:
  - Critical auth, space isolation, schema, route registration, and date-window logic have focused regression coverage.

### PRD-015: Reduce Generated-Artifact And Local-Tool Noise
- Severity: Low
- Owner: repo-quality
- Surface: `.gitignore`, docs, developer scripts
- Issue: Generated files such as coverage output and local tooling folders are ignored, but local review output can still become noisy.
- Implementation:
  - Add or document a cleanup command for local generated artifacts.
  - Keep `.auto-research/` and local assistant/tooling state out of commits unless explicitly requested.
  - Add repository-local checks for accidental generated artifacts if needed.
- Exit criteria:
  - Production PRs contain only intentional source, tests, docs, and migration files.

## Validation Snapshot
- `python3 scripts/check_route_module_test_mapping.py`: passed.
- `python3 -m pytest -q src/main/test/test_models_schema_contract.py src/main/test/test_route_space_enforcement_gate.py`: passed with 11 tests.
- Full frontend validation was not rerun in this review pass; CI is configured to run `npm run lint:ui`, `npm run test:ui`, and `npm run test:ui:smoke`.

## Suggested Implementation Order
1. Close PRD-001 and PRD-002 together as the WebSocket auth hardening slice.
2. Add PRD-003 migration ledger/check tooling before the next schema change.
3. Add PRD-004 runtime contract docs and PRD-010 proxy-auth boundary tests.
4. Ship PRD-006 security headers and PRD-011 security regression tests.
5. Normalize dates through PRD-007 before expanding roadmap/calendar reporting.
6. Continue frontend decomposition through PRD-005 as part of normal feature work.
7. Complete PRD-009, PRD-012, PRD-013, PRD-014, and PRD-015 before broad rollout.
