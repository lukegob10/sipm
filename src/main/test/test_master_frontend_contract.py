from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
MASTER_ROUTE_TABLE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master" / "table.js"
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
    text = APP_JS.read_text(encoding="utf-8")

    assert 'const actionBtn = e.target.closest("[data-action]");' in text
    assert 'if (action === "edit") {' in text
    assert 'if (type === "project") {' in text
    assert "openProjectForm(proj);" in text
    assert '} else if (type === "solution") {' in text
    assert 'openSolutionModal(sol, "details");' in text


def test_master_name_links_use_flat_text_link_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

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
    text = STYLES_CSS.read_text(encoding="utf-8")

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


def test_master_engineering_preset_adds_repo_visibility_and_missing_repo_filter():
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    route_text = MASTER_ROUTE_TABLE.read_text(encoding="utf-8")
    styles_text = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="preset-engineering"' in html_text
    assert 'presetEngineering: document.getElementById("preset-engineering")' in app_text
    assert 'const VALID_DELIVERABLE_PRESETS = new Set(["", "my", "overdue", "blocked", "engineering"]);' in app_text
    assert 'const VALID_DELIVERABLE_REPO_PRESENCE = new Set(["", "has_repo", "missing_repo"]);' in app_text
    assert 'els.presetEngineering?.addEventListener("click", () => setDeliverablesPreset("engineering"));' in app_text
    assert "const isEngineeringPreset = (state.deliverablesPreset || \"\") === \"engineering\";" in route_text
    assert 'id="filter-repo-presence"' in route_text
    assert 'Missing Repo' in route_text
    assert 'class="deliverables-repo-link"' in route_text
    assert 'deliverables-table-engineering' in route_text
    assert ".deliverables-repo-link," in styles_text
    assert ".deliverables-repo-missing {" in styles_text
