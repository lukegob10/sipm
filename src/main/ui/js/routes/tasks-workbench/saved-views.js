import { VALID_TASKS_WORKBENCH_PRESETS } from "./filters.js";

function tasksWorkbenchStorageKey(ctx) {
  const { state, normalize, activeSpaceId, tasksWorkbenchSavedViewsKeyPrefix } = ctx;
  const userKey = normalize(state.user?.soeid || state.user?.user_id || "anon");
  const spaceKey = normalize(activeSpaceId() || "no-space");
  return `${tasksWorkbenchSavedViewsKeyPrefix}:${userKey}:${spaceKey}`;
}

export function setTasksWorkbenchSavedStatus(ctx, text) {
  const { els } = ctx;
  if (!els.tasksWorkbenchSavedStatus) return;
  els.tasksWorkbenchSavedStatus.textContent = text || "";
}

export function loadTasksWorkbenchSavedViews(ctx) {
  const { state } = ctx;
  const wb = state.tasksWorkbench;
  wb.savedViews = [];
  wb.selectedSavedViewId = "";
  if (!state.authed) return;
  let recovered = false;
  let parsed = [];
  try {
    const raw = localStorage.getItem(tasksWorkbenchStorageKey(ctx)) || "[]";
    const candidate = JSON.parse(raw);
    if (Array.isArray(candidate)) {
      parsed = candidate;
    } else {
      recovered = true;
    }
  } catch (err) {
    recovered = true;
    console.warn("Unable to load task workbench saved views", err);
  }
  const normalizedViews = parsed
    .filter((row) => row && typeof row === "object" && typeof row.name === "string")
    .map((row) => ({
      view_id: String(row.view_id || `sv_${Math.random().toString(36).slice(2, 10)}`),
      name: String(row.name || "").trim(),
      preset: VALID_TASKS_WORKBENCH_PRESETS.has(String(row.preset || "all"))
        ? String(row.preset || "all")
        : "all",
      filters: {
        search: String(row.filters?.search || ""),
        project_id: String(row.filters?.project_id || ""),
        solution_id: String(row.filters?.solution_id || ""),
        assignee: String(row.filters?.assignee || ""),
        assignee_name: String(row.filters?.assignee_name || ""),
        status: String(row.filters?.status || ""),
        priority_max: String(row.filters?.priority_max || ""),
      },
      updated_at: String(row.updated_at || ""),
    }))
    .filter((row) => row.name);
  wb.savedViews = normalizedViews;
  if (recovered || JSON.stringify(parsed) !== JSON.stringify(normalizedViews)) {
    persistTasksWorkbenchSavedViews(ctx);
  }
}

export function persistTasksWorkbenchSavedViews(ctx) {
  const { state } = ctx;
  if (!state.authed) return;
  try {
    localStorage.setItem(
      tasksWorkbenchStorageKey(ctx),
      JSON.stringify(state.tasksWorkbench.savedViews || [])
    );
  } catch (err) {
    console.warn("Unable to persist task workbench saved views", err);
  }
}

export function updateTasksWorkbenchSavedViewsUI(ctx) {
  const { state, els, escapeHtml, persistTasksWorkbenchUiState } = ctx;
  const wb = state.tasksWorkbench;
  if (!els.tasksWorkbenchSavedSelect) return;
  const options = (wb.savedViews || [])
    .slice()
    .sort((a, b) => (a.name || "").localeCompare(b.name || ""))
    .map((row) => `<option value="${row.view_id}">${escapeHtml(row.name)}</option>`)
    .join("");
  els.tasksWorkbenchSavedSelect.innerHTML = `<option value="">Select</option>${options}`;
  let selectionChanged = false;
  if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {
    els.tasksWorkbenchSavedSelect.value = wb.selectedSavedViewId;
  } else if (wb.selectedSavedViewId) {
    wb.selectedSavedViewId = "";
    els.tasksWorkbenchSavedSelect.value = "";
    selectionChanged = true;
  } else if (els.tasksWorkbenchSavedSelect.value) {
    wb.selectedSavedViewId = els.tasksWorkbenchSavedSelect.value;
    selectionChanged = true;
  }
  if (
    els.tasksWorkbenchSavedName &&
    wb.selectedSavedViewId &&
    document.activeElement !== els.tasksWorkbenchSavedName
  ) {
    const saved = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId);
    if (saved) els.tasksWorkbenchSavedName.value = saved.name || "";
  }
  if (selectionChanged) persistTasksWorkbenchUiState();
}

