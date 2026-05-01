from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_modal_shell_constrains_layout_and_scroll():
    text = read_ui_styles(STYLES_CSS)
    assert ".modal-content {" in text
    assert "--modal-shell-padding: 16px;" in text
    assert "max-width: calc(100vw - 32px);" in text
    assert "max-height: min(88dvh, 980px);" in text
    assert "min-width: 0;" in text
    assert ".modal-body {" in text
    assert ".modal-header-sticky {" in text
    assert ".modal-sticky-chrome {" in text
    assert "top: calc(var(--modal-shell-padding) * -1);" in text
    assert ".modal-tabs {" in text
    assert "margin: 0;" in text
    assert "padding: 0 var(--modal-shell-padding) 8px;" in text
    assert "border-bottom: 1px solid var(--border);" in text


def test_form_controls_are_box_sized_and_textareas_resize_vertically_only():
    text = read_ui_styles(STYLES_CSS)
    assert ".form input," in text
    assert "box-sizing: border-box;" in text
    assert "max-width: 100%;" in text
    assert "resize: vertical;" in text


def test_auth_and_mobile_modal_surfaces_have_height_guards():
    text = read_ui_styles(STYLES_CSS)
    assert ".auth-card {" in text
    assert "max-height: calc(100dvh - 32px);" in text
    assert "@media (max-width: 820px)" in text
    assert "max-height: calc(100dvh - 10px);" in text
