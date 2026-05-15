export const VALID_DELIVERABLE_PRESETS = new Set(["", "my", "overdue", "blocked"]);
export const VALID_DELIVERABLE_TYPES = new Set(["", "project", "solution"]);
export const MASTER_TEXT_FILTER_KEYS = ["project", "sponsor", "solution", "version", "owner", "current_phase", "due", "rag", "status"];

function lower(value) {
  return String(value || "").toLowerCase();
}

export function normalizeMasterPriorityFilter(value) {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 && n <= 5 ? String(n) : "";
}

export function normalizeMasterProgressFilter(value) {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 && n <= 100 ? String(n) : "";
}

export function normalizeMasterFilters(filters = {}, _preset = "") {
  const source = filters && typeof filters === "object" ? filters : {};
  const next = {};
  let changed = filters !== source;
  MASTER_TEXT_FILTER_KEYS.forEach((key) => {
    const value = source[key];
    if (typeof value === "string") {
      next[key] = value;
      return;
    }
    next[key] = "";
    if (value !== null && value !== undefined && value !== "") changed = true;
  });
  const type = String(source.type || "");
  next.type = VALID_DELIVERABLE_TYPES.has(type) ? type : "";
  if (next.type !== type) changed = true;
  const priority = normalizeMasterPriorityFilter(source.priority);
  const progress = normalizeMasterProgressFilter(source.progress);
  if (priority !== String(source.priority || "")) changed = true;
  if (progress !== String(source.progress || "")) changed = true;
  next.priority = priority;
  next.progress = progress;

  if (source.repo_presence) {
    changed = true;
  }

  return { filters: next, changed };
}

function currentUserName(state) {
  return lower(state?.user?.display_name || state?.user?.soeid || "");
}

function projectMatchesDeliverablesFilters(ctx, project, filters, preset) {
  const { hideClosedDeliverables, isClosedProjectStatus, formatStatus, state } = ctx;
  const f = filters || {};
  if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;
  if (f.project && !lower(project?.project_name).includes(lower(f.project))) return false;
  if (f.sponsor && !lower(project?.sponsor).includes(lower(f.sponsor))) return false;
  if (f.priority && Number(project?.priority) > Number(f.priority)) return false;
  if (f.status && !lower(formatStatus(project?.status)).includes(lower(f.status))) return false;
  if (preset === "my") {
    const userName = currentUserName(state);
    if (!userName || !lower(project?.sponsor).includes(userName)) return false;
  }
  if (preset === "overdue" || preset === "blocked") return false;
  return true;
}

export function filteredSolutions(ctx) {
  const { state, hideClosedDeliverables, isClosedSolutionStatus, solutionProgress } = ctx;
  const f = state.filters || {};
  if (f.type && f.type !== "solution") return [];
  const preset = state.deliverablesPreset || "";
  const userName = currentUserName(state);
  const projectById = new Map((state.projects || []).map((project) => [project.project_id, project]));

  return (state.solutions || []).filter((solution) => {
    if (hideClosedDeliverables() && isClosedSolutionStatus(solution.status)) return false;
    const project = projectById.get(solution.project_id) || null;
    if (f.project && !lower(project?.project_name).includes(lower(f.project))) return false;
    if (f.sponsor && !lower(project?.sponsor).includes(lower(f.sponsor))) return false;
    if (f.solution && !lower(solution.solution_name).includes(lower(f.solution))) return false;
    if (f.version && !lower(solution.version).includes(lower(f.version))) return false;
    if (f.owner && !lower(solution.owner).includes(lower(f.owner))) return false;
    if (f.current_phase && !lower(solution.current_phase).includes(lower(f.current_phase))) return false;
    if (f.priority && Number(solution.priority) > Number(f.priority)) return false;
    if (f.due && !lower(solution.due_date).includes(lower(f.due))) return false;
    if (f.rag && !lower(solution.rag_status).includes(lower(f.rag))) return false;
    if (f.status && !lower(solution.status).includes(lower(f.status))) return false;
    if (f.progress && solutionProgress(solution) > Number(f.progress)) return false;
    if (preset === "my") {
      const ownerMatch = lower(solution.owner).includes(userName);
      const assigneeMatch = lower(solution.assignee).includes(userName);
      if (!ownerMatch && !assigneeMatch) return false;
    }
    if (preset === "overdue") {
      if (!solution.due_date) return false;
      if (solution.status === "complete" || solution.status === "abandoned") return false;
      if (new Date(solution.due_date) >= new Date()) return false;
    }
    if (preset === "blocked") {
      const hasBlockers = String(solution.blockers || "").trim().length > 0;
      const hasRisks = String(solution.risks || "").trim().length > 0;
      if (!hasBlockers && !hasRisks && solution.status !== "on_hold") return false;
    }
    return true;
  });
}

export function filteredDeliverables(ctx) {
  const { state } = ctx;
  const f = state.filters || {};
  const preset = state.deliverablesPreset || "";
  const rows = [];
  const includeProjectRows = f.type !== "solution";
  const includeSolutionRows = f.type !== "project";
  const hasSolutionColumnFilters = Boolean(
    f.solution || f.version || f.owner || f.current_phase || f.due || f.rag || f.progress
  );
  const projectById = new Map((state.projects || []).map((project) => [project.project_id, project]));
  const groupedSolutions = new Map();
  const orphanSolutions = [];

  if (includeSolutionRows) {
    filteredSolutions(ctx).forEach((solution) => {
      const project = projectById.get(solution.project_id) || null;
      if (!project || !project.project_id) {
        orphanSolutions.push({ type: "solution", project: null, solution });
        return;
      }
      const bucket = groupedSolutions.get(project.project_id) || [];
      bucket.push({ type: "solution", project, solution });
      groupedSolutions.set(project.project_id, bucket);
    });
  }

  const sortedProjects = [...(state.projects || [])].sort((a, b) =>
    String(a.project_name || "").localeCompare(String(b.project_name || ""))
  );

  sortedProjects.forEach((project) => {
    const solutionRows = (groupedSolutions.get(project.project_id) || []).sort((a, b) =>
      String(a.solution?.solution_name || "").localeCompare(String(b.solution?.solution_name || ""))
    );
    const projectMatches = projectMatchesDeliverablesFilters(ctx, project, f, preset);
    const showProjectRow = includeProjectRows && projectMatches && (!hasSolutionColumnFilters || solutionRows.length > 0);
    if (showProjectRow) rows.push({ type: "project", project, solution: null });
    solutionRows.forEach((row) => rows.push(row));
  });

  orphanSolutions
    .sort((a, b) => String(a.solution?.solution_name || "").localeCompare(String(b.solution?.solution_name || "")))
    .forEach((row) => rows.push(row));

  return rows;
}
