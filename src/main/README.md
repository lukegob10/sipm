# SIPM App

## Run

```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
cd src/main
uvicorn backend.main:app --reload
```

Then open `http://127.0.0.1:8000/project-manager/`.

Use the repo-root `.env` or `.env.local` as the runtime source of truth. The nested `src/main/.env` file is deprecated and exists only as a legacy fallback when the repo-root environment files are missing. Start from the committed `.env.example` template; never commit real secrets.

Auth is application-managed. Users sign in with SOEID and password against the SIPM `users` table. SIPM stores bcrypt password hashes and mints its own HTTP-only access, refresh, and active-space cookies after local login.
Interactive browser sessions are also server-tracked and expire after 30 minutes without genuine user activity. Configure this independently with `SIPM_SESSION_IDLE_MINUTES`; access-token, refresh-token, and WebSocket idle durations do not replace this policy.

## Initial Data

No sample teams, people, or tasks are auto-created.

## Ops

- `GET /health` is a shallow liveness check and remains the quick `{"status":"ok"}` endpoint.
- `GET /health/ready` is the readiness check. It reports per-check status and returns `503` when config validation, frontend bundle verification, or DB connectivity fails. In test mode or when startup is intentionally disabled, the DB check is reported as `skipped`.
- Every response now includes `X-Request-ID`. Send your own `X-Request-ID` header to preserve upstream correlation, or let the app generate one.
- Request logs are emitted as compact JSON with `request_id`, `method`, `path`, `status`, `duration_ms`, `client_ip`, `space_id`, `user_id`, and `auth_method`.
- Sensitive values are intentionally excluded from request logs. Do not expect cookies, auth headers, or request bodies to appear there.
- The deployed artifact must include `src/main/ui` with at least `index.html`, `styles.css`, and `js/app.js`. If those files are missing, `/project-manager/` now returns `503` and readiness reports the bundle failure explicitly.
- Browser API access is cookie-backed. SIPM mints HTTP-only `access_token`, `refresh_token`, and `active_space_id` cookies after `/api/auth/login`.
- `SIPM_ALLOW_SELF_REGISTER=false` is required in UAT/prod; startup/readiness fails if non-dev self-registration is enabled.
- Admins can issue temporary passwords through the user-management password reset endpoints; users complete the reset at `/reset-password`.
- Service-account automation can use admin-issued personal access tokens through `Authorization: Bearer <token>` on HTTP API routes. Tokens are issued only for users marked as service accounts, stored as hashes, and never accepted in URL query strings.
- WebSockets use `/api/ws` with the existing browser cookies and optional `space_id` selection. Reusable access tokens are not accepted in WebSocket query strings.
- SIPM owns application response headers for CSP, referrer policy, and permissions policy. TLS/HSTS, ingress routing, and external platform files remain platform-owned.
- Shared runtime coordination is controlled with `SIPM_COORDINATION_BACKEND=memory|redis`.
- `SIPM_COORDINATION_BACKEND=redis` requires `SIPM_REDIS_URL`. `ENV=uat|prod` now requires the Redis backend at startup. `SIPM_REDIS_TIMEOUT_SECONDS` (default `5`) bounds Redis connection and startup subscription attempts.
- Redis coordinates cross-instance refresh fanout. Live socket connection counts and limits are process-local unless a future change moves accounting into Redis.
- Database connectivity uses TAConnection with Oracle. `ENV=dev|uat|prod` selects the TAConnection profile, and the readiness query is Oracle-safe.
- Database pool tuning is controlled by `SIPM_DB_POOL_SIZE`, `SIPM_DB_MAX_OVERFLOW`, `SIPM_DB_POOL_TIMEOUT_SECONDS`, `SIPM_DB_POOL_RECYCLE_SECONDS`, `SIPM_DB_POOL_PRE_PING`, and `SIPM_DB_POOL_USE_LIFO`.
- Optional startup pool warming is controlled by `SIPM_DB_PREWARM_ON_STARTUP=true` and `SIPM_DB_PREWARM_CONNECTIONS`; optional background keepalive is controlled by `SIPM_DB_KEEPWARM_INTERVAL_SECONDS`.
- Internal usage analytics is controlled with `SIPM_USAGE_ANALYTICS_ENABLED=false|true`.
- When usage analytics is enabled, the target database must match the canonical schema in [`docs/sql/schema_oracle_ta.sql`](../../docs/sql/schema_oracle_ta.sql), including raw telemetry and daily rollup tables.
- Service-account API tokens require the canonical `TB_TA_PM_USERS.IS_SERVICE_ACCOUNT` column and `TB_TA_PM_API_TOKENS` table from [`docs/sql/schema_oracle_ta.sql`](../../docs/sql/schema_oracle_ta.sql).
- The analytics tables are intended for short-lived operational insight. Purge raw rows older than 90 days with an external DBA/operator job; v1 does not add an in-app retention scheduler.
- Application startup is intentionally non-mutating for database schema. [`docs/sql/schema_oracle_ta.sql`](../../docs/sql/schema_oracle_ta.sql) is the repo-owned canonical Oracle schema contract; SIPM does not run schema changes during startup.
- First-deploy reference data SQL lives in [`docs/sql/first_deploy_reference_data.sql`](../../docs/sql/first_deploy_reference_data.sql). Run it after the canonical schema is created so required phase rows exist.
- Existing environments must run `python -m backend.app.db.phase_catalog_data` as an explicit deployment migration when phase-catalog repair is needed; the application no longer repeats that database-wide repair before serving traffic.
- First-time global admin bootstrap SQL lives in [`docs/sql/first_time_global_admin.sql`](../../docs/sql/first_time_global_admin.sql).
- CI/CD packaging, deployment manifests, environment injection, secret delivery, platform healthcheck wiring, log shipping, dashboards, and alert routing are external platform responsibilities.

## Frontend Validation

```bash
npm install
npm run lint:ui
npm run test:ui
npm run test:ui:coverage
npm run test:ui:smoke
```

- `lint:ui` runs the repo ESLint gate over `src/main/ui/js` and the browser test files.
- `test:ui` runs the Vitest/jsdom unit suite for router and live-sync behavior.
- `test:ui:coverage` runs the Vitest/jsdom unit suite with coverage over modular UI source. The current gate excludes the legacy `src/main/ui/js/app.js` monolith and should be raised as route modules gain focused unit tests.
- `test:ui:smoke` runs Playwright on dedicated port `8765` against `scripts/run_ui_smoke_app.py`, which boots the app on a temporary SQLite database instead of the Oracle runtime. Set `SIPM_UI_SMOKE_PORT` to choose another isolated port. Reusing an existing server is disabled unless `SIPM_UI_SMOKE_REUSE_SERVER=true` is set explicitly.
