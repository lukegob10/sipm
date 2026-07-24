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
    assert "function renderProgramNameLink(label, programId) {" in text
    assert "function renderSolutionNameLink(label, solutionId) {" in text
    assert 'class="deliverables-name-link deliverables-name-link-program" data-action="edit" data-type="program"' in text
    assert 'class="deliverables-name-link deliverables-name-link-project" data-action="edit" data-type="project"' in text
    assert 'class="deliverables-name-link deliverables-name-link-solution" data-action="edit" data-type="solution"' in text
    assert "renderProjectNameLink(projectLabel, row.project?.project_id)" in text
    assert 'renderSolutionNameLink(solution?.solution_name, solution?.solution_id)' in text


def test_master_route_entry_delegates_to_route_local_table_helper():
    text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert 'import { bindMasterTableInteractions, buildMasterTable } from "./master/table.js";' in text
    assert "const { html, rowCount } = buildMasterTable(ctx);" in text
    assert "bindMasterTableInteractions(ctx);" in text


def test_master_project_name_links_reuse_existing_project_modal_path():
    text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'const actionBtn = event.target.closest("[data-action]");' in text
    assert 'if (action === "edit") {' in text
    assert 'if (type === "program") {' in text
    assert "openProgramForm(program);" in text
    assert '} else if (type === "project") {' in text
    assert "openProjectForm(project);" in text
    assert '} else if (type === "solution") {' in text
    assert 'openSolutionModal(solution, "details");' in text
    assert "openProgramForm," in app_text


def test_master_name_links_use_flat_text_link_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".deliverables-name-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: -webkit-box;" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert ".deliverables-name-link-project {" in text
    assert ".deliverables-name-link-program {" in text
    assert ".deliverables-name-link-solution {" in text
    assert "-webkit-line-clamp: 2;" in text
    assert ".deliverables-name-link:hover," in text


def test_master_deliverables_uses_program_project_solution_outline():
    route_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    master_text = MASTER_ROUTE.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert "<th>Type</th>" not in route_text
    assert 'id="filter-type"' not in route_text
    assert "deliverable-chip-btn" not in route_text
    assert "deliverable-row-program-header" in route_text
    assert "deliverable-row-project-header" in route_text
    assert "deliverable-row-solution" in route_text
    assert "deliverable-program-band" in route_text
    assert "deliverable-project-band" in route_text
    assert "deliverable-outline-main" in route_text
    assert "master-outline-toggle" in route_text
    assert "master-tree-toggle" in route_text
    assert "deliverable-tree-depth-program" in route_text
    assert "deliverable-tree-depth-project" in route_text
    assert "deliverable-tree-depth-solution" in route_text
    assert "deliverable-outline-summary" in route_text
    assert 'const searchActive = String(state.filters?.query || "").trim().length > 0;' in route_text
    assert "programCollapsed = !searchActive && collapsedSet(state).has(key);" in route_text
    assert "projectCollapsed = !searchActive && collapsedSet(state).has(key);" in route_text
    assert "renderMetricPill" not in route_text
    assert "deliverable-outline-meta" not in route_text
    assert 'class="pill' not in route_text
    assert 'data-action="toggle-master-collapse"' in route_text
    assert 'data-master-collapse-key="${esc(key)}"' in route_text
    assert 'id="deliverables-select-all"' not in route_text
    assert 'class="deliverable-select"' not in route_text
    assert "filter-row" not in route_text
    assert "Workstream" not in route_text
    assert "<th>Solution</th>" not in route_text
    assert "<th>Project</th>" not in route_text
    assert "<th>Sponsor</th>" not in route_text
    assert '<td colspan="11">' in route_text
    assert "VALID_DELIVERABLE_TYPES" not in filters_text
    assert "source.type" not in filters_text
    assert "MASTER_QUERY_FIELDS" in filters_text
    assert '"task"' in filters_text
    assert '"deliverable"' in filters_text
    assert "function taskHaystack(ctx, tasks) {" in filters_text
    assert "const tasksBySolutionId = new Map();" in filters_text
    assert "(state.programs || []).forEach((program) => {" in filters_text
    assert "if (!programId || groupedPrograms.has(programId)) return;" in filters_text
    assert "ensureProgramGroup(groupedPrograms, program);" in filters_text
    assert 'id="filter-query"' in master_text
    assert "data-master-query" in master_text
    assert "Search or use field:value" in master_text
    assert 'input.addEventListener("input"' not in master_text
    assert 'input.addEventListener("keydown"' in master_text
    assert 'if (event.key !== "Enter") return;' in master_text
    assert 'data-master-outline-action="expand-all"' in master_text
    assert 'data-master-outline-action="collapse-all"' in master_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-program-header td" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-project-header td" in styles_text
    assert "--deliverable-program-row-bg:" in styles_text
    assert "--deliverable-program-accent:" in styles_text
    assert "--deliverable-project-row-bg:" in styles_text
    assert "--deliverable-project-accent:" in styles_text
    assert "--deliverable-program-kicker-text:" in styles_text
    assert "--deliverable-project-kicker-text:" in styles_text
    assert "--deliverable-solution-row-bg:" in styles_text
    assert "--deliverable-solution-accent: var(--solution-pill-dot);" in styles_text
    assert "--deliverable-program-accent: var(--calendar-task-border);" in styles_text
    assert "var(--product-surface-soft" in styles_text
    assert "--deliverable-project-row-border: var(--project-pill-border);" in styles_text
    assert "--deliverable-project-accent: var(--project-pill-dot);" in styles_text
    assert "border-left-color: var(--deliverable-program-accent);" in styles_text
    assert "border-left-color: var(--deliverable-project-accent);" in styles_text
    assert "border-left: 4px solid var(--deliverable-solution-accent);" in styles_text


