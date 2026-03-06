from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
SPACES_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces.js"
ACCESS_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "access.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_space_shell_uses_one_compact_switcher_surface():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="space-switcher-trigger"' in html
    assert 'id="space-switcher-panel"' in html
    assert 'id="space-switcher-search"' in html
    assert 'class="space-switcher-trigger-main"' in html
    assert 'class="space-switcher-trigger-caret"' in html
    assert 'class="space-switcher-trigger-kicker"' not in html
    assert 'id="space-switcher"' not in html
    assert 'id="space-role-pill"' not in html
    assert 'id="space-scope-bar"' not in html
    assert 'data-view="access"' not in html


def test_space_governance_hub_and_modals_exist_in_html():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="space-governance-shell"' in html
    assert "Space Governance" in html
    assert 'id="space-create-modal"' in html
    assert 'id="space-member-modal"' in html


def test_space_governance_app_logic_tracks_recents_and_access_alias():
    text = APP_JS.read_text(encoding="utf-8")
    assert 'const SPACE_RECENTS_KEY_PREFIX = "sipm-space-recents-v1";' in text
    assert "function viewDomIdForRoute(view)" in text
    assert 'return normalized === "access" ? "spaces" : normalized;' in text
    assert 'if (normalized === "access") return userCanAccessAdminViews();' in text
    assert "recordRecentSpace(spaceId)" in text
    assert "renderGovernanceHub(preferredSection = \"\")" in text


def test_spaces_and_access_routes_share_the_same_governance_hub():
    spaces_text = SPACES_ROUTE.read_text(encoding="utf-8")
    access_text = ACCESS_ROUTE.read_text(encoding="utf-8")
    assert 'renderGovernanceHub("current-space")' in spaces_text
    assert 'renderGovernanceHub("platform-access")' in access_text


def test_space_governance_styles_cover_compact_switcher_and_hub():
    css = STYLES_CSS.read_text(encoding="utf-8")
    for selector in [
        ".space-switcher-trigger",
        ".space-switcher-trigger-main",
        ".space-switcher-trigger-caret",
        ".space-switcher-panel",
        ".space-governance-shell",
        ".space-governance-tabs",
        ".space-directory-layout",
        ".space-action-menu",
    ]:
        assert selector in css
