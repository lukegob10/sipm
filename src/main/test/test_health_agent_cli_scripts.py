from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_FLAGS = {
    "ENV": "test",
    "SIPM_COORDINATION_BACKEND": "memory",
    "SIPM_DISABLE_STARTUP": "true",
    "SIPM_DISABLE_THREADPOOL": "true",
    "SIPM_KEEPALIVE_TASK": "false",
    "SIPM_ENV_OVERRIDE": "false",
}


def _load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli():
    return _load_script("health_agent_cli", "skills/sipm-agent/scripts/sipm_agent.py")


@pytest.fixture
def benchmark(monkeypatch):
    for name in BENCHMARK_FLAGS:
        monkeypatch.setenv(name, os.environ.get(name, ""))
    return _load_script("health_agent_benchmark", "scripts/benchmark_agent_api.py")


@pytest.mark.parametrize("value", ["[]", "null", '"text"', "1", "{invalid"])
def test_propose_update_rejects_invalid_fields_before_network(cli, monkeypatch, value):
    monkeypatch.setattr(sys, "argv", [
        "sipm_agent.py", "propose-update", "--entity-type", "task", "--id", "task",
        "--reason", "Update task", "--fields-json", value,
    ])
    client_factory = Mock(side_effect=AssertionError("invalid input reached the network"))
    monkeypatch.setattr(cli, "client_from_args", client_factory)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    client_factory.assert_not_called()


@pytest.mark.parametrize("command", ["validate-patch", "submit-change-request", "replace-change-request"])
@pytest.mark.parametrize("content", ["[]", "null", "{invalid"])
def test_patch_file_must_be_an_object_before_network(cli, monkeypatch, tmp_path, command, content):
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(content, encoding="utf-8")
    args = ["sipm_agent.py", command, "--patch-file", str(patch_path)]
    if command == "replace-change-request":
        args.extend(["--request-id", "request"])
    monkeypatch.setattr(sys, "argv", args)
    client_factory = Mock(side_effect=AssertionError("invalid file reached the network"))
    monkeypatch.setattr(cli, "client_from_args", client_factory)

    with pytest.raises(SystemExit, match="JSON"):
        cli.main()

    client_factory.assert_not_called()


def test_missing_patch_file_has_a_readable_error(cli, tmp_path):
    with pytest.raises(SystemExit, match="missing.json"):
        cli.load_json(str(tmp_path / "missing.json"))


