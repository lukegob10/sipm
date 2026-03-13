const DAY_MS = 24 * 60 * 60 * 1000;
const CLOSED_SOLUTION_STATUSES = new Set(["complete", "abandoned"]);
const CLOSED_SUBCOMPONENT_STATUSES = new Set(["complete", "abandoned"]);
const SOLUTION_STATUS_ORDER = ["not_started", "active", "on_hold", "complete", "abandoned"];
const SUBCOMPONENT_STATUS_ORDER = ["to_do", "in_progress", "on_hold", "complete", "abandoned"];
const PM_DASHBOARD_STORAGE_KEY_PREFIX = "sipm-pm-dashboard-ui-v1";

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function num(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function parseDate(value) {
  if (!value) return null;
  const iso = String(value).slice(0, 10);
  const parsed = new Date(`${iso}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfDay(value) {
  const date = new Date(value.getTime());
  date.setHours(0, 0, 0, 0);
  return date;
}

function daysUntil(fromDate, toDate) {
  return Math.ceil((toDate.getTime() - fromDate.getTime()) / DAY_MS);
}

function isClosedSolutionStatus(status) {
  return CLOSED_SOLUTION_STATUSES.has(String(status || "").toLowerCase());
}

function isClosedSubcomponentStatus(status) {
  return CLOSED_SUBCOMPONENT_STATUSES.has(String(status || "").toLowerCase());
}

function nonEmpty(value) {
  return String(value || "").trim().length > 0;
}

function scoreTone(score) {
  if (score >= 70) return "danger";
  if (score >= 45) return "warn";
  return "positive";
}

function healthTone(score) {
  if (score >= 85) return "positive";
  if (score >= 70) return "warn";
  return "danger";
}

function utilTone(utilization, capacity, allocated) {
  if (capacity <= 0 && allocated > 0) return "danger";
  if (utilization >= 100) return "danger";
  if (utilization >= 85) return "warn";
  return "positive";
}

function dueDeltaLabel(days) {
  if (!Number.isFinite(days)) return "No due date";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "Due today";
  return `Due in ${days}d`;
}

function isoDateLabel(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return date.toISOString().slice(0, 10);
}

function monthKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${month}`;
}

function currentMonthToken() {
  return monthKey(startOfDay(new Date()));
}

function normalizeMonthToken(value) {
  const token = String(value || "").trim();
  return /^\d{4}-\d{2}$/.test(token) ? token : "";
}

function pmDashboardStorageKey(spaceId) {
  const scope = String(spaceId || "no-space").trim().toLowerCase() || "no-space";
  return `${PM_DASHBOARD_STORAGE_KEY_PREFIX}:${scope}`;
}

function readStoredCapacityMonth(spaceId) {
  if (typeof window === "undefined" || !window.localStorage) return "";
  try {
    return normalizeMonthToken(window.localStorage.getItem(pmDashboardStorageKey(spaceId)) || "");
  } catch {
    return "";
  }
}

function persistCapacityMonth(spaceId, monthToken) {
  const normalized = normalizeMonthToken(monthToken);
  if (!normalized || typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(pmDashboardStorageKey(spaceId), normalized);
  } catch {
    // Ignore persistence failures.
  }
}

function formatFteValue(value, formatFte) {
  if (typeof formatFte === "function") return formatFte(value);
  return num(value).toFixed(2);
}

const pmDashboardState = {
  ctx: null,
  bound: false,
  capacityDrilldowns: new Map(),
  capacityScopeLabel: "",
  capacityMonth: "",
  capacitySpaceId: "",
};

function ensureCapacityMonth(spaceId) {
  const normalizedSpaceId = String(spaceId || "").trim();
  if (pmDashboardState.capacitySpaceId !== normalizedSpaceId) {
    pmDashboardState.capacitySpaceId = normalizedSpaceId;
    pmDashboardState.capacityMonth = readStoredCapacityMonth(normalizedSpaceId) || currentMonthToken();
  }
  const normalizedMonth = normalizeMonthToken(pmDashboardState.capacityMonth) || currentMonthToken();
  pmDashboardState.capacityMonth = normalizedMonth;
  return normalizedMonth;
}

function renderPMDashboardRowLink(label, action, attrs = {}) {
  const extraAttrs = Object.entries(attrs)
    .filter(([, value]) => String(value || "").trim())
    .map(([name, value]) => ` ${name}="${esc(value)}"`)
    .join("");
  return `<button type="button" class="pm-row-link" data-pm-dashboard-action="${esc(action)}"${extraAttrs}>${esc(label)}</button>`;
}

function renderPMDashboardProjectLink(label, projectId) {
  if (!String(projectId || "").trim()) return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(label, "open-project", {
    "data-project-id": projectId,
    "aria-label": `Open project ${label}`,
  });
}

function renderPMDashboardSolutionLink(label, solutionId) {
  if (!String(solutionId || "").trim()) return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(label, "open-solution", {
    "data-solution-id": solutionId,
    "aria-label": `Open solution ${label}`,
  });
}

function normalizePMDashboardIdentity(value) {
  return String(value || "").trim().toLowerCase();
}

function buildPMDashboardOwnerDirectory(users) {
  const activeUsers = Array.isArray(users) ? users.filter((user) => user && user.is_active !== false) : [];
  const soeidToKey = new Map();
  const displayNameCounts = new Map();

  activeUsers.forEach((user) => {
    const soeid = String(user?.soeid || "").trim();
    const displayName = String(user?.display_name || "").trim();
    const soeidToken = normalizePMDashboardIdentity(soeid);
    const displayNameToken = normalizePMDashboardIdentity(displayName);
    if (soeidToken) soeidToKey.set(soeidToken, soeid);
    if (displayNameToken && soeid) {
      displayNameCounts.set(displayNameToken, (displayNameCounts.get(displayNameToken) || 0) + 1);
    }
  });

  const uniqueDisplayNameToKey = new Map();
  activeUsers.forEach((user) => {
    const soeid = String(user?.soeid || "").trim();
    const displayNameToken = normalizePMDashboardIdentity(user?.display_name);
    if (!soeid || !displayNameToken) return;
    if ((displayNameCounts.get(displayNameToken) || 0) !== 1) return;
    uniqueDisplayNameToKey.set(displayNameToken, soeid);
  });

  return { soeidToKey, uniqueDisplayNameToKey };
}

function resolvePMDashboardOwnerAssigneeKey(soeidValue, labelValue, ownerDirectory) {
  const soeidToken = normalizePMDashboardIdentity(soeidValue);
  if (soeidToken && ownerDirectory?.soeidToKey?.has(soeidToken)) {
    return ownerDirectory.soeidToKey.get(soeidToken) || "";
  }
  const labelToken = normalizePMDashboardIdentity(labelValue);
  if (!labelToken || labelToken === "unassigned") return "";
  if (ownerDirectory?.soeidToKey?.has(labelToken)) {
    return ownerDirectory.soeidToKey.get(labelToken) || "";
  }
  return ownerDirectory?.uniqueDisplayNameToKey?.get(labelToken) || "";
}

function renderPMDashboardOwnerLink(label, assigneeKey) {
  const ownerLabel = String(label || "Unassigned").trim() || "Unassigned";
  const resolvedKey = String(assigneeKey || "").trim();
  if (!resolvedKey || resolvedKey === "unassigned") return esc(ownerLabel);
  return renderPMDashboardRowLink(ownerLabel, "open-capacity-allocations", {
    "data-assignee-key": resolvedKey,
    "aria-label": `Open workload for ${ownerLabel}`,
  });
}

function renderPMDashboardTimelineLink(row) {
  if (row.itemKind === "solution") {
    return renderPMDashboardSolutionLink(row.name, row.solutionId);
  }
  if (!String(row.subcomponentId || "").trim()) return `<strong>${esc(row.name)}</strong>`;
  return renderPMDashboardRowLink(row.name, "open-subcomponent", {
    "data-subcomponent-id": row.subcomponentId,
    "aria-label": `Open task ${row.name}`,
  });
}

function renderPMDashboardCapacityLink(row) {
  const assigneeKey = String(row?.key || "").trim();
  const label = String(row?.label || "Unassigned").trim() || "Unassigned";
  if (!assigneeKey || assigneeKey === "unassigned") return `<strong>${esc(label)}</strong>`;
  return renderPMDashboardRowLink(row.label, "open-capacity-allocations", {
    "data-assignee-key": row.key,
    "aria-label": `Open workload for ${row.label}`,
  });
}

function bindPMDashboardEvents() {
  const viewRoot = typeof document !== "undefined" ? document.getElementById("view-pm-dashboard") : null;
  if (!viewRoot || pmDashboardState.bound) return;
  pmDashboardState.bound = true;

  viewRoot.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-pm-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-pm-dashboard-action") || "";

    if (action === "open-project") {
      event.preventDefault();
      const projectId = String(actionEl.getAttribute("data-project-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardProjectDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardProjectDrilldown(projectId);
      }
      return;
    }

    if (action === "open-solution") {
      event.preventDefault();
      const solutionId = String(actionEl.getAttribute("data-solution-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardSolutionDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardSolutionDrilldown(solutionId);
      }
      return;
    }

    if (action === "open-capacity-allocations") {
      event.preventDefault();
      const assigneeKey = String(actionEl.getAttribute("data-assignee-key") || "");
      const detail = pmDashboardState.capacityDrilldowns.get(assigneeKey);
      if (!detail) return;
      if (typeof pmDashboardState.ctx?.openPMDashboardCapacityDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardCapacityDrilldown({
          key: detail.key,
          label: detail.label,
          allocated: detail.allocated,
          capacity: detail.capacity,
          utilization: detail.utilization,
          scopeLabel: pmDashboardState.capacityScopeLabel,
          allocations: detail.allocations,
        });
      }
      return;
    }

    if (action === "open-subcomponent") {
      event.preventDefault();
      const subcomponentId = String(actionEl.getAttribute("data-subcomponent-id") || "");
      if (typeof pmDashboardState.ctx?.openPMDashboardSubcomponentDrilldown === "function") {
        pmDashboardState.ctx.openPMDashboardSubcomponentDrilldown(subcomponentId);
      }
    }
  });

  viewRoot.addEventListener("change", (event) => {
    if (!(event.target instanceof Element)) return;
    const actionEl = event.target.closest("[data-pm-dashboard-action]");
    if (!actionEl) return;
    const action = actionEl.getAttribute("data-pm-dashboard-action") || "";
    if (action !== "set-capacity-month") return;
    const nextMonth = normalizeMonthToken(event.target.value) || currentMonthToken();
    pmDashboardState.capacityMonth = nextMonth;
    persistCapacityMonth(pmDashboardState.capacitySpaceId, nextMonth);
    renderPMDashboard(pmDashboardState.ctx);
  });
}

export function renderPMDashboard(ctx) {
  const {
    state,
    els,
    formatStatus,
    viewHref,
    assigneeKeyFromAlloc,
    assigneeLabelFromKey,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
  } = ctx;
  pmDashboardState.ctx = ctx;
  bindPMDashboardEvents();
  const hrefFor = (view) => {
    const normalized = String(view || "master").trim();
    if (typeof viewHref === "function") return viewHref(normalized);
    return normalized === "master" ? "/project-manager/" : `/project-manager/${normalized}`;
  };

  const activeSpaceName = String(state.activeSpace?.space_name || "").trim();
  const activeSpaceId = String(state.activeSpace?.space_id || "").trim();
  const activeSpaceLabel = activeSpaceName || activeSpaceId || "No active space";

  const rawProjects = Array.isArray(state.projects) ? state.projects : [];
  const rawSolutions = Array.isArray(state.solutions) ? state.solutions : [];
  const rawSubcomponents = Array.isArray(state.subcomponents) ? state.subcomponents : [];
  const rawUsers = Array.isArray(state.users) ? state.users : [];
  const rawAllocations = Array.isArray(state.allocations) ? state.allocations : [];

  const projectIds = new Set(rawProjects.map((project) => String(project?.project_id || "").trim()).filter(Boolean));
  const projects = rawProjects.filter((project) => projectIds.has(String(project?.project_id || "").trim()));

  const solutions = rawSolutions.filter((solution) => {
    const projectId = String(solution?.project_id || "").trim();
    return !!projectId && projectIds.has(projectId);
  });
  const solutionIds = new Set(solutions.map((solution) => String(solution?.solution_id || "").trim()).filter(Boolean));

  const subcomponents = rawSubcomponents.filter((subcomponent) => {
    const projectId = String(subcomponent?.project_id || "").trim();
    const solutionId = String(subcomponent?.solution_id || "").trim();
    return !!projectId && !!solutionId && projectIds.has(projectId) && solutionIds.has(solutionId);
  });
  const subcomponentIds = new Set(
    subcomponents.map((subcomponent) => String(subcomponent?.subcomponent_id || "").trim()).filter(Boolean)
  );

  const users = [...rawUsers];
  const allocations = rawAllocations.filter((allocation) => {
    const type = String(allocation?.work_item_type || "").toLowerCase();
    const workItemId = String(allocation?.work_item_id || "").trim();
    if (!workItemId) return false;
    if (type === "project") return projectIds.has(workItemId);
    if (type === "solution") return solutionIds.has(workItemId);
    if (type === "subcomponent") return subcomponentIds.has(workItemId);
    return false;
  });
  const today = startOfDay(new Date());
  const todayMonthKey = monthKey(today);
  const selectedCapacityMonth = ensureCapacityMonth(activeSpaceId);
  const ownerDirectory = buildPMDashboardOwnerDirectory(users);

  const projectNameById = new Map(
    projects.map((project) => [project.project_id, project.project_name || "Unmapped Project"])
  );
  const solutionNameById = new Map(
    solutions.map((solution) => [solution.solution_id, solution.solution_name || "Unnamed Solution"])
  );

  const subcomponentsByProject = new Map();
  const subcomponentsBySolution = new Map();
  subcomponents.forEach((subcomponent) => {
    const projectBucket = subcomponentsByProject.get(subcomponent.project_id) || [];
    projectBucket.push(subcomponent);
    subcomponentsByProject.set(subcomponent.project_id, projectBucket);

    const solutionBucket = subcomponentsBySolution.get(subcomponent.solution_id) || [];
    solutionBucket.push(subcomponent);
    subcomponentsBySolution.set(subcomponent.solution_id, solutionBucket);
  });

  const activeSolutions = solutions.filter((solution) => !isClosedSolutionStatus(solution.status));
  const activeSubcomponents = subcomponents.filter((subcomponent) => !isClosedSubcomponentStatus(subcomponent.status));

  const redSolutions = activeSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "red");
  const amberSolutions = activeSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "amber");
  const onHoldSolutions = activeSolutions.filter((solution) => String(solution.status || "").toLowerCase() === "on_hold");

  const overdueSolutions = activeSolutions.filter((solution) => {
    const dueDate = parseDate(solution.due_date);
    return !!dueDate && dueDate < today;
  });
  const dueSoonSolutions = activeSolutions.filter((solution) => {
    const dueDate = parseDate(solution.due_date);
    if (!dueDate) return false;
    const days = daysUntil(today, dueDate);
    return days >= 0 && days <= 14;
  });

  const overdueSubcomponents = activeSubcomponents.filter((subcomponent) => {
    const dueDate = parseDate(subcomponent.due_date);
    return !!dueDate && dueDate < today;
  });
  const dueSoonSubcomponents = activeSubcomponents.filter((subcomponent) => {
    const dueDate = parseDate(subcomponent.due_date);
    if (!dueDate) return false;
    const days = daysUntil(today, dueDate);
    return days >= 0 && days <= 14;
  });
  const blockedSubcomponents = activeSubcomponents.filter((subcomponent) => !!subcomponent.blocked);
  const unassignedSubcomponents = activeSubcomponents.filter(
    (subcomponent) => !nonEmpty(subcomponent.assignee) && !nonEmpty(subcomponent.assignee_user_soeid)
  );

  const projectSummaries = projects
    .map((project) => {
      const projectSolutions = solutions.filter((solution) => solution.project_id === project.project_id);
      const openSolutions = projectSolutions.filter((solution) => !isClosedSolutionStatus(solution.status));
      const projectSubcomponents = subcomponentsByProject.get(project.project_id) || [];
      const openSubcomponents = projectSubcomponents.filter((subcomponent) => !isClosedSubcomponentStatus(subcomponent.status));

      const redCount = openSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "red").length;
      const amberCount = openSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "amber").length;
      const onHoldCount = openSolutions.filter((solution) => String(solution.status || "").toLowerCase() === "on_hold").length;
      const overdueSolutionCount = openSolutions.filter((solution) => {
        const dueDate = parseDate(solution.due_date);
        return !!dueDate && dueDate < today;
      }).length;
      const overdueSubcomponentCount = openSubcomponents.filter((subcomponent) => {
        const dueDate = parseDate(subcomponent.due_date);
        return !!dueDate && dueDate < today;
      }).length;
      const blockedCount = openSubcomponents.filter((subcomponent) => !!subcomponent.blocked).length;
      const unassignedCount = openSubcomponents.filter(
        (subcomponent) => !nonEmpty(subcomponent.assignee) && !nonEmpty(subcomponent.assignee_user_soeid)
      ).length;
      const dueCandidates = [
        ...openSolutions.map((solution) => parseDate(solution.due_date)).filter(Boolean),
        ...openSubcomponents.map((subcomponent) => parseDate(subcomponent.due_date)).filter(Boolean),
      ];
      const nearestDue = dueCandidates.length
        ? dueCandidates.sort((a, b) => a.getTime() - b.getTime())[0]
        : null;

      const riskScore = clamp(
        redCount * 28
          + amberCount * 14
          + onHoldCount * 10
          + overdueSolutionCount * 10
          + overdueSubcomponentCount * 5
          + blockedCount * 6
          + unassignedCount * 3,
        0,
        100
      );
      const healthScore = clamp(100 - riskScore, 0, 100);

      return {
        projectId: project.project_id,
        projectName: project.project_name || "Unnamed Project",
        openSolutions: openSolutions.length,
        openSubcomponents: openSubcomponents.length,
        redCount,
        amberCount,
        blockedCount,
        overdueCount: overdueSolutionCount + overdueSubcomponentCount,
        riskScore,
        healthScore,
        nearestDue,
      };
    })
    .sort((a, b) => {
      if (a.healthScore !== b.healthScore) return a.healthScore - b.healthScore;
      if (a.openSolutions !== b.openSolutions) return b.openSolutions - a.openSolutions;
      return a.projectName.localeCompare(b.projectName);
    });

  const solutionRiskRows = activeSolutions
    .map((solution) => {
      const linkedSubcomponents = subcomponentsBySolution.get(solution.solution_id) || [];
      const openLinkedSubcomponents = linkedSubcomponents.filter((subcomponent) => !isClosedSubcomponentStatus(subcomponent.status));
      const blockedLinked = openLinkedSubcomponents.filter((subcomponent) => !!subcomponent.blocked).length;
      const overdueLinked = openLinkedSubcomponents.filter((subcomponent) => {
        const dueDate = parseDate(subcomponent.due_date);
        return !!dueDate && dueDate < today;
      }).length;

      let riskScore = 0;
      const signals = [];
      const rag = String(solution.rag_status || "").toLowerCase();
      const status = String(solution.status || "").toLowerCase();
      const dueDate = parseDate(solution.due_date);
      const dueDays = dueDate ? daysUntil(today, dueDate) : Number.NaN;

      if (rag === "red") {
        riskScore += 50;
        signals.push("RAG red");
      } else if (rag === "amber") {
        riskScore += 24;
        signals.push("RAG amber");
      }
      if (status === "on_hold") {
        riskScore += 20;
        signals.push("On hold");
      }
      if (Number.isFinite(dueDays) && dueDays < 0) {
        riskScore += 20;
        signals.push("Overdue");
      } else if (Number.isFinite(dueDays) && dueDays <= 14) {
        riskScore += 10;
        signals.push("Due <=14d");
      }
      if (nonEmpty(solution.blockers)) {
        riskScore += 16;
        signals.push("Blockers");
      }
      if (nonEmpty(solution.risks)) {
        riskScore += 12;
        signals.push("Risks noted");
      }
      if (!nonEmpty(solution.owner) && !nonEmpty(solution.owner_user_soeid)) {
        riskScore += 8;
        signals.push("No owner");
      }
      if (blockedLinked > 0) {
        riskScore += Math.min(16, blockedLinked * 4);
        signals.push(`Blocked tasks ${blockedLinked}`);
      }
      if (overdueLinked > 0) {
        riskScore += Math.min(16, overdueLinked * 4);
        signals.push(`Overdue tasks ${overdueLinked}`);
      }
      riskScore = clamp(riskScore, 0, 100);

      return {
        solutionId: solution.solution_id,
        solutionName: solution.solution_name || "Unnamed Solution",
        projectName: projectNameById.get(solution.project_id) || "Unmapped Project",
        owner: solution.owner || solution.owner_user_soeid || "Unassigned",
        ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(solution.owner_user_soeid, solution.owner, ownerDirectory),
        dueDate: solution.due_date,
        riskScore,
        signals,
      };
    })
    .sort((a, b) => b.riskScore - a.riskScore || a.solutionName.localeCompare(b.solutionName));

  const timelineRows = [
    ...activeSolutions
      .filter((solution) => !!solution.due_date)
      .map((solution) => {
        const dueDate = parseDate(solution.due_date);
        const days = dueDate ? daysUntil(today, dueDate) : Number.NaN;
        return {
          itemKind: "solution",
          kind: "Solution",
          solutionId: solution.solution_id,
          subcomponentId: "",
          name: solution.solution_name || "Unnamed Solution",
          projectName: projectNameById.get(solution.project_id) || "Unmapped Project",
          solutionName: "",
          owner: solution.owner || solution.owner_user_soeid || "Unassigned",
          ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(solution.owner_user_soeid, solution.owner, ownerDirectory),
          dueDate: solution.due_date,
          days,
        };
      }),
    ...activeSubcomponents
      .filter((subcomponent) => !!subcomponent.due_date)
      .map((subcomponent) => {
        const dueDate = parseDate(subcomponent.due_date);
        const days = dueDate ? daysUntil(today, dueDate) : Number.NaN;
        return {
          itemKind: "subcomponent",
          kind: "Task",
          solutionId: subcomponent.solution_id,
          subcomponentId: subcomponent.subcomponent_id,
          name: subcomponent.subcomponent_name || "Unnamed Task",
          projectName: projectNameById.get(subcomponent.project_id) || "Unmapped Project",
          solutionName: solutionNameById.get(subcomponent.solution_id) || "Unmapped Solution",
          owner: subcomponent.assignee || subcomponent.assignee_user_soeid || "Unassigned",
          ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(
            subcomponent.assignee_user_soeid,
            subcomponent.assignee,
            ownerDirectory
          ),
          dueDate: subcomponent.due_date,
          days,
        };
      }),
  ]
    .filter((row) => Number.isFinite(row.days))
    .sort((a, b) => a.days - b.days || a.projectName.localeCompare(b.projectName));

  const timelineFocusRows = timelineRows.filter((row) => row.days <= 30).slice(0, 14);
  const overdueTotal = overdueSolutions.length + overdueSubcomponents.length;
  const dueSoonTotal = dueSoonSolutions.length + dueSoonSubcomponents.length;

  const allocDate = (allocation) => parseDate(allocation?.month_start || allocation?.week_start);
  const scopedAllocations = allocations.filter((allocation) => {
    const date = allocDate(allocation);
    return !!date && monthKey(date) === selectedCapacityMonth;
  });
  const allocationScopeLabel = selectedCapacityMonth === todayMonthKey
    ? `Current month (${selectedCapacityMonth})`
    : `Selected month (${selectedCapacityMonth})`;
  const planningTaskAllocations = scopedAllocations.filter(
    (allocation) => String(allocation?.work_item_type || "").trim().toLowerCase() === "subcomponent"
  );
  const capacityScopeLabel = planningTaskAllocations.length
    ? allocationScopeLabel
    : scopedAllocations.length
      ? `${allocationScopeLabel} | No planning task assignments`
      : "No planning task assignments";

  const allocKey = typeof assigneeKeyFromAlloc === "function"
    ? assigneeKeyFromAlloc
    : (allocation) => allocation?.assignee_user_soeid || allocation?.assignee || "unassigned";
  const allocLabel = typeof assigneeLabelFromKey === "function"
    ? assigneeLabelFromKey
    : (key) => (key === "unassigned" ? "Unassigned" : key || "Unassigned");
  const allocFte = typeof allocationFteMonths === "function"
    ? allocationFteMonths
    : (allocation) => {
      if (!allocation) return 0;
      const byFte = Number(allocation.fte_months);
      if (Number.isFinite(byFte)) return byFte;
      const byHours = Number(allocation.hours);
      if (Number.isFinite(byHours)) return byHours / 160;
      return 0;
    };
  const userCapacity = typeof userCapacityFteMonth === "function"
    ? userCapacityFteMonth
    : (user) => {
      if (!user) return 1;
      const byFte = Number(user.capacity_fte_month);
      if (Number.isFinite(byFte)) return byFte;
      const byHours = Number(user.capacity_hours);
      return Number.isFinite(byHours) ? byHours / 40 : 1;
    };

  const capacityByKey = new Map();
  users
    .filter((user) => user && user.is_active !== false)
    .forEach((user) => {
      const key = String(user.soeid || "").trim();
      if (!key) return;
      capacityByKey.set(key, Math.max(0, userCapacity(user)));
    });
  const allocatedByKey = new Map();
  const allocationsByKey = new Map();
  planningTaskAllocations.forEach((allocation) => {
    const key = String(allocKey(allocation) || "unassigned");
    allocatedByKey.set(key, (allocatedByKey.get(key) || 0) + Math.max(0, allocFte(allocation)));
    const bucket = allocationsByKey.get(key) || [];
    bucket.push(allocation);
    allocationsByKey.set(key, bucket);
  });

  const allCapacityKeys = new Set([...capacityByKey.keys(), ...allocatedByKey.keys()]);
  const capacityRows = Array.from(allCapacityKeys)
    .map((key) => {
      const rowAllocations = allocationsByKey.get(key) || [];
      const capacity = capacityByKey.get(key) || 0;
      const allocated = allocatedByKey.get(key) || 0;
      const utilization = capacity > 0 ? (allocated / capacity) * 100 : allocated > 0 ? 999 : 0;
      return {
        key,
        label: allocLabel(key),
        capacity,
        allocated,
        gap: capacity - allocated,
        utilization,
        allocations: rowAllocations,
      };
    })
    .sort((a, b) => {
      if (a.utilization !== b.utilization) return b.utilization - a.utilization;
      if (a.allocated !== b.allocated) return b.allocated - a.allocated;
      return a.label.localeCompare(b.label);
    });
  pmDashboardState.capacityDrilldowns = new Map(capacityRows.map((row) => [row.key, row]));
  pmDashboardState.capacityScopeLabel = `${capacityScopeLabel} | Planning task assignments only`;
  const overloadedRows = capacityRows.filter((row) => row.capacity > 0 && row.allocated > row.capacity * 1.05);
  const totalCapacity = Array.from(capacityByKey.values()).reduce((sum, value) => sum + value, 0);
  const totalAllocated = Array.from(allocatedByKey.values()).reduce((sum, value) => sum + value, 0);
  const totalGap = totalCapacity - totalAllocated;

  const ragCounts = activeSolutions.reduce(
    (acc, solution) => {
      const rag = String(solution.rag_status || "").toLowerCase();
      if (rag === "red" || rag === "amber" || rag === "green") acc[rag] += 1;
      else acc.unknown += 1;
      return acc;
    },
    { red: 0, amber: 0, green: 0, unknown: 0 }
  );

  const solutionStatusCounts = new Map(SOLUTION_STATUS_ORDER.map((status) => [status, 0]));
  solutions.forEach((solution) => {
    const status = String(solution.status || "").toLowerCase();
    if (!solutionStatusCounts.has(status)) solutionStatusCounts.set(status, 0);
    solutionStatusCounts.set(status, (solutionStatusCounts.get(status) || 0) + 1);
  });
  const subcomponentStatusCounts = new Map(SUBCOMPONENT_STATUS_ORDER.map((status) => [status, 0]));
  subcomponents.forEach((subcomponent) => {
    const status = String(subcomponent.status || "").toLowerCase();
    if (!subcomponentStatusCounts.has(status)) subcomponentStatusCounts.set(status, 0);
    subcomponentStatusCounts.set(status, (subcomponentStatusCounts.get(status) || 0) + 1);
  });

  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const nextMonthStart = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const completionsThisMonth = solutions.filter((solution) => {
    if (String(solution.status || "").toLowerCase() !== "complete") return false;
    const date = solution.completed_at ? new Date(solution.completed_at) : parseDate(solution.updated_at);
    return !!date && date >= monthStart && date < nextMonthStart;
  }).length + subcomponents.filter((subcomponent) => {
    if (String(subcomponent.status || "").toLowerCase() !== "complete") return false;
    const date = subcomponent.completed_at ? new Date(subcomponent.completed_at) : parseDate(subcomponent.updated_at);
    return !!date && date >= monthStart && date < nextMonthStart;
  }).length;

  const riskUnits =
    redSolutions.length * 7
    + amberSolutions.length * 4
    + onHoldSolutions.length * 3
    + overdueTotal * 2
    + blockedSubcomponents.length * 2
    + unassignedSubcomponents.length;
  const riskDenominator = Math.max(activeSolutions.length * 7 + activeSubcomponents.length * 2, 1);
  const portfolioHealthScore = Math.round(clamp(100 - (riskUnits / riskDenominator) * 100, 0, 100));
  const atRiskSolutions = solutionRiskRows.filter((row) => row.riskScore >= 45).length;

  const actions = [];
  if (redSolutions.length > 0) {
    actions.push({
      tone: "danger",
      title: `${redSolutions.length} red solutions need intervention`,
      detail: "Review RAG reasons and assign recovery owners.",
      href: hrefFor("master"),
      cta: "Open Deliverables",
    });
  }
  if (overdueTotal > 0) {
    actions.push({
      tone: "danger",
      title: `${overdueTotal} overdue items require replan`,
      detail: "Rebaseline due dates or de-scope low-value work.",
      href: hrefFor("calendar"),
      cta: "Open Calendar",
    });
  }
  if (blockedSubcomponents.length > 0) {
    actions.push({
      tone: "warn",
      title: `${blockedSubcomponents.length} blocked tasks are stalling flow`,
      detail: "Clear blocker notes and escalate dependency owners.",
      href: hrefFor("subcomponents-workbench"),
      cta: "Open Subcomponents",
    });
  }
  if (overloadedRows.length > 0) {
    actions.push({
      tone: "warn",
      title: `${overloadedRows.length} assignees are overloaded`,
      detail: "Reallocate work in the planning window to reduce delivery risk.",
      href: hrefFor("planning"),
      cta: "Open Planning",
    });
  }
  if (unassignedSubcomponents.length > 0) {
    actions.push({
      tone: "warn",
      title: `${unassignedSubcomponents.length} active tasks are unassigned`,
      detail: "Assign owners so execution can start and status can move.",
      href: hrefFor("subcomponents-workbench"),
      cta: "Assign Tasks",
    });
  }
  if (!actions.length) {
    actions.push({
      tone: "positive",
      title: "No critical blockers detected",
      detail: "Portfolio is currently stable. Track due-soon work and keep cadence.",
      href: hrefFor("dashboard"),
      cta: "Open Standard Dashboard",
    });
  }

  if (els.pmDashboardSummary) {
    els.pmDashboardSummary.innerHTML = `
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Current Space</div>
        <div class="pm-kpi-value">${esc(activeSpaceLabel)}</div>
        <div class="pm-kpi-meta">PM Command Center only shows active-space data</div>
      </article>
      <article class="pm-kpi-card pm-kpi-health ${healthTone(portfolioHealthScore)}">
        <div class="pm-kpi-label">Portfolio Health</div>
        <div class="pm-kpi-value">${portfolioHealthScore}</div>
        <div class="pm-kpi-meta">Composite risk-adjusted score</div>
      </article>
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Active Solutions</div>
        <div class="pm-kpi-value">${activeSolutions.length}</div>
        <div class="pm-kpi-meta">${atRiskSolutions} currently at risk</div>
      </article>
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Open Tasks</div>
        <div class="pm-kpi-value">${activeSubcomponents.length}</div>
        <div class="pm-kpi-meta">${blockedSubcomponents.length} blocked, ${unassignedSubcomponents.length} unassigned</div>
      </article>
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Schedule Pressure</div>
        <div class="pm-kpi-value">${overdueTotal + dueSoonTotal}</div>
        <div class="pm-kpi-meta">${overdueTotal} overdue, ${dueSoonTotal} due in 14 days</div>
      </article>
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Capacity Gap</div>
        <div class="pm-kpi-value ${totalGap < 0 ? "danger" : "positive"}">${totalGap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(totalGap), formatFte)}</div>
        <div class="pm-kpi-meta">${formatFteValue(totalAllocated, formatFte)} allocated / ${formatFteValue(totalCapacity, formatFte)} capacity</div>
      </article>
      <article class="pm-kpi-card">
        <div class="pm-kpi-label">Throughput (This Month)</div>
        <div class="pm-kpi-value">${completionsThisMonth}</div>
        <div class="pm-kpi-meta">Completed solutions + tasks</div>
      </article>
    `;
  }

  if (els.pmDashboardHealth) {
    if (!projectSummaries.length) {
      els.pmDashboardHealth.innerHTML = "<h3>Project Health</h3><p class='muted'>No projects in this space yet.</p>";
    } else {
      const rows = projectSummaries
        .slice(0, 12)
        .map((summary) => {
          const hotspots = [
            summary.redCount ? `<span class="pill danger">Red ${summary.redCount}</span>` : "",
            summary.amberCount ? `<span class="pill warn">Amber ${summary.amberCount}</span>` : "",
            summary.overdueCount ? `<span class="pill danger">Overdue ${summary.overdueCount}</span>` : "",
            summary.blockedCount ? `<span class="pill warn">Blocked ${summary.blockedCount}</span>` : "",
          ].filter(Boolean).join(" ");
          return `<tr>
            <td>${renderPMDashboardProjectLink(summary.projectName, summary.projectId)}<div class="muted">Next due: ${summary.nearestDue ? summary.nearestDue.toISOString().slice(0, 10) : "—"}</div></td>
            <td><span class="pill ${healthTone(summary.healthScore)}">${summary.healthScore}</span></td>
            <td>${summary.openSolutions}</td>
            <td>${summary.openSubcomponents}</td>
            <td>${hotspots || "<span class='muted'>None</span>"}</td>
          </tr>`;
        })
        .join("");
      els.pmDashboardHealth.innerHTML = `
        <div class="pm-card-header">
          <h3>Project Health</h3>
          <a href="${esc(hrefFor("master"))}" class="pm-card-link">Deliverables</a>
        </div>
        <div class="table pm-table-wrap">
          <table>
            <thead>
              <tr><th>Project</th><th>Health</th><th>Open Sol.</th><th>Open Tasks</th><th>Hotspots</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    }
  }

  if (els.pmDashboardRisks) {
    const rows = solutionRiskRows
      .slice(0, 12)
      .filter((row) => row.riskScore > 0)
      .map((row) => `<tr>
        <td>${renderPMDashboardSolutionLink(row.solutionName, row.solutionId)}<div class="muted">${esc(row.projectName)}</div></td>
        <td><span class="pill ${scoreTone(row.riskScore)}">${row.riskScore}</span></td>
        <td>${renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)}</td>
        <td>${isoDateLabel(row.dueDate)}</td>
        <td>${row.signals.map((signal) => `<span class="pm-signal">${esc(signal)}</span>`).join("") || "<span class='muted'>No strong signals</span>"}</td>
      </tr>`)
      .join("");
    els.pmDashboardRisks.innerHTML = `
      <div class="pm-card-header">
        <h3>Risk Radar</h3>
        <a href="${esc(hrefFor("master"))}" class="pm-card-link">Update Status</a>
      </div>
      ${rows
        ? `<div class="table pm-table-wrap"><table><thead><tr><th>Solution</th><th>Risk</th><th>Owner</th><th>Due</th><th>Signals</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : "<p class='muted'>No elevated solution risks detected.</p>"
      }
    `;
  }

  if (els.pmDashboardTimeline) {
    const rows = timelineFocusRows
      .map((row) => {
        const dueClass = row.days < 0 ? "danger" : row.days <= 7 ? "warn" : "muted";
        return `<tr>
          <td><span class="pm-item-kind">${esc(row.kind)}</span></td>
          <td>${renderPMDashboardTimelineLink(row)}<div class="muted">${esc(row.projectName)}${row.solutionName ? ` / ${esc(row.solutionName)}` : ""}</div></td>
          <td>${renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)}</td>
          <td>${isoDateLabel(row.dueDate)}</td>
          <td><span class="pill ${dueClass}">${esc(dueDeltaLabel(row.days))}</span></td>
        </tr>`;
      })
      .join("");
    els.pmDashboardTimeline.innerHTML = `
      <div class="pm-card-header">
        <h3>Delivery Timeline</h3>
        <a href="${esc(hrefFor("calendar"))}" class="pm-card-link">Calendar</a>
      </div>
      <p class="muted">Overdue: ${overdueTotal} | Due in 14 days: ${dueSoonTotal}</p>
      ${rows
        ? `<div class="table pm-table-wrap"><table><thead><tr><th>Type</th><th>Work Item</th><th>Owner</th><th>Due</th><th>Urgency</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : "<p class='muted'>No due dates in the next 30 days.</p>"
      }
    `;
  }

  if (els.pmDashboardCapacity) {
    const rows = capacityRows
      .slice(0, 12)
      .map((row) => {
        const tone = utilTone(row.utilization, row.capacity, row.allocated);
        const width = clamp(
          row.capacity > 0 ? row.utilization : row.allocated > 0 ? 100 : 0,
          0,
          160
        );
        const utilLabel = row.capacity > 0 ? `${Math.round(row.utilization)}%` : row.allocated > 0 ? "n/a" : "0%";
        return `<tr>
          <td>${renderPMDashboardCapacityLink(row)}</td>
          <td>${formatFteValue(row.capacity, formatFte)}</td>
          <td>${formatFteValue(row.allocated, formatFte)}</td>
          <td class="${row.gap < 0 ? "danger" : "positive"}">${row.gap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(row.gap), formatFte)}</td>
          <td>
            <div class="pm-util-meter"><span class="${tone}" style="width:${width}%;"></span></div>
            <div class="muted">${utilLabel}</div>
          </td>
        </tr>`;
      })
      .join("");

    els.pmDashboardCapacity.innerHTML = `
      <div class="pm-card-header">
        <h3>Capacity and Allocation</h3>
        <div class="pm-card-controls">
          <label class="pm-scope-control">
            <span>Month</span>
            <input type="month" value="${esc(selectedCapacityMonth)}" data-pm-dashboard-action="set-capacity-month" aria-label="Select capacity month" />
          </label>
          <a href="${esc(hrefFor("planning"))}" class="pm-card-link">Planning</a>
        </div>
      </div>
      <p class="muted">${esc(capacityScopeLabel)}</p>
      <p class="muted">Source: Planning task assignments only.</p>
      <div class="pm-capacity-summary">
        <div><span>Total Capacity</span><strong>${formatFteValue(totalCapacity, formatFte)} FTE-mo</strong></div>
        <div><span>Allocated</span><strong>${formatFteValue(totalAllocated, formatFte)} FTE-mo</strong></div>
        <div><span>Gap</span><strong class="${totalGap < 0 ? "danger" : "positive"}">${totalGap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(totalGap), formatFte)} FTE-mo</strong></div>
        <div><span>Overloaded</span><strong>${overloadedRows.length}</strong></div>
      </div>
      ${rows
        ? `<div class="table pm-table-wrap"><table><thead><tr><th>Assignee</th><th>Cap.</th><th>Alloc.</th><th>Gap</th><th>Load</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : "<p class='muted'>No allocations found for this scope.</p>"
      }
    `;
  }

  if (els.pmDashboardStatus) {
    const solutionTotal = Math.max(1, solutions.length);
    const subcomponentTotal = Math.max(1, subcomponents.length);
    const ragTotal = Math.max(1, ragCounts.red + ragCounts.amber + ragCounts.green + ragCounts.unknown);

    const renderStatusRows = (counts, total, orderedKeys) =>
      orderedKeys
        .map((status) => {
          const count = counts.get(status) || 0;
          const width = Math.round((count / total) * 100);
          return `<li>
            <span>${esc(formatStatus(status))}</span>
            <strong>${count}</strong>
            <div class="pm-mini-meter"><span style="width:${width}%;"></span></div>
          </li>`;
        })
        .join("");

    els.pmDashboardStatus.innerHTML = `
      <div class="pm-card-header">
        <h3>Portfolio Flow</h3>
        <a href="${esc(hrefFor("kanban"))}" class="pm-card-link">Kanban</a>
      </div>
      <div class="pm-status-grid">
        <section>
          <h4>Solutions by Status</h4>
          <ul class="pm-status-list">${renderStatusRows(solutionStatusCounts, solutionTotal, SOLUTION_STATUS_ORDER)}</ul>
        </section>
        <section>
          <h4>Tasks by Status</h4>
          <ul class="pm-status-list">${renderStatusRows(subcomponentStatusCounts, subcomponentTotal, SUBCOMPONENT_STATUS_ORDER)}</ul>
        </section>
      </div>
      <h4>Active Solution RAG Mix</h4>
      <div class="pm-rag-stack" role="img" aria-label="RAG distribution for active solutions">
        <span class="rag-red" style="width:${Math.round((ragCounts.red / ragTotal) * 100)}%;"></span>
        <span class="rag-amber" style="width:${Math.round((ragCounts.amber / ragTotal) * 100)}%;"></span>
        <span class="rag-green" style="width:${Math.round((ragCounts.green / ragTotal) * 100)}%;"></span>
        <span class="rag-unknown" style="width:${Math.round((ragCounts.unknown / ragTotal) * 100)}%;"></span>
      </div>
      <div class="pm-rag-legend">
        <span><i class="dot red"></i>Red ${ragCounts.red}</span>
        <span><i class="dot amber"></i>Amber ${ragCounts.amber}</span>
        <span><i class="dot green"></i>Green ${ragCounts.green}</span>
        <span><i class="dot unknown"></i>Unknown ${ragCounts.unknown}</span>
      </div>
    `;
  }

  if (els.pmDashboardActions) {
    const actionRows = actions
      .slice(0, 6)
      .map((action) => `<li class="pm-action-row ${action.tone}">
        <div>
          <div class="pm-action-title">${esc(action.title)}</div>
          <div class="muted">${esc(action.detail)}</div>
        </div>
        <a href="${esc(action.href)}" class="pm-action-link">${esc(action.cta)}</a>
      </li>`)
      .join("");
    els.pmDashboardActions.innerHTML = `
      <div class="pm-card-header">
        <h3>Immediate Actions</h3>
      </div>
      <ul class="pm-actions-list">${actionRows}</ul>
      <div class="pm-quick-links">
        <a href="${esc(hrefFor("master"))}">Deliverables</a>
        <a href="${esc(hrefFor("planning"))}">Planning</a>
        <a href="${esc(hrefFor("subcomponents-workbench"))}">Subcomponents</a>
        <a href="${esc(hrefFor("calendar"))}">Calendar</a>
      </div>
    `;
  }
}
