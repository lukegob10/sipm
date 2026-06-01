from __future__ import annotations

import pytest

from backend.app.services.github_repo_urls import (
    normalize_github_repo_url,
    resolve_effective_github_repo_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        (
            "  https://github.com/ExampleOrg/example-repo.git/  ",
            "https://github.com/ExampleOrg/example-repo",
        ),
        (
            "https://github.com/example-org/example-repo",
            "https://github.com/example-org/example-repo",
        ),
    ],
)
def test_normalize_github_repo_url_preserves_existing_contract(raw, expected):
    assert normalize_github_repo_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "http://github.com/example-org/example-repo",
        "https://github.example.com/example-org/example-repo",
        "https://github.com/example-org/example-repo/issues/1",
        "https://github.com/example-org/example-repo?tab=readme",
        "https://github.com/example-org/example-repo#readme",
        "https://github.com/example-org",
    ],
)
def test_normalize_github_repo_url_rejects_non_repo_roots(raw):
    with pytest.raises(ValueError, match="github_repo_url"):
        normalize_github_repo_url(raw)


def test_resolve_effective_github_repo_url_prefers_override_then_inheritance():
    assert resolve_effective_github_repo_url(
        solution_repo_url="https://github.com/example-org/platform",
        subcomponent_repo_url="https://github.com/example-org/frontend",
    ) == ("https://github.com/example-org/frontend", "override")

    assert resolve_effective_github_repo_url(
        solution_repo_url="https://github.com/example-org/platform",
        subcomponent_repo_url=None,
    ) == ("https://github.com/example-org/platform", "inherited")

    assert resolve_effective_github_repo_url(
        solution_repo_url="",
        subcomponent_repo_url=None,
    ) == (None, "none")
