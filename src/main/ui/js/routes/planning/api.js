import {
  UNASSIGNED_TEAM_ID,
  boardState,
  currentMonthToken,
  defaultDetailDraft,
  rerenderPlanning,
} from "./state.js";
import {
  flashTargets,
  normalizeTeamId,
  numberOr,
  parseAssignmentTarget,
  setNotice,
} from "./common.js";
import {
  normalizePersistedBoardFilters,
  persistViewState,
} from "./storage.js";
import {
  selectedTask,
  selectTask,
  syncDetailDraft,
} from "./selection.js";

export function resolveApiBase(ctx) {
  if (ctx?.apiBase) return String(ctx.apiBase);
  try {
    const modulePath = new URL(import.meta.url, window.location.href).pathname || "";
    const marker = "/js/";
    const idx = modulePath.lastIndexOf(marker);
    const contextPath = idx <= 0 ? "" : modulePath.slice(0, idx).replace(/\/+$/, "");
    return `${contextPath}/api` || "/api";
  } catch {
    return "/api";
  }
}

export async function callApi(ctx, path, options = {}) {
  if (typeof ctx.api === "function") return ctx.api(path, options);
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(`${resolveApiBase(ctx)}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body,
    credentials: "include",
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && payload.detail) ||
      (typeof payload === "string" && payload) ||
      response.statusText ||
      "Request failed";
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  return payload;
}

async function confirmAction(options = {}) {
  const ctx = boardState.ctx;
  if (typeof ctx?.showConfirmModal === "function") {
    return !!(await ctx.showConfirmModal(options));
  }
  setNotice(options.message || options.title || "Confirmation is unavailable right now.", "warn");
  rerenderPlanning();
  return false;
}

async function refreshGlobal(ctx, entity) {
  if (typeof ctx.refreshFromServer !== "function") return;
  try {
    await ctx.refreshFromServer(entity);
  } catch {
    // Non-blocking. Board data is refreshed separately.
  }
}

export async function loadBoard(ctx, { allocationsOnly = false } = {}) {
  const startedAt = Date.now();
  if (boardState.loading) return;
  boardState.loading = true;
  boardState.error = "";
  rerenderPlanning();
  try {
    const month = boardState.month || currentMonthToken();
    if (allocationsOnly && boardState.loaded) {
      const [tasks, allocations] = await Promise.all([
        callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(month)}`),
        callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`),
      ]);
      boardState.data.tasks = Array.isArray(tasks) ? tasks : [];
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
    } else {
      const [tasks, teams, people, allocations] = await Promise.all([
        callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(month)}`),
        callApi(ctx, "/planning/work-allocation/teams"),
        callApi(ctx, "/planning/work-allocation/people"),
        callApi(ctx, `/planning/work-allocation/allocations?month=${encodeURIComponent(month)}`),
      ]);
      boardState.data.teams = Array.isArray(teams) ? teams : [];
      boardState.data.people = Array.isArray(people) ? people : [];
      boardState.data.tasks = Array.isArray(tasks) ? tasks : [];
      boardState.data.allocations = Array.isArray(allocations) ? allocations : [];
    }
    boardState.loaded = true;
    normalizePersistedBoardFilters();
    const nextSelectedTask = selectedTask();
    if (!nextSelectedTask) {
      boardState.selectedTaskId = "";
      boardState.detailDraft = defaultDetailDraft();
    } else {
      syncDetailDraft(nextSelectedTask);
    }
    persistViewState();
  } catch (err) {
    boardState.error = err?.message || "Failed to load board data";
    setNotice(boardState.error, "error");
  } finally {
    boardState.loading = false;
    rerenderPlanning();
    if (typeof ctx?.noteRouteDataLoaded === "function") {
      ctx.noteRouteDataLoaded(Date.now() - startedAt);
    }
  }
}

function allocationToCreatePayload(allocation) {
  return {
    task_id: allocation.task_id,
    assignee_type: allocation.assignee_type,
    assignee_id: allocation.assignee_id,
    month: allocation.month,
    fte_months_allocated: allocation.fte_months_allocated,
  };
}

function allocationToUpdatePayload(allocation) {
  return {
    assignee_type: allocation.assignee_type,
    assignee_id: allocation.assignee_id,
    fte_months_allocated: allocation.fte_months_allocated,
  };
}

