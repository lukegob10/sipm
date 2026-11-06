import pytest

from backend.app.paths import normalize_context_path


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, ""), ("", ""), ("/", ""), ("///", ""), ("/project-manager/", "/project-manager")],
)
def test_context_path_normalizes_root_and_trailing_slashes(value, expected):
    assert normalize_context_path(value) == expected
