import {
  dayNumberToDate,
  dayNumberToIso,
  parseDateOnly,
  todayDayNumber,
} from "../utils/date-only.js";

const LONG_RANGE_DAY_WIDTH = 3.5;
const DEFAULT_LEFT_RAIL_WIDTH = 620;
const MOBILE_LEFT_RAIL_WIDTH = 560;
const MIN_TRACK_WIDTH = 520;
const FIT_WINDOW_MAX_DAYS = 366;
const MILESTONE_SIZE = 9;
const GANTT_DUE_SOON_DAYS = 7;

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseDateParts(value) {
  return parseDateOnly(value);
}

function dayToDate(dayNumber) {
  return dayNumberToDate(dayNumber);
}

function dayToIso(dayNumber) {
  return dayNumberToIso(dayNumber);
}

function formatMonthLabel(dayNumber) {
  const d = dayToDate(dayNumber);
  return d.toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" });
}

function normalizeRange(startValue, endValue, { milestone = false } = {}) {
  const start = parseDateParts(startValue);
  const end = parseDateParts(endValue);
  if (!start && !end) return null;
  const first = start || end;
  const last = end || start;
  const startDay = Math.min(first.dayNumber, last.dayNumber);
  const endDay = Math.max(first.dayNumber, last.dayNumber);
  return {
    startDay,
    endDay,
    startIso: dayToIso(startDay),
    endIso: dayToIso(endDay),
    milestone: milestone || !start || !end || startDay === endDay,
  };
}

function mergeRanges(ranges) {
  const valid = (ranges || []).filter(Boolean);
  if (!valid.length) return null;
  const startDay = Math.min(...valid.map((range) => range.startDay));
  const endDay = Math.max(...valid.map((range) => range.endDay));
  return {
    startDay,
    endDay,
    startIso: dayToIso(startDay),
    endIso: dayToIso(endDay),
    milestone: startDay === endDay,
  };
}

export function dateRangesOverlap(startDay, endDay, windowStartDay, windowEndDay) {
  return startDay <= windowEndDay && endDay >= windowStartDay;
}

function rangeOverlapsWindow(range, windowRange) {
  return !!(
    range
    && windowRange
    && dateRangesOverlap(range.startDay, range.endDay, windowRange.startDay, windowRange.endDay)
  );
}

function sortByName(items, fieldName) {
  return [...(items || [])].sort((a, b) => String(a?.[fieldName] || "").localeCompare(String(b?.[fieldName] || "")));
}

function labelRange(range) {
  if (!range) return "";
  return range.startIso === range.endIso ? range.startIso : `${range.startIso} - ${range.endIso}`;
}

function displayValue(value) {
  return String(value ?? "").trim();
}

function priorityLabel(value) {
  const raw = displayValue(value);
  return raw ? `P${raw}` : "";
}

function statusClassName(value) {
  const key = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return key ? ` gantt-status-${key}` : "";
}

function renderFieldValue(value, emptyLabel = "No value") {
  const text = displayValue(value);
  if (!text) return `<span class="gantt-empty-value" aria-label="${esc(emptyLabel)}">&mdash;</span>`;
  return esc(text);
}

function renderChipValue(value, className, emptyLabel = "No value") {
  const text = displayValue(value);
  if (!text) return `<span class="gantt-empty-value" aria-label="${esc(emptyLabel)}">&mdash;</span>`;
  return `<span class="${className}">${esc(text)}</span>`;
}

function normalizeWindow(ganttWindow) {
  const start = parseDateParts(ganttWindow?.from);
  const end = parseDateParts(ganttWindow?.to);
  if (!start || !end || start.dayNumber > end.dayNumber) return null;
  return {
    startDay: start.dayNumber,
    endDay: end.dayNumber,
    from: start.iso,
    to: end.iso,
    totalDays: end.dayNumber - start.dayNumber + 1,
  };
}

function measureElementWidth(el) {
  const rectWidth = typeof el?.getBoundingClientRect === "function" ? el.getBoundingClientRect().width : 0;
  const width = rectWidth || el?.clientWidth || 0;
  return Number.isFinite(width) ? Math.floor(width) : 0;
}

