from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
PLANNING_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning.js"
PLANNING_STATE = (
    REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "state.js"
)
PLANNING_RENDER = (
    REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "planning" / "render.js"
)
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_planning_header_uses_compact_toggle_panels_instead_of_always_open_stacks():
    state_text = PLANNING_STATE.read_text(encoding="utf-8")
    text = PLANNING_RENDER.read_text(encoding="utf-8")

    assert 'topPanel: ""' in state_text
    assert 'data-wab-action="toggle-filters"' in text
    assert 'data-wab-action="toggle-create"' in text
    assert 'data-wab-action="toggle-guide"' in text
    assert 'data-wab-action="toggle-tools"' in text
    assert 'data-wab-action="reset-filters"' in text
    assert "wab-toolbar-main" in text
    assert "wab-toolbar-meta" in text
    assert "wab-toolbar-panel" in text
    assert "wab-selected-pill" in text
    assert "wab-selection-summary" not in text
    assert "wab-summary-strip" not in text
    assert "wab-legend" not in text


def test_planning_board_uses_unassigned_right_rail_instead_of_virtual_center_column():
    text = PLANNING_RENDER.read_text(encoding="utf-8")

    assert 'class="wab-side-rail wab-backlog"' in text
    assert 'class="wab-side-rail wab-unassigned-rail"' in text
    assert 'data-dropzone="unassigned"' in text
    assert 'class="wab-unassigned-dropzone"' in text
    assert 'data-wab-action="move-person-to-unassigned"' in text
    assert "Unassigned People" in text
    assert (
        "Drop tasks here to unassign them. Drop people here to move them into Unassigned."
        not in text
    )
    assert (
        '<option value="${UNASSIGNED_TEAM_ID}" ${boardState.teamFilter === UNASSIGNED_TEAM_ID ? "selected" : ""}>Unassigned Team</option>'
        not in text
    )
    assert (
        'columns.push({ id: UNASSIGNED_TEAM_ID, name: "Unassigned", virtual: true });'
        not in text
    )


def test_planning_styles_define_compact_toolbar_and_disclosure_panel_layout():
    text = read_ui_styles(STYLES_CSS)
    compact = "".join(text.split())

    snippets = [
        ".wab-toolbar-main {",
        ".wab-toolbar-actions {",
        ".wab-toolbar-toggle {",
        ".wab-toolbar-toggle-count {",
        ".wab-toolbar-panel {",
        ".wab-toolbar-create-grid {",
        ".wab-create-stack {",
        ".wab-create-group-head {",
        ".wab-create-group-label {",
        ".wab-create-form {",
        ".wab-create-divider {",
        ".wab-create-row-team {",
        ".wab-create-row-person {",
        ".wab-create-row-backlog {",
        ".wab-create-action {",
        ".wab-toolbar-guide-grid {",
        ".wab-toolbar-tools-grid {",
        ".wab-toolbar-meta {",
        ".wab-stat-chip,",
        ".wab-selected-pill {",
        ".wab-side-rail {",
        ".wab-unassigned-rail {",
        ".wab-unassigned-dropzone {",
        ".wab-unassigned-rail.is-drop-target .wab-unassigned-dropzone {",
        ".wab-unassigned-list {",
        ".wab-unassigned-person-card {",
        ".wab-unassigned-person-capacity {",
        ".wab-person-head-actions {",
        ".wab-person-unassign {",
    ]
    for snippet in snippets:
        assert snippet in text

    assert (
        "grid-template-columns:minmax(240px,280px)minmax(0,1fr)minmax(220px,260px);"
        in compact
    )


def test_planning_people_and_teams_create_card_uses_grouped_add_team_and_add_person_rows():
    text = PLANNING_RENDER.read_text(encoding="utf-8")

    assert 'class="wab-create-stack wab-create-stack-flat"' in text
    assert 'class="wab-create-group-label">Add Team</span>' in text
    assert 'class="wab-create-group-label">Add Person</span>' in text
    assert 'class="wab-create-divider"' in text
    assert 'class="wab-create-form wab-create-row wab-create-row-team"' in text
    assert 'class="wab-create-form wab-create-row wab-create-row-person"' in text
    assert 'class="wab-create-form wab-create-row wab-create-row-backlog"' in text
    assert 'class="secondary" data-wab-action="add-team"' in text
    assert 'class="secondary" data-wab-action="add-person"' in text


def test_planning_task_detail_uses_modal_shell_instead_of_side_column():
    text = PLANNING_RENDER.read_text(encoding="utf-8")

    assert 'class="wab-modal-shell wab-task-modal-shell"' in text
    assert 'class="wab-modal-backdrop wab-task-modal-backdrop"' in text
    assert 'class="wab-modal-card wab-detail-panel wab-detail-panel-open"' in text
    assert 'data-wab-action="close-task-modal"' in text
    assert 'id="wab-task-modal-title"' in text
    assert 'class="wab-layout${selected ? " has-detail" : ""}"' not in text
