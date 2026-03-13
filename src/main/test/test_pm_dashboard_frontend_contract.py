from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_pm_dashboard_route_renders_title_drilldowns_for_project_risk_timeline_and_capacity_rows():
    text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert "function normalizePMDashboardIdentity(value) {" in text
    assert "function buildPMDashboardOwnerDirectory(users) {" in text
    assert "function resolvePMDashboardOwnerAssigneeKey(soeidValue, labelValue, ownerDirectory) {" in text
    assert "function renderPMDashboardOwnerLink(label, assigneeKey) {" in text
    assert 'function renderPMDashboardProjectLink(label, projectId)' in text
    assert 'function renderPMDashboardSolutionLink(label, solutionId)' in text
    assert 'function renderPMDashboardTimelineLink(row)' in text
    assert 'function renderPMDashboardCapacityLink(row)' in text
    assert 'return ownerDirectory?.uniqueDisplayNameToKey?.get(labelToken) || "";' in text
    assert 'if (!resolvedKey || resolvedKey === "unassigned") return esc(ownerLabel);' in text
    assert 'renderPMDashboardRowLink(ownerLabel, "open-capacity-allocations"' in text
    assert 'renderPMDashboardRowLink(label, "open-project"' in text
    assert 'renderPMDashboardRowLink(label, "open-solution"' in text
    assert 'renderPMDashboardRowLink(row.name, "open-subcomponent"' in text
    assert 'renderPMDashboardRowLink(row.label, "open-capacity-allocations"' in text
    assert "renderPMDashboardProjectLink(summary.projectName, summary.projectId)" in text
    assert "renderPMDashboardSolutionLink(row.solutionName, row.solutionId)" in text
    assert "renderPMDashboardTimelineLink(row)" in text
    assert "renderPMDashboardCapacityLink(row)" in text
    assert "renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)" in text
    assert "const ownerDirectory = buildPMDashboardOwnerDirectory(users);" in text
    assert 'if (!assigneeKey || assigneeKey === "unassigned") return `<strong>${esc(label)}</strong>`;' in text
    assert "projectId: project.project_id" in text
    assert 'itemKind: "solution"' in text
    assert 'itemKind: "subcomponent"' in text
    assert "solutionId: solution.solution_id" in text
    assert "subcomponentId: subcomponent.subcomponent_id" in text
    assert "ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(solution.owner_user_soeid, solution.owner, ownerDirectory)," in text
    assert 'ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(' in text
    assert "allocations: rowAllocations" in text
    assert "pmDashboardState.capacityDrilldowns = new Map(capacityRows.map((row) => [row.key, row]));" in text


def test_pm_dashboard_route_handles_project_solution_task_and_capacity_drilldown_actions():
    text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    assert 'const pmDashboardState = {' in text
    assert 'document.getElementById("view-pm-dashboard")' in text
    assert 'const actionEl = event.target.closest("[data-pm-dashboard-action]")' in text
    assert 'if (action === "open-project") {' in text
    assert 'pmDashboardState.ctx?.openPMDashboardProjectDrilldown' in text
    assert 'if (action === "open-solution") {' in text
    assert 'pmDashboardState.ctx?.openPMDashboardSolutionDrilldown' in text
    assert 'if (action === "open-subcomponent") {' in text
    assert 'pmDashboardState.ctx?.openPMDashboardSubcomponentDrilldown' in text
    assert 'if (action === "open-capacity-allocations") {' in text
    assert 'const detail = pmDashboardState.capacityDrilldowns.get(assigneeKey);' in text
    assert 'pmDashboardState.ctx?.openPMDashboardCapacityDrilldown' in text
    assert 'if (action !== "set-capacity-month") return;' in text
    assert 'persistCapacityMonth(pmDashboardState.capacitySpaceId, nextMonth);' in text
    assert 'renderPMDashboard(pmDashboardState.ctx);' in text
    assert "pmDashboardState.ctx = ctx;" in text


def test_pm_dashboard_drilldown_helpers_reuse_existing_project_solution_task_and_capacity_surfaces():
    text = APP_JS.read_text(encoding="utf-8")
    assert "function closePlanningModal()" in text
    assert "function openPlanningModal(title, bodyHtml)" in text
    assert "function openPMDashboardProjectDrilldown(projectId)" in text
    assert "function openPMDashboardCapacityDrilldown(detail)" in text
    assert "function openPMDashboardSolutionDrilldown(solutionId)" in text
    assert "function openPMDashboardSubcomponentDrilldown(subcomponentId)" in text
    assert "function openAllocationWorkItemDrilldown(allocationId)" in text
    assert 'openPMDashboardCapacityDrilldown,' in text
    assert 'openPMDashboardProjectDrilldown,' in text
    assert 'openPMDashboardSolutionDrilldown,' in text
    assert 'openPMDashboardSubcomponentDrilldown,' in text
    assert 'data-planning-modal-action="open-allocation-work-item"' in text
    assert 'openPlanningModal(`${assigneeLabel} Allocation Detail`, bodyHtml);' in text
    assert "No allocations in this scope." in text
    assert "openProjectForm(project)" in text
    assert 'openSolutionModal(solution, "details")' in text
    assert 'openSolutionModal(solution, "subcomponents")' in text
    assert "fillSubcomponentForm(subcomponent)" in text


def test_pm_dashboard_uses_pm_row_link_style_for_dense_title_actions():
    text = STYLES_CSS.read_text(encoding="utf-8")
    assert ".pm-row-link {" in text
    assert "appearance: none;" in text
    assert "box-shadow: none;" in text
    assert "display: inline;" in text
    assert "vertical-align: baseline;" in text
    assert ".pm-row-link:hover {" in text
    assert "text-underline-offset: 0.12em;" in text
    assert ".pm-row-link:focus-visible {" in text
    assert ".pm-card-controls {" in text
    assert ".pm-scope-control {" in text


def test_pm_dashboard_immediate_action_links_use_text_first_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".pm-action-link {" in text
    assert "color: inherit;" in text
    assert "text-underline-offset: 0.12em;" in text
    assert ".pm-action-link:hover {" in text
    assert "color: var(--accent-strong);" in text


def test_pm_dashboard_quick_links_use_text_first_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".pm-quick-links a {" in text
    assert "color: inherit;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "padding: 0;" in text
    assert ".pm-quick-links a:hover {" in text
    assert "text-decoration: underline;" in text


def test_pm_dashboard_action_rows_use_lighter_container_chrome():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".pm-action-row {" in text
    assert "background: transparent;" in text


def test_pm_dashboard_signal_tokens_use_quieter_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".pm-signal {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "background: transparent;" in text


def test_pm_dashboard_item_kind_tokens_use_quieter_styling():
    text = STYLES_CSS.read_text(encoding="utf-8")

    assert ".pm-item-kind {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "background: transparent;" in text