function currentLeftRailWidth() {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia("(max-width: 900px)").matches ? MOBILE_LEFT_RAIL_WIDTH : DEFAULT_LEFT_RAIL_WIDTH;
  }
  return DEFAULT_LEFT_RAIL_WIDTH;
}

function px(value) {
  return Number(value || 0).toFixed(2).replace(/\.?0+$/, "");
}

function normalizeGanttStatus(value) {
  return String(value || "").trim().toLowerCase();
}

function isClosedGanttStatus(value) {
  const status = normalizeGanttStatus(value);
  return status === "complete" || status === "abandoned";
}

function isNotStartedGanttStatus(value) {
  const status = normalizeGanttStatus(value);
  return status === "not_started" || status === "to_do";
}

function isActiveGanttStatus(value) {
  const status = normalizeGanttStatus(value);
  return status === "active" || status === "in_progress";
}

function isGanttRangeOverdue(range, todayDay) {
  return !!range && range.endDay < todayDay;
}

function isGanttItemOverdue(status, range, todayDay) {
  return !isClosedGanttStatus(status) && isGanttRangeOverdue(range, todayDay);
}

function healthResult(health, healthLabel, healthReason = "") {
  return { health, healthLabel, healthReason };
}

export function resolveGanttHealth(row = {}, { todayDay = todayDayNumber(), dueSoonDays = GANTT_DUE_SOON_DAYS } = {}) {
  const status = normalizeGanttStatus(row.status);
  const range = row.scheduleRange || row.range || null;
  const currentDay = Number.isFinite(Number(todayDay)) ? Number(todayDay) : todayDayNumber();
  const warningDays = Number.isFinite(Number(dueSoonDays)) ? Number(dueSoonDays) : GANTT_DUE_SOON_DAYS;

  if (status === "complete") {
    return healthResult("complete", "Complete", "Closed complete");
  }
  if (status === "abandoned") {
    return healthResult("abandoned", "Abandoned", "Closed abandoned");
  }
  if (isGanttRangeOverdue(range, currentDay)) {
    return healthResult("red", "Overdue", "Past due date");
  }
  if ((row.type === "project" || row.type === "solution") && row.hasOverdueChild) {
    return healthResult("yellow", "Child overdue", "Underlying item is overdue");
  }
  if (status === "on_hold") {
    return healthResult("yellow", "On hold", "Work is on hold");
  }
  if (isNotStartedGanttStatus(status)) {
    if (range) {
      const daysToStart = range.startDay - currentDay;
      const daysToDue = range.endDay - currentDay;
      if (daysToStart <= warningDays || daysToDue <= warningDays) {
        return healthResult("yellow", "Due soon", "Not started and approaching schedule");
      }
    }
    return healthResult("future", "Future", "Planned for later");
  }
  if (isActiveGanttStatus(status)) {
    return healthResult("green", "On time", "Active and on time");
  }
  return healthResult("green", "On time", "No schedule alert");
}

function withGanttHealth(row, todayDay) {
  return {
    ...row,
    ...resolveGanttHealth(row, { todayDay }),
  };
}

function markOverdue(map, key) {
  const normalizedKey = String(key || "__unassigned__").trim() || "__unassigned__";
  map.set(normalizedKey, true);
}

function buildGanttHealthContext({ solutions = [], tasks = [], todayDay = todayDayNumber() } = {}) {
  const overdueTasksBySolution = new Map();
  const overdueChildrenByProject = new Map();

  (tasks || []).forEach((task) => {
    const range = normalizeRange(task?.due_date, task?.due_date, { milestone: true });
    if (!isGanttItemOverdue(task?.status, range, todayDay)) return;
    if (task?.solution_id) markOverdue(overdueTasksBySolution, task.solution_id);
    markOverdue(overdueChildrenByProject, task?.project_id);
  });

  (solutions || []).forEach((solution) => {
    const range = normalizeRange(solution?.planned_start_date, solution?.due_date);
    if (!isGanttItemOverdue(solution?.status, range, todayDay)) return;
    markOverdue(overdueChildrenByProject, solution?.project_id);
  });

  return {
    solutionHasOverdueChild(solutionId) {
      return overdueTasksBySolution.get(String(solutionId || "").trim()) === true;
    },
    projectHasOverdueChild(projectId) {
      const key = String(projectId || "__unassigned__").trim() || "__unassigned__";
      return overdueChildrenByProject.get(key) === true;
    },
  };
}

