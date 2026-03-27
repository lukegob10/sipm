# SIPM Repo Operability Guide

Date: 2026-03-25
Scope: repo-visible runtime and operator expectations only; vendor-specific deployment and observability tooling are intentionally out of scope for wave 1.

## Runtime Modes

| Mode | Primary use | Required settings | Notes |
| --- | --- | --- | --- |
| `ENV=dev` or `ENV=local` | local development | `SIPM_COORDINATION_BACKEND=memory` by default | local auth defaults are relaxed compared to non-dev modes |
| `ENV=test` | automated tests and smoke harnesses | test harness may disable startup / use SQLite overrides | TA runtime normalizes `test` to `dev` semantics |
| `ENV=uat` | shared staging-like runtime | `SIPM_COORDINATION_BACKEND=redis`, `SIPM_REDIS_URL` required | non-dev auth safety applies |
| `ENV=prod` | production runtime | `SIPM_COORDINATION_BACKEND=redis`, `SIPM_REDIS_URL` required | non-dev auth safety applies and secret management is mandatory |

## Readiness And Liveness
- `GET /health`
  - shallow liveness probe
  - expected response: `{"status":"ok"}`
- `GET /health/ready`
  - readiness probe
  - validates auth/runtime configuration
  - validates DB connectivity unless startup is disabled or test mode is active
  - returns `503` when readiness checks fail
- Every response includes `X-Request-ID`; operators should use it as the first correlation key when tracing a failed request through logs and audit rows.

## Redis And Oracle Expectations
- Redis:
  - required when `ENV` resolves to `uat` or `prod`
  - used for coordination, scope-version invalidation, and cross-worker realtime refresh fanout
  - if Redis is unavailable in non-required modes, local memory fallback may keep development usable, but that is not an acceptable production posture
- Oracle / TA runtime:
  - non-test DB access depends on TAConnection-backed SQLAlchemy sessions
  - valid TA environment targets are `dev`, `uat`, and `prod`
  - pool settings are validated at startup and should fail fast on invalid values

## Local And CI Verification Paths
- Local app run:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r src/main/requirements.txt`
  - `uvicorn backend.main:app --reload --app-dir src/main`
- Frontend validation:
  - `npm run lint:ui`
  - `npm run test:ui`
  - `npm run test:ui:smoke`
- Repo quality tooling:
  - `python3 scripts/check_requirements_lock.py`
  - `python3 scripts/check_route_module_test_mapping.py`
  - `python3 scripts/codebase_review.py inventory`
  - `python3 scripts/codebase_review.py stale-scripts`
  - `python3 scripts/codebase_review.py quality-gates`

## Incident Triage
1. Confirm whether the failure is liveness, readiness, request-path, or browser-path only.
2. Capture the `X-Request-ID` from the failing response or reverse-proxy logs.
3. Check the request log line for `request_id`, `status`, `path`, `duration_ms`, and `space_id`.
4. If the failure touched a write path, check audit rows that share the same request ID.
5. If the issue looks like stale data or missed live refresh:
   - verify Redis coordination state in `uat`/`prod`
   - verify websocket connectivity and recent reconnect behavior
6. If the issue is startup or readiness related:
   - validate `ENV`, coordination backend, Redis URL, auth cookie settings, and DB pool values
7. Before escalating to product behavior, reproduce the path with the focused test suite that owns that area.

## Wave 1 Boundaries
- This guide is intentionally repo-scoped.
- It does not define deployment manifests, vendor-specific tracing, metrics backends, or infrastructure ownership.
- Those concerns can be added later, but only after the hotspot-reduction work in the enterprise roadmap is materially complete.
