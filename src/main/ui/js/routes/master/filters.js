export const MASTER_QUERY_FIELDS = new Set([
  "program",
  "project",
  "sponsor",
  "solution",
  "task",
  "deliverable",
  "version",
  "owner",
  "phase",
  "current_phase",
  "rag",
  "status",
  "due",
  "priority",
  "progress",
]);

function lower(value) {
  return String(value || "").toLowerCase();
}

function tokenizeQuery(query) {
  const source = String(query || "").trim();
  const tokens = [];
  const pattern = /([^\s:"=]+)([:=])(?:"([^"]*)"|(\S+))|"([^"]*)"|(\S+)/g;
  let match;
  while ((match = pattern.exec(source)) !== null) {
    if (match[2]) {
      const field = lower(match[1]);
      const value = String(match[3] ?? match[4] ?? "").trim();
      tokens.push(MASTER_QUERY_FIELDS.has(field) ? { field, value } : { value: `${match[1]}${match[2]}${value}` });
      continue;
    }
    tokens.push({ value: String(match[5] ?? match[6] ?? "").trim() });
  }
  return tokens.filter((token) => token.value);
}

export function normalizeMasterFilters(filters = {}) {
  const source = filters && typeof filters === "object" ? filters : {};
  const query = typeof source.query === "string" ? source.query : "";
  const changed = filters !== source
    || Object.keys(source).some((key) => key !== "query")
    || source.query !== query;
  return { filters: { query }, changed };
}

function currentUserName(state) {
  return lower(state?.user?.display_name || state?.user?.soeid || "");
}

function isMyTokenMatch(ctx, project, solution) {
  const userName = currentUserName(ctx.state);
  if (!userName) return false;
  return lower(project?.owner).includes(userName)
    || lower(project?.owner_user_soeid).includes(userName)
    || lower(project?.sponsor).includes(userName)
    || lower(solution?.owner).includes(userName)
    || lower(solution?.assignee).includes(userName);
}

function isOverdue(solution) {
  if (!solution?.due_date) return false;
  if (solution.status === "complete" || solution.status === "abandoned") return false;
  return new Date(solution.due_date) < new Date();
}

function hasRiskOrBlocker(solution) {
  return String(solution?.blockers || "").trim().length > 0
    || String(solution?.risks || "").trim().length > 0
    || solution?.status === "on_hold"
    || lower(solution?.rag_status) === "red"
    || lower(solution?.rag_status) === "amber";
}

function phaseLabel(ctx, solution) {
  return typeof ctx.phaseDisplayName === "function"
    ? ctx.phaseDisplayName(solution?.current_phase)
    : solution?.current_phase;
}

function statusLabel(ctx, value) {
  return typeof ctx.formatStatus === "function" ? ctx.formatStatus(value) : value;
}

function fieldValue(ctx, field, program, project, solution) {
  switch (field) {
    case "program":
      return program?.program_name || project?.program_name;
    case "project":
      return project?.project_name;
    case "sponsor":
      return project?.sponsor;
    case "solution":
      return solution?.solution_name;
    case "version":
      return solution?.version;
    case "owner":
      return `${project?.owner || ""} ${project?.owner_user_soeid || ""} ${solution?.owner || ""} ${solution?.assignee || ""}`;
    case "phase":
    case "current_phase":
      return phaseLabel(ctx, solution);
    case "rag":
      return solution?.rag_status;
    case "status":
      return statusLabel(ctx, solution?.status);
    case "due":
      return solution?.due_date;
    default:
      return "";
  }
}

function numericFieldMatches(ctx, field, value, solution) {
  const target = Number(value);
  if (!Number.isFinite(target)) return false;
  if (field === "priority") return Number(solution?.priority) <= target;
  if (field === "progress") return Number(ctx.solutionProgress?.(solution) || 0) <= target;
  return false;
}

function taskHaystack(ctx, tasks) {
  return (Array.isArray(tasks) ? tasks : [])
    .flatMap((task) => [
      task?.task_name,
      task?.assignee,
      task?.assignee_user_soeid,
      task?.status,
      statusLabel(ctx, task?.status),
      task?.due_date,
      task?.github_repo_url,
      task?.blocker_note,
      task?.description,
      task?.acceptance_criteria,
      task?.done_criteria,
    ]);
}

function freeTextHaystack(ctx, program, project, solution, tasks = []) {
  return [
    program?.program_name,
    project?.program_name,
    project?.project_name,
    project?.sponsor,
    project?.owner,
    project?.owner_user_soeid,
    solution?.solution_name,
    solution?.version,
    solution?.owner,
    solution?.assignee,
    phaseLabel(ctx, solution),
    solution?.rag_status,
    statusLabel(ctx, solution?.status),
    solution?.due_date,
    solution?.priority,
    ctx.solutionProgress?.(solution),
    ...taskHaystack(ctx, tasks),
  ].map((value) => lower(value)).join(" ");
}

function tokenMatches(ctx, token, program, project, solution, tasks = []) {
  const value = lower(token.value);
  if (!value) return true;
  if (!token.field) {
    if (value === "my") return isMyTokenMatch(ctx, project, solution);
    if (value === "overdue") return isOverdue(solution);
    if (value === "blocked" || value === "risk" || value === "at-risk") return hasRiskOrBlocker(solution);
    return freeTextHaystack(ctx, program, project, solution, tasks).includes(value);
  }
  if (token.field === "task" || token.field === "deliverable") {
    return taskHaystack(ctx, tasks).map((item) => lower(item)).join(" ").includes(value);
  }
  if (token.field === "priority" || token.field === "progress") {
    return numericFieldMatches(ctx, token.field, token.value, solution);
  }
  return lower(fieldValue(ctx, token.field, program, project, solution)).includes(value);
}

function solutionMatchesQuery(ctx, solution, project, program, tokens, tasks = []) {
  if (!tokens.length) return true;
  return tokens.every((token) => tokenMatches(ctx, token, program, project, solution, tasks));
}

function projectMatchesQuery(ctx, project, program, tokens) {
  if (!tokens.length) return true;
  return tokens.every((token) => {
    if (token.field && !["program", "project", "sponsor", "owner", "status", "priority"].includes(token.field)) return false;
    if (token.field === "priority") {
      const target = Number(token.value);
      return Number.isFinite(target) && Number(project?.priority) <= target;
    }
    if (token.field === "status") return lower(statusLabel(ctx, project?.status)).includes(lower(token.value));
    const value = token.field
      ? fieldValue(ctx, token.field, program, project, null)
      : [program?.program_name, project?.program_name, project?.project_name, project?.sponsor, project?.owner, project?.owner_user_soeid, statusLabel(ctx, project?.status), project?.priority]
        .map((item) => lower(item)).join(" ");
    return lower(value).includes(lower(token.value));
  });
}

function programMatchesQuery(program, tokens) {
  if (!tokens.length) return true;
  return tokens.every((token) => {
    const value = lower(token.value);
    if (!value) return true;
    if (token.field && token.field !== "program") return false;
    return lower(program?.program_name).includes(value);
  });
}

export function filteredSolutions(ctx) {
  const { state, hideClosedDeliverables, isClosedSolutionStatus } = ctx;
  const tokens = tokenizeQuery(state.filters?.query || "");
  const programsById = new Map((state.programs || []).map((program) => [program.program_id, program]));
  const projectById = new Map((state.projects || []).map((project) => [project.project_id, project]));
  const tasksBySolutionId = new Map();
  (state.tasks || []).forEach((task) => {
    const solutionId = String(task?.solution_id || "").trim();
    if (!solutionId) return;
    const bucket = tasksBySolutionId.get(solutionId) || [];
    bucket.push(task);
    tasksBySolutionId.set(solutionId, bucket);
  });

  return (state.solutions || []).filter((solution) => {
    if (hideClosedDeliverables() && isClosedSolutionStatus(solution.status)) return false;
    const project = projectById.get(solution.project_id) || null;
    const program = programsById.get(project?.program_id) || null;
    return solutionMatchesQuery(ctx, solution, project, program, tokens, tasksBySolutionId.get(solution.solution_id) || []);
  });
}

function dueSoon(solution) {
  const raw = String(solution?.due_date || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return false;
  if (solution.status === "complete" || solution.status === "abandoned") return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(due.getTime())) return false;
  const days = Math.round((due.getTime() - today.getTime()) / 86400000);
  return days >= 0 && days <= 14;
}

function summarizeSolutions(solutionRows, solutionProgress) {
  const rows = Array.isArray(solutionRows) ? solutionRows : [];
  const count = rows.length;
  const resolveProgress = typeof solutionProgress === "function" ? solutionProgress : () => 0;
  const progressTotal = rows.reduce((total, row) => total + Number(resolveProgress(row.solution) || 0), 0);
  return {
    solutionCount: count,
    atRiskCount: rows.filter((row) => hasRiskOrBlocker(row.solution)).length,
    dueSoonCount: rows.filter((row) => dueSoon(row.solution)).length,
    progress: count ? Math.round(progressTotal / count) : 0,
  };
}

function ensureProgramGroup(groups, program) {
  const fallbackProgram = {
    program_id: "__unassigned__",
    program_name: "Unassigned Program",
  };
  const target = program?.program_id ? program : fallbackProgram;
  const key = target.program_id || "__unassigned__";
  if (!groups.has(key)) {
    groups.set(key, {
      program: target,
      programKey: key,
      projects: [],
    });
  }
  return groups.get(key);
}

export function filteredDeliverables(ctx) {
  const { state, solutionProgress, hideClosedDeliverables, isClosedProjectStatus, isClosedSolutionStatus } = ctx;
  const tokens = tokenizeQuery(state.filters?.query || "");
  const rows = [];
  const programsById = new Map((state.programs || []).map((program) => [program.program_id, program]));
  const projectById = new Map((state.projects || []).map((project) => [project.project_id, project]));
  const allGroupedSolutions = new Map();
  const matchedGroupedSolutions = new Map();
  const allOrphanSolutions = [];
  const matchedOrphanSolutions = [];

  const appendSolutionRow = (target, orphanTarget, solution) => {
    const project = projectById.get(solution.project_id) || null;
    if (!project || !project.project_id) {
      orphanTarget.push({ type: "solution", program: null, project: null, solution });
      return;
    }
    const bucket = target.get(project.project_id) || [];
    bucket.push({ type: "solution", program: programsById.get(project.program_id) || null, project, solution });
    target.set(project.project_id, bucket);
  };

  (state.solutions || []).forEach((solution) => {
    if (hideClosedDeliverables() && isClosedSolutionStatus(solution.status)) return;
    appendSolutionRow(allGroupedSolutions, allOrphanSolutions, solution);
  });

  filteredSolutions(ctx).forEach((solution) => {
    appendSolutionRow(matchedGroupedSolutions, matchedOrphanSolutions, solution);
  });

  const sortedProjects = [...(state.projects || [])].sort((a, b) =>
    String(a.project_name || "").localeCompare(String(b.project_name || ""))
  );
  const groupedPrograms = new Map();

  const visibleProjects = sortedProjects.filter((project) => {
    if (hideClosedDeliverables() && isClosedProjectStatus(project?.status)) return false;
    return true;
  });

  visibleProjects.forEach((project) => {
    const program = programsById.get(project.program_id) || {
      program_id: project.program_id || "__unassigned__",
      program_name: project.program_name || "Unassigned Program",
    };
    const programMatches = programMatchesQuery(program, tokens);
    const projectMatches = projectMatchesQuery(ctx, project, program, tokens);
    const matchedRows = matchedGroupedSolutions.get(project.project_id) || [];
    const sourceRows = matchedRows.length
      ? matchedRows
      : programMatches || projectMatches
        ? allGroupedSolutions.get(project.project_id) || []
        : matchedRows;
    const solutionRows = sourceRows.sort((a, b) =>
      String(a.solution?.solution_name || "").localeCompare(String(b.solution?.solution_name || ""))
    );
    const showProjectGroup = solutionRows.length > 0 || projectMatches || programMatches;
    if (!showProjectGroup) return;
    const group = ensureProgramGroup(groupedPrograms, program);
    group.projects.push({ program, project, projectKey: project.project_id || "__unassigned-project__", solutionRows });
  });

  (state.programs || []).forEach((program) => {
    const programId = String(program?.program_id || "").trim();
    if (!programId || groupedPrograms.has(programId)) return;
    if (!programMatchesQuery(program, tokens)) return;
    ensureProgramGroup(groupedPrograms, program);
  });

  const orphanSolutions = tokens.length ? matchedOrphanSolutions : allOrphanSolutions;
  if (orphanSolutions.length) {
    const group = ensureProgramGroup(groupedPrograms, null);
    group.projects.push({
      program: group.program,
      project: {
        project_id: "",
        project_name: "Unassigned Project",
        status: "",
        sponsor: "",
        priority: "",
      },
      projectKey: "__orphan-solutions__",
      solutionRows: orphanSolutions.sort((a, b) =>
        String(a.solution?.solution_name || "").localeCompare(String(b.solution?.solution_name || ""))
      ),
    });
  }

  [...groupedPrograms.values()]
    .sort((a, b) => String(a.program?.program_name || "").localeCompare(String(b.program?.program_name || "")))
    .forEach((programGroup) => {
      programGroup.projects.sort((a, b) =>
        String(a.project?.project_name || "").localeCompare(String(b.project?.project_name || ""))
      );
      const allSolutions = programGroup.projects.flatMap((projectGroup) => projectGroup.solutionRows);
      const programSummary = summarizeSolutions(allSolutions, solutionProgress);
      rows.push({
        type: "program-header",
        program: programGroup.program,
        programKey: programGroup.programKey,
        projectCount: programGroup.projects.length,
        ...programSummary,
      });
      programGroup.projects.forEach(({ program, project, projectKey, solutionRows }) => {
        const projectSummary = summarizeSolutions(solutionRows, solutionProgress);
        rows.push({
          type: "project-header",
          program,
          project,
          projectKey,
          solution: null,
          ...projectSummary,
        });
        solutionRows.forEach((row) => rows.push(row));
      });
    });

  return rows;
}
