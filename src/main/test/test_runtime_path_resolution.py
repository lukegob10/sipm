from __future__ import annotations

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
