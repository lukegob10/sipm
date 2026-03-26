from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_view_titles_use_shared_heading_tokens():
    text = read_ui_styles(STYLES_CSS)
    assert "--view-title-font-size:" in text
    assert "--view-title-mobile-size:" in text
    assert ".panel-header h2 {" in text
    assert "font-size: var(--view-title-font-size);" in text
    assert "line-height: var(--view-title-line-height);" in text
    assert "letter-spacing: var(--view-title-letter-spacing);" in text
    assert "font-weight: var(--view-title-weight);" in text


def test_mobile_view_titles_use_one_shared_size():
    text = read_ui_styles(STYLES_CSS)
    assert "@media (max-width: 1024px)" in text
    assert "font-size: var(--view-title-mobile-size);" in text


def test_insight_view_breadcrumbs_are_not_hidden():
    text = read_ui_styles(STYLES_CSS)
    assert "#view-dashboard .view-breadcrumb" not in text
    assert "#view-pm-dashboard .view-breadcrumb" not in text
