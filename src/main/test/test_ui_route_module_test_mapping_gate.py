import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_route_module_test_mapping.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "route_module_mapping_check", CHECK_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import checker script: {CHECK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frontend_route_modules_have_mapped_tests():
    checker = _load_checker()
    errors = checker.validate_route_module_test_mapping(REPO_ROOT)
    assert not errors, "Route module test mapping violations:\n" + "\n".join(
        sorted(errors)
    )
