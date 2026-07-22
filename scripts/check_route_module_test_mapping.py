#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROUTE_MAP_PATH = Path("src/main/ui/js/route-module-test-map.json")
ROUTES_DIR = Path("src/main/ui/js/routes")


def validate_route_module_test_mapping(repo_root: Path) -> list[str]:
    repo_root = Path(repo_root).resolve()
    route_map_path = repo_root / ROUTE_MAP_PATH
    routes_dir = repo_root / ROUTES_DIR
    errors: list[str] = []

    if not route_map_path.exists():
        return [f"Missing route module mapping file: {route_map_path}"]
    if not routes_dir.exists():
        return [f"Missing routes directory: {routes_dir}"]

    try:
        payload: Any = json.loads(route_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to parse route module mapping file: {exc}"]

    modules = payload.get("modules")
    if not isinstance(modules, dict):
        return ["route-module-test-map.json must contain a top-level `modules` object."]

    route_files = sorted(path.name for path in routes_dir.glob("*.js"))
    mapped_files = set(modules.keys())

    for route_file in route_files:
        mapped_tests = modules.get(route_file)
        if not isinstance(mapped_tests, list) or not mapped_tests:
            errors.append(
                f"{route_file} must map to at least one test file in {route_map_path}."
            )
            continue
        for rel_test_path in mapped_tests:
            if not isinstance(rel_test_path, str) or not rel_test_path.strip():
                errors.append(
                    f"{route_file} contains an invalid test path: {rel_test_path!r}"
                )
                continue
            test_path = repo_root / rel_test_path
            if not test_path.exists():
                errors.append(f"{route_file} maps to missing test file: {test_path}")

    for mapped_file in sorted(mapped_files - set(route_files)):
        errors.append(f"Mapping exists for missing route module: {mapped_file}")

    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    failures = validate_route_module_test_mapping(root)
    if failures:
        raise SystemExit("\n".join(sorted(failures)))
