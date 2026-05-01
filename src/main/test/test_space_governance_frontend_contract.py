from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
SPACES_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces.js"
SPACES_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces" / "interactions.js"
SPACES_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "spaces" / "render.js"
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
    assert 'id="space-directory-modal"' in html


def test_space_governance_app_logic_tracks_recents_and_access_alias():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = SPACES_INTERACTIONS.read_text(encoding="utf-8")
    render_text = SPACES_RENDER.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")
    assert 'const SPACE_RECENTS_KEY_PREFIX = "sipm-space-recents-v1";' in app_text
    assert "const { value: stored, recovered } = readStoredJsonState(storageKey, { recent: [] });" in app_text
    assert "const normalizedRecent = recent" in app_text
    assert "if (recovered || JSON.stringify(recent) !== JSON.stringify(normalizedRecent)) {" in app_text
    assert "function viewDomIdForRoute(view)" in router_text
    assert 'return normalized === "access" ? "spaces" : normalized;' in router_text
    assert 'if (normalized === "access") return userCanAccessAdminViews();' in router_text
    assert "recordRecentSpace(spaceId)" in app_text
    assert "renderGovernanceHub(preferredSection = \"\")" in app_text
    assert "Issue Password Reset" in render_text
    assert 'data-space-action="issue-password-reset"' in render_text
    assert 'data-space-action="copy-temp-password"' in render_text
    assert 'data-space-action="copy-reset-link"' in render_text
    assert 'from "./routes/spaces/interactions.js";' in app_text
    assert 'from "./routes/spaces/render.js";' in app_text
    assert 'event.composedPath()' in interactions_text
    assert 'classList.contains("space-member-actions")' in interactions_text
    assert "Workspace atlas" in render_text
    assert "space-directory-card-fact" in render_text
    assert 'data-space-action="open-directory-space"' in render_text


def test_spaces_and_access_routes_share_the_same_governance_hub():
    spaces_text = SPACES_ROUTE.read_text(encoding="utf-8")
    access_text = ACCESS_ROUTE.read_text(encoding="utf-8")
    assert 'renderGovernanceHub("current-space")' in spaces_text
    assert 'renderGovernanceHub("platform-access")' in access_text


def test_space_governance_controls_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = SPACES_INTERACTIONS.read_text(encoding="utf-8")
    render_text = SPACES_RENDER.read_text(encoding="utf-8")

    assert 'from "./routes/spaces/interactions.js";' in app_text
    assert "const spaceGovernanceController = createSpaceGovernanceController({" in app_text
    assert "function closeSpaceDirectoryModal() {" in app_text
    assert "return spaceGovernanceController.closeSpaceDirectoryModal();" in app_text
    assert "async function refreshGlobalAdmins() {" in app_text
    assert "return spaceGovernanceController.refreshGlobalAdmins();" in app_text
    assert "async function refreshSpaceMembers(spaceId, options = {}) {" in app_text
    assert "return spaceGovernanceController.refreshSpaceMembers(spaceId, options);" in app_text
    assert "function bindSpaceAdminControls() {" in app_text
    assert "return spaceGovernanceController.bindSpaceAdminControls();" in app_text
    assert "function renderGovernanceHub(preferredSection = \"\") {" in app_text
    assert "return spaceGovernanceRenderer.renderGovernanceHub(preferredSection);" in app_text
    assert "function renderSpaceDirectoryModal() {" in app_text
    assert "return spaceGovernanceRenderer.renderSpaceDirectoryModal();" in app_text
    assert "export function createSpaceGovernanceController({" in interactions_text
    assert "async function handleSpaceGovernanceAction(button) {" in interactions_text
    assert "function bindSpaceAdminControls() {" in interactions_text
    assert 'title: "Issue Password Reset"' in interactions_text
    assert "document._spaceGovernanceEscapeBound = true;" in interactions_text
    assert "export function createSpaceGovernanceRenderer({" in render_text
    assert "function renderPlatformAccessSection() {" in render_text
    assert "function renderDirectorySection() {" in render_text
    assert "function renderCurrentSpaceSection() {" in render_text


def test_space_governance_styles_cover_compact_switcher_and_hub():
    css = read_ui_styles(STYLES_CSS)
    for selector in [
        ".space-switcher-trigger",
        ".space-switcher-trigger-main",
        ".space-switcher-trigger-caret",
        ".space-switcher-panel",
        ".space-governance-shell",
        ".space-governance-tabs",
        ".space-directory-layout",
        ".space-directory-overview",
        ".space-directory-stat",
        ".space-action-menu",
        ".space-member-actions",
        ".space-directory-card-fact",
        ".space-directory-card-note",
        ".space-directory-modal-shell",
        ".space-directory-preview-hero",
        ".platform-reset-grid",
        ".platform-access-actions",
    ]:
        assert selector in css
