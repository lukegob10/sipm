function isTypingInputTarget(target) {
  if (!target) return false;
  const tag = (target.tagName || "").toLowerCase();
  if (["input", "textarea", "select", "button"].includes(tag)) return true;
  if (target.isContentEditable) return true;
  return false;
}

function renderSubcomponentsWorkbenchDrawerProjectLink(ctx, label, projectId) {
  const { escapeHtml } = ctx;
  const text = String(label || "").trim() || "Unknown project";
  const targetId = String(projectId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-context-action="open-project" data-project-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderSubcomponentsWorkbenchDrawerSolutionLink(ctx, label, solutionId) {
  const { escapeHtml } = ctx;
  const text = String(label || "").trim() || "Unknown solution";
  const targetId = String(solutionId || "").trim();
  if (!targetId) return escapeHtml(text);
  return `<button type="button" class="sub-workbench-context-link" data-scwb-context-action="open-solution" data-solution-id="${escapeHtml(targetId)}">${escapeHtml(text)}</button>`;
}

function renderSubcomponentsWorkbenchDrawerRepoContext(ctx, subcomponent) {
  const { effectiveSubcomponentRepoInfo, renderExternalRepoLink, escapeHtml } = ctx;
  const { url, source } = effectiveSubcomponentRepoInfo(
    subcomponent?.solution_id,
    subcomponent?.github_repo_url
  );
  if (!url) {
    return `<span class="sub-workbench-context-secondary">Repo: <span class="muted">Not set</span></span>`;
  }
  const sourceLabel = source === "override" ? "override" : "inherited";
  return `<span class="sub-workbench-context-secondary">Repo: ${renderExternalRepoLink(url, {
    label: url,
    className: "repo-external-link-inline",
  })} <span class="sub-workbench-context-source">(${escapeHtml(sourceLabel)})</span></span>`;
}

export function syncSubcomponentsWorkbenchDrawer(ctx) {
  const { state, els } = ctx;
  const wb = state.subcomponentsWorkbench;
  const drawerOpen = wb.drawerOpen !== false;
  if (els.subcomponentsWorkbenchDrawer) {
    els.subcomponentsWorkbenchDrawer.classList.toggle("hidden", !drawerOpen);
  }
  if (els.subcomponentsWorkbenchLayout) {
    els.subcomponentsWorkbenchLayout.classList.toggle("sub-workbench-layout-drawer-hidden", !drawerOpen);
  }
}

export function openSubcomponentsWorkbenchDrawer(ctx, preferredSubcomponentId = "") {
  const { state, persistSubcomponentsWorkbenchUiState, renderSubcomponentsWorkbench } = ctx;
  const wb = state.subcomponentsWorkbench;
  if (wb.drawerOpen === false) {
    const anchorId =
      preferredSubcomponentId || wb.activeSubcomponentId || (Array.isArray(wb.visibleIds) ? wb.visibleIds[0] : "") || "";
    wb.drawerReturnSubcomponentId = anchorId;
    wb.drawerReturnScrollY = window.scrollY || window.pageYOffset || 0;
  }
  if (preferredSubcomponentId) {
    wb.activeSubcomponentId = preferredSubcomponentId;
  } else if (!wb.activeSubcomponentId && Array.isArray(wb.visibleIds) && wb.visibleIds.length) {
    wb.activeSubcomponentId = wb.visibleIds[0];
  }
  wb.drawerOpen = true;
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
}

export function closeSubcomponentsWorkbenchDrawer(ctx) {
  const { state, els, persistSubcomponentsWorkbenchUiState, renderSubcomponentsWorkbench } = ctx;
  const wb = state.subcomponentsWorkbench;
  const returnSubcomponentId = wb.activeSubcomponentId || wb.drawerReturnSubcomponentId || "";
  wb.activeSubcomponentId = returnSubcomponentId;
  wb.drawerOpen = false;
  wb.drawerReturnSubcomponentId = "";
  wb.drawerReturnScrollY = null;
  wb.suppressAutoScrollOnce = true;
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
  window.requestAnimationFrame(() => {
    if (!returnSubcomponentId || !els.subcomponentsWorkbenchTable) return;
    const row = Array.from(els.subcomponentsWorkbenchTable.querySelectorAll("tr[data-id]")).find(
      (node) => node.getAttribute("data-id") === returnSubcomponentId
    );
    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
    const target = row || row?.querySelector(".scwb-select-row");
    if (!target || typeof target.focus !== "function") return;
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  });
}

export function setActiveSubcomponentByOffset(ctx, offset) {
  const { state, renderSubcomponentsWorkbench } = ctx;
  const wb = state.subcomponentsWorkbench;
  const ids = wb.visibleIds || [];
  if (!ids.length) return;
  const rawIndex = ids.indexOf(wb.activeSubcomponentId);
  if (rawIndex === -1) {
    wb.activeSubcomponentId = offset >= 0 ? ids[0] : ids[ids.length - 1];
    renderSubcomponentsWorkbench();
    return;
  }
  const nextIndex = Math.min(ids.length - 1, Math.max(0, rawIndex + offset));
  const nextId = ids[nextIndex];
  if (!nextId) return;
  wb.activeSubcomponentId = nextId;
  renderSubcomponentsWorkbench();
}

export function scrollActiveSubcomponentIntoView(ctx) {
  const { state, els } = ctx;
  const wb = state.subcomponentsWorkbench;
  if (!wb.activeSubcomponentId || !els.subcomponentsWorkbenchTable) return;
  const row = els.subcomponentsWorkbenchTable.querySelector(`tr[data-id="${wb.activeSubcomponentId}"]`);
  if (row && typeof row.scrollIntoView === "function") {
    row.scrollIntoView({ block: "nearest" });
  }
}

export async function renderSubcomponentsWorkbenchActivity(ctx, subcomponentId) {
  const { els, state, api, escapeHtml } = ctx;
  const activityEl = els.subcomponentsWorkbenchActivity;
  const wb = state.subcomponentsWorkbench;
  if (!activityEl) return;
  const reqId = (wb.activityRequestId || 0) + 1;
  wb.activityRequestId = reqId;
  if (!subcomponentId) {
    activityEl.innerHTML = "<p class='muted'>Select a subcomponent to see activity.</p>";
    return;
  }
  activityEl.innerHTML = "<p class='muted'>Loading activity…</p>";
  try {
    const rows = await api(`/subcomponents/${encodeURIComponent(subcomponentId)}/activity?limit=12`);
    if (wb.activityRequestId !== reqId) return;
    if (!rows?.length) {
      activityEl.innerHTML = "<p class='muted'>No activity yet.</p>";
      return;
    }
    activityEl.innerHTML = rows
      .map((row) => {
        const action = escapeHtml(row.action || "update");
        const field = row.field ? ` • ${escapeHtml(row.field)}` : "";
        const change = row.new_value ? ` → ${escapeHtml(String(row.new_value).slice(0, 90))}` : "";
        const when = row.created_at ? new Date(row.created_at).toLocaleString() : "";
        return `<div class="activity-item">
          <div class="activity-title">${action}${field}${change}</div>
          <div class="activity-meta">${escapeHtml(row.user_id || "system")} • ${escapeHtml(when)}</div>
        </div>`;
      })
      .join("");
  } catch (_err) {
    if (wb.activityRequestId !== reqId) return;
    activityEl.innerHTML = "<p class='muted'>Activity unavailable for this role.</p>";
  }
}

export function fillSubcomponentsWorkbenchForm(ctx, subcomponent) {
  const {
    els,
    state,
    clearDeliverableFormNotice,
    resolveAssigneeSelectValue,
  } = ctx;
  if (!els.subcomponentsWorkbenchForm) return;
  const form = els.subcomponentsWorkbenchForm;
  const idInput = form.querySelector('[name="subcomponent_id"]');
  const saveButton = form.querySelector('button[type="submit"]');
  const deleteButton = els.subcomponentsWorkbenchDelete;
  const previousId = form.dataset.activeSubcomponentId || "";
  const setValue = (name, value) => {
    const el = form.querySelector(`[name="${name}"]`);
    if (el) el.value = value == null ? "" : value;
  };
  if (!subcomponent) {
    form.dataset.activeSubcomponentId = "";
    form.reset();
    if (idInput) idInput.value = "";
    if (els.subcomponentsWorkbenchContext) {
      els.subcomponentsWorkbenchContext.textContent = "Select a subcomponent to edit.";
    }
    if (saveButton) saveButton.disabled = true;
    if (deleteButton) deleteButton.disabled = true;
    clearDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus);
    void renderSubcomponentsWorkbenchActivity(ctx, "");
    return;
  }
  const currentId = subcomponent.subcomponent_id || "";
  if (previousId !== currentId) {
    clearDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus);
  }
  form.dataset.activeSubcomponentId = currentId;
  if (saveButton) saveButton.disabled = false;
  if (deleteButton) deleteButton.disabled = !currentId;
  if (idInput) idInput.value = subcomponent.subcomponent_id || "";
  setValue("subcomponent_name", subcomponent.subcomponent_name || "");
  setValue("status", subcomponent.status || "to_do");
  setValue("priority", subcomponent.priority ?? "");
  setValue("due_date", subcomponent.due_date || "");
  setValue("blocker_note", subcomponent.blocker_note || "");
  const blocked = form.querySelector('[name="blocked"]');
  if (blocked) blocked.checked = !!subcomponent.blocked;

  const assigneeSelect = form.querySelector('[name="assignee"]');
  const assigneeUserInput = form.querySelector('[name="assignee_user_soeid"]');
  const assigneeValue = resolveAssigneeSelectValue(subcomponent.assignee_user_soeid, subcomponent.assignee);
  if (assigneeSelect) assigneeSelect.value = assigneeValue || "";
  if (assigneeUserInput) assigneeUserInput.value = assigneeValue || "";

  if (els.subcomponentsWorkbenchContext) {
    const project = state.projects.find((row) => row.project_id === subcomponent.project_id)?.project_name || "Unknown project";
    const solution = state.solutions.find((row) => row.solution_id === subcomponent.solution_id)?.solution_name || "Unknown solution";
    els.subcomponentsWorkbenchContext.innerHTML = `
      <span class="sub-workbench-context-primary">${renderSubcomponentsWorkbenchDrawerProjectLink(ctx, project, subcomponent.project_id)} / ${renderSubcomponentsWorkbenchDrawerSolutionLink(ctx, solution, subcomponent.solution_id)}</span>
      ${renderSubcomponentsWorkbenchDrawerRepoContext(ctx, subcomponent)}
    `;
  }
  void renderSubcomponentsWorkbenchActivity(ctx, subcomponent.subcomponent_id);
}

