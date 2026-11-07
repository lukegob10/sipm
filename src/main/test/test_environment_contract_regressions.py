from __future__ import annotations

import os

import pytest

from backend.app import environment


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ('SIPM_ENV_REVIEW_VALUE="alpha # beta"\n', "alpha # beta"),
        ("SIPM_ENV_REVIEW_VALUE='alpha # beta'\n", "alpha # beta"),
        ('SIPM_ENV_REVIEW_VALUE="alpha # beta" # comment\n', "alpha # beta"),
        ('export SIPM_ENV_REVIEW_VALUE="alpha # beta"\n', "alpha # beta"),
        ("SIPM_ENV_REVIEW_VALUE=alpha # comment\n", "alpha"),
    ],
)
def test_env_parser_preserves_hash_in_quoted_values(monkeypatch, tmp_path, contents, expected):
    env_file = tmp_path / ".env"
    env_file.write_text(contents, encoding="utf-8")
    monkeypatch.delenv("SIPM_ENV_REVIEW_VALUE", raising=False)
    environment._load_env_file(env_file, override_existing=False)
    assert os.environ["SIPM_ENV_REVIEW_VALUE"] == expected


def test_external_cwd_env_does_not_override_source_repo_env(monkeypatch, tmp_path):
    repo_root = tmp_path / "sipm"
    runtime_root = repo_root / "src" / "main"
    source_file = runtime_root / "backend" / "app" / "environment.py"
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    external = tmp_path / "unrelated"
    external.mkdir()
    (repo_root / ".env").write_text("SIPM_ENV_REVIEW_VALUE=repo\n", encoding="utf-8")
    (external / ".env").write_text("SIPM_ENV_REVIEW_VALUE=external\n", encoding="utf-8")
    monkeypatch.setattr(environment, "__file__", str(source_file))
    monkeypatch.setattr(environment.Path, "cwd", classmethod(lambda cls: external))
    monkeypatch.delenv("SIPM_ENV_REVIEW_VALUE", raising=False)

    selected_root = environment._find_repo_root()
    assert selected_root == repo_root
    environment._load_env_file(selected_root / ".env", override_existing=False)
    assert os.environ["SIPM_ENV_REVIEW_VALUE"] == "repo"


@pytest.mark.parametrize("override, expected", [(False, "process"), (True, "alpha # beta")])
def test_quoted_values_preserve_process_environment_precedence(monkeypatch, tmp_path, override, expected):
    env_file = tmp_path / ".env"
    env_file.write_text('SIPM_ENV_REVIEW_VALUE="alpha # beta"\n', encoding="utf-8")
    monkeypatch.setenv("SIPM_ENV_REVIEW_VALUE", "process")
    environment._load_env_file(env_file, override_existing=override)
    assert os.environ["SIPM_ENV_REVIEW_VALUE"] == expected


@pytest.mark.parametrize("layout", ["source", "flattened"])
def test_external_cwd_env_does_not_override_runtime_fallback(monkeypatch, tmp_path, layout):
    runtime_root = tmp_path / "sipm" / "src" / "main" if layout == "source" else tmp_path / "app"
    source_file = runtime_root / "backend" / "app" / "environment.py"
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    external = tmp_path / "unrelated"
    external.mkdir()
    (runtime_root / ".env").write_text("SIPM_ENV_REVIEW_VALUE=runtime\n", encoding="utf-8")
    (external / ".env").write_text("SIPM_ENV_REVIEW_VALUE=external\n", encoding="utf-8")
    monkeypatch.setattr(environment, "__file__", str(source_file))
    monkeypatch.setattr(environment.Path, "cwd", classmethod(lambda cls: external))
    assert environment._find_repo_root() == runtime_root
