from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class RuntimePaths:
    base_dir: Path
    repo_dir: Path
    frontend_dir: Path
    frontend_required_files: tuple[Path, ...]


def repo_dir_for(base_dir: Path) -> Path:
    # Local source runs from <repo>/src/main, while the Docker image flattens that to /app.
    if len(base_dir.parents) > 1:
        return base_dir.parents[1]
    return base_dir


def build_runtime_paths(base_dir: Path | None = None) -> RuntimePaths:
    resolved_base_dir = base_dir or Path(__file__).resolve().parents[2]
    frontend_dir = resolved_base_dir / "ui"
    return RuntimePaths(
        base_dir=resolved_base_dir,
        repo_dir=repo_dir_for(resolved_base_dir),
        frontend_dir=frontend_dir,
        frontend_required_files=(
            frontend_dir / "index.html",
            frontend_dir / "styles.css",
            frontend_dir / "js" / "app.js",
        ),
    )


RUNTIME_PATHS = build_runtime_paths()
BASE_DIR = RUNTIME_PATHS.base_dir
REPO_DIR = RUNTIME_PATHS.repo_dir
FRONTEND_DIR = RUNTIME_PATHS.frontend_dir
FRONTEND_REQUIRED_FILES = RUNTIME_PATHS.frontend_required_files
_ENV_LOADED = False


def bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def require_min(name: str, value: int, minimum: int) -> int:
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}.")
    return value


def require_min_or_disable(
    name: str, value: int, disable_value: int, minimum: int
) -> int:
    if value == disable_value:
        return value
    if value < minimum:
        raise RuntimeError(f"{name} must be {disable_value} or >= {minimum}.")
    return value


def load_env_file(path: Path, *, override_existing: bool | None = None) -> None:
    if not path.exists():
        return
    if override_existing is None:
        override_existing = bool_env("SIPM_ENV_OVERRIDE", False)
    for key, value in dotenv_values(path).items():
        if not key or value is None:
            continue
        if (
            override_existing
            or key not in os.environ
            or not str(os.environ.get(key) or "").strip()
        ):
            os.environ[key] = value


def runtime_env_files(paths: RuntimePaths = RUNTIME_PATHS) -> tuple[Path, ...]:
    repo_env = paths.repo_dir / ".env"
    repo_env_local = paths.repo_dir / ".env.local"

    # Use the repo-root env files as the single source of truth.
    # Keep `src/main/.env` only as a legacy fallback for older local setups.
    if repo_env.exists() or repo_env_local.exists():
        return repo_env, repo_env_local
    return paths.base_dir / ".env", paths.base_dir / ".env.local"


def load_runtime_env(
    *, force: bool = False, paths: RuntimePaths = RUNTIME_PATHS
) -> None:
    global _ENV_LOADED
    if _ENV_LOADED and not force:
        return
    for env_file in runtime_env_files(paths):
        load_env_file(env_file)
    _ENV_LOADED = True


def startup_db_disabled() -> bool:
    return bool_env("SIPM_DISABLE_STARTUP", False)


def db_prewarm_connection_count() -> int:
    if not bool_env("SIPM_DB_PREWARM_ON_STARTUP", False):
        return 0
    return require_min(
        "SIPM_DB_PREWARM_CONNECTIONS",
        int_env("SIPM_DB_PREWARM_CONNECTIONS", 1),
        1,
    )


def db_keepwarm_interval_seconds() -> int:
    return require_min_or_disable(
        "SIPM_DB_KEEPWARM_INTERVAL_SECONDS",
        int_env("SIPM_DB_KEEPWARM_INTERVAL_SECONDS", 0),
        0,
        1,
    )
