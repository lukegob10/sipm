#!/usr/bin/env python3
"""Fail when frontend route modules are added without mapped tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROUTE_MODULES_DIR = Path("src/main/ui/js/routes")
MAP_FILE = Path("src/main/ui/js/route-module-test-map.json")
IGNORED_MODULES = {"index.js"}


def _discover_route_modules(repo_root: Path) -> set[str]:
    routes_dir = repo_root / ROUTE_MODULES_DIR
    if not routes_dir.exists():
        return set()
    return {
        path.name
        for path in routes_dir.glob("*.js")
        if path.name not in IGNORED_MODULES and not path.name.startswith("_")
    }


def _load_mapping(repo_root: Path) -> dict[str, list[str]]:
    map_file = repo_root / MAP_FILE
    if not map_file.exists():
        raise FileNotFoundError(
            f"Missing mapping file: {MAP_FILE}. Add it before introducing route modules."
        )
    data = json.loads(map_file.read_text(encoding="utf-8"))
    modules = data.get("modules")
    if not isinstance(modules, dict):
        raise ValueError(f"{MAP_FILE} must include a top-level 'modules' object.")
    normalized: dict[str, list[str]] = {}
    for module_name, tests in modules.items():
        if not isinstance(module_name, str):
            raise ValueError(f"{MAP_FILE} has a non-string module name key.")
        if not isinstance(tests, list) or not tests or any(not isinstance(t, str) for t in tests):
            raise ValueError(
                f"{MAP_FILE} entry '{module_name}' must map to a non-empty list of test file paths."
            )
        normalized[module_name] = tests
    return normalized


def validate_route_module_test_mapping(repo_root: Path) -> list[str]:
    errors: list[str] = []
    modules = _discover_route_modules(repo_root)

    try:
        mapping = _load_mapping(repo_root)
    except Exception as exc:  # pragma: no cover - covered by direct assertions below
        return [str(exc)]

    mapped_modules = set(mapping.keys())
    missing_map = sorted(modules - mapped_modules)
    stale_map = sorted(mapped_modules - modules)

    for module in missing_map:
        errors.append(
            f"Route module '{module}' is missing from {MAP_FILE}. "
            "Add a mapping entry to one or more test files."
        )

    for module in stale_map:
        errors.append(
            f"Mapping entry '{module}' in {MAP_FILE} has no matching module in {ROUTE_MODULES_DIR}."
        )

    for module in sorted(modules & mapped_modules):
        for test_file in mapping[module]:
            test_path = repo_root / test_file
            if not test_path.exists():
                errors.append(
                    f"Mapped test path '{test_file}' for route module '{module}' does not exist."
                )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors = validate_route_module_test_mapping(repo_root)
    if errors:
        print("Route module test mapping check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1
    print("Route module test mapping check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
