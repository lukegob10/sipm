export function populateTasksWorkbenchOptions(ctx, { projectOptionsHtml = "" } = {}) {
  const { state, els, normalizeTasksWorkbenchUiState } = ctx;

  if (els.tasksWorkbenchProject) {
    els.tasksWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOptionsHtml}`;
  }

  if (els.tasksWorkbenchAssignee || els.tasksWorkbenchBulkAssignee || els.tasksWorkbenchForm) {
    const users = state.users
      .filter((user) => user.display_name && user.soeid)
      .sort((a, b) => (a.display_name || "").localeCompare(b.display_name || ""));
    const userOptions = users.map((user) => `<option value="${user.soeid}">${user.display_name}</option>`).join("");

    if (els.tasksWorkbenchAssignee) {
      els.tasksWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;
    }
    if (els.tasksWorkbenchBulkAssignee) {
      const prior = els.tasksWorkbenchBulkAssignee.value || "";
      els.tasksWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;
      if (prior && users.find((user) => user.soeid === prior)) {
        els.tasksWorkbenchBulkAssignee.value = prior;
      }
    }
    if (els.tasksWorkbenchForm) {
      const assigneeSel = els.tasksWorkbenchForm.querySelector('[name="assignee"]');
      const assigneeUserInput = els.tasksWorkbenchForm.querySelector('[name="assignee_user_soeid"]');
      if (assigneeSel) {
        const prior = assigneeSel.value || "";
        assigneeSel.innerHTML = `<option value="">Unassigned</option>${userOptions}`;
        if (prior && users.find((user) => user.soeid === prior)) {
          assigneeSel.value = prior;
        }
        assigneeSel.onchange = () => {
          if (assigneeUserInput) assigneeUserInput.value = assigneeSel.value || "";
        };
      }
    }
  }

  normalizeTasksWorkbenchUiState({ persist: true });
}
