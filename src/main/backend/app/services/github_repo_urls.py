from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from ..utils import normalize_str

GITHUB_HOST = "github.com"
RepoSource = Literal["override", "inherited", "none"]


def _repo_root_path(path: str) -> tuple[str, str]:
    normalized_path = path.strip().rstrip("/")
    if normalized_path.endswith(".git"):
        normalized_path = normalized_path[:-4]

    parts = [segment for segment in normalized_path.split("/") if segment]
    if len(parts) != 2:
        raise ValueError("github_repo_url must point to a GitHub repository root")

    return parts[0], parts[1]


def normalize_github_repo_url(value: str | None, *, validate_length: bool = True) -> str | None:
    raw = normalize_str(value)
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("github_repo_url must use https")
    if parsed.netloc.lower() != GITHUB_HOST:
        raise ValueError("github_repo_url must point to github.com")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("github_repo_url must be a clean GitHub repository URL")

    owner, repo = _repo_root_path(parsed.path or "")
    normalized = f"https://{GITHUB_HOST}/{owner}/{repo}"
    if validate_length and len(normalized) > 1024:
        raise ValueError("github_repo_url must be 1024 characters or fewer")
    return normalized


def resolve_effective_github_repo_url(
    *,
    solution_repo_url: str | None,
    task_repo_url: str | None,
) -> tuple[str | None, RepoSource]:
    # Historical values may predate repository validation. Keep reads usable,
    # but never interpret an invalid explicit override as permission to use the
    # parent repository instead. Write paths still validate with the strict parser.
    if normalize_str(task_repo_url):
        try:
            return normalize_github_repo_url(task_repo_url, validate_length=False), "override"
        except ValueError:
            return None, "none"
    try:
        inherited = normalize_github_repo_url(solution_repo_url, validate_length=False)
    except ValueError:
        return None, "none"
    return (inherited, "inherited") if inherited else (None, "none")