def test_master_deliverables_uses_shared_product_route_shell():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert '<section id="view-master" class="view active">' in html_text
    assert '<div class="panel product-route-panel">' in html_text
    assert "#view-master .panel.product-route-panel {" in styles_text
    assert "#view-master #master-table {" in styles_text
    assert "var(--product-table-head" in styles_text
    assert "#view-master #master-table .deliverables-table th {" in styles_text


def test_master_csv_menu_uses_explicit_project_solution_and_task_labels():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")

    for label in [
        "Download Projects CSV",
        "Upload Projects CSV",
        "Download Solutions CSV",
        "Upload Solutions CSV",
        "Download Tasks CSV",
        "Upload Tasks CSV",
    ]:
        assert label in html_text

    csv_menu = html_text.split('id="csv-actions-menu"', 1)[1].split('<input type="file" id="projects-file"', 1)[0]
    assert ">Download</button>" not in csv_menu
    assert ">Upload</button>" not in csv_menu

    assert 'tasksCsvDownload: document.getElementById("tasks-csv-download")' in dom_text
    assert 'tasksCsvUpload: document.getElementById("tasks-csv-upload")' in dom_text
    assert 'taskCsvImportResult: document.getElementById("task-csv-import-result")' in dom_text
    assert 'downloadCsv("tasks", "tasks.csv", els.taskCsvImportResult);' in app_text
    assert 'openCsvUploadModal("tasks");' in app_text


def test_csv_upload_modal_is_configured_for_task_csv_templates():
    app_text = APP_JS.read_text(encoding="utf-8")

    assert 'tasks: {' in app_text
    assert 'label: "Tasks"' in app_text
    assert 'filename: "tasks-template.csv"' in app_text
    assert (
        "project_name,solution_name,version,task_name,description,status,priority,due_date,assignee,"
        "assignee_user_soeid,github_repo_url,estimate_hours,blocked,blocker_note,acceptance_criteria,completed_at"
    ) in app_text
    assert 'els.csvUploadTitle.textContent = `Upload ${config.label} CSV`;' in app_text
    assert 'els.csvUploadDescription.textContent = `Upload a ${config.label} CSV. Use the template if you need the expected columns.`;' in app_text
    assert 'els.csvSubmitUpload.textContent = `Upload ${config.label} CSV`;' in app_text