def test_valid_update_keeps_fields_and_idempotency_key(cli, monkeypatch, capsys):
    client = SimpleNamespace(
        resolve_space_id=lambda _space: "space",
        get_detail=lambda *_args, **_kwargs: {"updated_at": "2026-11-06T12:00:00"},
        request=Mock(return_value={"status": "pending"}),
    )
    monkeypatch.setattr(cli, "client_from_args", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(sys, "argv", [
        "sipm_agent.py", "propose-update", "--entity-type", "task", "--id", "task",
        "--reason", "Update task", "--fields-json", '{"description":null,"priority":2}',
        "--idempotency-key", "same-key",
    ])

    assert cli.main() == 0

    body = client.request.call_args.kwargs["body"]
    assert body["operations"][0]["fields"] == {"description": None, "priority": 2}
    assert body["idempotency_key"] == "same-key"
    assert json.loads(capsys.readouterr().out) == {"status": "pending"}


@pytest.mark.parametrize("body, expected", [
    (b'{"detail":"bad input"}', {"detail": "bad input"}),
    (b"upstream unavailable", {"message": "upstream unavailable"}),
])
def test_http_error_preserves_output_and_closes_response(cli, body, expected):
    response = BytesIO(body)
    error = urllib.error.HTTPError("http://example.invalid/api/test", 400, "Bad request", {}, response)
    client = cli.SipmClient("http://example.invalid", "token")
    client.opener = SimpleNamespace(open=Mock(side_effect=error))

    with pytest.raises(SystemExit) as raised:
        client.request("GET", "/test")

    assert json.loads(str(raised.value)) == {"status": 400, "error": expected}
    assert response.closed


def test_rejected_redirect_closes_response(cli):
    response = BytesIO(b"")
    request = urllib.request.Request("https://example.invalid/api/test")

    with pytest.raises(SystemExit, match="different origin"):
        cli.SameOriginRedirectHandler().redirect_request(
            request, response, 302, "Found", {}, "https://other.invalid/collect"
        )

    assert response.closed


def test_benchmark_forces_isolated_flags_before_backend_import():
    probe = """
import builtins
import json
import os
import runpy
import sys

class Captured(Exception):
    pass

original_import = builtins.__import__
def intercept(name, *args, **kwargs):
    if name.startswith("backend."):
        print(json.dumps({key: os.environ.get(key) for key in json.loads(sys.argv[2])}))
        raise Captured
    return original_import(name, *args, **kwargs)

builtins.__import__ = intercept
try:
    runpy.run_path(sys.argv[1], run_name="benchmark_probe")
except Captured:
    pass
"""
    child_environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
        if key in os.environ
    }
    child_environment.update({
        "ENV": "prod", "SIPM_COORDINATION_BACKEND": "redis",
        "SIPM_DISABLE_STARTUP": "false", "SIPM_DISABLE_THREADPOOL": "false",
        "SIPM_KEEPALIVE_TASK": "true", "SIPM_ENV_OVERRIDE": "true",
    })
    result = subprocess.run(
        [sys.executable, "-c", probe, str(REPO_ROOT / "scripts/benchmark_agent_api.py"), json.dumps(list(BENCHMARK_FLAGS))],
        cwd=REPO_ROOT, env=child_environment, capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == BENCHMARK_FLAGS


@pytest.mark.anyio
@pytest.mark.parametrize("failure_stage", ["schema", "seed"])
async def test_benchmark_disposes_engine_when_setup_fails(benchmark, monkeypatch, failure_stage):
    engine = SimpleNamespace(dispose=Mock())
    monkeypatch.setattr(benchmark, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(benchmark, "sessionmaker", lambda **_kwargs: object())
    monkeypatch.setattr(benchmark.Base.metadata, "create_all", Mock(
        side_effect=RuntimeError("setup failed") if failure_stage == "schema" else None,
    ))
    monkeypatch.setattr(benchmark, "_seed_data", Mock(side_effect=RuntimeError("setup failed")))

    with pytest.raises(RuntimeError, match="setup failed"):
        await benchmark._run(argparse.Namespace(projects=1, solutions_per_project=1, tasks_per_solution=1, iterations=1))

    engine.dispose.assert_called_once_with()


@pytest.mark.anyio
@pytest.mark.parametrize("measurement_fails", [False, True])
@pytest.mark.parametrize("has_db_override", [False, True])
async def test_benchmark_restores_only_its_own_dependency_override(benchmark, monkeypatch, measurement_fails, has_db_override):
    engine = SimpleNamespace(dispose=Mock())
    monkeypatch.setattr(benchmark, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr(benchmark, "sessionmaker", lambda **_kwargs: object())
    monkeypatch.setattr(benchmark.event, "listens_for", lambda *_args: lambda function: function)
    monkeypatch.setattr(benchmark.Base.metadata, "create_all", lambda **_kwargs: None)
    monkeypatch.setattr(benchmark, "_seed_data", lambda *_args, **_kwargs: ("token", "space", "project", "timestamp"))
    existing_db_override = Mock(name="existing_db_override")
    other_dependency = Mock(name="other_dependency")
    other_override = Mock(name="other_override")
    overrides = {other_dependency: other_override}
    if has_db_override:
        overrides[benchmark.deps_module.get_db] = existing_db_override
    expected_overrides = dict(overrides)

    @asynccontextmanager
    async def lifespan(_app):
        yield

    fake_app = SimpleNamespace(dependency_overrides=overrides, router=SimpleNamespace(lifespan_context=lifespan))
    monkeypatch.setattr(benchmark, "app", fake_app)

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def get(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=200)

    async def measure(*_args, name, **_kwargs):
        assert overrides[benchmark.deps_module.get_db] is not existing_db_override
        assert overrides[other_dependency] is other_override
        if measurement_fails:
            raise RuntimeError("measurement failed")
        return {"name": name}

    monkeypatch.setattr(benchmark.httpx, "AsyncClient", Client)
    monkeypatch.setattr(benchmark, "_measure_case", measure)
    args = argparse.Namespace(projects=1, solutions_per_project=1, tasks_per_solution=1, iterations=1)

    if measurement_fails:
        with pytest.raises(RuntimeError, match="measurement failed"):
            await benchmark._run(args)
    else:
        result = await benchmark._run(args)
        assert len(result["results"]) == 6

    assert overrides == expected_overrides
    engine.dispose.assert_called_once_with()
