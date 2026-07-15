import {
  TASK_STATUS_ORDER,
  SOLUTION_STATUS_ORDER,
  buildPMDashboardOwnerDirectory,
  clamp,
  daysUntil,
  isClosedSolutionStatus,
  isClosedTaskStatus,
  nonEmpty,
  parseDate,
  startOfDay,
  resolvePMDashboardOwnerAssigneeKey,
} from "./analytics.js";
import { bindPMDashboardEvents } from "./interactions.js";
import { ensureActiveSection } from "./storage.js";
import {
  renderPMDashboardActionsSection,
  renderPMDashboardCapacitySection,
  renderPMDashboardHealthSection,
  renderPMDashboardRiskSection,
  renderPMDashboardStatusSection,
  renderPMDashboardSummarySection,
  renderPMDashboardTimelineSection,
} from "./sections.js";

const STALE_STATUS_DAYS = 7;
const PM_DASHBOARD_FOCUS_SECTIONS = [
  { id: "actions", label: "Immediate Actions", panelId: "pm-dashboard-actions", inputId: "pm-focus-actions" },
  { id: "health", label: "Project Health", panelId: "pm-dashboard-health", inputId: "pm-focus-health" },
  { id: "risks", label: "Risk Radar", panelId: "pm-dashboard-risks", inputId: "pm-focus-risks" },
  { id: "timeline", label: "Delivery Timeline", panelId: "pm-dashboard-timeline", inputId: "pm-focus-timeline" },
  { id: "capacity", label: "Capacity", panelId: "pm-dashboard-capacity", inputId: "pm-focus-capacity" },
  { id: "status", label: "Portfolio Flow", panelId: "pm-dashboard-status", inputId: "pm-focus-status" },
];

function isStaleStatusRecord(record, today) {
  if (record?.is_stale === true) return true;
  const updatedAt = parseDate(record?.updated_at);
  return !!updatedAt && daysUntil(updatedAt, today) > STALE_STATUS_DAYS;
}

function renderPMDashboardFocusNav(activeSection, metrics) {
  const nav = typeof document !== "undefined" ? document.getElementById("pm-dashboard-focus-nav") : null;
  if (!nav) return;
  const sectionMeta = {
    actions: {
      meta: `${metrics.actionCount} action${metrics.actionCount === 1 ? "" : "s"}`,
      tone: metrics.actionCount > 0 && metrics.hasCriticalAction ? "danger" : metrics.actionCount > 0 ? "warn" : "positive",
    },
    health: {
      meta: `${metrics.projectCount} project${metrics.projectCount === 1 ? "" : "s"}`,
      tone: metrics.atRiskSolutions > 0 ? "warn" : "positive",
    },
    risks: {
      meta: `${metrics.riskCount} elevated`,
      tone: metrics.riskCount > 0 ? "danger" : "positive",
    },
    timeline: {
      meta: `${metrics.overdueTotal} overdue`,
      tone: metrics.overdueTotal > 0 ? "danger" : metrics.dueSoonTotal > 0 ? "warn" : "positive",
    },
    capacity: {
      meta: `${metrics.overloadedCount} overloaded`,
      tone: metrics.overloadedCount > 0 ? "warn" : "positive",
    },
    status: {
      meta: `${metrics.staleTotal} stale`,
      tone: metrics.staleTotal > 0 ? "warn" : "positive",
    },
  };

  PM_DASHBOARD_FOCUS_SECTIONS.forEach((section) => {
    const isActive = section.id === activeSection;
    const meta = sectionMeta[section.id] || { meta: "", tone: "positive" };
    const label = document.getElementById(`pm-focus-label-${section.id}`);
    if (!label) return;
    label.classList.toggle("active", isActive);
    label.setAttribute("aria-current", isActive ? "page" : "false");
    label.innerHTML = `
      <span>${section.label}</span>
      <strong class="${meta.tone}">${meta.meta}</strong>
    `;
  });
}

function applyPMDashboardFocus(activeSection) {
  if (typeof document === "undefined") return;
  PM_DASHBOARD_FOCUS_SECTIONS.forEach((section) => {
    const input = document.getElementById(section.inputId);
    if (input instanceof HTMLInputElement) input.checked = section.id === activeSection;
    const panel = document.getElementById(section.panelId);
    if (!panel) return;
    const isActive = section.id === activeSection;
    panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    panel.classList.toggle("active", isActive);
  });
}

export function createPMDashboardState() {
  return {
    ctx: null,
    bound: false,
    activeSection: "",
    capacityScopeLabel: "",
    capacityMonth: "",
    capacitySpaceId: "",
  };
}

