from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
SHARED_STYLES = (
    REPO_ROOT
    / "src"
    / "main"
    / "ui"
    / "styles"
    / "routes"
    / "workbench-planning-admin.css"
)
SUBCOMPONENTS_STYLES = (
    REPO_ROOT
    / "src"
    / "main"
    / "ui"
    / "styles"
    / "routes"
    / "subcomponents-workbench.css"
)
PLANNING_STYLES = (
    REPO_ROOT
    / "src"
    / "main"
    / "ui"
    / "styles"
    / "routes"
    / "planning-work-allocation.css"
)
TEAM_CAPACITY_STYLES = (
    REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "team-capacity.css"
)
SPACE_GOVERNANCE_STYLES = (
    REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "space-governance.css"
)


def test_styles_entrypoint_imports_route_partials():
    text = STYLES_CSS.read_text(encoding="utf-8")

    for snippet in [
        '@import "./styles/routes/workbench-planning-admin.css";',
        '@import "./styles/routes/subcomponents-workbench.css";',
        '@import "./styles/routes/planning-work-allocation.css";',
        '@import "./styles/routes/team-capacity.css";',
        '@import "./styles/routes/space-governance.css";',
    ]:
        assert snippet in text


def test_subcomponents_workbench_styles_move_into_route_partial():
    route_text = SUBCOMPONENTS_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")

    for snippet in [
        ".sub-workbench-context-link {",
        ".drawer-panel {",
        "#view-subcomponents-workbench .panel {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text


def test_planning_work_allocation_styles_move_into_route_partial_and_drop_stale_shells():
    route_text = PLANNING_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")
    all_styles = read_ui_styles(STYLES_CSS)

    for snippet in [
        "#view-planning .panel {",
        ".wab-toolbar-main {",
        ".wab-shell {",
        ".wab-detail-panel {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text

    for stale_snippet in [
        ".wab-legend {",
        ".wab-selection-summary {",
        ".wab-summary-strip {",
    ]:
        assert stale_snippet not in all_styles


def test_team_capacity_styles_move_into_route_partial():
    route_text = TEAM_CAPACITY_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")

    for snippet in [
        ".planning-kpis {",
        ".capacity-badge {",
        ".stacked {",
        "#view-team-capacity .panel-header {",
        ".theme-light .capacity-badge.ok {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text


def test_space_governance_styles_move_into_route_partial():
    route_text = SPACE_GOVERNANCE_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")

    for snippet in [
        ".inline-form {",
        ".muted-action:disabled {",
        ".space-governance-shell {",
        ".space-directory-overview {",
        ".platform-reset-grid {",
        ".theme-light .space-directory-card.is-selected {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text
