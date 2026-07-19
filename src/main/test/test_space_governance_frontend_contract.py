from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
ROUTE_REGISTRY_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "route-registry.js"
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
    route_registry_text = ROUTE_REGISTRY_JS.read_text(encoding="utf-8")
    assert 'const SPACE_RECENTS_KEY_PREFIX = "sipm-space-recents-v1";' in app_text
    assert "const { value: stored, recovered } = readStoredJsonState(storageKey, { recent: [] });" in app_text
    assert "const normalizedRecent = recent" in app_text
    assert "if (recovered || JSON.stringify(recent) !== JSON.stringify(normalizedRecent)) {" in app_text
    assert "function viewDomIdForRoute(view)" in router_text
    assert 'return routeDefinition(view).domView;' in router_text
    assert '["access", {' in route_registry_text
    assert 'domView: "spaces",' in route_registry_text
    assert 'navView: "spaces",' in route_registry_text
    assert 'return normalized === "spaces" || normalized === "access";' in router_text
    assert "recordRecentSpace(spaceId)" in app_text
    assert "renderGovernanceHub(preferredSection = \"\")" in render_text
    assert "Issue Password Reset" in render_text
    assert 'data-space-action="issue-password-reset"' in render_text
    assert 'data-space-action="copy-temp-password"' in render_text
    assert 'data-space-action="copy-reset-link"' in render_text
    assert 'from "./routes/spaces/interactions.js' in app_text
    assert 'from "./routes/spaces/render.js' in app_text
    assert 'event.composedPath()' in interactions_text
    assert 'classList.contains("space-member-actions")' in interactions_text
    assert "Workspace atlas" in render_text
    assert "space-directory-table" in render_text
    assert "space-directory-space-cell" in render_text
    assert 'data-space-action="open-directory-space"' in render_text


def test_public_program_dashboard_frontend_contract():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    render_text = (REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "program-dashboard" / "render.js").read_text(encoding="utf-8")
    styles_text = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="public-login-link"' in html_text
    assert 'aria-label="Log in to SIPM"' in html_text
    assert "function publicProgramDashboardSlug" in app_text
    assert 'match(/^\\/public\\/program-dashboard\\/' in app_text
    assert 'credentials: "omit"' in app_text
    assert "bootstrapAuth();" in app_text
    assert "if (publicProgramDashboardSlug())" in app_text
    assert "loadPublicProgramDashboard();" in app_text
    assert "readOnly: true" in app_text
    assert "publicMode: true" in app_text
    assert 'document.getElementById("public-login-link")?.setAttribute("href", buildAppUrl("/"));' in app_text
    assert "const readOnly = !!(ctx.readOnly || ctx.publicMode);" in render_text
    assert 'data-program-dashboard-action="download-pdf"' in render_text
    assert 'data-program-dashboard-action="download-excel"' in render_text
    assert "/public/program-dashboard/" in render_text
    assert 'credentials: isPublicMode ? "omit" : "include"' in render_text
    assert "publicSlug: slug" in app_text
    assert "body.public-program-dashboard-page #topbar-create-shell" in styles_text
    assert "body.public-program-dashboard-page .sidebar" in styles_text
    assert "body.public-program-dashboard-page #app-shell" in styles_text
    assert 'content: "SIPM";' in styles_text
    assert ".public-login-link" in styles_text
    assert "body.public-program-dashboard-page .public-login-link" in styles_text
    assert "border-radius: 999px;" in styles_text
    assert "body.public-program-dashboard-page .program-dashboard-subtitle" in styles_text


def test_space_governance_public_dashboard_toggle_contract():
    interactions_text = SPACES_INTERACTIONS.read_text(encoding="utf-8")
    render_text = SPACES_RENDER.read_text(encoding="utf-8")

    assert 'data-space-action="toggle-public-program-dashboard"' in render_text
    assert "public_program_dashboard_enabled" in render_text
    assert "Public program dashboard" in render_text
    assert 'action === "toggle-public-program-dashboard"' in interactions_text
    assert "public_program_dashboard_enabled: nextEnabled" in interactions_text
    assert "/public/program-dashboard/" in interactions_text


def test_confirm_modal_layers_above_space_directory_modal():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#confirm-modal {" in styles_text
    assert "z-index: 1100;" in styles_text


def test_spaces_and_access_routes_share_the_same_governance_hub():
    spaces_text = SPACES_ROUTE.read_text(encoding="utf-8")
    access_text = ACCESS_ROUTE.read_text(encoding="utf-8")
    assert "renderGovernanceHub();" in spaces_text
    assert 'renderGovernanceHub("current-space")' not in spaces_text
    assert 'renderGovernanceHub("platform-access")' in access_text


def test_space_governance_controls_move_into_route_local_module():
    app_text = APP_JS.read_text(encoding="utf-8")
    interactions_text = SPACES_INTERACTIONS.read_text(encoding="utf-8")
    render_text = SPACES_RENDER.read_text(encoding="utf-8")

    assert 'from "./routes/spaces/interactions.js' in app_text
    assert "const spaceGovernanceController = createSpaceGovernanceController({" in app_text
    assert "function closeSpaceDirectoryModal() {" in interactions_text
    assert "async function refreshGlobalAdmins() {" in interactions_text
    assert "async function refreshSpaceMembers(spaceId, options = {}) {" in interactions_text
    assert "function bindSpaceAdminControls() {" in interactions_text
    assert "function renderGovernanceHub(preferredSection = \"\") {" in render_text
    assert "function renderSpaceDirectoryModal() {" in render_text
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
        ".space-governance-layout",
        ".space-governance-sidebar",
        ".space-governance-tabs",
        ".space-governance-nav-item",
        ".space-governance-main",
        ".space-directory-layout",
        ".space-directory-overview",
        ".space-directory-stat",
        ".space-action-menu",
        ".space-member-actions",
        ".space-directory-table",
        ".space-directory-space-cell",
        ".space-directory-actions",
        ".space-directory-modal-shell",
        ".space-directory-preview-hero",
        ".platform-reset-grid",
        ".platform-access-actions",
        ".platform-tool-tabs",
        ".platform-tool-tab",
        ".platform-tool-surface",
    ]:
        assert selector in css
    assert 'data-space-action="select-platform-tool"' in SPACES_RENDER.read_text(encoding="utf-8")
    assert 'action === "select-platform-tool"' in SPACES_INTERACTIONS.read_text(encoding="utf-8")