export function renderPMDashboardView(pmDashboardState, ctx) {
  const {
    state,
    els,
    formatStatus,
    viewHref,
    userCapacityFteMonth,
    formatFte,
  } = ctx;
  pmDashboardState.ctx = ctx;
  bindPMDashboardEvents(pmDashboardState, () => {
    if (pmDashboardState.ctx) renderPMDashboardView(pmDashboardState, pmDashboardState.ctx);
  });
  const activeSection = ensureActiveSection(pmDashboardState);
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
  const rawTasks = Array.isArray(state.tasks) ? state.tasks : [];
  const rawUsers = Array.isArray(state.users) ? state.users : [];

  const projectIds = new Set(rawProjects.map((project) => String(project?.project_id || "").trim()).filter(Boolean));
  const projects = rawProjects.filter((project) => projectIds.has(String(project?.project_id || "").trim()));

  const solutions = rawSolutions.filter((solution) => {
    const projectId = String(solution?.project_id || "").trim();
    return !!projectId && projectIds.has(projectId);
  });
  const solutionIds = new Set(solutions.map((solution) => String(solution?.solution_id || "").trim()).filter(Boolean));

  const tasks = rawTasks.filter((task) => {
    const projectId = String(task?.project_id || "").trim();
    const solutionId = String(task?.solution_id || "").trim();
    return !!projectId && !!solutionId && projectIds.has(projectId) && solutionIds.has(solutionId);
  });
  const users = [...rawUsers];
  const projectNameById = new Map(
    projects.map((project) => [project.project_id, project.project_name || "Unmapped Project"])
  );
  const solutionNameById = new Map(
    solutions.map((solution) => [solution.solution_id, solution.solution_name || "Unnamed Workstream"])
  );
  const ownerDirectory = buildPMDashboardOwnerDirectory(users);
  const today = startOfDay(new Date());

  const tasksByProject = new Map();
  const tasksBySolution = new Map();
  tasks.forEach((task) => {
    const projectBucket = tasksByProject.get(task.project_id) || [];
    projectBucket.push(task);
    tasksByProject.set(task.project_id, projectBucket);

    const solutionBucket = tasksBySolution.get(task.solution_id) || [];
    solutionBucket.push(task);
    tasksBySolution.set(task.solution_id, solutionBucket);
  });

  const activeSolutions = solutions.filter((solution) => !isClosedSolutionStatus(solution.status));
  const activeTasks = tasks.filter((task) => !isClosedTaskStatus(task.status));

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

  const overdueTasks = activeTasks.filter((task) => {
    const dueDate = parseDate(task.due_date);
    return !!dueDate && dueDate < today;
  });
  const dueSoonTasks = activeTasks.filter((task) => {
    const dueDate = parseDate(task.due_date);
    if (!dueDate) return false;
    const days = daysUntil(today, dueDate);
    return days >= 0 && days <= 14;
  });
  const blockedTasks = activeTasks.filter((task) => !!task.blocked);
  const unassignedTasks = activeTasks.filter(
    (task) => !nonEmpty(task.assignee) && !nonEmpty(task.assignee_user_soeid)
  );
  const staleSolutions = activeSolutions.filter((solution) => isStaleStatusRecord(solution, today));
  const staleTasks = activeTasks.filter((task) => isStaleStatusRecord(task, today));
  const staleTotal = staleSolutions.length + staleTasks.length;

  const projectSummaries = projects
    .map((project) => {
      const projectSolutions = solutions.filter((solution) => solution.project_id === project.project_id);
      const openSolutions = projectSolutions.filter((solution) => !isClosedSolutionStatus(solution.status));
      const projectTasks = tasksByProject.get(project.project_id) || [];
      const openTasks = projectTasks.filter((task) => !isClosedTaskStatus(task.status));

      const redCount = openSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "red").length;
      const amberCount = openSolutions.filter((solution) => String(solution.rag_status || "").toLowerCase() === "amber").length;
      const onHoldCount = openSolutions.filter((solution) => String(solution.status || "").toLowerCase() === "on_hold").length;
      const overdueSolutionCount = openSolutions.filter((solution) => {
        const dueDate = parseDate(solution.due_date);
        return !!dueDate && dueDate < today;
      }).length;
      const overdueTaskCount = openTasks.filter((task) => {
        const dueDate = parseDate(task.due_date);
        return !!dueDate && dueDate < today;
      }).length;
      const blockedCount = openTasks.filter((task) => !!task.blocked).length;
      const unassignedCount = openTasks.filter(
        (task) => !nonEmpty(task.assignee) && !nonEmpty(task.assignee_user_soeid)
      ).length;
      const staleCount =
        openSolutions.filter((solution) => isStaleStatusRecord(solution, today)).length
        + openTasks.filter((task) => isStaleStatusRecord(task, today)).length;
      const dueCandidates = [
        ...openSolutions.map((solution) => parseDate(solution.due_date)).filter(Boolean),
        ...openTasks.map((task) => parseDate(task.due_date)).filter(Boolean),
      ];
      const nearestDue = dueCandidates.length
        ? dueCandidates.sort((a, b) => a.getTime() - b.getTime())[0]
        : null;

      const riskScore = clamp(
        redCount * 28
          + amberCount * 14
          + onHoldCount * 10
          + overdueSolutionCount * 10
          + overdueTaskCount * 5
          + staleCount * 4
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
        openTasks: openTasks.length,
        redCount,
        amberCount,
        blockedCount,
        overdueCount: overdueSolutionCount + overdueTaskCount,
        staleCount,
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
      const linkedTasks = tasksBySolution.get(solution.solution_id) || [];
      const openLinkedTasks = linkedTasks.filter((task) => !isClosedTaskStatus(task.status));
      const blockedLinked = openLinkedTasks.filter((task) => !!task.blocked).length;
      const overdueLinked = openLinkedTasks.filter((task) => {
        const dueDate = parseDate(task.due_date);
        return !!dueDate && dueDate < today;
      }).length;

      let riskScore = 0;
      const signals = [];
      const rag = String(solution.rag_status || "").toLowerCase();
      const status = String(solution.status || "").toLowerCase();
      const dueDate = parseDate(solution.due_date);
      const dueDays = dueDate ? daysUntil(today, dueDate) : Number.NaN;
      const statusIsStale = isStaleStatusRecord(solution, today);

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
      if (statusIsStale) {
        riskScore += 10;
        signals.push("Status stale");
      }
      if (!nonEmpty(solution.owner) && !nonEmpty(solution.owner_user_soeid)) {
        riskScore += 8;
        signals.push("No owner");
      }
      if (blockedLinked > 0) {
        riskScore += Math.min(16, blockedLinked * 4);
        signals.push(`Blocked deliverables ${blockedLinked}`);
      }
      if (overdueLinked > 0) {
        riskScore += Math.min(16, overdueLinked * 4);
        signals.push(`Overdue deliverables ${overdueLinked}`);
      }
      riskScore = clamp(riskScore, 0, 100);

      return {
        solutionId: solution.solution_id,
        solutionName: solution.solution_name || "Unnamed Workstream",
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
          taskId: "",
          name: solution.solution_name || "Unnamed Workstream",
          projectName: projectNameById.get(solution.project_id) || "Unmapped Project",
          solutionName: "",
          owner: solution.owner || solution.owner_user_soeid || "Unassigned",
          ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(solution.owner_user_soeid, solution.owner, ownerDirectory),
          dueDate: solution.due_date,
          days,
        };
      }),
    ...activeTasks
      .filter((task) => !!task.due_date)
      .map((task) => {
        const dueDate = parseDate(task.due_date);
        const days = dueDate ? daysUntil(today, dueDate) : Number.NaN;
        return {
          itemKind: "task",
          kind: "Task",
          solutionId: task.solution_id,
          taskId: task.task_id,
          name: task.task_name || "Unnamed Deliverable",
          projectName: projectNameById.get(task.project_id) || "Unmapped Project",
          solutionName: solutionNameById.get(task.solution_id) || "Unmapped Workstream",
          owner: task.assignee || task.assignee_user_soeid || "Unassigned",
          ownerAssigneeKey: resolvePMDashboardOwnerAssigneeKey(
            task.assignee_user_soeid,
            task.assignee,
            ownerDirectory
          ),
          dueDate: task.due_date,
          days,
        };
      }),
  ]
    .filter((row) => Number.isFinite(row.days))
    .sort((a, b) => a.days - b.days || a.projectName.localeCompare(b.projectName));

  const timelineFocusRows = timelineRows.filter((row) => row.days <= 30).slice(0, 14);
  const overdueTotal = overdueSolutions.length + overdueTasks.length;
  const dueSoonTotal = dueSoonSolutions.length + dueSoonTasks.length;
  const userCapacity = typeof userCapacityFteMonth === "function"
    ? userCapacityFteMonth
    : (user) => {
      if (!user) return 1;
      const byFte = Number(user.capacity_fte_month);
      if (Number.isFinite(byFte)) return byFte;
      const byHours = Number(user.capacity_hours);
      return Number.isFinite(byHours) ? byHours / 40 : 1;
    };

  const capacityRows = users
    .filter((user) => user && user.is_active !== false && String(user.soeid || "").trim())
    .map((user) => ({
      key: String(user.soeid || "").trim(),
      label: String(user.display_name || user.soeid || "Unassigned"),
      capacity: Math.max(0, userCapacity(user)),
    }))
    .sort((a, b) => b.capacity - a.capacity || a.label.localeCompare(b.label));
  pmDashboardState.capacityScopeLabel = "";
  const overloadedRows = [];
  const totalCapacity = capacityRows.reduce((sum, row) => sum + row.capacity, 0);

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
  const taskStatusCounts = new Map(TASK_STATUS_ORDER.map((status) => [status, 0]));
  tasks.forEach((task) => {
    const status = String(task.status || "").toLowerCase();
    if (!taskStatusCounts.has(status)) taskStatusCounts.set(status, 0);
    taskStatusCounts.set(status, (taskStatusCounts.get(status) || 0) + 1);
  });

  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const nextMonthStart = new Date(today.getFullYear(), today.getMonth() + 1, 1);
  const completionsThisMonth = solutions.filter((solution) => {
    if (String(solution.status || "").toLowerCase() !== "complete") return false;
    const date = solution.completed_at ? new Date(solution.completed_at) : parseDate(solution.updated_at);
    return !!date && date >= monthStart && date < nextMonthStart;
  }).length + tasks.filter((task) => {
    if (String(task.status || "").toLowerCase() !== "complete") return false;
    const date = task.completed_at ? new Date(task.completed_at) : parseDate(task.updated_at);
    return !!date && date >= monthStart && date < nextMonthStart;
  }).length;

  const riskUnits =
    redSolutions.length * 7
    + amberSolutions.length * 4
    + onHoldSolutions.length * 3
    + overdueTotal * 2
    + blockedTasks.length * 2
    + unassignedTasks.length
    + staleTotal;
  const riskDenominator = Math.max(activeSolutions.length * 7 + activeTasks.length * 2, 1);
  const portfolioHealthScore = Math.round(clamp(100 - (riskUnits / riskDenominator) * 100, 0, 100));
  const atRiskSolutions = solutionRiskRows.filter((row) => row.riskScore >= 45).length;

  const actions = [];
  if (redSolutions.length > 0) {
    actions.push({
      tone: "danger",
      title: `${redSolutions.length} red workstreams need intervention`,
      detail: "Review health reasons and assign recovery owners.",
      href: hrefFor("master"),
      cta: "Open Work List",
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
  if (blockedTasks.length > 0) {
    actions.push({
      tone: "warn",
      title: `${blockedTasks.length} blocked deliverables are stalling flow`,
      detail: "Clear blocker notes and escalate dependency owners.",
      href: hrefFor("tasks-workbench"),
      cta: "Open Deliverables",
    });
  }
  if (unassignedTasks.length > 0) {
    actions.push({
      tone: "warn",
      title: `${unassignedTasks.length} active deliverables are unassigned`,
      detail: "Assign owners so execution can start and status can move.",
      href: hrefFor("tasks-workbench"),
      cta: "Assign Deliverables",
    });
  }
  if (staleTotal > 0) {
    actions.push({
      tone: "warn",
      title: `${staleTotal} records need status refresh`,
      detail: "Refresh stale work before leadership review.",
      href: hrefFor("master"),
      cta: "Review Status",
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

  renderPMDashboardFocusNav(activeSection, {
    actionCount: actions.length,
    hasCriticalAction: actions.some((action) => action.tone === "danger"),
    projectCount: projectSummaries.length,
    atRiskSolutions,
    riskCount: solutionRiskRows.filter((row) => row.riskScore > 0).length,
    overdueTotal,
    dueSoonTotal,
    overloadedCount: overloadedRows.length,
    staleTotal,
  });

  renderPMDashboardSummarySection({
    els,
    activeSpaceLabel,
    portfolioHealthScore,
    activeSolutionsCount: activeSolutions.length,
    atRiskSolutions,
    activeTasksCount: activeTasks.length,
    blockedTasksCount: blockedTasks.length,
    unassignedTasksCount: unassignedTasks.length,
    overdueTotal,
    dueSoonTotal,
    staleTotal,
    staleStatusDays: STALE_STATUS_DAYS,
    totalCapacity,
    completionsThisMonth,
    formatFte,
  });
  renderPMDashboardHealthSection({ els, projectSummaries, hrefFor });
  renderPMDashboardRiskSection({ els, solutionRiskRows, hrefFor });
  renderPMDashboardTimelineSection({
    els,
    timelineFocusRows,
    overdueTotal,
    dueSoonTotal,
    hrefFor,
  });
  renderPMDashboardCapacitySection({
    els,
    capacityRows,
    totalCapacity,
    formatFte,
  });
  renderPMDashboardStatusSection({
    els,
    solutions,
    tasks,
    ragCounts,
    solutionStatusCounts,
    taskStatusCounts,
    formatStatus,
    hrefFor,
  });
  renderPMDashboardActionsSection({ els, actions, hrefFor });
  applyPMDashboardFocus(activeSection);
}
