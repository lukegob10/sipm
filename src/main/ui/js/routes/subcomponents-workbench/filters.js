export const VALID_SUBCOMPONENTS_WORKBENCH_PRESETS = new Set([
  "all",
  "my",
  "due_soon",
  "overdue",
  "blocked",
  "unassigned",
  "stale",
]);

export const VALID_SUBCOMPONENTS_WORKBENCH_STATUSES = new Set([
  "",
  "not_started",
  "to_do",
  "in_progress",
  "on_hold",
  "complete",
  "abandoned",
]);

function hideClosedSubcomponentsWorkbench(ctx) {
  const { state, showCompletedOperationalWork, requestsClosedStatuses } = ctx;
  return !showCompletedOperationalWork() && !requestsClosedStatuses(state.subcomponentsWorkbench?.filters?.status);
}

export function subcomponentsWorkbenchRows(ctx) {
  const { state, deriveSubcomponentActionability, normalize, isCompletedSubcomponentStatus, numberOr } = ctx;
  const wb = state.subcomponentsWorkbench;
  const rows = (state.subcomponents || []).map((subcomponent) => {
    const project = state.projects.find((row) => row.project_id === subcomponent.project_id);
    const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id);
    return {
      ...subcomponent,
      ...deriveSubcomponentActionability(subcomponent),
      project_name: project?.project_name || "",
      solution_name: solution?.solution_name || "",
    };
  });

  const filters = wb.filters || {};
  const search = normalize(filters.search);
  const userName = normalize(state.user?.display_name);
  const userSoeid = normalize(state.user?.soeid);

  const visible = rows.filter((row) => {
    if (hideClosedSubcomponentsWorkbench(ctx) && isCompletedSubcomponentStatus(row.status)) return false;
    if (filters.project_id && row.project_id !== filters.project_id) return false;
    if (filters.solution_id && row.solution_id !== filters.solution_id) return false;
    if (filters.status && row.status !== filters.status) return false;
    if (filters.priority_max && Number(row.priority || 999) > Number(filters.priority_max)) return false;
    if (filters.assignee) {
      if (filters.assignee === "__unassigned__") {
        if (String(row.assignee || "").trim() || row.assignee_user_soeid) return false;
      } else {
        const assigneeId = normalize(row.assignee_user_soeid);
        const assigneeName = normalize(row.assignee);
        if (assigneeId !== normalize(filters.assignee) && assigneeName !== normalize(filters.assignee_name)) return false;
      }
    }

    if (search) {
      const blob = [
        row.subcomponent_name,
        row.project_name,
        row.solution_name,
        row.assignee,
        row.status,
      ]
        .map((value) => normalize(value))
        .join(" ");
      if (!blob.includes(search)) return false;
    }

    switch (wb.preset) {
      case "my": {
        const assigneeId = normalize(row.assignee_user_soeid);
        const assigneeName = normalize(row.assignee);
        const matchesSelf = (userSoeid && assigneeId === userSoeid) || (userName && assigneeName === userName);
        if (!matchesSelf) return false;
        break;
      }
      case "due_soon":
        if (!row.is_due_soon) return false;
        break;
      case "overdue":
        if (!row.is_overdue) return false;
        break;
      case "blocked":
        if (!row.blocked) return false;
        break;
      case "unassigned":
        if (String(row.assignee || "").trim() || row.assignee_user_soeid) return false;
        break;
      case "stale":
        if (!row.is_stale) return false;
        break;
      default:
        break;
    }
    return true;
  });

  visible.sort((a, b) => {
    const urgencyDiff = numberOr(b.urgency_score, 0) - numberOr(a.urgency_score, 0);
    if (urgencyDiff !== 0) return urgencyDiff;
    const dueA = a.due_date ? new Date(`${a.due_date}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
    const dueB = b.due_date ? new Date(`${b.due_date}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
    if (dueA !== dueB) return dueA - dueB;
    const priorityDiff = numberOr(a.priority, 99) - numberOr(b.priority, 99);
    if (priorityDiff !== 0) return priorityDiff;
    return String(a.subcomponent_name || "").localeCompare(String(b.subcomponent_name || ""));
  });

  wb.visibleIds = visible.map((row) => row.subcomponent_id);
  return { allRows: rows, visibleRows: visible };
}

export function subcomponentsWorkbenchSummary(ctx, allRows, visibleRows) {
  const { isCompletedSubcomponentStatus } = ctx;
  const rows = allRows || [];
  return {
    total: rows.length,
    visible: (visibleRows || []).length,
    hiddenClosed: hideClosedSubcomponentsWorkbench(ctx)
      ? rows.filter((row) => isCompletedSubcomponentStatus(row.status)).length
      : 0,
    overdue: rows.filter((row) => row.is_overdue).length,
    dueSoon: rows.filter((row) => row.is_due_soon).length,
    blocked: rows.filter((row) => row.blocked).length,
    unassigned: rows.filter((row) => !String(row.assignee || "").trim() && !row.assignee_user_soeid).length,
  };
}