export function openSubcomponentsWorkbenchProjectDrilldown(ctx, projectId) {
  const { state, openProjectForm } = ctx;
  const targetId = String(projectId || "").trim();
  if (!targetId) return;
  const project = state.projects.find((row) => row.project_id === targetId);
  if (!project) return;
  openProjectForm(project);
}

export function openSubcomponentsWorkbenchSolutionDrilldown(ctx, solutionId) {
  const { state, openSolutionModal } = ctx;
  const targetId = String(solutionId || "").trim();
  if (!targetId) return;
  const solution = state.solutions.find((row) => row.solution_id === targetId);
  if (!solution) return;
  openSolutionModal(solution, "details");
}

export function handleSubcomponentsWorkbenchTableClick(ctx, event) {
  const actionEl = event.target.closest("[data-scwb-action]");
  if (actionEl) {
    const action = actionEl.getAttribute("data-scwb-action") || "";
    if (action === "open-project") {
      openSubcomponentsWorkbenchProjectDrilldown(ctx, actionEl.getAttribute("data-project-id"));
    }
    if (action === "open-solution") {
      openSubcomponentsWorkbenchSolutionDrilldown(ctx, actionEl.getAttribute("data-solution-id"));
    }
    return;
  }
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  if (event.target.closest("button,input,select,textarea,label")) return;
  const subId = row.getAttribute("data-id") || "";
  if (!subId) return;
  openSubcomponentsWorkbenchDrawer(ctx, subId);
}

