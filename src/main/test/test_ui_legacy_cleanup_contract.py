from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "main" / "ui" / "index.html"


def test_removed_legacy_function_defs_are_not_present():
    text = APP_JS.read_text(encoding="utf-8")
    removed = [
        "function tableFrom(",
        "function bindProjectListClicks(",
        "function bindSolutionListClicks(",
        "function bindSubcomponentListClicks(",
        "function bindTeamSettings(",
        "function renderPriorityLane(",
        "function renderCapacityPanel(",
        "function renderReportingPanel(",
        "function renderProjects(",
        "function renderSolutions(",
        "function renderSubcomponents(",
    ]
    for marker in removed:
        assert marker not in text


def test_stale_legacy_els_references_are_not_present():
    text = APP_JS.read_text(encoding="utf-8")
    removed_refs = [
        "els.projectList",
        "els.solutionList",
        "els.subcomponentList",
        "els.subcomponentsDownload",
        "els.subcomponentsUpload",
        "els.subcomponentsFile",
        "els.subcomponentsImportResult",
        "els.priorityLanePanel",
        "els.capacityPanel",
        "els.reportingPanel",
    ]
    for marker in removed_refs:
        assert marker not in text


def test_legacy_list_view_mount_points_not_present_in_html():
    text = INDEX_HTML.read_text(encoding="utf-8")
    removed_ids = [
        'id="project-list"',
        'id="solution-list"',
        'id="subcomponent-list"',
    ]
    for marker in removed_ids:
        assert marker not in text
