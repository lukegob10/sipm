from __future__ import annotations

from pathlib import Path

import backend.main as main_module
from backend.app import environment as environment_module


def test_repo_dir_resolves_repo_root_from_source_tree_layout(tmp_path):
    repo_root = tmp_path / "sipm"
    layout_path = repo_root / "src" / "main"
    assert main_module._repo_dir_for(layout_path) == repo_root


def test_repo_dir_falls_back_to_runtime_root_for_flattened_container_layout(tmp_path):
    runtime_root = tmp_path / "app"
    assert main_module._repo_dir_for(runtime_root) == runtime_root


def test_main_keeps_environment_path_helper_compatibility():
    assert main_module._repo_dir_for is environment_module._repo_dir_for


def test_load_repo_env_prefers_repo_root_files(monkeypatch, tmp_path):
    repo_env = tmp_path / ".env"
    repo_local = tmp_path / ".env.local"
    base_env = tmp_path / "src" / "main" / ".env"
    base_env.parent.mkdir(parents=True)
    repo_env.write_text("SIPM_ENV_TEST_VALUE=repo\n", encoding="utf-8")
    repo_local.write_text("SIPM_ENV_TEST_LOCAL=local\n", encoding="utf-8")
    base_env.write_text("SIPM_ENV_TEST_VALUE=base\n", encoding="utf-8")

    monkeypatch.delenv("SIPM_ENV_TEST_VALUE", raising=False)
    monkeypatch.delenv("SIPM_ENV_TEST_LOCAL", raising=False)
    monkeypatch.setattr(environment_module, "REPO_ENV", repo_env)
    monkeypatch.setattr(environment_module, "REPO_ENV_LOCAL", repo_local)
    monkeypatch.setattr(environment_module, "BASE_DIR", base_env.parent)
    monkeypatch.setattr(environment_module, "_ENV_LOADED", False)

    environment_module.load_repo_env()

    assert environment_module.os.environ["SIPM_ENV_TEST_VALUE"] == "repo"
    assert environment_module.os.environ["SIPM_ENV_TEST_LOCAL"] == "local"


def test_load_repo_env_falls_back_to_runtime_env_files(monkeypatch, tmp_path):
    repo_env = tmp_path / "missing" / ".env"
    repo_local = tmp_path / "missing" / ".env.local"
    base_dir = tmp_path / "runtime"
    base_dir.mkdir()
    (base_dir / ".env").write_text("SIPM_ENV_TEST_VALUE=base\n", encoding="utf-8")

    monkeypatch.delenv("SIPM_ENV_TEST_VALUE", raising=False)
    monkeypatch.setattr(environment_module, "REPO_ENV", repo_env)
    monkeypatch.setattr(environment_module, "REPO_ENV_LOCAL", repo_local)
    monkeypatch.setattr(environment_module, "BASE_DIR", base_dir)
    monkeypatch.setattr(environment_module, "_ENV_LOADED", False)

    environment_module.load_repo_env()

    assert environment_module.os.environ["SIPM_ENV_TEST_VALUE"] == "base"


def test_find_repo_root_prefers_root_env_over_legacy_nested_env(monkeypatch, tmp_path):
    repo_root = tmp_path / "sipm"
    runtime_root = repo_root / "src" / "main"
    runtime_root.mkdir(parents=True)
    (repo_root / ".env").write_text("SIPM_TEST_MARKER=root\n", encoding="utf-8")
    (runtime_root / ".env").write_text("SIPM_TEST_MARKER=legacy\n", encoding="utf-8")
    monkeypatch.setattr(environment_module.Path, "cwd", classmethod(lambda cls: runtime_root))

    assert environment_module._find_repo_root() == repo_root


def test_find_repo_root_prefers_source_root_env_from_external_working_directory(monkeypatch, tmp_path):
    repo_root = tmp_path / "sipm"
    runtime_root = repo_root / "src" / "main"
    source_file = runtime_root / "backend" / "app" / "environment.py"
    external_workdir = tmp_path / "external"
    source_file.parent.mkdir(parents=True)
    external_workdir.mkdir()
    source_file.touch()
    (repo_root / ".env").write_text("SIPM_TEST_MARKER=root\n", encoding="utf-8")
    (runtime_root / ".env").write_text("SIPM_TEST_MARKER=legacy\n", encoding="utf-8")
    monkeypatch.setattr(environment_module, "__file__", str(source_file))
    monkeypatch.setattr(environment_module.Path, "cwd", classmethod(lambda cls: external_workdir))

    assert environment_module._find_repo_root() == repo_root


def test_base_dir_matches_runtime_root_for_source_layout():
    assert environment_module.BASE_DIR == Path(environment_module.__file__).resolve().parents[2]