export function updateSubcomponentsWorkbenchPresetButtons(ctx) {
  const { state } = ctx;
  const wb = state.subcomponentsWorkbench;
  document.querySelectorAll(".scwb-preset").forEach((btn) => {
    const preset = btn.getAttribute("data-preset") || "";
    const active = preset === wb.preset;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

export function updateSubcomponentsWorkbenchSelectionCount(ctx) {
  const { state, els } = ctx;
  if (!els.subcomponentsWorkbenchSelectionCount) return;
  const count = state.subcomponentsWorkbench.selected.size;
  els.subcomponentsWorkbenchSelectionCount.textContent = `${count} selected`;
  if (els.subcomponentsWorkbenchBulkApply) {
    const action = els.subcomponentsWorkbenchBulkAction?.value || "";
    const hasActiveDeleteTarget = action === "delete" && !!state.subcomponentsWorkbench.activeSubcomponentId;
    els.subcomponentsWorkbenchBulkApply.disabled = !action || (!count && !hasActiveDeleteTarget);
  }
}

export function normalizeSubcomponentsWorkbenchPriorityFilter(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 5) return "";
  return String(parsed);
}

export function normalizeSubcomponentsWorkbenchFilters(ctx, filters = {}) {
  const { state } = ctx;
  const next = {
    search: String(filters.search || ""),
    project_id: String(filters.project_id || ""),
    solution_id: String(filters.solution_id || ""),
    assignee: String(filters.assignee || ""),
    assignee_name: String(filters.assignee_name || ""),
    status: String(filters.status || ""),
    priority_max: normalizeSubcomponentsWorkbenchPriorityFilter(filters.priority_max),
  };
  let changed = next.priority_max !== String(filters.priority_max || "");

  if (!VALID_SUBCOMPONENTS_WORKBENCH_STATUSES.has(next.status)) {
    next.status = "";
    changed = true;
  }

  if (state.loadedEntities?.has("projects")) {
    const validProjectIds = new Set((state.projects || []).map((project) => project.project_id));
    if (next.project_id && !validProjectIds.has(next.project_id)) {
      next.project_id = "";
      changed = true;
    }
  }

  if (state.loadedEntities?.has("solutions")) {
    const filteredSolutions = next.project_id
      ? (state.solutions || []).filter((solution) => solution.project_id === next.project_id)
      : (state.solutions || []);
    const validSolutionIds = new Set(filteredSolutions.map((solution) => solution.solution_id));
    if (next.solution_id && !validSolutionIds.has(next.solution_id)) {
      next.solution_id = "";
      changed = true;
    }
  }

  if (state.loadedEntities?.has("users")) {
    const usersBySoeid = new Map(
      (state.users || [])
        .filter((user) => user?.soeid && user?.display_name)
        .map((user) => [String(user.soeid), String(user.display_name)])
    );
    if (next.assignee === "__unassigned__") {
      if (next.assignee_name) {
        next.assignee_name = "";
        changed = true;
      }
    } else if (next.assignee) {
      const displayName = usersBySoeid.get(next.assignee) || "";
      if (!displayName) {
        next.assignee = "";
        next.assignee_name = "";
        changed = true;
      } else if (next.assignee_name !== displayName) {
        next.assignee_name = displayName;
        changed = true;
      }
    } else if (next.assignee_name) {
      next.assignee_name = "";
      changed = true;
    }
  }

  return { filters: next, changed };
}

export function syncSubcomponentsWorkbenchFilterControls(ctx) {
  const { state, els, updateSubcomponentsWorkbenchSolutionOptions } = ctx;
  const wb = state.subcomponentsWorkbench;
  if (els.subcomponentsWorkbenchSearch) els.subcomponentsWorkbenchSearch.value = wb.filters.search || "";
  if (els.subcomponentsWorkbenchProject) els.subcomponentsWorkbenchProject.value = wb.filters.project_id || "";
  updateSubcomponentsWorkbenchSolutionOptions(wb.filters.project_id || "");
  if (els.subcomponentsWorkbenchSolution) els.subcomponentsWorkbenchSolution.value = wb.filters.solution_id || "";
  if (els.subcomponentsWorkbenchAssignee) els.subcomponentsWorkbenchAssignee.value = wb.filters.assignee || "";
  if (els.subcomponentsWorkbenchStatus) els.subcomponentsWorkbenchStatus.value = wb.filters.status || "";
  if (els.subcomponentsWorkbenchPriority) els.subcomponentsWorkbenchPriority.value = wb.filters.priority_max || "";
}

export function normalizeSubcomponentsWorkbenchUiState(ctx, { persist = false } = {}) {
  const { state, persistSubcomponentsWorkbenchUiState } = ctx;
  const wb = state.subcomponentsWorkbench;
  let changed = false;
  if (!VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(wb.preset || "all"))) {
    wb.preset = "all";
    changed = true;
  }
  const normalized = normalizeSubcomponentsWorkbenchFilters(ctx, wb.filters);
  wb.filters = normalized.filters;
  syncSubcomponentsWorkbenchFilterControls(ctx);
  if (persist && (normalized.changed || changed)) persistSubcomponentsWorkbenchUiState();
  return normalized.changed || changed;
}

export function clearSubcomponentsWorkbenchFilters(ctx) {
  const { state, persistSubcomponentsWorkbenchUiState, renderSubcomponentsWorkbench } = ctx;
  const wb = state.subcomponentsWorkbench;
  wb.preset = "all";
  wb.filters = {
    search: "",
    project_id: "",
    solution_id: "",
    assignee: "",
    assignee_name: "",
    status: "",
    priority_max: "",
  };
  wb.selected.clear();
  wb.activeSubcomponentId = "";
  syncSubcomponentsWorkbenchFilterControls(ctx);
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
}
