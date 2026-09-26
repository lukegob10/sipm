from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def deploy_step():
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/deploy-homelab.yml").read_text(encoding="utf-8")
    )
    return next(step["run"] for step in workflow["jobs"]["deploy"]["steps"] if step["name"] == "Deploy")


@pytest.fixture
def bash():
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            return str(candidate)
        pytest.skip("Workflow execution requires Git Bash on Windows")
    executable = shutil.which("bash")
    if not executable:
        pytest.skip("Workflow execution requires Bash")
    return executable


def run_deploy_step(bash, deploy_step, tmp_path, *, ready="true", fail_migration="false"):
    # Execute the real workflow shell with a fake Docker boundary: no daemon or
    # external services are accessed, and readiness failure follows Compose's CLI contract.
    command_log = tmp_path / "docker-calls.txt"
    env = {
        **os.environ,
        "CALL_LOG": command_log.as_posix(),
        "CONTAINER_READY": ready,
        "FAIL_MIGRATION": fail_migration,
        "BASH_ENV": "",
    }
    fake_docker = """
docker() {
    printf '%s\\n' "$*" >> "$CALL_LOG"
    if [ "$1 $2" = "compose run" ] && [ "$FAIL_MIGRATION" = "true" ]; then
        return 42
    fi
    if [ "$1 $2" = "compose up" ]; then
        case " $* " in
            *" --wait "*) [ "$CONTAINER_READY" = "true" ] || return 1 ;;
        esac
    fi
}
"""
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", fake_docker + deploy_step],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    return result, command_log.read_text(encoding="utf-8").splitlines()


def test_deploy_fails_when_container_never_becomes_ready(bash, deploy_step, tmp_path):
    result, commands = run_deploy_step(bash, deploy_step, tmp_path, ready="false")

    assert result.returncode == 1, result.stderr
    assert commands[-1].startswith("compose up ")
    assert "compose ps" not in commands


def test_deploy_succeeds_after_migrations_and_readiness(bash, deploy_step, tmp_path):
    result, commands = run_deploy_step(bash, deploy_step, tmp_path)

    assert result.returncode == 0, result.stderr
    migration_commands = [command for command in commands if command.startswith("compose run ")]
    assert len(migration_commands) == 3
    assert commands[-1] == "compose ps"


def test_deploy_does_not_start_app_after_migration_failure(bash, deploy_step, tmp_path):
    result, commands = run_deploy_step(bash, deploy_step, tmp_path, fail_migration="true")

    assert result.returncode == 42, result.stderr
    assert not any(command.startswith("compose up ") for command in commands)
