from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def _load_env_file(path: Path, *, override_existing: bool | None = None) -> None:
    if not path.exists():
        return
    if override_existing is None:
        override_existing = _bool_env("SIPM_ENV_OVERRIDE", False)
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        # Support common dotenv style: `export KEY=value`
        if key.lower().startswith("export "):
            parts = key.split(None, 1)
            key = parts[1].strip() if len(parts) > 1 else ""
        value = value.strip().strip("'").strip('"')
        # Support inline comments: KEY=value # comment
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        # Prefer explicit process env by default. Opt in to file overrides with
        # SIPM_ENV_OVERRIDE=true when local development needs it.
        if key and (override_existing or key not in os.environ or not str(os.environ.get(key) or "").strip()):
            os.environ[key] = value


def _repo_root_with_env(directories: tuple[Path, ...]) -> Path | None:
    for candidate in directories:
        if candidate.name == "main" and candidate.parent.name == "src":
            repo_root = candidate.parents[1]
            if (repo_root / ".env").exists() or (repo_root / ".env.local").exists():
                return repo_root
    return None


def _find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    directories = (cwd, *cwd.parents)

    # The repo-root environment is authoritative over the deprecated
    # src/main/.env fallback, even when the process starts inside src/main.
    repo_root = _repo_root_with_env(directories)
    if repo_root is not None:
        return repo_root

    for candidate in directories:
        if (candidate / ".env").exists() or (candidate / ".env.local").exists():
            return candidate
    # Walk upward to locate the first directory that contains `.env`.
    source_directories = tuple(Path(__file__).resolve().parents)
    repo_root = _repo_root_with_env(source_directories)
    if repo_root is not None:
        return repo_root
    for candidate in source_directories:
        if (candidate / ".env").exists() or (candidate / ".env.local").exists():
            return candidate
    # Fallback: repository layout under src/main in this workspace.
    base_dir = Path(__file__).resolve().parents[2]
    if len(base_dir.parents) > 1:
        return base_dir.parents[1]
    return base_dir


def _repo_dir_for(base_dir: Path) -> Path:
    """Resolve the repository root for a Python source root path."""
    if base_dir.name == "main" and base_dir.parent.name == "src" and len(base_dir.parents) > 1:
        return base_dir.parents[1]
    return base_dir


REPO_DIR = _find_repo_root()
REPO_ENV = REPO_DIR / ".env"
REPO_ENV_LOCAL = REPO_DIR / ".env.local"

_ENV_LOADED = False


def load_repo_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if REPO_ENV.exists() or REPO_ENV_LOCAL.exists():
        _load_env_file(REPO_ENV)
        _load_env_file(REPO_ENV_LOCAL)
    else:
        fallback_dir = BASE_DIR if BASE_DIR.exists() else REPO_DIR
        _load_env_file(fallback_dir / ".env")
        _load_env_file(fallback_dir / ".env.local")
    _ENV_LOADED = True


__all__ = ["_load_env_file", "_repo_dir_for", "load_repo_env"]
