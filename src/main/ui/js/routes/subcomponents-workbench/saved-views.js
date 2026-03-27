import { VALID_SUBCOMPONENTS_WORKBENCH_PRESETS } from "./filters.js";

function subcomponentsWorkbenchStorageKey(ctx) {
  const { state, normalize, activeSpaceId, subcomponentsWorkbenchSavedViewsKeyPrefix } = ctx;
  const userKey = normalize(state.user?.soeid || state.user?.user_id || "anon");
  const spaceKey = normalize(activeSpaceId() || "no-space");
  return `${subcomponentsWorkbenchSavedViewsKeyPrefix}:${userKey}:${spaceKey}`;
}

export function setSubcomponentsWorkbenchSavedStatus(ctx, text) {
  const { els } = ctx;
  if (!els.subcomponentsWorkbenchSavedStatus) return;
  els.subcomponentsWorkbenchSavedStatus.textContent = text || "";
}

export function loadSubcomponentsWorkbenchSavedViews(ctx) {
  const { state } = ctx;
  const wb = state.subcomponentsWorkbench;
  wb.savedViews = [];
  wb.selectedSavedViewId = "";
  if (!state.authed) return;
  let recovered = false;
  let parsed = [];
  try {
    const raw = localStorage.getItem(subcomponentsWorkbenchStorageKey(ctx)) || "[]";
    const candidate = JSON.parse(raw);
    if (Array.isArray(candidate)) {
      parsed = candidate;
    } else {
      recovered = true;
    }
  } catch (err) {
    recovered = true;
    console.warn("Unable to load subcomponent workbench saved views", err);
  }
  const normalizedViews = parsed
    .filter((row) => row && typeof row === "object" && typeof row.name === "string")
    .map((row) => ({
      view_id: String(row.view_id || `sv_${Math.random().toString(36).slice(2, 10)}`),
      name: String(row.name || "").trim(),
      preset: VALID_SUBCOMPONENTS_WORKBENCH_PRESETS.has(String(row.preset || "all"))
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
    persistSubcomponentsWorkbenchSavedViews(ctx);
  }
}

export function persistSubcomponentsWorkbenchSavedViews(ctx) {
  const { state } = ctx;
  if (!state.authed) return;
  try {
    localStorage.setItem(
      subcomponentsWorkbenchStorageKey(ctx),
      JSON.stringify(state.subcomponentsWorkbench.savedViews || [])
    );
  } catch (err) {
    console.warn("Unable to persist subcomponent workbench saved views", err);
  }
}

export function updateSubcomponentsWorkbenchSavedViewsUI(ctx) {
  const { state, els, escapeHtml, persistSubcomponentsWorkbenchUiState } = ctx;
  const wb = state.subcomponentsWorkbench;
  if (!els.subcomponentsWorkbenchSavedSelect) return;
  const options = (wb.savedViews || [])
    .slice()
    .sort((a, b) => (a.name || "").localeCompare(b.name || ""))
    .map((row) => `<option value="${row.view_id}">${escapeHtml(row.name)}</option>`)
    .join("");
  els.subcomponentsWorkbenchSavedSelect.innerHTML = `<option value="">Select</option>${options}`;
  let selectionChanged = false;
  if (wb.selectedSavedViewId && wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId)) {
    els.subcomponentsWorkbenchSavedSelect.value = wb.selectedSavedViewId;
  } else if (wb.selectedSavedViewId) {
    wb.selectedSavedViewId = "";
    els.subcomponentsWorkbenchSavedSelect.value = "";
    selectionChanged = true;
  } else if (els.subcomponentsWorkbenchSavedSelect.value) {
    wb.selectedSavedViewId = els.subcomponentsWorkbenchSavedSelect.value;
    selectionChanged = true;
  }
  if (
    els.subcomponentsWorkbenchSavedName &&
    wb.selectedSavedViewId &&
    document.activeElement !== els.subcomponentsWorkbenchSavedName
  ) {
    const saved = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId);
    if (saved) els.subcomponentsWorkbenchSavedName.value = saved.name || "";
  }
  if (selectionChanged) persistSubcomponentsWorkbenchUiState();
}

