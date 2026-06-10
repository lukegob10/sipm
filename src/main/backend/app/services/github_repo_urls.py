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


def normalize_github_repo_url(value: str | None) -> str | None:
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
    return f"https://{GITHUB_HOST}/{owner}/{repo}"


def resolve_effective_github_repo_url(
    *,
    solution_repo_url: str | None,
    task_repo_url: str | None,
) -> tuple[str | None, RepoSource]:
    override = normalize_github_repo_url(task_repo_url)
    if override:
        return override, "override"

    inherited = normalize_github_repo_url(solution_repo_url)
    if inherited:
        return inherited, "inherited"

    return None, "none"
