from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
ROUTER_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "router.js"
DOM_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "shell" / "dom.js"
GANTT_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "gantt.js"
GANTT_INTERACTIONS_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "gantt" / "interactions.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"
GANTT_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles" / "routes" / "gantt.css"


def test_gantt_route_is_registered_and_rendered():
    index_text = INDEX_HTML.read_text(encoding="utf-8")
    router_text = ROUTER_JS.read_text(encoding="utf-8")
    app_text = APP_JS.read_text(encoding="utf-8")
    dom_text = DOM_JS.read_text(encoding="utf-8")

    assert 'type="button" data-view="gantt" class="nav-btn">Gantt</button>' in index_text
    work_section = index_text[index_text.index("<p class=\"nav-label\">Work</p>"):index_text.index("<p class=\"nav-label\">Insight</p>")]
    insight_section = index_text[index_text.index("<p class=\"nav-label\">Insight</p>"):index_text.index("<div id=\"nav-admin-section\"")]
    assert 'data-view="gantt"' not in work_section
    assert 'data-view="gantt"' in insight_section
    assert 'section id="view-gantt" class="view"' in index_text
    assert "Insight / Gantt" in index_text
    assert "<h2>Project Roadmap</h2>" in index_text
    for element_id in ("gantt-from", "gantt-to", "gantt-expand-all", "gantt-collapse-all", "gantt-chart"):
        assert f'id="{element_id}"' in index_text

    assert '"gantt",' in router_text
    assert 'gantt: ["programs", "projects", "solutions", "tasks"],' in router_text
    assert 'gantt: () => import("../routes/gantt.js")' in router_text
    assert 'gantt: () => renderGantt(),' in app_text
    assert 'from "./routes/gantt/interactions.js";' in app_text
    assert 'restoreGanttViewState();' in app_text
    assert 'ganttRouteController.bindGanttRouteControls();' in app_text
    assert 'ganttChart: document.getElementById("gantt-chart")' in dom_text


def test_gantt_contract_uses_existing_dates_rollups_and_drilldowns():
    app_text = APP_JS.read_text(encoding="utf-8")
    gantt_text = GANTT_JS.read_text(encoding="utf-8")
    interactions_text = GANTT_INTERACTIONS_JS.read_text(encoding="utf-8")

    assert "planned_start_date" in gantt_text
    assert "due_date" in gantt_text
    assert "const LONG_RANGE_DAY_WIDTH = 3.5;" in gantt_text
    assert "const FIT_WINDOW_MAX_DAYS = 366;" in gantt_text
    assert "const GANTT_DUE_SOON_DAYS = 7;" in gantt_text
    assert "export function resolveGanttTimelineScale" in gantt_text
    assert "export function resolveGanttHealth" in gantt_text
    assert 'type: "task"' in gantt_text
    assert "dateRangesOverlap(startDay, endDay, windowStartDay, windowEndDay)" in gantt_text
    assert "buildGanttHealthContext" in gantt_text
    assert "buildProgramNode(program, childNodes, todayDay)" in gantt_text
    assert "buildProjectNode(project, childNodes, healthContext, todayDay)" in gantt_text
    assert "buildSolutionNode(solution, childNodes, windowRange, healthContext, todayDay)" in gantt_text
    assert "hasOverdueChild" in gantt_text
    assert "healthLabel" in gantt_text
    assert "gantt-health-${esc(row.health)}" in gantt_text
    assert "function renderTodayMarker(windowRange, scale)" in gantt_text
    assert "function countRowsByType(rows)" in gantt_text
    assert 'class="gantt-summary-metrics"' in gantt_text
    assert "<strong>${counts.program}</strong> Programs" in gantt_text
    assert "Deliverable" in gantt_text
    assert "Assignee" in gantt_text
    assert "Priority" in gantt_text
    assert 'title="${esc(row.label)}"' in gantt_text
    assert 'class="gantt-level-marker"' in gantt_text
    assert "gantt-assignee-cell" in gantt_text
    assert "gantt-status-cell" in gantt_text
    assert "gantt-priority-cell" in gantt_text
    assert 'row.type === "program" ? "Program"' in gantt_text
    assert 'data-gantt-action="toggle-collapse"' in gantt_text
    assert 'state.ganttCollapsed.add(`program:${program.program_id}`);' in interactions_text
    assert 'state.ganttCollapsed.add(`project:${project.project_id}`);' in interactions_text
    assert 'state.ganttCollapsed.add(`solution:${solution.solution_id}`);' in interactions_text
    assert 'key.startsWith("program:")' in interactions_text
    assert 'state.currentView !== "gantt"' in interactions_text
    assert "requestAnimationFrame" in interactions_text
    assert "openGanttProgramDrilldown" in interactions_text
    assert "openProgramForm(program);" in interactions_text
    assert "openProgramForm," in app_text
    assert 'openSolutionModal(solution, "tasks");' in interactions_text
    assert "fillTaskForm(task);" in interactions_text


def test_gantt_styles_are_route_scoped_and_scrollable():
    styles_text = STYLES_CSS.read_text(encoding="utf-8")
    gantt_css_text = GANTT_CSS.read_text(encoding="utf-8")

    assert '@import "./styles/routes/gantt.css";' in styles_text
    assert "#view-gantt .panel" in gantt_css_text
    assert ".gantt-scroll" in gantt_css_text
    assert ".gantt-summary-metrics" in gantt_css_text
    assert ".gantt-left-header" in gantt_css_text
    assert ".gantt-status-pill" in gantt_css_text
    assert ".gantt-priority-pill" in gantt_css_text
    assert ".gantt-level-marker" in gantt_css_text
    assert ".gantt-today-marker" in gantt_css_text
    assert "overflow: auto;" in gantt_css_text
    assert "--gantt-left-width: 620px;" in gantt_css_text
    assert "z-index: 8;" in gantt_css_text
    assert "-webkit-line-clamp: 2;" in gantt_css_text
    assert "grid-template-columns: var(--gantt-left-width) var(--gantt-track-width);" in gantt_css_text
    assert ".gantt-bar-program" in gantt_css_text
    assert ".gantt-bar-project" in gantt_css_text
    assert ".gantt-row-program .gantt-label-cell" in gantt_css_text
    assert ".gantt-bar-solution" in gantt_css_text
    assert ".gantt-milestone-task" in gantt_css_text
    for health_class in (
        ".gantt-health-green",
        ".gantt-health-yellow",
        ".gantt-health-red",
        ".gantt-health-future",
        ".gantt-health-complete",
        ".gantt-health-abandoned",
    ):
        assert health_class in gantt_css_text
