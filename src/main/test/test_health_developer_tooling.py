from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("script_name", "failure"),
    [
        (script_name, failure)
        for script_name in ("run_ui_smoke_app", "run_developer_mode_demo")
        for failure in (None, "schema", "port", "server")
    ] + [("run_developer_mode_demo", "seed")],
)
def test_local_harness_releases_sqlite_before_temporary_directory_cleanup(
    monkeypatch, tmp_path, script_name, failure
):
    environment = {
        "ENV": "test",
        "SIPM_COORDINATION_BACKEND": "memory",
        "SIPM_DISABLE_STARTUP": "true",
        "SIPM_KEEPALIVE_TASK": "false",
        "SIPM_ENV_OVERRIDE": "false",
        "SIPM_BCRYPT_ROUNDS": "4",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    module = _load_script(script_name)
    monkeypatch.setattr(module.db_module, "engine", None)
    monkeypatch.setattr(module.db_module, "SessionLocal", None)
    events = []
    engines = []
    create_engine = module.create_engine

    def tracked_engine(*args, **kwargs):
        engine = create_engine(*args, **kwargs)
        engines.append(engine)
        dispose = engine.dispose

        def tracked_dispose():
            events.append("dispose")
            dispose()

        monkeypatch.setattr(engine, "dispose", tracked_dispose)
        return engine

    @contextmanager
    def temporary_directory(**kwargs):
        try:
            yield str(tmp_path)
        finally:
            events.append("temporary-directory-cleanup")

    monkeypatch.setattr(module, "create_engine", tracked_engine)
    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", temporary_directory)
    port_key = "SIPM_UI_SMOKE_PORT" if script_name == "run_ui_smoke_app" else "SIPM_DEVELOPER_MODE_DEMO_PORT"
    monkeypatch.setenv(port_key, "invalid" if failure == "port" else "8779")
    error = RuntimeError(f"{failure} failed")
    server = Mock(side_effect=error if failure == "server" else None)
    monkeypatch.setattr(module.uvicorn, "run", server)
    if failure == "schema":
        create_all = module.Base.metadata.create_all

        def fail_schema(*args, **kwargs):
            create_all(*args, **kwargs)
            raise error

        monkeypatch.setattr(module.Base.metadata, "create_all", fail_schema)
    if failure == "seed":
        monkeypatch.setattr(module, "seed_demo", Mock(side_effect=error))

    try:
        if failure == "port":
            with pytest.raises(ValueError, match="invalid"):
                module.main()
        elif failure:
            with pytest.raises(RuntimeError) as raised:
                module.main()
            assert raised.value is error
        else:
            module.main()
            server.assert_called_once()

        assert module.db_module.engine is None
        assert module.db_module.SessionLocal is None
        assert events == ["dispose", "temporary-directory-cleanup"]
        # A pooled SQLite connection keeps this file locked on Windows until disposal.
        for database in tmp_path.glob("*.db"):
            database.unlink()
    finally:
        for engine in engines:
            engine.dispose()


def _mapping_repo(tmp_path, payload):
    routes_dir = tmp_path / "src/main/ui/js/routes"
    routes_dir.mkdir(parents=True)
    (routes_dir / "example.js").write_text("export const render = () => {};", encoding="utf-8")
    (routes_dir.parent / "route-module-test-map.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("payload", [None, [], "modules", 1])
def test_route_mapping_rejects_non_object_json_without_crashing(tmp_path, payload):
    checker = _load_script("check_route_module_test_mapping")
    errors = checker.validate_route_module_test_mapping(_mapping_repo(tmp_path, payload))
    assert errors == ["route-module-test-map.json must contain a top-level `modules` object."]


def test_route_mapping_requires_a_test_file_instead_of_a_directory(tmp_path):
    checker = _load_script("check_route_module_test_mapping")
    repo = _mapping_repo(tmp_path, {"modules": {"example.js": ["src/main/ui/test"]}})
    tests_dir = repo / "src/main/ui/test"
    tests_dir.mkdir()
    errors = checker.validate_route_module_test_mapping(repo)
    assert len(errors) == 1
    assert str(tests_dir) in errors[0]


def test_route_mapping_accepts_existing_test_file(tmp_path):
    checker = _load_script("check_route_module_test_mapping")
    repo = _mapping_repo(tmp_path, {"modules": {"example.js": ["test_example.py"]}})
    (repo / "test_example.py").write_text("def test_example(): pass\n", encoding="utf-8")
    assert checker.validate_route_module_test_mapping(repo) == []