async function createAssignment(taskId, assigneeType, assigneeId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const task = (boardState.data.tasks || []).find((row) => row.id === taskId);
  if (!task) return;
  if (assigneeType === "person") {
    const person = (boardState.data.people || []).find((row) => row.id === assigneeId);
    if (!person) {
      setNotice("Person not found", "warn");
      rerenderPlanning();
      return;
    }
    if (!normalizeTeamId(person.team_id)) {
      setNotice("Move this person onto a team before assigning work", "warn");
      rerenderPlanning();
      return;
    }
  }
  const existingSame = (boardState.data.allocations || []).find(
    (row) => row.task_id === taskId && row.assignee_type === assigneeType && row.assignee_id === assigneeId
  );
  if (existingSame) {
    setNotice("Task is already assigned there", "warn");
    rerenderPlanning();
    return;
  }
  const payload = {
    task_id: taskId,
    assignee_type: assigneeType,
    assignee_id: assigneeId,
    month: boardState.month,
    fte_months_allocated: numberOr(task.fte_months, 0.25),
  };
  const created = await callApi(ctx, "/planning/work-allocation/allocations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (typeof ctx?.trackWorkflow === "function") {
    ctx.trackWorkflow("planning", "assignment_create", "success", {
      result_kind: assigneeType,
      source: "planning_board",
    });
  }
  boardState.data.allocations.push(created);
  if (pushUndo) {
    boardState.undoStack.push({ kind: "unassign", allocationId: created.id });
  }
  setNotice("Assignee added to task", "success");
  flashTargets([{ kind: "task", id: taskId }, { kind: assigneeType, id: assigneeId }], "success");
  await refreshGlobal(ctx, "allocations");
  rerenderPlanning();
}

export async function moveAssignment(allocationId, assigneeType, assigneeId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const existing = (boardState.data.allocations || []).find((row) => row.id === allocationId);
  if (!existing) return;
  if (existing.assignee_type === assigneeType && existing.assignee_id === assigneeId) {
    setNotice("Task is already assigned there", "warn");
    rerenderPlanning();
    return;
  }

  const updated = await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`, {
    method: "PATCH",
    body: JSON.stringify({
      assignee_type: assigneeType,
      assignee_id: assigneeId,
      fte_months_allocated: existing.fte_months_allocated,
    }),
  });
  if (typeof ctx?.trackWorkflow === "function") {
    ctx.trackWorkflow("planning", "assignment_update", "success", {
      result_kind: assigneeType,
      source: "planning_board",
    });
  }
  boardState.data.allocations = (boardState.data.allocations || [])
    .filter((row) => row.id !== existing.id && row.id !== updated.id);
  boardState.data.allocations.push(updated);
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "move-assignment",
      allocationId: updated.id,
      payload: allocationToUpdatePayload(existing),
    });
  }
  setNotice("Task moved to new assignee", "success");
  flashTargets(
    [
      { kind: "task", id: existing.task_id },
      { kind: existing.assignee_type, id: existing.assignee_id },
      { kind: assigneeType, id: assigneeId },
    ],
    "success"
  );
  await refreshGlobal(ctx, "allocations");
  rerenderPlanning();
}

async function unassignAllocation(
  allocationId,
  { pushUndo = true, noticeMessage = "Assignee removed from task", refresh = true, render = true } = {}
) {
  const ctx = boardState.ctx;
  const existing = (boardState.data.allocations || []).find((row) => row.id === allocationId);
  if (!existing) return;
  await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(existing.id)}`, {
    method: "DELETE",
  });
  if (typeof ctx?.trackWorkflow === "function") {
    ctx.trackWorkflow("planning", "assignment_delete", "success", {
      source: "planning_board",
    });
  }
  boardState.data.allocations = (boardState.data.allocations || []).filter((row) => row.id !== existing.id);
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "assign",
      payload: allocationToCreatePayload(existing),
    });
  }
  if (noticeMessage) setNotice(noticeMessage, "success");
  flashTargets([{ kind: "task", id: existing.task_id }, { kind: existing.assignee_type, id: existing.assignee_id }], "success");
  if (refresh) await refreshGlobal(ctx, "allocations");
  if (render) rerenderPlanning();
}

async function unassignTask(taskId, { pushUndo = true } = {}) {
  const matches = (boardState.data.allocations || []).filter((row) => row.task_id === taskId);
  if (!matches.length) {
    setNotice("Task is already in backlog", "warn");
    rerenderPlanning();
    return;
  }
  for (const allocation of matches) {
    await unassignAllocation(allocation.id, { pushUndo, noticeMessage: "", refresh: false, render: false });
  }
  await refreshGlobal(boardState.ctx, "allocations");
  setNotice(matches.length > 1 ? "Task unassigned from all assignees" : "Task moved back to backlog", "success");
  flashTargets([{ kind: "task", id: taskId }], "success");
  rerenderPlanning();
}