function captureSubcomponentsWorkbenchCurrentView(ctx, name) {
  const { state } = ctx;
  const wb = state.subcomponentsWorkbench;
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

export function applySubcomponentsWorkbenchSavedView(ctx, savedView) {
  const { state, renderSubcomponentsWorkbench, normalizeSubcomponentsWorkbenchUiState } = ctx;
  if (!savedView) return;
  const wb = state.subcomponentsWorkbench;
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
  wb.activeSubcomponentId = "";
  normalizeSubcomponentsWorkbenchUiState({ persist: true });
  renderSubcomponentsWorkbench();
}

export function bindSubcomponentsWorkbenchSavedViewControls(ctx) {
  const { state, els, normalize, showConfirmModal, persistSubcomponentsWorkbenchUiState } = ctx;
  const wb = state.subcomponentsWorkbench;

  if (els.subcomponentsWorkbenchSavedSelect && !els.subcomponentsWorkbenchSavedSelect._bound) {
    els.subcomponentsWorkbenchSavedSelect.addEventListener("change", () => {
      const nextId = els.subcomponentsWorkbenchSavedSelect.value || "";
      wb.selectedSavedViewId = nextId;
      if (!nextId) {
        setSubcomponentsWorkbenchSavedStatus(ctx, "");
        persistSubcomponentsWorkbenchUiState();
        return;
      }
      const saved = wb.savedViews.find((row) => row.view_id === nextId);
      if (!saved) return;
      if (els.subcomponentsWorkbenchSavedName) {
        els.subcomponentsWorkbenchSavedName.value = saved.name || "";
      }
      setSubcomponentsWorkbenchSavedStatus(ctx, `Applied "${saved.name}"`);
      persistSubcomponentsWorkbenchUiState();
      applySubcomponentsWorkbenchSavedView(ctx, saved);
    });
    els.subcomponentsWorkbenchSavedSelect._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedSave && !els.subcomponentsWorkbenchSavedSave._bound) {
    els.subcomponentsWorkbenchSavedSave.addEventListener("click", () => {
      const rawName = (els.subcomponentsWorkbenchSavedName?.value || "").trim();
      if (!rawName) {
        setSubcomponentsWorkbenchSavedStatus(ctx, "Enter a view name before saving.");
        return;
      }
      let existing = null;
      if (wb.selectedSavedViewId) {
        existing = wb.savedViews.find((row) => row.view_id === wb.selectedSavedViewId) || null;
      }
      if (!existing) {
        existing = wb.savedViews.find((row) => normalize(row.name) === normalize(rawName)) || null;
      }
      const captured = captureSubcomponentsWorkbenchCurrentView(ctx, rawName);
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
      persistSubcomponentsWorkbenchSavedViews(ctx);
      persistSubcomponentsWorkbenchUiState();
      updateSubcomponentsWorkbenchSavedViewsUI(ctx);
      setSubcomponentsWorkbenchSavedStatus(ctx, `Saved "${rawName}"`);
    });
    els.subcomponentsWorkbenchSavedSave._bound = true;
  }

  if (els.subcomponentsWorkbenchSavedDelete && !els.subcomponentsWorkbenchSavedDelete._bound) {
    els.subcomponentsWorkbenchSavedDelete.addEventListener("click", async () => {
      const selectedId = wb.selectedSavedViewId || els.subcomponentsWorkbenchSavedSelect?.value || "";
      if (!selectedId) {
        setSubcomponentsWorkbenchSavedStatus(ctx, "Select a saved view to delete.");
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
      persistSubcomponentsWorkbenchSavedViews(ctx);
      persistSubcomponentsWorkbenchUiState();
      updateSubcomponentsWorkbenchSavedViewsUI(ctx);
      setSubcomponentsWorkbenchSavedStatus(ctx, `Deleted "${saved.name}"`);
    });
    els.subcomponentsWorkbenchSavedDelete._bound = true;
  }
}