def test_master_deliverables_table_uses_product_object_shell_texture():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table {" in styles_text
    assert "border: 1px solid var(--product-border, var(--border));" in styles_text
    assert "border-radius: 8px;" in styles_text
    assert "background: var(--data-canvas);" in styles_text
    assert "box-shadow: none;" in styles_text
    assert "#view-master .panel-toolbar.compact {" in styles_text
    assert "#view-master .quickstart-card {" in styles_text


def test_master_deliverables_rows_and_headers_match_modern_object_language():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table .deliverables-table tbody tr:nth-child(even) {" in styles_text
    assert "background: var(--table-row-alt-bg);" in styles_text
    assert "#view-master #master-table .deliverables-table tbody tr:hover," in styles_text
    assert "background: var(--hover);" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-program-header td" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-project-header td" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-program-header:hover td" in styles_text
    assert "#view-master #master-table .deliverables-table tr.deliverable-row-project-header:hover td" in styles_text
    assert "background:\n    linear-gradient(90deg, var(--deliverable-program-row-bg)" in styles_text
    assert "background:\n    linear-gradient(90deg, var(--deliverable-project-row-bg)" in styles_text
    program_header_block = styles_text.split(
        "#view-master #master-table .deliverables-table tr.deliverable-row-program-header td {",
        1,
    )[1].split("}", 1)[0]
    assert "padding-left: 0;" in program_header_block
    assert "padding-right: 0;" in program_header_block
    assert ".deliverable-program-band" in styles_text
    assert ".deliverable-project-band" in styles_text
    assert ".deliverable-outline-title" in styles_text
    outline_title_block = styles_text.split(
        "#view-master #master-table .deliverables-table .deliverable-outline-title {",
        1,
    )[1].split("}", 1)[0]
    assert "display: inline-flex;" in outline_title_block
    assert "align-items: center;" in outline_title_block
    assert "gap: 8px;" in outline_title_block
    assert ".deliverable-outline-kicker" in styles_text
    assert ".deliverable-outline-summary" in styles_text
    outline_main_block = styles_text.split(
        "#view-master #master-table .deliverables-table .deliverable-outline-main {",
        1,
    )[1].split("}", 1)[0]
    assert "flex: 0 1 auto;" in outline_main_block
    outline_summary_block = styles_text.split(
        "#view-master #master-table .deliverables-table .deliverable-outline-summary {",
        1,
    )[1].split("}", 1)[0]
    assert "margin-left: auto;" in outline_summary_block
    assert "text-align: right;" in outline_summary_block
    assert ".master-outline-toggle" in styles_text
    assert ".master-tree-toggle-icon" in styles_text
    assert ".deliverable-program-band .deliverable-outline-kicker" in styles_text
    assert ".deliverable-project-band .deliverable-outline-kicker" in styles_text
    assert "background: var(--deliverable-program-kicker-bg);" in styles_text
    assert "color: var(--deliverable-program-kicker-text);" in styles_text
    assert "background: var(--deliverable-project-kicker-bg);" in styles_text
    assert "color: var(--deliverable-project-kicker-text);" in styles_text
    assert "\n  color: var(--deliverable-program-accent);" not in styles_text
    assert ".deliverable-tree-cell::before" in styles_text
    assert ".deliverable-tree-depth-project" in styles_text
    assert ".deliverable-tree-depth-solution" in styles_text
    assert "--deliverable-tree-indent: 34px;" in styles_text
    assert "--deliverable-tree-control-offset: 34px;" in styles_text
    assert "padding-left: var(--deliverable-tree-indent);" in styles_text
    assert "padding-left: calc((var(--deliverable-tree-indent) * 2) + var(--deliverable-tree-control-offset));" in styles_text
    assert "font-weight: 700;" in styles_text
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

    assert "function phaseLabel(ctx, solution) {" in filters_text
    assert "ctx.phaseDisplayName" in filters_text
    assert "solution?.current_phase" in filters_text
    assert "phaseLabel(ctx, solution)" in filters_text
    assert 'case "phase":' in filters_text
    assert 'case "current_phase":' in filters_text
    assert "lower(solution.current_phase).includes(lower(f.current_phase))" not in filters_text

    assert 'import { ragTone, statusTone } from "../../utils/display-tokens.js";' in table_text
    assert "ragTone(ragValue)" in table_text
    assert "statusTone(statusState)" in table_text
    assert 'class="inline-select status-select' in table_text
    assert "data-status-state=" in table_text
    assert "data-rag-state=" in table_text

    assert ".status-select[data-status-state=\"active\"]," in styles_text
    assert ".rag-select[data-rag-state=\"green\"] {" in styles_text
    assert "#view-master #master-table .deliverables-table .rag-select[data-rag-state=\"green\"] {" in styles_text
    assert "#view-master #master-table .deliverables-table .rag-select[data-rag-state=\"amber\"] {" in styles_text
    assert "#view-master #master-table .deliverables-table .rag-select[data-rag-state=\"red\"] {" in styles_text
    assert "color: var(--rag-green-text);" in styles_text
    assert "color: var(--rag-amber-text);" in styles_text
    assert "color: var(--rag-red-text);" in styles_text
    assert "#master-table .deliverables-table .rag-select option {" in styles_text
    assert "background-color: var(--field-bg);" in styles_text
    assert 'option[value="green"] {' in styles_text
    assert "background-color: var(--rag-green-option-bg);" in styles_text
    assert 'option[value="amber"] {' in styles_text
    assert "background-color: var(--rag-amber-option-bg);" in styles_text
    assert 'option[value="red"] {' in styles_text
    assert "background-color: var(--rag-red-option-bg);" in styles_text
    assert ".theme-light #master-table .deliverables-table .rag-select option {" in styles_text


def test_master_deliverables_project_solution_titles_use_dense_wrapping():
    styles_text = read_ui_styles(STYLES_CSS)

    assert "#view-master #master-table .deliverables-table .deliverables-name-link {" in styles_text
    assert "display: -webkit-box;" in styles_text
    assert "-webkit-line-clamp: 2;" in styles_text
    assert "#view-master #master-table .deliverables-table .deliverables-name-link-project {" in styles_text
    assert "font-weight: 600;" in styles_text
    assert "#view-master #master-table .deliverables-table .deliverables-name-link-program {" in styles_text
    assert "font-weight: 500;" in styles_text
    assert ".deliverable-outline-name-program .deliverables-name-link-program" in styles_text
    assert "font-weight: 800;" in styles_text
    assert "#view-master #master-table .deliverables-table .deliverables-name-link-solution {" in styles_text
    assert "font-weight: 500;" in styles_text
    assert "color: var(--accent-strong);" in styles_text
    assert "#view-master #master-table .deliverables-table th:nth-child(1)," in styles_text
    assert "#view-master #master-table .deliverables-table td:nth-child(1) {" in styles_text
    assert "text-align: left !important;" in styles_text
    assert "#view-master #master-table .deliverables-table td:nth-child(1) .deliverables-name-link-solution {" in styles_text
    assert "width: 100%;" in styles_text
    assert "justify-content: flex-start;" in styles_text


def test_master_table_keeps_broad_deliverables_columns_without_repo_mode():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")
    filters_text = MASTER_ROUTE_FILTERS.read_text(encoding="utf-8")
    interactions_text = MASTER_ROUTE_INTERACTIONS.read_text(encoding="utf-8")
    route_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    styles_text = read_ui_styles(STYLES_CSS)

    assert 'id="preset-engineering"' not in html_text
    assert 'id="preset-my"' not in html_text
    assert "deliverables-prototype-switcher" not in html_text
    assert "deliverables-bulk-toolbar" not in html_text
    assert "presetEngineering" not in dom_text
    assert "VALID_DELIVERABLE_PRESETS" not in filters_text
    assert "engineering" not in filters_text
    assert "presetEngineering" not in interactions_text
    assert "<th>Version</th>" in route_text
    assert "<th>Solution</th>" not in route_text
    assert "<th>Project</th>" not in route_text
    assert "<th>Sponsor</th>" not in route_text
    assert "<th>Repo</th>" not in route_text
    assert 'id="filter-repo-presence"' not in route_text
    assert '<th>Type</th>' not in route_text
    assert 'id="filter-type"' not in route_text
    assert 'value="project"' not in route_text
    assert 'value="solution"' not in route_text
    assert "deliverable-repo" not in styles_text
    assert "deliverables-table-engineering" not in styles_text
