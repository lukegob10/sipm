from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
MASTER_ROUTE_TABLE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "table.js"
MASTER_ROUTE_FILTERS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "filters.js"
MASTER_ROUTE_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "interactions.js"
DISPLAY_TOKENS = REPO_ROOT / "src" / "main" / "ui" / "js" / "utils" / "display-tokens.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_master_route_renders_project_names_as_drilldown_links():
    text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")

    assert "function renderProjectNameLink(label, projectId) {" in text
    assert "function renderSolutionNameLink(label, solutionId) {" in text
    assert 'class="deliverables-name-link deliverables-name-link-project" data-action="edit" data-type="project"' in text
    assert 'class="deliverables-name-link deliverables-name-link-solution" data-action="edit" data-type="solution"' in text
    assert 'renderProjectNameLink(project?.project_name, project?.project_id)' in text
    assert 'renderSolutionNameLink(solution?.solution_name, solution?.solution_id)' in text


def test_master_route_entry_delegates_to_route_local_table_helper():
    text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert 'import { bindMasterTableInteractions, buildMasterTable } from "./master/table.js";' in text
    assert "const { html, rowCount } = buildMasterTable(ctx);" in text
    assert "bindMasterTableInteractions(ctx, {" in text


def test_master_project_name_links_reuse_existing_project_modal_path():
    text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")

    assert 'const actionBtn = event.target.closest("[data-action]");' in text
    assert 'if (action === "edit") {' in text
    assert 'if (type === "project") {' in text
    assert "openProjectForm(project);" in text
    assert '} else if (type === "solution") {' in text
    assert 'openSolutionModal(solution, "details");' in text


def test_master_name_links_use_flat_text_link_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".deliverables-name-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline-block;" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert ".deliverables-name-link-project {" in text
    assert ".deliverables-name-link-solution {" in text
    assert "content: none;" in text
    assert ".deliverables-name-link:hover {" in text
    assert "text-decoration: underline;" in text


def test_master_type_chip_uses_colored_chip_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".deliverable-chip-btn {" in text
    assert "cursor: pointer;" in text
    assert ".deliverable-chip-btn .pill {" in text
    assert "box-shadow: none;" in text
    assert ".deliverable-chip-btn:hover .pill {" in text
    assert "filter: brightness(1.03);" in text
    assert ".pill-project {" in text
    assert "background: var(--project-pill-bg);" in text
    assert ".pill-solution {" in text
    assert "background: var(--solution-pill-bg);" in text


def test_master_deliverables_uses_shared_product_route_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert '<section id="view-master" class="view active">' in html_text
    assert '<div class="panel product-route-panel">' in html_text
    assert "#view-master .panel.product-route-panel {" in styles_text
    assert "#view-master #master-table {" in styles_text
    assert "var(--product-table-head" in styles_text
    assert "#view-master #master-table .deliverables-table th {" in styles_text


def test_master_deliverables_table_uses_product_object_shell_texture():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table {" in styles_text
    assert "border: 1px solid var(--product-border, var(--border));" in styles_text
    assert "border-radius: 8px;" in styles_text
    assert "linear-gradient(180deg, color-mix(in srgb, var(--panel-soft) 78%, transparent), color-mix(in srgb, var(--panel) 86%, transparent));" in styles_text
    assert "box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);" in styles_text
    assert "#view-master .panel-toolbar.compact {" in styles_text
    assert "#view-master .quickstart-card {" in styles_text


def test_master_deliverables_rows_and_chips_match_modern_object_language():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table .deliverables-table tbody tr:nth-child(even) {" in styles_text
    assert "background: color-mix(in srgb, var(--panel-soft) 84%, transparent);" in styles_text
    assert "#view-master #master-table .deliverables-table tbody tr:hover," in styles_text
    assert "background: var(--hover);" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-project," in styles_text
    assert "background: color-mix(in srgb, var(--panel-soft) 92%, var(--project-pill-bg));" in styles_text
    assert "font-weight: 500;" in styles_text
    assert "#view-master #master-table .deliverables-table .pill {" in styles_text
    assert "border-radius: 5px;" in styles_text
    assert "background: var(--tone-positive-bg);" in styles_text
    assert "background: var(--tone-warn-bg);" in styles_text
    assert "background: var(--tone-danger-bg);" in styles_text


def test_master_deliverables_use_shared_display_tokens_for_status_rag_and_phase_labels():
    app_text = APP_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    table_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    token_text = DISPLAY_TOKENS.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert "export function formatStatusLabel" in token_text
    assert "export function statusTone" in token_text
    assert "export function ragTone" in token_text
    assert 'status === "in_progress"' in token_text
    assert 'rag === "green"' in token_text
    assert 'import { formatStatusLabel } from "./utils/display-tokens.js";' in app_text
    assert "return formatStatusLabel(status, \"—\");" in app_text

    assert "phaseDisplayName(solution.current_phase)" in filters_text
    assert "lower(phaseLabel).includes(lower(f.current_phase))" in filters_text
    assert "lower(solution.current_phase).includes(lower(f.current_phase))" not in filters_text

    assert 'import { ragTone, statusTone } from "../../utils/display-tokens.js";' in table_text
    assert "ragTone(ragValue)" in table_text
    assert "statusTone(statusState)" in table_text
    assert 'class="inline-select status-select' in table_text
    assert "data-status-state=" in table_text
    assert "data-rag-state=" in table_text

    assert ".status-select[data-status-state=\"active\"]," in styles_text
    assert ".rag-select[data-rag-state=\"green\"] {" in styles_text


def test_master_deliverables_project_solution_titles_use_dense_wrapping():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table .deliverables-table .deliverables-name-link {" in styles_text
    assert "display: -webkit-box;" in styles_text
    assert "-webkit-line-clamp: 2;" in styles_text
    assert "#view-master #master-table .deliverables-table .deliverables-name-link-project {" in styles_text
    assert "font-weight: 600;" in styles_text
    assert "#view-master #master-table .deliverables-table .deliverables-name-link-solution {" in styles_text
    assert "font-weight: 500;" in styles_text
    assert "color: var(--accent-strong);" in styles_text


def test_master_table_keeps_broad_deliverables_columns_without_repo_mode():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    interactions_text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")
    route_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="preset-engineering"' not in html_text
    assert "presetEngineering" not in dom_text
    assert 'export const VALID_DELIVERABLE_PRESETS = new Set(["", "my", "overdue", "blocked"]);' in filters_text
    assert "engineering" not in filters_text
    assert "presetEngineering" not in interactions_text
    assert "<th>Version</th>" in route_text
    assert "<th>Repo</th>" not in route_text
    assert 'id="filter-repo-presence"' not in route_text
    assert 'value="project"' in route_text
    assert 'value="solution"' in route_text
    assert "deliverable-repo" not in styles_text
    assert "deliverables-table-engineering" not in styles_text