export function handleSubcomponentsWorkbenchContextClick(ctx, event) {
  const actionEl = event.target.closest("[data-scwb-context-action]");
  if (!actionEl) return;
  const action = actionEl.getAttribute("data-scwb-context-action") || "";
  if (action === "open-project") {
    openSubcomponentsWorkbenchProjectDrilldown(ctx, actionEl.getAttribute("data-project-id"));
  }
  if (action === "open-solution") {
    openSubcomponentsWorkbenchSolutionDrilldown(ctx, actionEl.getAttribute("data-solution-id"));
  }
}

export async function saveSubcomponentsWorkbenchForm(ctx) {
  const {
    state,
    els,
    api,
    upsertById,
    findUserBySoeid,
    renderSubcomponentsWorkbench,
    renderSolutionSubcomponents,
    setDeliverableFormNotice,
    timestampLabel,
  } = ctx;
  const formEl = els.subcomponentsWorkbenchForm;
  if (!formEl) return;
  const data = new FormData(formEl);
  const subId = data.get("subcomponent_id");
  if (!subId) {
    setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Select a subcomponent first.", "error");
    return;
  }
  const assigneeUserId = data.get("assignee") || "";
  const assigneeUser = findUserBySoeid(assigneeUserId);
  const payload = {
    subcomponent_name: data.get("subcomponent_name") || "",
    status: data.get("status") || "to_do",
    priority: Number(data.get("priority") || 3),
    due_date: data.get("due_date") || null,
    assignee: assigneeUser?.display_name || "",
    assignee_user_soeid: assigneeUserId || null,
    blocked: !!data.get("blocked"),
    blocker_note: data.get("blocker_note") || null,
  };
  try {
    setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Saving subcomponent...");
    const updated = await api(`/subcomponents/${subId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    upsertById(state.subcomponents, updated, "subcomponent_id");
    state.subcomponentsWorkbench.activeSubcomponentId = updated.subcomponent_id;
    ctx.persistSubcomponentsWorkbenchUiState();
    renderSubcomponentsWorkbench();
    const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
    if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
      renderSolutionSubcomponents(openSolutionId);
    }
    setDeliverableFormNotice(
      els.subcomponentsWorkbenchFormStatus,
      `Saved subcomponent at ${timestampLabel()}.`,
      "success",
      3200
    );
  } catch (err) {
    setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, `Save failed: ${err.message || err}`, "error");
  }
}

export async function deleteActiveSubcomponentsWorkbenchItem(ctx) {
  const {
    els,
    markIgnoreRefresh,
    deleteSubcomponentsById,
    ignoreNextRefresh,
    renderSubcomponentsWorkbench,
    renderSolutionSubcomponents,
    renderDashboard,
    setDeliverableFormNotice,
    timestampLabel,
  } = ctx;
  const subId = els.subcomponentsWorkbenchForm?.querySelector('[name="subcomponent_id"]')?.value || "";
  if (!subId) {
    setDeliverableFormNotice(els.subcomponentsWorkbenchFormStatus, "Select a subcomponent first.", "error");
    return;
  }
  markIgnoreRefresh("subcomponents");
  const result = await deleteSubcomponentsById([subId], {
    title: "Delete Subcomponent?",
  });
  if (result.cancelled) return;
  if (!result.deletedIds.length) {
    ignoreNextRefresh.delete("subcomponents");
  }
  renderSubcomponentsWorkbench();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
    renderSolutionSubcomponents(openSolutionId);
  }
  renderDashboard();
  if (result.failed.length) {
    setDeliverableFormNotice(
      els.subcomponentsWorkbenchFormStatus,
      `Delete failed for ${result.failed.length} subcomponent(s).`,
      "error"
    );
    return;
  }
  setDeliverableFormNotice(
    els.subcomponentsWorkbenchFormStatus,
    `Deleted subcomponent at ${timestampLabel()}.`,
    "success",
    3200
  );
}

export function resetSubcomponentsWorkbenchEditor(ctx) {
  const { state, persistSubcomponentsWorkbenchUiState, renderSubcomponentsWorkbench } = ctx;
  state.subcomponentsWorkbench.activeSubcomponentId = "";
  persistSubcomponentsWorkbenchUiState();
  renderSubcomponentsWorkbench();
}

export async function handleSubcomponentsWorkbenchShortcut(ctx, event) {
  const {
    state,
    els,
    markIgnoreRefresh,
    deleteSubcomponentsById,
    ignoreNextRefresh,
    renderSubcomponentsWorkbench,
    renderSolutionSubcomponents,
    renderDashboard,
    setSubcomponentsWorkbenchBulkFeedback,
  } = ctx;
  if (state.currentView !== "subcomponents-workbench") return;
  if (event.altKey || event.ctrlKey || event.metaKey) return;

  const wb = state.subcomponentsWorkbench;
  const key = (event.key || "").toLowerCase();
  const inWorkbenchTable = !!event.target?.closest?.("#subcomponents-workbench-table");
  const typingContext = isTypingInputTarget(event.target) && !inWorkbenchTable;

  if (key === "/" && !typingContext) {
    event.preventDefault();
    els.subcomponentsWorkbenchSearch?.focus();
    return;
  }
  if (key === "escape") {
    if (wb.drawerOpen !== false) {
      event.preventDefault();
      closeSubcomponentsWorkbenchDrawer(ctx);
    }
    return;
  }
  if (typingContext) return;

  if (key === "arrowdown" || key === "arrowup") {
    event.preventDefault();
    setActiveSubcomponentByOffset(ctx, key === "arrowdown" ? 1 : -1);
    return;
  }
  if (key === "e") {
    event.preventDefault();
    openSubcomponentsWorkbenchDrawer(ctx);
    window.setTimeout(() => {
      const target = els.subcomponentsWorkbenchForm?.querySelector('[name="subcomponent_name"]');
      if (target) target.focus();
    }, 0);
    return;
  }
  if (key !== "delete") return;

  const selectedIds = Array.from(wb.selected);
  const targetIds = selectedIds.length
    ? selectedIds
    : (wb.activeSubcomponentId ? [wb.activeSubcomponentId] : []);
  if (!targetIds.length) return;
  event.preventDefault();
  markIgnoreRefresh("subcomponents");
  const result = await deleteSubcomponentsById(targetIds, {
    title: targetIds.length === 1 ? "Delete Subcomponent?" : "Delete Selected Subcomponents?",
  });
  if (result.cancelled) return;
  if (!result.deletedIds.length) {
    ignoreNextRefresh.delete("subcomponents");
  }
  renderSubcomponentsWorkbench();
  const openSolutionId = els.solutionForm?.querySelector('[name="solution_id"]')?.value || "";
  if (openSolutionId && !els.solutionModal?.classList.contains("hidden")) {
    renderSolutionSubcomponents(openSolutionId);
  }
  renderDashboard();
  if (result.failed.length) {
    setSubcomponentsWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length}, but ${result.failed.length} failed.`,
      "error"
    );
  } else {
    setSubcomponentsWorkbenchBulkFeedback(
      `Deleted ${result.deletedIds.length} subcomponent${result.deletedIds.length === 1 ? "" : "s"}.`,
      "success",
      3200
    );
  }
}
