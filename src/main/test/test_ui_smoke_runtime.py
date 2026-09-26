from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_ui_smoke_runner_forces_isolated_flags_before_backend_imports() -> None:
    smoke_script = REPO_ROOT / "scripts" / "run_ui_smoke_app.py"
    probe = r"""
import builtins
import importlib
import json
import os
from pathlib import Path
import runpy
import sys

main_dir = Path(sys.argv[1]).resolve().parents[1] / "src" / "main"
sys.path.insert(0, str(main_dir))
environment = importlib.import_module("backend.app.environment")
environment._ENV_LOADED = True

protected = (
    "ENV",
    "SIPM_COORDINATION_BACKEND",
    "SIPM_DISABLE_STARTUP",
    "SIPM_KEEPALIVE_TASK",
    "SIPM_ENV_OVERRIDE",
)
imports = {}
watched = {"backend.app.models", "backend.app.db.db", "backend.main"}
original_import = builtins.__import__

def capture_flags_before_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in watched:
        imports[name] = {key: os.environ.get(key) for key in protected}
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = capture_flags_before_import

import uvicorn

def reject_server_start(*args, **kwargs):
    raise AssertionError("server must not start during import")

uvicorn.run = reject_server_start
runpy.run_path(sys.argv[1], run_name="sipm_ui_smoke_probe")
print(json.dumps({
    "imports": imports,
    "preserved": {
        "SIPM_UI_SMOKE_PORT": os.environ.get("SIPM_UI_SMOKE_PORT"),
        "SIPM_BCRYPT_ROUNDS": os.environ.get("SIPM_BCRYPT_ROUNDS"),
    },
}))
"""
    safe_environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
        if key in os.environ
    }
    safe_environment.update(
        {
            "ENV": "prod",
            "SIPM_COORDINATION_BACKEND": "redis",
            "SIPM_DISABLE_STARTUP": "false",
            "SIPM_KEEPALIVE_TASK": "true",
            "SIPM_ENV_OVERRIDE": "true",
            "SIPM_UI_SMOKE_PORT": "8776",
            "SIPM_BCRYPT_ROUNDS": "12",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(smoke_script)],
        cwd=REPO_ROOT,
        env=safe_environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    expected_flags = {
        "ENV": "dev",
        "SIPM_COORDINATION_BACKEND": "memory",
        "SIPM_DISABLE_STARTUP": "true",
        "SIPM_KEEPALIVE_TASK": "false",
        "SIPM_ENV_OVERRIDE": "false",
    }
    assert observed["imports"] == {
        "backend.app.models": expected_flags,
        "backend.app.db.db": expected_flags,
        "backend.main": expected_flags,
    }
    assert observed["preserved"] == {"SIPM_UI_SMOKE_PORT": "8776", "SIPM_BCRYPT_ROUNDS": "12"}