export function resolveGanttTimelineScale(windowRange, chartWidth = 0, leftRailWidth = DEFAULT_LEFT_RAIL_WIDTH) {
  const totalDays = Math.max(1, Number(windowRange?.totalDays || 0));
  const measuredWidth = Math.max(0, Number(chartWidth) || 0);
  const availableTrackWidth = Math.max(0, measuredWidth - leftRailWidth - 2);
  const fitToArea = totalDays <= FIT_WINDOW_MAX_DAYS && availableTrackWidth > 0;

  if (fitToArea) {
    return {
      dayWidth: availableTrackWidth / totalDays,
      trackWidth: availableTrackWidth,
      leftRailWidth,
      fitToArea,
    };
  }

  const trackWidth = Math.max(totalDays * LONG_RANGE_DAY_WIDTH, availableTrackWidth, MIN_TRACK_WIDTH);
  return {
    dayWidth: trackWidth / totalDays,
    trackWidth,
    leftRailWidth,
    fitToArea,
  };
}

function buildTaskNode(task, windowRange, todayDay) {
  const range = normalizeRange(task?.due_date, task?.due_date, { milestone: true });
  if (!rangeOverlapsWindow(range, windowRange)) return null;
  return withGanttHealth({
    type: "task",
    id: task.task_id,
    key: `task:${task.task_id}`,
    projectId: task.project_id,
    solutionId: task.solution_id,
    label: task.task_name || "Untitled task",
    assignee: task.assignee || task.assignee_user_soeid || "Unassigned",
    status: task.status || "",
    priority: task.priority ?? "",
    range,
    scheduleRange: range,
    milestone: true,
    collapsible: false,
    childCount: 0,
    children: [],
    hasOverdueChild: false,
  }, todayDay);
}

function buildSolutionNode(solution, childNodes, windowRange, healthContext, todayDay) {
  const ownRange = normalizeRange(solution?.planned_start_date, solution?.due_date);
  const ownOverlaps = rangeOverlapsWindow(ownRange, windowRange);
  if (!ownOverlaps && !childNodes.length) return null;
  const range = mergeRanges([ownOverlaps ? ownRange : null, ...childNodes.map((child) => child.range)]);
  const scheduleRange = ownRange || range;
  return withGanttHealth({
    type: "solution",
    id: solution.solution_id,
    key: `solution:${solution.solution_id}`,
    projectId: solution.project_id,
    label: solution.solution_name || "Untitled solution",
    assignee: solution.assignee || solution.owner || solution.assignee_user_soeid || solution.owner_user_soeid || "Unassigned",
    status: solution.status || "",
    priority: solution.priority ?? "",
    range,
    scheduleRange,
    milestone: range?.milestone && !childNodes.length,
    collapsible: childNodes.length > 0,
    childCount: childNodes.length,
    children: childNodes,
    hasOverdueChild: healthContext.solutionHasOverdueChild(solution.solution_id),
  }, todayDay);
}

function buildProjectNode(project, childNodes, healthContext, todayDay) {
  if (!childNodes.length) return null;
  const range = mergeRanges(childNodes.map((child) => child.range));
  return withGanttHealth({
    type: "project",
    id: project.project_id,
    key: `project:${project.project_id}`,
    label: project.project_name || "Untitled project",
    assignee: project.sponsor || project.sponsor_user_soeid || "Unassigned",
    status: project.status || "",
    priority: project.priority ?? "",
    range,
    scheduleRange: range,
    milestone: range?.milestone,
    collapsible: childNodes.length > 0,
    childCount: childNodes.length,
    children: childNodes,
    hasOverdueChild: healthContext.projectHasOverdueChild(project.project_id),
  }, todayDay);
}

