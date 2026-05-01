# SIPM Production Readiness Enhancements

Date: 2026-05-01
Mode: full-surface clean-code review
Scope: backend, frontend, schema, CI, configuration, documentation, and operations

## Purpose
- Capture the production-readiness improvement backlog from the clean-code review pass.
- Separate concrete implementation work from general observations.
- Keep the list actionable with owners, severity, affected surfaces, and expected outcomes.

## Current Strengths
- Runtime auth configuration validates non-dev secret and secure-cookie requirements.
- `/health` and `/health/ready` exist and readiness checks auth, proxy auth, frontend files, and DB connectivity.
- Request IDs are generated, propagated, and logged for HTTP requests.
- Space isolation has a route-level enforcement gate in `src/main/test/test_route_space_enforcement_gate.py`.
- Schema/model drift is covered by `src/main/test/test_models_schema_contract.py`.
- CI runs backend tests, frontend lint, frontend unit tests, frontend smoke tests, route-module mapping checks, Redis-backed tests, and dependency lock verification.
- The new Gantt view is covered by route/module contract tests and follows the lazy route-module pattern.

## Priority 1: Must Fix Before Production

### PRD-001: Remove WebSocket Token Auth From Query Strings
- Severity: High
- Owner: backend/security
- Surface: `src/main/backend/app/routes/sync.py`
- Issue: The WebSocket endpoint accepts `?token=...` as an access-token source. Query tokens can leak through browser history, proxy logs, referrers, tracing systems, and support screenshots.
- Implementation:
  - Stop reading `query_params.get("token")` in production.
  - Prefer the existing `access_token` HTTP-only cookie for browser sockets.
  - If non-browser clients need socket auth, add a short-lived one-time WebSocket ticket created through an authenticated HTTP endpoint.
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
  - Gate this branch to `ENV=test`, or move the behavior into test-only dependency overrides.
  - Add a production-mode test proving a malformed/non-query session cannot register anonymously.
- Exit criteria:
  - Production route execution always requires authenticated socket identity.

### PRD-003: Add Formal Database Migration Discipline
- Severity: High
- Owner: backend/database
- Surface: `docs/sql/migrations/`, `src/main/backend/app/db/db.py`
- Issue: Startup intentionally avoids schema mutation, which is right for managed Oracle deployments, but migrations are currently loose SQL files without a repo-owned ledger or verification workflow.
- Implementation:
  - Add a `schema_migrations` ledger table contract.
  - Add a migration runner or documented apply/check script that can run in dry-run and apply modes.
  - Require each migration to be idempotent, ordered, documented, and tied to an application version.
  - Add CI checks that every model/schema change has a migration or an explicit no-migration note.
  - Keep production startup non-mutating.
- Exit criteria:
  - Operators can determine which migrations have run.
  - CI catches schema drift before merge.

### PRD-004: Create A Production Deployment Runbook
- Severity: High
- Owner: platform/operations
- Surface: repo root, `src/main/README.md`, `.env.example`
- Issue: The repo has good local README material, but it lacks a single production runbook covering release, deployment, migration, rollback, and incident operations.
- Implementation:
  - Add a root `README.md` or `docs/production-runbook.md`.
  - Document environment modes, Oracle/TAConnection setup, Redis requirements, reverse-proxy auth headers, cookie/security settings, health checks, startup order, migration flow, rollback flow, and smoke validation.
  - Include the exact commands CI runs and the exact checks operators should run after deploy.
- Exit criteria:
  - A new operator can deploy, verify, roll back, and triage the app from repo docs alone.

## Priority 2: Should Fix Before Broad Rollout

### PRD-005: Finish Frontend Core Decomposition
- Severity: Medium-high
- Owner: frontend
- Surface: `src/main/ui/js/app.js`
- Issue: `app.js` remains a large shell/state module. Route extraction is underway, but more modal wiring, state persistence, route loaders, repository helpers, and entity orchestration still belong in focused modules.
- Implementation:
  - Continue the existing decomposition roadmap in `docs/codebase-review/05-enterprise-roadmap.md`.
  - Keep `app.js` limited to bootstrap, shell state, route dispatch, cross-route callbacks, and shared lifecycle.
  - Move route-specific behavior into route-owned modules and entity modal behavior into `src/main/ui/js/entities/`.
- Exit criteria:
  - `app.js` stays within the quality-gate budget.
  - New views do not add route-local behavior back to the shell.

### PRD-006: Add Application Security Headers
- Severity: Medium-high
- Owner: backend/platform
- Surface: `src/main/backend/main.py`, reverse-proxy config
- Issue: The app logs request metadata and validates auth config, but production browser hardening headers are not enforced in app code.
- Implementation:
  - Add or document enforcement for `Content-Security-Policy`, `frame-ancestors` or `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-Security`, and `Permissions-Policy`.
  - Decide whether headers are app-owned or proxy-owned, then add tests for the chosen contract.
  - Keep CSP compatible with the current static frontend.
- Exit criteria:
  - Production responses have a tested browser security-header contract.

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
- Surface: `src/main/backend/app/services/realtime.py`, Redis deployment docs
- Issue: Redis coordinates refresh broadcasts, but socket connection state and connection limits remain per process. This needs an explicit production deployment contract.
- Implementation:
  - Document whether production uses one worker, sticky sessions, or per-instance connection limits.
  - If horizontal scaling is required, move connection accounting or fanout semantics to Redis-backed primitives.
  - Add operational metrics for open sockets, rejected sockets, idle timeouts, and broadcast failures.
