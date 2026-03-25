import importlib.util
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "codebase_review.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("codebase_review", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import review helper: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_active_repo_files_exclude_git_ignored_noise():
    module = _load_module()
    paths = {path.as_posix() for path in module.list_active_repo_files(REPO_ROOT)}

    assert "scripts/check_requirements_lock.py" in paths
    assert "scripts/check_route_module_test_mapping.py" in paths
    assert "scripts/codebase_review.py" in paths

    assert not any(path.startswith("htmlcov/") for path in paths)
    assert not any(path.startswith(".venv/") for path in paths)
    assert not any(path.startswith(".pytest_cache/") for path in paths)
    assert not any("__pycache__/" in path for path in paths)


def test_script_candidates_only_include_repo_scripts():
    module = _load_module()
    files = module.list_active_repo_files(REPO_ROOT)
    candidates = module.collect_script_candidates(REPO_ROOT, files)
    candidate_paths = {record.rel_path for record in candidates}

    assert "scripts/check_requirements_lock.py" in candidate_paths
    assert "scripts/check_route_module_test_mapping.py" in candidate_paths
    assert "scripts/codebase_review.py" in candidate_paths
    assert "src/main/ui/js/app.js" not in candidate_paths
    assert all(path.startswith("scripts/") for path in candidate_paths)


def test_inventory_and_stale_script_reports_are_noise_filtered():
    module = _load_module()

    inventory = module.render_inventory(REPO_ROOT)
    assert "htmlcov/" not in inventory
    assert "frontend:" in inventory
    assert "backend:" in inventory

    stale_report = module.render_stale_scripts(REPO_ROOT)
    assert "src/main/ui/js/app.js" not in stale_report
    assert "scripts/check_requirements_lock.py" in stale_report
