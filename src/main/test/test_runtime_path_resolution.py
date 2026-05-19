from __future__ import annotations

from pathlib import Path

from backend.app.config import repo_dir_for


def test_repo_dir_resolves_repo_root_from_source_tree_layout():
    assert repo_dir_for(Path("/workspace/sipm/src/main")) == Path("/workspace/sipm")


def test_repo_dir_falls_back_to_runtime_root_for_flattened_container_layout():
    assert repo_dir_for(Path("/app")) == Path("/app")
