from pathlib import Path

from ui_style_contract import read_ui_styles


REPO_ROOT = Path(__file__).resolve().parents[3]
APP_JS = REPO_ROOT / "src" / "main" / "ui" / "js" / "app.js"
PM_DASHBOARD_ROUTE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard.js"
PM_DASHBOARD_ANALYTICS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "analytics.js"
PM_DASHBOARD_STORAGE = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "storage.js"
PM_DASHBOARD_INTERACTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "interactions.js"
PM_DASHBOARD_RENDER = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "render.js"
PM_DASHBOARD_SECTIONS = REPO_ROOT / "src" / "main" / "ui" / "js" / "routes" / "pm-dashboard" / "sections.js"
STYLES_CSS = REPO_ROOT / "src" / "main" / "ui" / "styles.css"


def test_pm_dashboard_route_renders_title_drilldowns_for_project_risk_timeline_and_capacity_rows():
    route_text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    analytics_text = PM_DASHBOARD_ANALYTICS.read_text(encoding="utf-8")
    render_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    sections_text = PM_DASHBOARD_SECTIONS.read_text(encoding="utf-8")

    assert 'import { createPMDashboardState, renderPMDashboardView } from "./pm-dashboard/render.js";' in route_text
    assert "function normalizePMDashboardIdentity(value) {" in analytics_text
    assert "function buildPMDashboardOwnerDirectory(users) {" in analytics_text
    assert "function resolvePMDashboardOwnerAssigneeKey(soeidValue, labelValue, ownerDirectory) {" in analytics_text
    assert "function renderPMDashboardOwnerLink(label, assigneeKey) {" in analytics_text
    assert "function renderPMDashboardProjectLink(label, projectId) {" in analytics_text
    assert "function renderPMDashboardSolutionLink(label, solutionId) {" in analytics_text
    assert "function renderPMDashboardTimelineLink(row) {" in analytics_text
    assert "function renderPMDashboardCapacityLink(row) {" in analytics_text
    assert 'return ownerDirectory?.uniqueDisplayNameToKey?.get(labelToken) || "";' in analytics_text
    assert 'if (!resolvedKey || resolvedKey === "unassigned") return esc(ownerLabel);' in analytics_text
    assert 'renderPMDashboardRowLink(ownerLabel, "open-capacity-allocations"' in analytics_text
    assert 'renderPMDashboardRowLink(label, "open-project"' in analytics_text
    assert 'renderPMDashboardRowLink(label, "open-solution"' in analytics_text
    assert 'renderPMDashboardRowLink(row.name, "open-subcomponent"' in analytics_text
    assert 'renderPMDashboardRowLink(row.label, "open-capacity-allocations"' in analytics_text
    assert 'from "./sections.js";' in render_text
    assert "renderPMDashboardProjectLink(summary.projectName, summary.projectId)" in sections_text
    assert "renderPMDashboardSolutionLink(row.solutionName, row.solutionId)" in sections_text
    assert "renderPMDashboardTimelineLink(row)" in sections_text
    assert "renderPMDashboardCapacityLink(row)" in sections_text
    assert "renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)" in sections_text
    assert "const ownerDirectory = buildPMDashboardOwnerDirectory(users);" in render_text
    assert 'if (!assigneeKey || assigneeKey === "unassigned") return `<strong>${esc(label)}</strong>`;' in analytics_text
    assert "projectId: project.project_id" in render_text
    assert 'itemKind: "solution"' in render_text
    assert 'itemKind: "subcomponent"' in render_text
    assert "solutionId: solution.solution_id" in render_text
    assert "subcomponentId: subcomponent.subcomponent_id" in render_text
    assert "ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(solution.owner_user_soeid, solution.owner, ownerDirectory)," in render_text
    assert "ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(" in render_text
    assert "allocations: rowAllocations" in render_text
    assert "pmDashboardState.capacityDrilldowns = new Map(capacityRows.map((row) => [row.key, row]));" in render_text


def test_pm_dashboard_route_handles_project_solution_task_and_capacity_drilldown_actions():
    route_text = PM_DASHBOARD_ROUTE.read_text(encoding="utf-8")
    interactions_text = PM_DASHBOARD_INTERACTIONS.read_text(encoding="utf-8")
    render_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    storage_text = PM_DASHBOARD_STORAGE.read_text(encoding="utf-8")

    assert "const pmDashboardState = createPMDashboardState();" in route_text
    assert 'document.getElementById("view-pm-dashboard")' in interactions_text
    assert 'const actionEl = event.target.closest("[data-pm-dashboard-action]")' in interactions_text
    assert 'if (action === "open-project") {' in interactions_text
    assert "pmDashboardState.ctx?.openPMDashboardProjectDrilldown" in interactions_text
    assert 'if (action === "open-solution") {' in interactions_text
    assert "pmDashboardState.ctx?.openPMDashboardSolutionDrilldown" in interactions_text
    assert 'if (action === "open-subcomponent") {' in interactions_text
    assert "pmDashboardState.ctx?.openPMDashboardSubcomponentDrilldown" in interactions_text
    assert 'if (action === "open-capacity-allocations") {' in interactions_text
    assert 'const detail = pmDashboardState.capacityDrilldowns.get(assigneeKey);' in interactions_text
    assert "pmDashboardState.ctx?.openPMDashboardCapacityDrilldown" in interactions_text
    assert 'if (action !== "set-capacity-month") return;' in interactions_text
    assert 'persistCapacityMonth(pmDashboardState.capacitySpaceId, nextMonth);' in interactions_text
    assert "rerender();" in interactions_text
    assert "pmDashboardState.ctx = ctx;" in render_text
    assert "renderPMDashboardCapacitySection({" in render_text
    assert "function ensureCapacityMonth(pmDashboardState, spaceId) {" in storage_text


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
    assert 'type === "solution" ? "Open Workstream"' in text
    assert 'type === "subcomponent" ? "Open Deliverable"' in text
    assert 'type === "solution" ? "Workstream"' in text
    assert 'type === "subcomponent" ? "Deliverable"' in text
    assert "The linked workstream is unavailable." in text
    assert "The linked deliverable is unavailable." in text
    assert "No allocations in this scope." in text
    assert "openProjectForm(project)" in text
    assert 'openSolutionModal(solution, "details")' in text
    assert 'openSolutionModal(solution, "subcomponents")' in text
    assert "fillSubcomponentForm(subcomponent)" in text