function flattenProject(projectNode, collapsedKeys) {
  const rows = [{ ...projectNode, depth: 0, collapsed: collapsedKeys.has(projectNode.key) }];
  if (collapsedKeys.has(projectNode.key)) return rows;
  projectNode.children.forEach((solutionNode) => {
    rows.push({ ...solutionNode, depth: 1, collapsed: collapsedKeys.has(solutionNode.key) });
    if (!collapsedKeys.has(solutionNode.key)) {
      solutionNode.children.forEach((childNode) => rows.push({ ...childNode, depth: 2, collapsed: false }));
    }
  });
  return rows;
}

export function buildGanttRows({
  projects = [],
  solutions = [],
  tasks = [],
  ganttWindow = {},
  collapsedKeys = new Set(),
  todayDay = todayDayNumber(),
} = {}) {
  const windowRange = normalizeWindow(ganttWindow);
  if (!windowRange) return { rows: [], projectNodes: [], windowRange: null };
  const healthContext = buildGanttHealthContext({ solutions, tasks, todayDay });

  const tasksBySolution = new Map();
  sortByName(tasks, "task_name").forEach((task) => {
    const node = buildTaskNode(task, windowRange, todayDay);
    if (!node) return;
    const bucket = tasksBySolution.get(task.solution_id) || [];
    bucket.push(node);
    tasksBySolution.set(task.solution_id, bucket);
  });

  const solutionsByProject = new Map();
  sortByName(solutions, "solution_name").forEach((solution) => {
    const childNodes = tasksBySolution.get(solution.solution_id) || [];
    const node = buildSolutionNode(solution, childNodes, windowRange, healthContext, todayDay);
    if (!node) return;
    const projectId = solution.project_id || "__unassigned__";
    const bucket = solutionsByProject.get(projectId) || [];
    bucket.push(node);
    solutionsByProject.set(projectId, bucket);
  });

  const projectNodes = [];
  const seenProjectIds = new Set();
  sortByName(projects, "project_name").forEach((project) => {
    const childNodes = solutionsByProject.get(project.project_id) || [];
    const node = buildProjectNode(project, childNodes, healthContext, todayDay);
    if (!node) return;
    seenProjectIds.add(project.project_id);
    projectNodes.push(node);
  });

  Array.from(solutionsByProject.entries())
    .filter(([projectId]) => !seenProjectIds.has(projectId))
    .sort(([a], [b]) => String(a).localeCompare(String(b)))
    .forEach(([projectId, childNodes]) => {
      const node = buildProjectNode(
        {
          project_id: projectId,
          project_name: "Unassigned Project",
          sponsor: "",
        },
        childNodes,
        healthContext,
        todayDay
      );
      if (node) projectNodes.push(node);
    });

  return {
    rows: projectNodes.flatMap((projectNode) => flattenProject(projectNode, collapsedKeys)),
    projectNodes,
    windowRange,
  };
}

function renderToggle(row) {
  if (!row.collapsible) return `<span class="gantt-toggle-spacer" aria-hidden="true"></span>`;
  const label = row.collapsed ? "Expand" : "Collapse";
  return `<button type="button" class="gantt-toggle" data-gantt-action="toggle-collapse" data-gantt-key="${esc(row.key)}" aria-label="${label} ${esc(row.label)}">${row.collapsed ? "+" : "-"}</button>`;
}

