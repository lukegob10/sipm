# SIPM Home Lab Deployment

This folder documents the environment expected by `docker-compose.yml` and
`.github/workflows/deploy-homelab.yml`.

## Server Prerequisites

- Self-hosted GitHub Actions runner on `homelab001` with labels
  `self-hosted`, `homelab`, `docker`, and `sipm`.
- Docker Engine with the Compose plugin available as `docker compose`.
- Network access from the SIPM container to the TA/Oracle runtime used by
  `treasury_analytics.TAConnection`.
- The image must include a `treasury_analytics` package. Corporate-style builds
  should install the real package from Artifactory or the company package index.
  Home-lab rehearsal builds can opt into the local mock package documented below.
- Any host-level reverse proxy or TLS termination you want in front of SIPM.
  The container exposes HTTP on port `8000`.

## GitHub Secrets

Create these repository secrets:

- `HOMELAB_ENV_FILE`: full contents of the deployment `.env` file.
- `PIP_EXTRA_INDEX_URL`: optional package-index URL used only when installing
  the real `treasury_analytics` package during the image build.

Create these repository variables if the defaults are not right:

- `INSTALL_TREASURY_ANALYTICS_MOCK`: defaults to `true` for this home-lab
  workflow. Set to `false` when using the real package.
- `TREASURY_ANALYTICS_PACKAGE`: package spec for the real connector, for example
  `treasury-analytics==1.2.3`.

## Runtime Environment

Use `.env.example` as the starting point for `HOMELAB_ENV_FILE`.

Keep the SIPM deployment isolated from other apps on the same server:

- Install the GitHub runner in a SIPM-specific directory and service. See
  `deployment/runner-isolation.md`.
- Keep `COMPOSE_PROJECT_NAME=sipm`.
- Keep `SIPM_CONTAINER_NAME=sipm` and `SIPM_REDIS_CONTAINER_NAME=sipm-redis`,
  or change them to another SIPM-specific pair if those names are already used.
- Use a host port that does not conflict with another app.

For HTTP-only home-lab deployment, use a local profile while keeping
self-registration disabled:

- `ENV=dev`
- `SIPM_ALLOW_SELF_REGISTER=false`
- `SIPM_SECURE_COOKIES=false`
- `SIPM_COOKIE_SAMESITE=lax`
- `SIPM_SECRET_KEY` set to a long random value

This is required for browser login over plain HTTP. If `SIPM_SECURE_COOKIES=true`
on an HTTP origin, the browser will not keep/send the login cookies and the UI
will immediately behave like the session expired.

For HTTPS UAT/prod, keep:

- `ENV=uat` or `ENV=prod`
- `SIPM_ALLOW_SELF_REGISTER=false`
- `SIPM_SECURE_COOKIES=true`
- `SIPM_COOKIE_SAMESITE=lax` or `strict`
- `SIPM_SECRET_KEY` set to a long random value

The compose file always runs Redis and injects:

- `SIPM_COORDINATION_BACKEND=redis`
- `SIPM_REDIS_URL=redis://redis:6379/0`

Add any TA/Oracle environment variables required by your `treasury_analytics`
configuration to `HOMELAB_ENV_FILE`. Do not commit those values.

## treasury_analytics Strategy

The app code keeps the corporate boundary:

```python
from treasury_analytics import TAConnection
```

There are two image build modes:

- Local/home-lab rehearsal: leave `INSTALL_TREASURY_ANALYTICS_MOCK=true`. The
  Dockerfile installs `deployment/mock-packages/treasury_analytics`, which
  exposes `TAConnection(env=...).connect()` and delegates to `oracledb`.
- Corporate/UAT/prod-like package install: set
  `INSTALL_TREASURY_ANALYTICS_MOCK=false`, set `TREASURY_ANALYTICS_PACKAGE`, and
  provide `PIP_EXTRA_INDEX_URL` if the package index needs it.

The local mock reads `TA_<ENV>_DSN`, `TA_<ENV>_USER`, and
`TA_<ENV>_PASSWORD`, with `TA_DSN`, `TA_USER`, and `TA_PASSWORD` as generic
fallbacks. For HTTP home lab with `ENV=dev`, use `TA_DEV_DSN`, `TA_DEV_USER`,
and `TA_DEV_PASSWORD`.

For the current home-lab Oracle database, use:

```text
TA_DEV_DSN=host.docker.internal:1521/FREEPDB1
TA_DEV_USER=app_user
TA_DEV_PASSWORD=<store only in GitHub secret or untracked local env file>
```

`docker-compose.yml` maps `host.docker.internal` to the Docker host gateway so
the SIPM container can reach Oracle published on the homelab host port `1521`.
If your Docker networking requires the LAN IP instead, set
`TA_DEV_DSN=192.168.1.151:1521/FREEPDB1` in `HOMELAB_ENV_FILE`.

Do not hard-code `TA_DEV_PASSWORD` in committed files. Put the real password in
the `HOMELAB_ENV_FILE` GitHub secret. For one-off local Docker testing, place it
in an untracked repo-root `.env` file next to `docker-compose.yml`.

Do not put secrets in committed files. Store the final `.env` content in the
`HOMELAB_ENV_FILE` GitHub secret or place it directly on the server.

## Deploy

The workflow deploys automatically on pushes to `main`. You can also run it
manually from GitHub Actions with `workflow_dispatch`. Because the runner is
already on `homelab001`, deployment runs directly with `docker compose up -d
--build`; no SSH key, `scp`, or remote shell step is used.

After the first deploy, check:

```bash
cd ~/actions-runners/sipm/actions-runner/_work/sipm/sipm
docker compose ps
docker compose logs -f sipm
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/health/ready
```

Open the app at:

```text
http://<server>:8000/project-manager/
```

## First-Deploy Database Setup

SIPM does not mutate Oracle schema or reference data during application
startup. For a new database, run the SQL artifacts in this order:

1. `docs/sql/schema_oracle_ta.sql`
2. `docs/sql/first_deploy_reference_data.sql`
3. `docs/sql/first_time_global_admin.sql`, after the first user row exists

`first_deploy_reference_data.sql` seeds the canonical phase catalog required by
the planning and solution phase workflows. It is idempotent and can be rerun if
an environment is missing phase rows.

## Oracle Migration Repairs

After deploying the server-enforced inactivity-session feature to an existing
database, run:

1. `docs/sql/20260715_auth_sessions_v1.sql`

The migration is idempotent and must be applied before the updated application
accepts interactive logins. It creates `TB_TA_PM_AUTH_SESSIONS` and its required
indexes; application startup intentionally does not create it automatically.

If an environment has already renamed `TB_TA_PM_SUBCOMPONENTS` to
`TB_TA_PM_TASKS` but still errors with `ORA-00904:
"TB_TA_PM_TASKS"."TASK_NAME": invalid identifier`, run:

1. `docs/sql/20260610_repair_partial_task_rename.sql`

The repair script is guarded by Oracle data-dictionary checks and is safe to run
after a successful task rename migration.