def test_pm_dashboard_uses_pm_row_link_style_for_dense_title_actions():
    text = read_ui_styles(STYLES_CSS)
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
    text = read_ui_styles(STYLES_CSS)

    assert ".pm-action-link {" in text
    assert "color: inherit;" in text
    assert "text-underline-offset: 0.12em;" in text
    assert ".pm-action-link:hover {" in text
    assert "color: var(--accent-strong);" in text


def test_pm_dashboard_surfaces_status_freshness_for_leadership_trust():
    render_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    sections_text = PM_DASHBOARD_SECTIONS.read_text(encoding="utf-8")

    assert "const STALE_STATUS_DAYS = 7;" in render_text
    assert "function isStaleStatusRecord(record, today) {" in render_text
    assert "const staleSolutions = activeSolutions.filter((solution) => isStaleStatusRecord(solution, today));" in render_text
    assert "const staleSubcomponents = activeSubcomponents.filter((subcomponent) => isStaleStatusRecord(subcomponent, today));" in render_text
    assert "const staleTotal = staleSolutions.length + staleSubcomponents.length;" in render_text
    assert "const staleCount =" in render_text
    assert "+ staleCount * 4" in render_text
    assert "staleCount," in render_text
    assert "const statusIsStale = isStaleStatusRecord(solution, today);" in render_text
    assert 'signals.push("Status stale");' in render_text
    assert "`${staleTotal} records need status refresh`" in render_text
    assert 'cta: "Review Status"' in render_text
    assert "staleTotal," in render_text
    assert "staleStatusDays: STALE_STATUS_DAYS," in render_text
    assert "+ staleTotal;" in render_text
    assert "Status Freshness" in sections_text
    assert "Records older than ${staleStatusDays} days" in sections_text
    assert "No stale active records" in sections_text
    assert "Stale ${summary.staleCount}" in sections_text


def test_pm_dashboard_uses_business_led_workstream_and_deliverable_language():
    render_text = PM_DASHBOARD_RENDER.read_text(encoding="utf-8")
    sections_text = PM_DASHBOARD_SECTIONS.read_text(encoding="utf-8")

    assert "Active Workstreams" in sections_text
    assert "Open Deliverables" in sections_text
    assert "Open Workstreams" in sections_text
    assert "Workstreams by Status" in sections_text
    assert "Deliverables by Status" in sections_text
    assert "Active Workstream RAG Mix" in sections_text
    assert "Work List" in sections_text
    assert "Planning deliverable assignments only." in sections_text
    assert "No elevated workstream risks detected." in sections_text
    assert 'kind: "Workstream"' in render_text
    assert 'kind: "Deliverable"' in render_text
    assert "red workstreams need intervention" in render_text
    assert "blocked deliverables are stalling flow" in render_text
    assert "active deliverables are unassigned" in render_text
    assert "Blocked deliverables" in render_text
    assert "Overdue deliverables" in render_text
    assert "Active Solutions" not in sections_text
    assert "Open Tasks" not in sections_text
    assert "Open Sol." not in sections_text
    assert "Solutions by Status" not in sections_text
    assert "Tasks by Status" not in sections_text
    assert "Subcomponents</a>" not in sections_text


def test_pm_dashboard_quick_links_use_text_first_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".pm-quick-links a {" in text
    assert "color: inherit;" in text
    assert "border: none;" in text
    assert "border-radius: 0;" in text
    assert "padding: 0;" in text
    assert ".pm-quick-links a:hover {" in text
    assert "text-decoration: underline;" in text


def test_pm_dashboard_action_rows_use_lighter_container_chrome():
    text = read_ui_styles(STYLES_CSS)

    assert ".pm-action-row {" in text
    assert "background: transparent;" in text


def test_pm_dashboard_signal_tokens_use_quieter_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".pm-signal {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "background: transparent;" in text


def test_pm_dashboard_item_kind_tokens_use_quieter_styling():
    text = read_ui_styles(STYLES_CSS)

    assert ".pm-item-kind {" in text
    assert "padding: 0;" in text
    assert "border: none;" in text
    assert "background: transparent;" in text