function captureTasksWorkbenchCurrentView(ctx, name) {
  const { state } = ctx;
  const wb = state.tasksWorkbench;
  return {
    view_id: `sv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
    name: String(name || "").trim(),
    preset: wb.preset || "all",
    filters: {
      search: wb.filters.search || "",
      project_id: wb.filters.project_id || "",
      solution_id: wb.filters.solution_id || "",
      assignee: wb.filters.assignee || "",
      assignee_name: wb.filters.assignee_name || "",
      status: wb.filters.status || "",
      priority_max: wb.filters.priority_max || "",
    },
    updated_at: new Date().toISOString(),
  };
}

export function applyTasksWorkbenchSavedView(ctx, savedView) {
  const { state, renderTasksWorkbench, normalizeTasksWorkbenchUiState } = ctx;
  if (!savedView) return;
  const wb = state.tasksWorkbench;
  wb.selectedSavedViewId = savedView.view_id || wb.selectedSavedViewId || "";
  wb.preset = savedView.preset || "all";
  wb.filters = {
    search: savedView.filters?.search || "",
    project_id: savedView.filters?.project_id || "",
    solution_id: savedView.filters?.solution_id || "",
    assignee: savedView.filters?.assignee || "",
    assignee_name: savedView.filters?.assignee_name || "",
    status: savedView.filters?.status || "",
    priority_max: savedView.filters?.priority_max || "",
  };
  wb.selected.clear();
  wb.activeTaskId = "";
  normalizeTasksWorkbenchUiState({ persist: true });
  renderTasksWorkbench();
}

export function bindTasksWorkbenchSavedViewControls(ctx) {
  const { state, els, normalize, showConfirmModal, persistTasksWorkbenchUiState } = ctx;
  const wb = state.tasksWorkbench;

  if (els.tasksWorkbenchSavedSelect && !els.tasksWorkbenchSavedSelect._bound) {
    els.tasksWorkbenchSavedSelect.addEventListener("change", () => {
      const nextId = els.tasksWorkbenchSavedSelect.value || "";
      wb.selectedSavedViewId = nextId;
      if (!nextId) {
        setTasksWorkbenchSavedStatus(ctx, "");
        persistTasksWorkbenchUiState();
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === nextId);
      if (!saved) return;
      if (els.tasksWorkbenchSavedName) {
        els.tasksWorkbenchSavedName.value = saved.name || "";
      }
      setTasksWorkbenchSavedStatus(ctx, `Applied "${saved.name}"`);
      persistTasksWorkbenchUiState();
      applyTasksWorkbenchSavedView(ctx, saved);
    });
    els.tasksWorkbenchSavedSelect._bound = true;
  }

  if (els.tasksWorkbenchSavedSave && !els.tasksWorkbenchSavedSave._bound) {
    els.tasksWorkbenchSavedSave.addEventListener("click", () => {
      const rawName = (els.tasksWorkbenchSavedName?.value || "").trim();
      if (!rawName) {
        setTasksWorkbenchSavedStatus(ctx, "Enter a view name before saving.");
        return;
      }
      let existing = null;
      if (wb.selectedSavedViewId) {
        existing = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId) || null;
      }
      if (!existing) {
        existing = wb.savedViews.find((row) => normalize(row.name) === normalize(rawName)) || null;
      }
      const captured = captureTasksWorkbenchCurrentView(ctx, rawName);
      if (existing) {
        existing.name = captured.name;
        existing.preset = captured.preset;
        existing.filters = captured.filters;
        existing.updated_at = captured.updated_at;
        wb.selectedSavedViewId = existing.view_id;
      } else {
        wb.savedViews.push(captured);
        wb.selectedSavedViewId = captured.view_id;
      }
      persistTasksWorkbenchSavedViews(ctx);
      persistTasksWorkbenchUiState();
      updateTasksWorkbenchSavedViewsUI(ctx);
      setTasksWorkbenchSavedStatus(ctx, `Saved "${rawName}"`);
    });
    els.tasksWorkbenchSavedSave._bound = true;
  }

  if (els.tasksWorkbenchSavedDelete && !els.tasksWorkbenchSavedDelete._bound) {
    els.tasksWorkbenchSavedDelete.addEventListener("click", async () => {
      const selectedId = wb.selectedSavedViewId || els.tasksWorkbenchSavedSelect?.value || "";
      if (!selectedId) {
        setTasksWorkbenchSavedStatus(ctx, "Select a saved view to delete.");
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === selectedId);
      if (!saved) return;
      const confirmed = await showConfirmModal({
        title: "Delete Saved View?",
        message: `Delete saved view "${saved.name}"?`,
        confirmLabel: "Delete Saved View",
      });
      if (!confirmed) return;
      wb.savedViews = wb.savedViews.filter((row) => row.view_id !== selectedId);
      wb.selectedSavedViewId = "";
      persistTasksWorkbenchSavedViews(ctx);
      persistTasksWorkbenchUiState();
      updateTasksWorkbenchSavedViewsUI(ctx);
      setTasksWorkbenchSavedStatus(ctx, `Deleted "${saved.name}"`);
    });
    els.tasksWorkbenchSavedDelete._bound = true;
  }
}
