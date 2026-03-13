from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
MASTER_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "master.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_master_route_renders_project_names_as_drilldown_links():
    text = MASTER_ROUTE.read_text(encoding="utf-8")

    assert "const renderProjectNameLink = (label, projectId) => {" in text
    assert "const renderSolutionNameLink = (label, solutionId) => {" in text
    assert 'class="deliverables-name-link deliverables-name-link-project" data-action="edit" data-type="project"' in text
    assert 'class="deliverables-name-link deliverables-name-link-solution" data-action="edit" data-type="solution"' in text
    assert 'renderProjectNameLink(project?.project_name, project?.project_id)' in text
    assert 'renderSolutionNameLink(solution?.solution_name, solution?.solution_id)' in text


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