- Exit criteria:
  - Production scaling behavior is explicit and observable.

### PRD-010: Align `.env.example` With Production Proxy Auth Contract
- Severity: Medium
- Owner: platform/security
- Surface: `.env.example`, `src/main/backend/app/auth/proxy_auth.py`, `src/main/README.md`
- Issue: Code defaults use `SM_USER` and `name`, while `.env.example` uses `user` and `full_name`. Both may be valid in different environments, but the production contract is ambiguous.
- Implementation:
  - Split dev/local and prod examples, or comment the expected production proxy headers directly.
  - Make `.env.example` safe as a template without implying insecure dev values are production-ready.
  - Add readiness/config docs for proxy header ownership and spoofing protection at the reverse proxy.
- Exit criteria:
  - Operators know exactly which headers production must set and which clients are trusted to set them.

## Priority 3: Production Hardening And Maintainability

### PRD-011: Add Dependency And Static Security Gates
- Severity: Medium
- Owner: repo-quality/security
- Surface: `.github/workflows/backend-tests.yml`, `package.json`, `src/main/requirements.txt`
- Issue: CI verifies dependency lock state, but the repo does not currently run dependency vulnerability scanning or Python static security checks.
- Implementation:
  - Add `pip-audit` or an approved equivalent for Python dependencies.
  - Add `npm audit` or an approved equivalent for frontend dependencies.
  - Add Python lint/static checks such as Ruff plus Bandit/Semgrep where appropriate.
  - Start report-only if existing findings need triage, then promote to blocking.
- Exit criteria:
  - CI surfaces vulnerable dependencies and high-confidence static security findings before merge.

### PRD-012: Add Operational Observability Beyond Request Logs
- Severity: Medium
- Owner: platform/operations
- Surface: `src/main/backend/main.py`, analytics services, deployment config
- Issue: Request IDs and key-value request logs exist, but production needs metrics, dashboards, alerts, retention, and error aggregation.
- Implementation:
  - Emit structured JSON logs with request ID, route, status, latency, user/space identifiers where safe, and error category.
  - Add metrics for request latency, status rates, DB readiness failures, WebSocket counts, cache invalidations, analytics ingestion, and migration state.
  - Add alert thresholds and an incident triage guide.
  - Document analytics retention and purge operations.
- Exit criteria:
  - Operators can detect, localize, and triage production incidents without reproducing them locally.

### PRD-013: Add Production Packaging Artifacts
- Severity: Medium
- Owner: platform
- Surface: repo root
- Issue: The repo does not expose a production packaging contract such as Dockerfile, compose file, or equivalent deployment manifest.
- Implementation:
  - Add the packaging artifact required by the target deployment environment.
  - Include non-root runtime, healthcheck, static asset serving expectations, env injection, and startup command.
  - Keep local development instructions separate from production packaging.
- Exit criteria:
  - CI or release automation can build the same artifact that production runs.

### PRD-014: Add Coverage And Quality Thresholds
- Severity: Medium-low
- Owner: repo-quality
- Surface: CI, tests
- Issue: CI has strong suites, but no coverage threshold or explicit quality trend gate.
- Implementation:
  - Add Python coverage reporting for backend-critical paths.
  - Add frontend coverage or focused contract coverage checks for route modules.
  - Track thresholds per domain instead of chasing a single vanity percentage.
- Exit criteria:
  - Critical auth, space isolation, schema, route registration, and date-window logic have durable coverage thresholds.

### PRD-015: Reduce Generated-Artifact And Local-Tool Noise
- Severity: Low
- Owner: repo-quality
- Surface: `.gitignore`, docs, developer scripts
- Issue: Generated files such as coverage output and local tooling folders are ignored, but local review output can still become noisy.
- Implementation:
  - Add or document a cleanup command for local generated artifacts.
  - Keep `.auto-research/` and local assistant/tooling state out of commits unless explicitly requested.
  - Add pre-commit or CI checks for accidental generated artifacts if needed.
- Exit criteria:
  - Production PRs contain only intentional source, tests, docs, and migration files.

## Validation Snapshot
- `python3 scripts/check_route_module_test_mapping.py`: passed.
- `python3 -m pytest -q src/main/test/test_models_schema_contract.py src/main/test/test_route_space_enforcement_gate.py`: passed with 11 tests.
- Full frontend validation was not rerun in this review pass; CI is configured to run `npm run lint:ui`, `npm run test:ui`, and `npm run test:ui:smoke`.

## Suggested Implementation Order
1. Close PRD-001 and PRD-002 together as the WebSocket auth hardening slice.
2. Add PRD-003 migration ledger/check tooling before the next schema change.
3. Add PRD-004 production runbook and PRD-010 environment-contract cleanup.
4. Ship PRD-006 security headers and PRD-011 scanning gates.
5. Normalize dates through PRD-007 before expanding roadmap/calendar reporting.
6. Continue frontend decomposition through PRD-005 as part of normal feature work.
7. Complete PRD-009, PRD-012, PRD-013, PRD-014, and PRD-015 before broad rollout.
