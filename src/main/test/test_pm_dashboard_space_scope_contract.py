from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"


def test_pm_dashboard_shows_current_space_scope():
    text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert "Current Space" in text
    assert "PM Command Center only shows active-space data" in text


def test_pm_dashboard_filters_records_to_project_graph():
    text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert "const projectIds = new Set" in text
    assert "const solutions = rawSolutions.filter" in text
    assert "const subcomponents = rawSubcomponents.filter" in text
    assert "const allocations = rawAllocations.filter" in text
