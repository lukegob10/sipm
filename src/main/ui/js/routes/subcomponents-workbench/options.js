export function populateSubcomponentsWorkbenchOptions(ctx, { projectOptionsHtml = "" } = {}) {
  const { state, els, normalizeSubcomponentsWorkbenchUiState } = ctx;

  if (els.subcomponentsWorkbenchProject) {
    els.subcomponentsWorkbenchProject.innerHTML = `<option value="">All Projects</option>${projectOptionsHtml}`;
  }

  if (els.subcomponentsWorkbenchAssignee || els.subcomponentsWorkbenchBulkAssignee || els.subcomponentsWorkbenchForm) {
    const users = state.users
      .filter((user) => user.display_name && user.soeid)
      .sort((a, b) => (a.display_name || "").localeCompare(b.display_name || ""));
    const userOptions = users.map((user) => `<option value="${user.soeid}">${user.display_name}</option>`).join("");

    if (els.subcomponentsWorkbenchAssignee) {
      els.subcomponentsWorkbenchAssignee.innerHTML = `<option value="">Any</option><option value="__unassigned__">Unassigned</option>${userOptions}`;
    }
    if (els.subcomponentsWorkbenchBulkAssignee) {
      const prior = els.subcomponentsWorkbenchBulkAssignee.value || "";
      els.subcomponentsWorkbenchBulkAssignee.innerHTML = `<option value="">Unassigned</option>${userOptions}`;
      if (prior && users.find((user) => user.soeid === prior)) {
        els.subcomponentsWorkbenchBulkAssignee.value = prior;
      }
    }
    if (els.subcomponentsWorkbenchForm) {
      const assigneeSel = els.subcomponentsWorkbenchForm.querySelector('[name="assignee"]');
      const assigneeUserInput = els.subcomponentsWorkbenchForm.querySelector('[name="assignee_user_soeid"]');
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

  normalizeSubcomponentsWorkbenchUiState({ persist: true });
}
