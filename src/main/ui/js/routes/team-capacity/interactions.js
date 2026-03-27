export function createTeamCapacityRouteController({
  state,
  els,
  teamCapacityViewStateKey,
  writeStoredJson,
  readStoredJsonState,
  activeSpaceScopedStorageKey,
  bindDebouncedInput,
  renderTeamCapacity,
  api,
  applyEntityData,
  handleAuthError,
  populateSelects,
  clearCapacityUserFormStatus,
  setCapacityUserFormStatus,
  userCapacityFteMonth,
  formatFte,
  numberOr,
  timestampLabel,
  showConfirmModal,
}) {
  function normalizeCapacityLookup(value) {
    return String(value || "").trim().toLowerCase();
  }

  function findCapacityUserBySoeid(soeid) {
    const norm = normalizeCapacityLookup(soeid);
    if (!norm) return null;
    return state.users.find((u) => normalizeCapacityLookup(u.soeid) === norm) || null;
  }

  function findCapacityUserByValue(value) {
    const norm = normalizeCapacityLookup(value);
    if (!norm) return null;
    return (
      findCapacityUserBySoeid(norm) ||
      state.users.find((u) => normalizeCapacityLookup(u.display_name) === norm) ||
      null
    );
  }

  function persistTeamCapacityViewState() {
    writeStoredJson(
      activeSpaceScopedStorageKey(teamCapacityViewStateKey),
      {
        team_filter: String(els.capacityTeamFilter?.value || ""),
        name_filter: String(els.capacityNameFilter?.value || ""),
        selected_soeid: String(state.capacitySelectedSoeid || ""),
      }
    );
  }

  function restoreTeamCapacityViewState() {
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(teamCapacityViewStateKey), {});
    if (els.capacityTeamFilter) els.capacityTeamFilter.value = String(stored.team_filter || "");
    if (els.capacityNameFilter) els.capacityNameFilter.value = String(stored.name_filter || "");
    state.capacitySelectedSoeid = String(stored.selected_soeid || "");
    if (recovered) persistTeamCapacityViewState();
    if (recovered) return;
    if (recovered || !Object.keys(stored || {}).length) persistTeamCapacityViewState();
  }

  function selectCapacityUser(user, options = {}) {
    const form = els.capacityUserForm;
    if (!form) return;
    const preserveName = !!options.preserveName;
    const preserveStatus = !!options.preserveStatus;
    const shouldRender = options.render !== false;
    const next = user || null;
    if (!preserveStatus) clearCapacityUserFormStatus();
    state.capacitySelectedSoeid = next?.soeid || "";
    form.querySelector('[name="soeid"]').value = next?.soeid || "";
    if (!preserveName) {
      form.querySelector('[name="display_name"]').value = next?.display_name || "";
    }
    form.querySelector('[name="team_tag"]').value = next?.team_tag || "";
    form.querySelector('[name="capacity_fte_month"]').value = formatFte(next ? userCapacityFteMonth(next) : 1);
    persistTeamCapacityViewState();
    if (shouldRender && state.currentView === "team-capacity") {
      renderTeamCapacity();
    }
  }

  function clearCapacityUserForm(options = {}) {
    if (!els.capacityUserForm) return;
    const preserveStatus = !!options.preserveStatus;
    const shouldRender = options.render !== false;
    if (!preserveStatus) clearCapacityUserFormStatus();
    els.capacityUserForm.reset();
    state.capacitySelectedSoeid = "";
    els.capacityUserForm.querySelector('[name="soeid"]').value = "";
    const fteField = els.capacityUserForm.querySelector('[name="capacity_fte_month"]');
    if (fteField) fteField.value = "1.00";
    persistTeamCapacityViewState();
    if (shouldRender && state.currentView === "team-capacity") {
      renderTeamCapacity();
    }
  }

  async function loadTeamCapacityData(options = {}) {
    if (!state.authed) return;
    const force = !!options.force;
    const preserveSelection = options.preserveSelection !== false;
    if (!force && state.teamCapacity.loading) return;
    const requestedSpaceId = state.activeSpace?.space_id || "";
    const requestedSpaceName = state.activeSpace?.space_name || "";
    if (!requestedSpaceId) {
      state.teamCapacity.error = "No active space selected.";
      state.teamCapacity.lastLoadedAt = "";
      applyEntityData("users", []);
      applyEntityData("allocations", []);
      if (state.currentView === "team-capacity") renderTeamCapacity();
      return;
    }

    const requestId = (state.teamCapacity.requestId || 0) + 1;
    state.teamCapacity.requestId = requestId;
    state.teamCapacity.loading = true;
    state.teamCapacity.error = "";
    if (state.currentView === "team-capacity") renderTeamCapacity();

    try {
      const spaceHeaders = { "X-Space-Id": requestedSpaceId };
      const [usersResult, allocationsResult] = await Promise.allSettled([
        api("/users?active_only=true", { timeoutMs: 45000, headers: spaceHeaders }),
        api("/resource-allocations", { timeoutMs: 45000, headers: spaceHeaders }),
      ]);
      if (state.teamCapacity.requestId !== requestId) return;
      if ((state.activeSpace?.space_id || "") !== requestedSpaceId) return;

      const loadErrors = [];
      if (usersResult.status === "fulfilled") {
        applyEntityData("users", usersResult.value);
      } else {
        if (handleAuthError(usersResult.reason)) return;
        loadErrors.push(`roster: ${usersResult.reason?.message || "failed"}`);
      }
      if (allocationsResult.status === "fulfilled") {
        applyEntityData("allocations", allocationsResult.value);
      } else {
        if (handleAuthError(allocationsResult.reason)) return;
        loadErrors.push(`allocations: ${allocationsResult.reason?.message || "failed"}`);
        applyEntityData("allocations", []);
      }

      if (loadErrors.length) {
        state.teamCapacity.error = `Partial load: ${loadErrors.join(" | ")}`;
      }
      state.teamCapacity.lastLoadedAt = new Date().toISOString();
      state.teamCapacity.lastLoadedSpaceId = requestedSpaceId;
      state.teamCapacity.lastLoadedSpaceName = requestedSpaceName;
      populateSelects();
      if (preserveSelection && state.capacitySelectedSoeid) {
        const selected = findCapacityUserBySoeid(state.capacitySelectedSoeid);
        if (selected) selectCapacityUser(selected, { render: false });
        else clearCapacityUserForm({ render: false });
      }
      persistTeamCapacityViewState();
    } catch (err) {
      if (state.teamCapacity.requestId !== requestId) return;
      if (handleAuthError(err)) return;
      state.teamCapacity.error = err?.message || "Failed to load team capacity data.";
    } finally {
      if (state.teamCapacity.requestId === requestId) {
        state.teamCapacity.loading = false;
        if (state.currentView === "team-capacity") renderTeamCapacity();
      }
    }
  }

  function bindTeamCapacityControls() {
    if (els.capacityUserForm) {
      const nameInput = els.capacityUserForm.querySelector('[name="display_name"]');
      if (nameInput) {
        nameInput.addEventListener("input", () => {
          clearCapacityUserFormStatus();
          const match = findCapacityUserByValue(nameInput.value || "");
          els.capacityUserForm.querySelector('[name="soeid"]').value = match?.soeid || "";
          if (match) {
            state.capacitySelectedSoeid = match.soeid || "";
            els.capacityUserForm.querySelector('[name="team_tag"]').value = match.team_tag || "";
            els.capacityUserForm.querySelector('[name="capacity_fte_month"]').value = formatFte(userCapacityFteMonth(match));
            persistTeamCapacityViewState();
            if (state.currentView === "team-capacity") renderTeamCapacity();
          } else if (state.capacitySelectedSoeid) {
            state.capacitySelectedSoeid = "";
            persistTeamCapacityViewState();
            renderTeamCapacity();
          }
        });
        nameInput.addEventListener("blur", () => {
          const match = findCapacityUserByValue(nameInput.value || "");
          if (match) {
            selectCapacityUser(match);
          }
        });
      }
      els.capacityUserForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const data = new FormData(els.capacityUserForm);
        const soeid = normalizeCapacityLookup(data.get("soeid")) || normalizeCapacityLookup(findCapacityUserByValue(data.get("display_name"))?.soeid);
        if (!soeid) {
          setCapacityUserFormStatus("Select a member from the roster (or type an exact SOEID/name match) first.", "error");
          return;
        }
        const payload = {
          team_tag: data.get("team_tag") || null,
          capacity_fte_month: numberOr(data.get("capacity_fte_month"), 0),
        };
        try {
          await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify(payload) });
          await loadTeamCapacityData({ force: true, preserveSelection: false });
          const refreshed = findCapacityUserBySoeid(soeid);
          if (refreshed) selectCapacityUser(refreshed, { preserveStatus: true });
          else clearCapacityUserForm({ preserveStatus: true });
          setCapacityUserFormStatus(`Saved member at ${timestampLabel()}.`, "success", 3200);
        } catch (err) {
          setCapacityUserFormStatus(`Save failed: ${err.message}`, "error");
        }
      });
      els.capacityUserForm.addEventListener("reset", () => {
        clearCapacityUserForm();
      });
    }
    if (els.capacityUserDelete) {
      els.capacityUserDelete.addEventListener("click", async () => {
        const soeid = els.capacityUserForm?.querySelector('[name="soeid"]')?.value;
        if (!soeid) {
          setCapacityUserFormStatus("Select a member first.", "error");
          return;
        }
        const confirmed = await showConfirmModal({
          title: "Deactivate Member?",
          message: "Deactivate this member? They will be hidden from the roster.",
          confirmLabel: "Deactivate Member",
        });
        if (!confirmed) return;
        try {
          await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify({ is_active: false }) });
          clearCapacityUserForm({ render: false, preserveStatus: true });
          await loadTeamCapacityData({ force: true, preserveSelection: false });
          setCapacityUserFormStatus(`Member deactivated at ${timestampLabel()}.`, "success", 3200);
        } catch (err) {
          setCapacityUserFormStatus(`Delete failed: ${err.message}`, "error");
        }
      });
    }
    if (els.capacityUserList) {
      els.capacityUserList.addEventListener("click", (e) => {
        const row = e.target.closest("tr[data-soeid]");
        if (!row) return;
        const soeid = row.getAttribute("data-soeid");
        const user = state.users.find((u) => u.soeid === soeid);
        if (!user) return;
        selectCapacityUser(user);
      });
    }
    bindDebouncedInput(els.capacityTeamFilter, () => {
      persistTeamCapacityViewState();
      renderTeamCapacity();
    });
    bindDebouncedInput(els.capacityNameFilter, () => {
      persistTeamCapacityViewState();
      renderTeamCapacity();
    });
    if (els.capacityReload) {
      els.capacityReload.addEventListener("click", async () => {
        await loadTeamCapacityData({ force: true });
      });
    }
    if (els.capacityClearFilters) {
      els.capacityClearFilters.addEventListener("click", () => {
        if (els.capacityTeamFilter) els.capacityTeamFilter.value = "";
        if (els.capacityNameFilter) els.capacityNameFilter.value = "";
        persistTeamCapacityViewState();
        renderTeamCapacity();
      });
    }
  }

  return {
    bindTeamCapacityControls,
    loadTeamCapacityData,
    persistTeamCapacityViewState,
    restoreTeamCapacityViewState,
  };
}