async function movePersonToTeam(personId, teamId, { pushUndo = true } = {}) {
  const ctx = boardState.ctx;
  const person = (boardState.data.people || []).find((row) => row.id === personId);
  if (!person) return;

  const previousTeamId = person.team_id || UNASSIGNED_TEAM_ID;
  const nextTeamId = normalizeTeamId(teamId);
  const nextTeamToken = nextTeamId || UNASSIGNED_TEAM_ID;
  if (previousTeamId === nextTeamToken) return;

  const updated = await callApi(ctx, `/planning/work-allocation/people/${encodeURIComponent(personId)}`, {
    method: "PATCH",
    body: JSON.stringify({ team_id: nextTeamId }),
  });

  boardState.data.people = (boardState.data.people || []).map((row) => (row.id === personId ? updated : row));
  if (pushUndo) {
    boardState.undoStack.push({
      kind: "move-person",
      personId,
      teamId: previousTeamId,
    });
  }
  setNotice(nextTeamToken === UNASSIGNED_TEAM_ID ? "Person moved to Unassigned" : "Person moved to team", "success");
  flashTargets([
    { kind: "person", id: personId },
    ...(nextTeamToken === UNASSIGNED_TEAM_ID ? [] : [{ kind: "team", id: nextTeamToken }]),
  ]);
  await refreshGlobal(ctx, "users");
  rerenderPlanning();
}

