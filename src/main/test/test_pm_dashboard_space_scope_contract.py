from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PM_DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "render.js"
PM_DASHBOARD_STORAGE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "storage.js"


def test_pm_dashboard_shows_current_space_scope():
    text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    assert "Current Space" in text
    assert "PM Command Center only shows active-space data" in text


def test_pm_dashboard_filters_records_to_project_graph():
    text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    assert "const projectIds = new Set" in text
    assert "const solutions = rawSolutions.filter" in text
    assert "const subcomponents = rawSubcomponents.filter" in text
    assert "const allocations = rawAllocations.filter" in text


def test_pm_dashboard_capacity_card_uses_planning_task_assignments_only():
    text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    assert "const planningTaskAllocations = scopedAllocations.filter" in text
    assert 'String(allocation?.work_item_type || "").trim().toLowerCase() === "subcomponent"' in text
    assert "planningTaskAllocations.forEach((allocation) => {" in text
    assert "Source: Planning task assignments only." in text


def test_pm_dashboard_capacity_card_defaults_to_current_month_and_exposes_month_picker():
    storage_text = PM_DASHBOARD_STORAGE.read_text(encoding="utf-8")
    render_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    assert 'const PM_DASHBOARD_STORAGE_KEY_PREFIX = "sipm-pm-dashboard-ui-v1";' in storage_text
    assert "function currentMonthToken() {" in storage_text
    assert "function ensureCapacityMonth(pmDashboardState, spaceId) {" in storage_text
    assert "const restoredMonth = readStoredCapacityMonth(normalizedSpaceId);" in storage_text
    assert "pmDashboardState.capacityMonth = restoredMonth || currentMonthToken();" in storage_text
    assert "if (!restoredMonth) persistCapacityMonth(normalizedSpaceId, pmDashboardState.capacityMonth);" in storage_text
    assert "if (pmDashboardState.capacityMonth !== normalizedMonth) {" in storage_text
    assert "persistCapacityMonth(normalizedSpaceId, normalizedMonth);" in storage_text
    assert "const allocationScopeLabel = selectedCapacityMonth === todayMonthKey" in render_text
    assert "Current month (${selectedCapacityMonth})" in render_text
    assert "Selected month (${selectedCapacityMonth})" in render_text
    assert '<input type="month" value="${esc(selectedCapacityMonth)}" data-pm-dashboard-action="set-capacity-month"' in render_text
