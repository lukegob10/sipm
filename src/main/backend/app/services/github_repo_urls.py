from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

from ..utils import normalize_str


def normalize_github_repo_url(value: Optional[str]) -> Optional[str]:
    raw = normalize_str(value)
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("github_repo_url must use https")
    if parsed.netloc.lower() != "github.com":
        raise ValueError("github_repo_url must point to github.com")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("github_repo_url must be a clean GitHub repository URL")

    path = (parsed.path or "").strip().rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [segment for segment in path.split("/") if segment]
    if len(parts) != 2:
        raise ValueError("github_repo_url must point to a GitHub repository root")

    owner, repo = parts
    if not owner or not repo:
        raise ValueError("github_repo_url must point to a GitHub repository root")

    return f"https://github.com/{owner}/{repo}"


def resolve_effective_github_repo_url(
    *,
    solution_repo_url: Optional[str],
    subcomponent_repo_url: Optional[str],
) -> Tuple[Optional[str], str]:
    override = (
        normalize_github_repo_url(subcomponent_repo_url)
        if subcomponent_repo_url
        else None
    )
    if override:
        return override, "override"

    inherited = (
        normalize_github_repo_url(solution_repo_url) if solution_repo_url else None
    )
    if inherited:
        return inherited, "inherited"

    return None, "none"