async function performUndo() {
  const ctx = boardState.ctx;
  const next = boardState.undoStack.pop();
  if (!next) return;
  try {
    if (next.kind === "unassign") {
      await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(next.allocationId)}`, { method: "DELETE" });
    } else if (next.kind === "assign") {
      await callApi(ctx, "/planning/work-allocation/allocations", {
        method: "POST",
        body: JSON.stringify(next.payload),
      });
    } else if (next.kind === "move-assignment") {
      await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(next.allocationId)}`, {
        method: "PATCH",
        body: JSON.stringify(next.payload),
      });
    } else if (next.kind === "delete-task") {
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(next.taskId)}`, { method: "DELETE" });
    } else if (next.kind === "move-person") {
      await callApi(ctx, `/planning/work-allocation/people/${encodeURIComponent(next.personId)}`, {
        method: "PATCH",
        body: JSON.stringify({ team_id: normalizeTeamId(next.teamId) }),
      });
    }
    setNotice("Undo applied", "success");
    await loadBoard(ctx, { allocationsOnly: false });
    await refreshGlobal(ctx, "all");
  } catch (err) {
    setNotice(`Undo failed: ${err?.message || err}`, "error");
    rerenderPlanning();
  }
}

async function assignSelectedTaskToTarget(rawTarget) {
  const target = parseAssignmentTarget(rawTarget);
  const taskId = boardState.selectedTaskId;
  if (!taskId) {
    setNotice("Select a task first", "warn");
    rerenderPlanning();
    return;
  }
  if (!target) return;
  if (target.type === "backlog") {
    await unassignTask(taskId, { pushUndo: true });
    return;
  }
  if (target.type === "team" && target.id === UNASSIGNED_TEAM_ID) {
    await unassignTask(taskId, { pushUndo: true });
    return;
  }
  await createAssignment(taskId, target.type, target.id, { pushUndo: true });
}

export async function onPlanningAction(action, actionEl = null) {
  const ctx = boardState.ctx;
  const root = ctx.els?.planningBoard;
  if (!root) return;

  try {
    if (action === "toggle-filters") {
      boardState.topPanel = boardState.topPanel === "filters" ? "" : "filters";
      rerenderPlanning();
      return;
    }
    if (action === "toggle-create") {
      boardState.topPanel = boardState.topPanel === "create" ? "" : "create";
      rerenderPlanning();
      return;
    }
    if (action === "toggle-guide") {
      boardState.topPanel = boardState.topPanel === "guide" ? "" : "guide";
      rerenderPlanning();
      return;
    }
    if (action === "toggle-tools") {
      boardState.topPanel = boardState.topPanel === "tools" ? "" : "tools";
      rerenderPlanning();
      return;
    }
    if (action === "reset-filters") {
      boardState.teamFilter = "all";
      boardState.effortFilter = "all";
      boardState.search = "";
      boardState.personSearch = "";
      persistViewState();
      rerenderPlanning();
      return;
    }
    if (action === "refresh") {
      await loadBoard(ctx, { allocationsOnly: false });
      return;
    }
    if (action === "download-report") {
      const month = boardState.month || currentMonthToken();
      const headers = {};
      const activeSpaceId = ctx?.state?.activeSpace?.space_id || "";
      if (activeSpaceId) headers["X-Space-Id"] = activeSpaceId;
      const response = await fetch(
        `${resolveApiBase(ctx)}/planning/work-allocation/report.pdf?month=${encodeURIComponent(month)}`,
        {
          method: "GET",
          headers,
          credentials: "include",
        }
      );
      if (!response.ok) {
        const text = await response.text();
        let message = `Download failed (${response.status})`;
        try {
          const payload = text ? JSON.parse(text) : null;
          if (payload?.detail) message = String(payload.detail);
          else if (text) message = text;
        } catch {
          if (text) message = text;
        }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `work-allocation-report-${month}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("planning", "report_download", "success", {
          source: "planning_board",
        });
      }
      setNotice("Report downloaded", "success");
      rerenderPlanning();
      return;
    }
    if (action === "close-task-detail" || action === "close-task-modal") {
      const { closeTaskDetail } = await import("./selection.js");
      closeTaskDetail({ restoreFocus: true });
      return;
    }
    if (action === "undo") {
      await performUndo();
      return;
    }
    if (action === "add-team") {
      const name = String(boardState.drafts.teamName || "").trim();
      if (!name) {
        setNotice("Team name is required", "warn");
        rerenderPlanning();
        return;
      }
      const created = await callApi(ctx, "/planning/work-allocation/teams", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("teams", "create", "success", { source: "planning_board" });
      }
      boardState.drafts.teamName = "";
      setNotice("Team added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) flashTargets([{ kind: "team", id: created.id }], "success");
      await refreshGlobal(ctx, "teams");
      return;
    }
    if (action === "delete-team") {
      const teamId = String(actionEl?.getAttribute("data-team-id") || "").trim();
      if (!teamId || teamId === UNASSIGNED_TEAM_ID) return;
      const team = (boardState.data.teams || []).find((row) => row.id === teamId);
      if (!team) {
        setNotice("Team not found", "warn");
        rerenderPlanning();
        return;
      }
      const teamPeopleCount = (boardState.data.people || []).filter((person) => person.team_id === teamId).length;
      const teamAllocations = (boardState.data.allocations || []).filter(
        (allocation) => allocation.assignee_type === "team" && allocation.assignee_id === teamId
      );
      const confirmed = await confirmAction({
        title: "Delete Team?",
        message: `Delete team "${team.name}"? ${teamPeopleCount} people will move to Unassigned. ${teamAllocations.length} team-level assignments will move back to Backlog.`,
        confirmLabel: "Delete Team",
      });
      if (!confirmed) return;

      for (const allocation of teamAllocations) {
        await callApi(ctx, `/planning/work-allocation/allocations/${encodeURIComponent(allocation.id)}`, {
          method: "DELETE",
        });
      }
      await callApi(ctx, `/planning/work-allocation/teams/${encodeURIComponent(teamId)}`, {
        method: "DELETE",
      });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("teams", "delete", "success", { source: "planning_board" });
      }
      setNotice("Team deleted", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "teams");
      await refreshGlobal(ctx, "users");
      await refreshGlobal(ctx, "allocations");
      return;
    }
    if (action === "add-person") {
      const name = String(boardState.drafts.personName || "").trim();
      if (!name) {
        setNotice("Person name is required", "warn");
        rerenderPlanning();
        return;
      }
      const teamId = String(boardState.drafts.personTeamId || "").trim() || null;
      const cap = Math.max(numberOr(boardState.drafts.personCapacity, 1), 0.1);
      const created = await callApi(ctx, "/planning/work-allocation/people", {
        method: "POST",
        body: JSON.stringify({ name, team_id: teamId, capacity_fte_months: cap }),
      });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("users", "create", "success", { source: "planning_board" });
      }
      boardState.drafts.personName = "";
      boardState.drafts.personCapacity = "1.00";
      boardState.drafts.personTeamId = "";
      setNotice("Person added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) flashTargets([{ kind: "person", id: created.id }], "success");
      await refreshGlobal(ctx, "users");
      return;
    }
    if (action === "add-task") {
      const title = String(boardState.drafts.taskTitle || "").trim();
      if (!title) {
        setNotice("Task title is required", "warn");
        rerenderPlanning();
        return;
      }
      const fte = Math.max(numberOr(boardState.drafts.taskFte, 0.25), 0.05);
      const created = await callApi(ctx, `/planning/work-allocation/tasks?month=${encodeURIComponent(boardState.month)}`, {
        method: "POST",
        body: JSON.stringify({ title, fte_months: fte }),
      });
      boardState.selectedTaskId = created?.id || "";
      boardState.focusReturnTaskId = boardState.selectedTaskId;
      boardState.undoStack.push({ kind: "delete-task", taskId: created.id });
      boardState.drafts.taskTitle = "";
      boardState.drafts.taskFte = "0.25";
      setNotice("Task added", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      if (created?.id) {
        flashTargets([{ kind: "task", id: created.id }], "success");
        selectTask(created.id, { focusReturnTaskId: created.id });
      }
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "assign-task") {
      const assignmentSelect = root.querySelector("#wab-detail-assignee-target");
      const target = String(assignmentSelect?.value || "").trim();
      if (!target) {
        setNotice("Choose a team or person first", "warn");
        rerenderPlanning();
        return;
      }
      boardState.detailDraft.assignmentTarget = "";
      await assignSelectedTaskToTarget(target);
      return;
    }
    if (action === "remove-assignment") {
      const allocationId = String(actionEl?.getAttribute("data-allocation-id") || "").trim();
      if (!allocationId) return;
      await unassignAllocation(allocationId, { pushUndo: true, noticeMessage: "Assignee removed from task" });
      return;
    }
    if (action === "move-person-to-unassigned") {
      const personId = String(actionEl?.getAttribute("data-person-id") || "").trim();
      if (!personId) return;
      await movePersonToTeam(personId, UNASSIGNED_TEAM_ID, { pushUndo: true });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("users", "update", "success", { source: "planning_board" });
      }
      return;
    }
    if (action === "save-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      const title = String(boardState.detailDraft.title || "").trim();
      const fte = Math.max(numberOr(boardState.detailDraft.fte, 0.25), 0.05);
      if (!title) {
        setNotice("Task title is required", "warn");
        rerenderPlanning();
        return;
      }
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(selectedId)}?month=${encodeURIComponent(boardState.month)}`, {
        method: "PATCH",
        body: JSON.stringify({ title, fte_months: fte }),
      });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("planning", "update", "success", { source: "planning_board" });
      }
      setNotice("Task updated", "success");
      flashTargets([{ kind: "task", id: selectedId }], "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "delete-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      const confirmed = await confirmAction({
        title: "Delete Task?",
        message: "Delete this task and remove its assignments?",
        confirmLabel: "Delete Task",
      });
      if (!confirmed) return;
      await callApi(ctx, `/planning/work-allocation/tasks/${encodeURIComponent(selectedId)}`, {
        method: "DELETE",
      });
      if (typeof ctx?.trackWorkflow === "function") {
        ctx.trackWorkflow("planning", "delete", "success", { source: "planning_board" });
      }
      boardState.selectedTaskId = "";
      boardState.detailDraft = defaultDetailDraft();
      persistViewState();
      setNotice("Task deleted", "success");
      await loadBoard(ctx, { allocationsOnly: false });
      await refreshGlobal(ctx, "subcomponents");
      return;
    }
    if (action === "unassign-task") {
      const selectedId = boardState.selectedTaskId;
      if (!selectedId) return;
      await unassignTask(selectedId, { pushUndo: true });
      return;
    }
  } catch (err) {
    if (typeof ctx?.trackWorkflow === "function") {
      const workflowAction = (
        action === "download-report" ? "report_download"
          : action === "add-team" ? "create"
            : action === "delete-team" ? "delete"
              : action === "add-person" ? "create"
                : action === "assign-task" ? "assignment_create"
                  : action === "remove-assignment" || action === "unassign-task" ? "assignment_delete"
                    : action === "save-task" || action === "move-person-to-unassigned" ? "update"
                      : ""
      );
      const workflowFeature = (
        action === "add-team" || action === "delete-team" ? "teams"
          : action === "add-person" || action === "move-person-to-unassigned" ? "users"
            : "planning"
      );
      if (workflowAction) {
        ctx.trackWorkflow(workflowFeature, workflowAction, "failure", { source: "planning_board" });
      }
    }
    setNotice(err?.message || "Action failed", "error");
    rerenderPlanning();
  }
}

export { assignSelectedTaskToTarget, createAssignment, movePersonToTeam, unassignAllocation, unassignTask };
