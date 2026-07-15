from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
SHARED_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "workbench-admin.css"
TASKS_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "tasks-workbench.css"
TEAM_CAPACITY_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "team-capacity.css"
SPACE_GOVERNANCE_STYLES = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "space-governance.css"


def test_styles_entrypoint_imports_route_partials():
    text = STYLES_CSS.read_text(encoding="utf-8")

    for snippet in [
        '@import "./styles/routes/workbench-admin.css";',
        '@import "./styles/routes/tasks-workbench.css";',
        '@import "./styles/routes/team-capacity.css";',
        '@import "./styles/routes/space-governance.css";',
    ]:
        assert snippet in text


def test_tasks_workbench_styles_move_into_route_partial():
    route_text = TASKS_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")

    for snippet in [
        ".task-workbench-context-link {",
        ".task-workbench-editor-content {",
        "#view-tasks-workbench > .panel {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text


def test_team_capacity_styles_move_into_route_partial():
    route_text = TEAM_CAPACITY_STYLES.read_text(encoding="utf-8")
    shared_text = SHARED_STYLES.read_text(encoding="utf-8")

    for snippet in [
        ".capacity-kpis {",
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
        ".theme-light .space-directory-row.is-selected td {",
    ]:
        assert snippet in route_text
        assert snippet not in shared_text
