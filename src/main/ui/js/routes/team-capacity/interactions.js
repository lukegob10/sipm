import { createFormDraftGuard } from "../../utils/form-draft.js";
import { captureEntityMutationContext, clearTeamCapacityFields, isEntityMutationContextCurrent, isSameMutationSession } from "../../utils/form-state.js";

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
  timestampLabel,
  showConfirmModal,
  onViewDataLoaded = null,
  trackWorkflow = null,
}) {
  let pendingMutation = null;
  let editorRevision = 0;
  const pendingFilters = new Map();
  const capacityDraft = createFormDraftGuard({ form: els.capacityUserForm });
  let formContext = captureEntityMutationContext(state);
  let fieldBaseline = "";
  let selectionConfirmation = null;
  const editableFields = () => JSON.stringify([
    els.capacityUserForm?.querySelector('[name="team_tag"]')?.value || "",
    els.capacityUserForm?.querySelector('[name="capacity_fte_month"]')?.value || "",
  ]);
  function captureCapacityBaseline() {
    capacityDraft.capture();
    fieldBaseline = editableFields();
  }

  function beginMutation(context) {
    if (pendingMutation && isSameMutationSession(pendingMutation, context)) return null;
    const request = { ...context };
    pendingMutation = request;
    return request;
  }

  function endMutation(request) {
    if (pendingMutation === request) pendingMutation = null;
  }

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
    const bySoeid = findCapacityUserBySoeid(norm);
    if (bySoeid) return bySoeid;
    const matches = state.users.filter((u) => normalizeCapacityLookup(u.display_name) === norm);
    return matches.length === 1 ? matches[0] : null;
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
    if (!isEntityMutationContextCurrent(state, formContext)) {
      formContext = captureEntityMutationContext(state);
      selectionConfirmation = null;
      editorRevision += 1;
      captureCapacityBaseline();
    }
    const { value: stored, recovered } = readStoredJsonState(activeSpaceScopedStorageKey(teamCapacityViewStateKey), {});
    for (const [element, key] of [[els.capacityTeamFilter, "team_filter"], [els.capacityNameFilter, "name_filter"]]) {
      if (!element) continue;
      const pending = pendingFilters.get(element);
      if (pending && pending.authed === state.authed && isEntityMutationContextCurrent(state, pending.context)) element.value = pending.value;
      else { pendingFilters.delete(element); element.value = String(stored[key] || ""); }
    }
    state.capacitySelectedSoeid = String(stored.selected_soeid || "");
    if (recovered) persistTeamCapacityViewState();
    if (recovered) return;
    if (!Object.keys(stored || {}).length) persistTeamCapacityViewState();
  }

  function selectCapacityUser(user, options = {}) {
    const form = els.capacityUserForm;
    if (!form) return;
    editorRevision += 1;
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
    captureCapacityBaseline();
    persistTeamCapacityViewState();
    if (shouldRender && state.currentView === "team-capacity") {
      renderTeamCapacity();
    }
  }

  function clearCapacityUserForm(options = {}) {
    if (!els.capacityUserForm) return;
    editorRevision += 1;
    const preserveStatus = !!options.preserveStatus;
    const shouldRender = options.render !== false;
    if (!preserveStatus) clearCapacityUserFormStatus();
    state.capacitySelectedSoeid = "";
    clearTeamCapacityFields(els.capacityUserForm);
    captureCapacityBaseline();
    persistTeamCapacityViewState();
    if (shouldRender && state.currentView === "team-capacity") {
      renderTeamCapacity();
    }
  }

  function requestCapacityUserSelection(user, options = {}) {
    if (!user || !els.capacityUserForm) return;
    if (editableFields() === fieldBaseline) {
      selectCapacityUser(user, options);
      return;
    }
    if (selectionConfirmation) return;
    const context = captureEntityMutationContext(state);
    const revision = editorRevision;
    const snapshot = JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
    const request = {};
    selectionConfirmation = request;
    Promise.resolve(showConfirmModal({
      title: "Discard member changes?",
      message: "You have unsaved changes to this member. Discard them and select another member?",
      confirmLabel: "Discard Changes",
      cancelLabel: "Keep Editing",
    })).then((confirmed) => {
      if (selectionConfirmation !== request || revision !== editorRevision
          || !isEntityMutationContextCurrent(state, context)
          || snapshot !== JSON.stringify([...new FormData(els.capacityUserForm).entries()])) return;
      if (!confirmed) {
        if (options.preserveName) {
          const previous = findCapacityUserBySoeid(state.capacitySelectedSoeid);
          els.capacityUserForm.querySelector('[name="display_name"]').value = previous?.display_name || "";
          els.capacityUserForm.querySelector('[name="soeid"]').value = previous?.soeid || "";
        }
        return;
      }
      const latest = findCapacityUserBySoeid(user.soeid);
      if (latest) selectCapacityUser(latest, options);
    }).finally(() => { if (selectionConfirmation === request) selectionConfirmation = null; });
  }

  async function loadTeamCapacityData(options = {}) {
    const startedAt = Date.now();
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
      if (state.currentView === "team-capacity") renderTeamCapacity();
      if (typeof onViewDataLoaded === "function") {
        onViewDataLoaded({ view: "team-capacity", durationMs: Date.now() - startedAt, changed: false });
      }
      return;
    }

    const context = captureEntityMutationContext(state);
    const authed = state.authed;
    const capacity = state.teamCapacity;
    const requestId = (capacity.requestId || 0) + 1;
    const initialForm = els.capacityUserForm ? JSON.stringify([...new FormData(els.capacityUserForm).entries()]) : null;
    const hadDraft = capacityDraft.isDirty();
    const isCurrent = () => state.teamCapacity === capacity && capacity.requestId === requestId
      && state.authed === authed && isEntityMutationContextCurrent(state, context);
    state.teamCapacity.requestId = requestId;
    state.teamCapacity.loading = true;
    state.teamCapacity.error = "";
    if (state.currentView === "team-capacity") renderTeamCapacity();

    try {
      const spaceHeaders = { "X-Space-Id": requestedSpaceId };
      const usersResult = await api("/users?active_only=true", {
        timeoutMs: 45000,
        headers: spaceHeaders,
        signal: options.signal,
      });
      if (!isCurrent()) return;
      if (!Array.isArray(usersResult)) throw new Error("Team capacity returned an invalid response.");

      applyEntityData("users", usersResult);
      state.teamCapacity.lastLoadedAt = new Date().toISOString();
      state.teamCapacity.lastLoadedSpaceId = requestedSpaceId;
      state.teamCapacity.lastLoadedSpaceName = requestedSpaceName;
      populateSelects();
      const formUnchanged = !els.capacityUserForm || initialForm === JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
      if (preserveSelection && state.capacitySelectedSoeid && formUnchanged && !hadDraft) {
        const selected = findCapacityUserBySoeid(state.capacitySelectedSoeid);
        if (selected) selectCapacityUser(selected, { render: false });
        else clearCapacityUserForm({ render: false });
      }
      persistTeamCapacityViewState();
    } catch (err) {
      if (!isCurrent()) return;
      if (handleAuthError(err)) return;
      state.teamCapacity.error = err?.message || "Failed to load team capacity data.";
    } finally {
      const ownsRequest = state.teamCapacity === capacity && capacity.requestId === requestId
        && isSameMutationSession(captureEntityMutationContext(state), context);
      if (ownsRequest) capacity.loading = false;
      if (isCurrent()) {
        if (state.currentView === "team-capacity") renderTeamCapacity();
        if (typeof onViewDataLoaded === "function") {
          onViewDataLoaded({ view: "team-capacity", durationMs: Date.now() - startedAt, changed: true });
        }
      }
    }
  }

  function bindTeamCapacityControls() {
    if (els.capacityUserForm) {
      capacityDraft.bind();
      captureCapacityBaseline();
      els.capacityUserForm.addEventListener("input", () => { editorRevision += 1; }, true);
      els.capacityUserForm.addEventListener("change", () => { editorRevision += 1; }, true);
      const nameInput = els.capacityUserForm.querySelector('[name="display_name"]');
      if (nameInput) {
        nameInput.addEventListener("input", () => {
          clearCapacityUserFormStatus();
          const match = findCapacityUserByValue(nameInput.value || "");
          if (match && normalizeCapacityLookup(match.soeid) !== normalizeCapacityLookup(state.capacitySelectedSoeid)) {
            requestCapacityUserSelection(match, { preserveName: true });
          } else {
            // Keep the selected member while the lookup is incomplete so a
            // cancelled switch can restore its identity and unsaved fields.
            els.capacityUserForm.querySelector('[name="soeid"]').value = match?.soeid || "";
          }
        });
        nameInput.addEventListener("blur", () => {
          const match = findCapacityUserByValue(nameInput.value || "");
          if (match && normalizeCapacityLookup(match.soeid) !== normalizeCapacityLookup(state.capacitySelectedSoeid)) {
            requestCapacityUserSelection(match);
          }
        });
      }
      els.capacityUserForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (selectionConfirmation) return;
        const data = new FormData(els.capacityUserForm);
        const soeid = normalizeCapacityLookup(data.get("soeid")) || normalizeCapacityLookup(findCapacityUserByValue(data.get("display_name"))?.soeid);
        if (!soeid) {
          setCapacityUserFormStatus("Select a member from the roster (or type an exact SOEID/name match) first.", "error");
          return;
        }
        const capacityValue = String(data.get("capacity_fte_month") ?? "").trim();
        const capacityNumber = Number(capacityValue);
        if (!capacityValue || !Number.isFinite(capacityNumber) || capacityNumber < 0) {
          setCapacityUserFormStatus("Enter a non-negative capacity value.", "error");
          return;
        }
        const payload = {
          team_tag: data.get("team_tag") || null,
          capacity_fte_month: capacityNumber,
        };
        const context = captureEntityMutationContext(state);
        const authed = state.authed;
        const isCurrent = () => state.authed === authed && isEntityMutationContextCurrent(state, context);
        const request = beginMutation(context);
        if (!request) {
          setCapacityUserFormStatus("Another member change is in progress.", "error");
          return;
        }
        const snapshot = JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
        const revision = editorRevision;
        const sameEditor = () => isCurrent() && revision === editorRevision && snapshot === JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
        try {
          await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify(payload) });
          if (!isCurrent()) return;
          await loadTeamCapacityData({ force: true, preserveSelection: false });
          if (!isCurrent() || !sameEditor()) return;
          if (state.teamCapacity.error) {
            setCapacityUserFormStatus(`Member saved, but refresh failed: ${state.teamCapacity.error}`, "error");
            return;
          }
          const refreshed = findCapacityUserBySoeid(soeid);
          if (refreshed) selectCapacityUser(refreshed, { preserveStatus: true });
          else clearCapacityUserForm({ preserveStatus: true });
          if (typeof trackWorkflow === "function") {
            trackWorkflow("users", "update", "success", { source: "team_capacity" });
          }
          setCapacityUserFormStatus(`Saved member at ${timestampLabel()}.`, "success", 3200);
        } catch (err) {
          if (!sameEditor()) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("users", "update", "failure", { source: "team_capacity" });
          }
          setCapacityUserFormStatus(`Save failed: ${err.message}`, "error");
        } finally {
          endMutation(request);
        }
      });
      els.capacityUserForm.addEventListener("reset", (event) => {
        event.preventDefault();
        clearCapacityUserForm();
      });
    }
    if (els.capacityUserDelete) {
      els.capacityUserDelete.addEventListener("click", async () => {
        if (selectionConfirmation) return;
        const soeid = els.capacityUserForm?.querySelector('[name="soeid"]')?.value;
        if (!soeid) {
          setCapacityUserFormStatus("Select a member first.", "error");
          return;
        }
        const context = captureEntityMutationContext(state);
        const authed = state.authed;
        const revision = editorRevision;
        const confirmationSnapshot = JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
        const isCurrent = () => state.authed === authed && isEntityMutationContextCurrent(state, context);
        const confirmed = await showConfirmModal({
          title: "Deactivate Member?",
          message: "Deactivate this member? They will be hidden from the roster.",
          confirmLabel: "Deactivate Member",
        });
        if (!confirmed || !isCurrent() || revision !== editorRevision
            || confirmationSnapshot !== JSON.stringify([...new FormData(els.capacityUserForm).entries()])
            || els.capacityUserForm?.querySelector('[name="soeid"]')?.value !== soeid) return;
        const request = beginMutation(context);
        if (!request) {
          setCapacityUserFormStatus("Another member change is in progress.", "error");
          return;
        }
        const snapshot = JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
        const sameEditor = () => isCurrent() && revision === editorRevision && snapshot === JSON.stringify([...new FormData(els.capacityUserForm).entries()]);
        try {
          await api(`/users/by-soeid/${encodeURIComponent(soeid)}`, { method: "PATCH", body: JSON.stringify({ is_active: false }) });
          if (!isCurrent()) return;
          const shouldClear = sameEditor();
          if (shouldClear) clearCapacityUserForm({ render: false, preserveStatus: true });
          const clearedSnapshot = shouldClear ? JSON.stringify([...new FormData(els.capacityUserForm).entries()]) : null;
          await loadTeamCapacityData({ force: true, preserveSelection: false });
          if (!isCurrent() || !shouldClear || clearedSnapshot !== JSON.stringify([...new FormData(els.capacityUserForm).entries()])) return;
          if (state.teamCapacity.error) {
            setCapacityUserFormStatus(`Member deactivated, but refresh failed: ${state.teamCapacity.error}`, "error");
            return;
          }
          if (typeof trackWorkflow === "function") {
            trackWorkflow("users", "update", "success", { source: "team_capacity" });
          }
          setCapacityUserFormStatus(`Member deactivated at ${timestampLabel()}.`, "success", 3200);
        } catch (err) {
          if (!sameEditor()) return;
          if (typeof trackWorkflow === "function") {
            trackWorkflow("users", "update", "failure", { source: "team_capacity" });
          }
          setCapacityUserFormStatus(`Delete failed: ${err.message}`, "error");
        } finally {
          endMutation(request);
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
        requestCapacityUserSelection(user);
      });
    }
    for (const element of [els.capacityTeamFilter, els.capacityNameFilter]) {
      bindDebouncedInput(element, () => {
        const pending = pendingFilters.get(element);
        pendingFilters.delete(element);
        if (!pending || pending.authed !== state.authed || !isEntityMutationContextCurrent(state, pending.context)) return;
        persistTeamCapacityViewState();
        renderTeamCapacity();
      }, 180, (value) => {
        pendingFilters.set(element, { value, context: captureEntityMutationContext(state), authed: state.authed });
      });
    }
    if (els.capacityReload) {
      els.capacityReload.addEventListener("click", async () => {
        await loadTeamCapacityData({ force: true });
      });
    }
    if (els.capacityClearFilters) {
      els.capacityClearFilters.addEventListener("click", () => {
        pendingFilters.clear();
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
