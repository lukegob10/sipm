# SIPM App (Work Allocation Board MVP)

This app now uses `#/planning` as a **Work Allocation Board** for FTE-month task allocation.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/main/requirements.txt
uvicorn backend.main:app --reload --app-dir src/main
```

Then open `http://127.0.0.1:8000/project-manager/`.

Use the repo-root [.env](/mnt/f/vault/projects/sipm/.env) or `.env.local` as the runtime source of truth. The nested [src/main/.env](/mnt/f/vault/projects/sipm/src/main/.env) file is deprecated and only exists as a legacy fallback if the repo-root env files are missing.

Auth is application-managed. Users sign in with SOEID and password against the SIPM `users` table. SIPM stores bcrypt password hashes and mints its own HTTP-only access, refresh, and active-space cookies after local login.

## Planning MVP Features

- Backlog tasks with search and effort filter.
- Team columns with person cards and capacity bars.
- Drag/drop assignment:
  - Backlog -> person
  - Backlog -> team header
  - Assigned task -> backlog (unassign)
- Task details side panel (edit/unassign/delete).
- Month selector (`YYYY-MM`) and month-scoped allocations.
- Inline add team/person/task.
- Undo last action (client-side stack).

## Initial Data

No sample teams, people, or tasks are auto-created.
Use the work-allocation create endpoints to add board data explicitly.

## Work Allocation API

- `GET/POST/PATCH/DELETE /api/planning/work-allocation/teams`
- `GET/POST/PATCH/DELETE /api/planning/work-allocation/people`
- `GET/POST/PATCH/DELETE /api/planning/work-allocation/tasks`
- `GET/POST/DELETE /api/planning/work-allocation/allocations`

Validation highlights:

- A task can have only one allocation per month (no split allocation in MVP).
- Assignee must exist (person or team).

## Ops

- `GET /health` is a shallow liveness check and remains the quick `{"status":"ok"}` endpoint.
- `GET /health/ready` is the readiness check. It reports per-check status and returns `503` when config validation, frontend bundle verification, or DB connectivity fails. In test mode or when startup is intentionally disabled, the DB check is reported as `skipped`.
- Every response now includes `X-Request-ID`. Send your own `X-Request-ID` header to preserve upstream correlation, or let the app generate one.
- Request logs are emitted with simple `key=value` fields: `request_id`, `method`, `path`, `status`, `duration_ms`, `client_ip`, and `space_id`.
- Sensitive values are intentionally excluded from request logs. Do not expect cookies, auth headers, or request bodies to appear there.
- The deployed artifact must include `src/main/ui` with at least `index.html`, `styles.css`, and `js/app.js`. If those files are missing, `/project-manager/` now returns `503` and readiness reports the bundle failure explicitly.
- Browser API access is cookie-backed. SIPM mints HTTP-only `access_token`, `refresh_token`, and `active_space_id` cookies after `/api/auth/login`.
- `SIPM_ALLOW_SELF_REGISTER=false` should be used in UAT/prod unless self-registration is explicitly approved.
- Admins can issue temporary passwords through the user-management password reset endpoints; users complete the reset at `/reset-password`.
- Service-account automation can use admin-issued personal access tokens through `Authorization: Bearer <token>` on HTTP API routes. Tokens are issued only for users marked as service accounts, stored as hashes, and never accepted in URL query strings.
- WebSockets use `/api/ws` with the existing browser cookies and optional `space_id` selection. Reusable access tokens are not accepted in WebSocket query strings.
- SIPM owns application response headers for CSP, referrer policy, and permissions policy. TLS/HSTS, ingress routing, and external platform files remain platform-owned.
- Shared runtime coordination is controlled with `SIPM_COORDINATION_BACKEND=memory|redis`.
- `SIPM_COORDINATION_BACKEND=redis` requires `SIPM_REDIS_URL`. `ENV=uat|prod` now requires the Redis backend at startup.
- Redis coordinates cross-instance refresh fanout. Live socket connection counts and limits are process-local unless a future change moves accounting into Redis.
- Internal usage analytics is controlled with `SIPM_USAGE_ANALYTICS_ENABLED=false|true`.
- When usage analytics is enabled, apply [`docs/sql/migrations/2026-03-29_usage_analytics.sql`](/mnt/f/vault/projects/sipm/docs/sql/migrations/2026-03-29_usage_analytics.sql) before exposing the admin dashboard.
- Service-account API tokens require [`docs/sql/migrations/2026-05-01_service_account_api_tokens.sql`](/mnt/f/vault/projects/the-eco-system/sipm/docs/sql/migrations/2026-05-01_service_account_api_tokens.sql). If Oracle raises `ORA-00904` for `TB_TA_PM_USERS.IS_SERVICE_ACCOUNT`, this migration has not been applied to the target schema yet.
- The analytics tables are intended for short-lived operational insight. Purge raw rows older than 90 days with an external DBA/operator job; v1 does not add an in-app retention scheduler.
- Application startup is intentionally non-mutating for database schema. SQL files in `docs/sql/migrations/` document schema changes for the external deployment migration process. Use a `schema_migrations` ledger in the managed database to record applied migrations; SIPM does not run migration apply steps during startup.
- CI/CD packaging, deployment manifests, environment injection, secret delivery, platform healthcheck wiring, log shipping, dashboards, and alert routing are external platform responsibilities.

## Frontend Validation

```bash
npm install
npm run lint:ui
npm run test:ui
npm run test:ui:smoke
```

- `lint:ui` runs the repo ESLint gate over `src/main/ui/js` and the browser test files.
- `test:ui` runs the Vitest/jsdom unit suite for router and live-sync behavior.
- `test:ui:smoke` runs Playwright against `scripts/run_ui_smoke_app.py`, which boots the app on a temporary SQLite database instead of the Oracle runtime.
