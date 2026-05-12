# SIPM Home Lab Deployment

This folder documents the environment expected by `docker-compose.yml` and
`.github/workflows/deployment-home-lab.yml`.

## Server Prerequisites

- Linux host reachable by SSH from GitHub Actions.
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

- `HOMELAB_SSH_HOST`: server hostname or IP.
- `HOMELAB_SSH_USER`: SSH user that can run Docker commands.
- `HOMELAB_SSH_KEY`: private SSH key for that user.
- `HOMELAB_SSH_PORT`: optional SSH port; defaults to `22`.
- `HOMELAB_ENV_FILE`: full contents of the deployment `.env` file.
- `GHCR_USERNAME`: optional, required if the server must authenticate to GHCR.
- `GHCR_TOKEN`: optional, a PAT with package read permission for GHCR pulls.
- `PIP_EXTRA_INDEX_URL`: optional package-index URL used only when installing
  the real `treasury_analytics` package during the image build.

Create these repository variables if the defaults are not right:

- `HOMELAB_DEPLOY_PATH`: directory on the server; defaults to `~/sipm`.
- `HOMELAB_APP_PORT`: host port mapped to container port `8000`; defaults to `8000`.
- `INSTALL_TREASURY_ANALYTICS_MOCK`: defaults to `true` for this home-lab
  workflow. Set to `false` when using the real package.
- `TREASURY_ANALYTICS_PACKAGE`: package spec for the real connector, for example
  `treasury-analytics==1.2.3`.

## Runtime Environment

Use `.env.example` as the starting point for `HOMELAB_ENV_FILE`.

For UAT/prod, keep:

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
fallbacks. For `ENV=uat`, use `TA_UAT_DSN`, `TA_UAT_USER`, and
`TA_UAT_PASSWORD`.

For the current home-lab Oracle database, use:

```text
TA_UAT_DSN=192.168.1.151:1521/FREEPDB1
TA_UAT_USER=LG22254
TA_UAT_PASSWORD=<store only in GitHub secret or untracked local env file>
```

Do not hard-code `TA_UAT_PASSWORD` in committed files. Put the real password in
the `HOMELAB_ENV_FILE` GitHub secret. For one-off local Docker testing, place it
in an untracked repo-root `.env` file next to `docker-compose.yml`.

Do not put secrets in committed files. Store the final `.env` content in the
`HOMELAB_ENV_FILE` GitHub secret or place it directly on the server.

## Deploy

The workflow deploys automatically on pushes to `main`. You can also run it
manually from GitHub Actions with `workflow_dispatch`.

After the first deploy, check:

```bash
cd ~/sipm
docker compose ps
docker compose logs -f sipm
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/health/ready
```

Open the app at:

```text
http://<server>:8000/project-manager/
```
