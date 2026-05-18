# SIPM Self-Hosted Runner Isolation

Use a dedicated GitHub Actions runner installation for SIPM. Do not reuse a
runner directory or systemd service that belongs to another project.

## Recommended Server Layout

```text
~/actions-runners/
  sipm/
    actions-runner/
  other-project/
    actions-runner/
```

The SIPM runner should be registered with these labels:

```text
self-hosted, homelab, docker, sipm
```

The deploy workflow requires the `sipm` label so another homelab runner with
generic `homelab` and `docker` labels is not selected accidentally.

## Recovery Checklist

On the server, inspect existing runner services before installing anything:

```bash
systemctl list-units 'actions.runner.*' --all
```

If another project already has a runner, leave its install directory and service
alone. Create a separate SIPM directory:

```bash
mkdir -p ~/actions-runners/sipm
cd ~/actions-runners/sipm
```

Download and configure the GitHub runner from this directory only, using the
current token and URL from GitHub repository settings. Use a distinct runner
name, for example:

```bash
./config.sh \
  --url https://github.com/<owner>/sipm \
  --token <registration-token> \
  --name homelab001-sipm \
  --labels self-hosted,homelab,docker,sipm \
  --work _work
```

Install the service from the SIPM runner directory:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

After registration, confirm the runner appears online in GitHub with the `sipm`
label before running the deploy workflow.

## Compose Isolation

SIPM uses a fixed Compose project name:

```text
COMPOSE_PROJECT_NAME=sipm
```

Keep this value in `HOMELAB_ENV_FILE` unless you intentionally want a parallel
SIPM stack. If you deploy another app on the same server, give that app its own
Compose project name, container names, host port, volumes, and runner label.