function renderItemLabel(row, formatStatus) {
  const typeLabel = row.type === "task" ? "Task" : row.type === "solution" ? "Solution" : "Project";
  const statusText = row.status ? formatStatus(row.status) : "";
  const priorityText = priorityLabel(row.priority);
  return `<div class="gantt-label-content gantt-depth-${row.depth}">
    <div class="gantt-item-cell">
      ${renderToggle(row)}
      <span class="gantt-level-marker" aria-hidden="true"></span>
      <button type="button" class="gantt-item-link" data-gantt-action="open-item" data-gantt-type="${esc(row.type)}" data-gantt-id="${esc(row.id)}" title="${esc(row.label)}" aria-label="Open ${esc(typeLabel)} ${esc(row.label)}">
        <span class="gantt-title">${esc(row.label)}</span>
      </button>
    </div>
    <div class="gantt-row-field gantt-assignee-cell">${renderFieldValue(row.assignee, "No assignee")}</div>
    <div class="gantt-row-field gantt-status-cell">${renderChipValue(statusText, `gantt-status-pill${statusClassName(row.status)}`, "No status")}</div>
    <div class="gantt-row-field gantt-priority-cell">${renderChipValue(priorityText, "gantt-priority-pill", "No priority")}</div>
  </div>`;
}

function renderBar(row, windowRange, scale) {
  const dayWidth = scale.dayWidth;
  const clippedStart = Math.max(row.range.startDay, windowRange.startDay);
  const clippedEnd = Math.min(row.range.endDay, windowRange.endDay);
  const left = (clippedStart - windowRange.startDay) * dayWidth;
  const width = Math.max((clippedEnd - clippedStart + 1) * dayWidth, MILESTONE_SIZE);
  const dateText = labelRange(row.range);
  const healthText = row.healthLabel ? ` (${row.healthLabel})` : "";
  const healthClass = row.health ? ` gantt-health-${esc(row.health)}` : "";
  const attrs = `data-gantt-action="open-item" data-gantt-type="${esc(row.type)}" data-gantt-id="${esc(row.id)}"`;
  if (row.milestone) {
    const milestoneLeft = left + Math.max((width - MILESTONE_SIZE) / 2, 0);
    return `<button type="button" class="gantt-milestone gantt-milestone-${esc(row.type)}${healthClass}" style="left: ${px(milestoneLeft)}px;" ${attrs} title="${esc(row.label)}: ${esc(dateText)}${esc(healthText)}" aria-label="Open ${esc(row.label)}${esc(healthText)}"></button>`;
  }
  const barLabel = width >= 72 ? `<span>${esc(dateText)}</span>` : "";
  return `<button type="button" class="gantt-bar gantt-bar-${esc(row.type)}${healthClass}" style="left: ${px(left)}px; width: ${px(width)}px;" ${attrs} title="${esc(row.label)}: ${esc(dateText)}${esc(healthText)}" aria-label="Open ${esc(row.label)}${esc(healthText)}">
    ${barLabel}
  </button>`;
}

function renderMonthTicks(windowRange, scale) {
  const dayWidth = scale.dayWidth;
  const ticks = [];
  let currentStart = windowRange.startDay;
  for (let day = windowRange.startDay; day <= windowRange.endDay; day += 1) {
    const d = dayToDate(day);
    if (day > windowRange.startDay && d.getUTCDate() === 1) {
      const tickEnd = day - 1;
      const left = (currentStart - windowRange.startDay) * dayWidth;
      const width = (tickEnd - currentStart + 1) * dayWidth;
      ticks.push(`<div class="gantt-month-tick" style="left: ${px(left)}px; width: ${px(width)}px;">${esc(formatMonthLabel(currentStart))}</div>`);
      currentStart = day;
    }
    if (day === windowRange.endDay) {
      const left = (currentStart - windowRange.startDay) * dayWidth;
      const width = (day - currentStart + 1) * dayWidth;
      ticks.push(`<div class="gantt-month-tick" style="left: ${px(left)}px; width: ${px(width)}px;">${esc(formatMonthLabel(currentStart))}</div>`);
    }
  }
  return ticks.join("");
}

