from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
TOPBAR_CREATE_JS = (
    REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "topbar-create.js"
)


def test_topbar_create_controller_exports_close_helper_used_by_csv_menu():
    topbar_text = TOPBAR_CREATE_JS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert "closeTopbarCreateMenu," in topbar_text
    assert "closeTopbarCreateMenu({ restoreFocus: false });" in app_text