function renderWeekTicks(windowRange, scale) {
  const dayWidth = scale.dayWidth;
  if (dayWidth < 4.5) return "";
  const ticks = [];
  for (let day = windowRange.startDay; day <= windowRange.endDay; day += 1) {
    const date = dayToDate(day);
    const isFirst = day === windowRange.startDay;
    if (!isFirst && date.getUTCDay() !== 1) continue;
    const left = (day - windowRange.startDay) * dayWidth;
    const label = `${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
    ticks.push(`<div class="gantt-week-tick" style="left: ${px(left)}px;">${esc(label)}</div>`);
  }
  return ticks.join("");
}

function renderTodayMarker(windowRange, scale) {
  const day = todayDayNumber();
  if (day < windowRange.startDay || day > windowRange.endDay) return "";
  const left = (day - windowRange.startDay) * scale.dayWidth + scale.dayWidth / 2;
  return `<div class="gantt-today-marker" style="left: ${px(left)}px;" title="Today" aria-hidden="true"></div>`;
}

function countRowsByType(rows) {
  return rows.reduce(
    (counts, row) => {
      counts[row.type] = (counts[row.type] || 0) + 1;
      return counts;
    },
    { project: 0, solution: 0, task: 0 }
  );
}

export function renderGantt(ctx) {
  const { state, els, formatStatus = (value) => value } = ctx;
  if (!els.ganttChart) return;
  if (els.ganttFrom) els.ganttFrom.value = state.ganttWindow?.from || "";
  if (els.ganttTo) els.ganttTo.value = state.ganttWindow?.to || "";

  const { rows, windowRange } = buildGanttRows({
    projects: state.projects,
    solutions: state.solutions,
    tasks: state.tasks,
    ganttWindow: state.ganttWindow,
    collapsedKeys: state.ganttCollapsed,
  });

  if (!windowRange) {
    els.ganttChart.innerHTML = `<div class="gantt-empty">Select a valid Gantt date range.</div>`;
    return;
  }

  const scale = resolveGanttTimelineScale(windowRange, measureElementWidth(els.ganttChart), currentLeftRailWidth());
  const trackWidth = scale.trackWidth;
  if (!rows.length) {
    els.ganttChart.innerHTML = `<div class="gantt-empty">No scheduled items overlap ${esc(windowRange.from)} - ${esc(windowRange.to)}.</div>`;
    return;
  }

  const counts = countRowsByType(rows);
  const todayMarker = renderTodayMarker(windowRange, scale);
  const rowHtml = rows
    .map((row) => `<div class="gantt-row gantt-row-${esc(row.type)}" data-gantt-row-key="${esc(row.key)}">
      <div class="gantt-label-cell">${renderItemLabel(row, formatStatus)}</div>
      <div class="gantt-track-cell">
        <div class="gantt-track" style="width: ${px(trackWidth)}px;">${todayMarker}${renderBar(row, windowRange, scale)}</div>
      </div>
    </div>`)
    .join("");

  els.ganttChart.innerHTML = `
    <div class="gantt-summary">
      <div class="gantt-summary-main">
        <span class="gantt-summary-title">Scheduled Work</span>
        <span class="gantt-summary-window">${esc(windowRange.from)} - ${esc(windowRange.to)}</span>
      </div>
      <div class="gantt-summary-metrics" aria-label="Visible Gantt rows">
        <span><strong>${counts.project}</strong> Projects</span>
        <span><strong>${counts.solution}</strong> Solutions</span>
        <span><strong>${counts.task}</strong> Tasks</span>
      </div>
    </div>
    <div class="gantt-scroll" style="--gantt-left-width: ${px(scale.leftRailWidth)}px; --gantt-track-width: ${px(trackWidth)}px; --gantt-day-width: ${px(scale.dayWidth)}px; --gantt-week-width: ${px(scale.dayWidth * 7)}px;">
      <div class="gantt-row gantt-header-row">
        <div class="gantt-label-cell gantt-header-label">
          <div class="gantt-left-header">
            <span>Deliverable</span>
            <span>Assignee</span>
            <span>Status</span>
            <span>Priority</span>
          </div>
        </div>
        <div class="gantt-track-cell gantt-header-track">
          <div class="gantt-track gantt-time-header" style="width: ${px(trackWidth)}px;">
            ${todayMarker}
            ${renderMonthTicks(windowRange, scale)}
            ${renderWeekTicks(windowRange, scale)}
          </div>
        </div>
      </div>
      ${rowHtml}
    </div>
  `;
}

export function render(ctx) {
  renderGantt(ctx);
}
