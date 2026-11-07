export function textValue(value) {
  return String(value ?? "").trim();
}

export function nullableTextValue(value) {
  const text = textValue(value);
  return text || null;
}

const mutationContextLifetimes = new WeakMap();

export function registerMutationContextLifetime(state, getLifetime) {
  mutationContextLifetimes.set(state, getLifetime);
}

export function captureEntityMutationContext(state) {
  const user = state.user || null;
  const activeSpace = state.activeSpace || null;
  const lifetime = mutationContextLifetimes.get(state)?.();
  return {
    userId: String(user?.user_id || user?.soeid || user?.email || ""),
    spaceId: String(activeSpace?.space_id || ""),
    userRef: user,
    spaceRef: activeSpace,
    sessionGeneration: lifetime?.session,
    spaceGeneration: lifetime?.space,
  };
}

export function isSameMutationSession(left, right) {
  if (left.sessionGeneration !== undefined && right.sessionGeneration !== undefined) {
    return left.userId === right.userId && left.sessionGeneration === right.sessionGeneration;
  }
  return left.userId === right.userId && left.userRef === right.userRef;
}

export function isEntityMutationContextCurrent(state, context) {
  const current = captureEntityMutationContext(state);
  const sameSpaceLifetime = current.spaceGeneration !== undefined && context.spaceGeneration !== undefined
    ? current.spaceGeneration === context.spaceGeneration
    : current.spaceRef === context.spaceRef;
  return isSameMutationSession(current, context)
    && current.spaceId === context.spaceId
    && sameSpaceLifetime;
}

// Keep the original opener when an already-open editor is refreshed or replaced.
export function createEditorModalFocus(state, modal, initialFocus) {
  let opener = null;
  let context = null;
  let view = null;
  let masterAction = null;
  const higherModalOpen = () => ["idle-modal", "confirm-modal"].some((id) => {
    const element = document.getElementById(id);
    return element && !element.classList.contains("hidden");
  });
  const topModal = () => document.elementFromPoint?.(window.innerWidth / 2, window.innerHeight / 2)?.closest(".modal");
  return {
    open() {
      if (!modal || !modal.classList.contains("hidden")) return false;
      opener = document.activeElement;
      context = captureEntityMutationContext(state);
      view = state.currentView;
      masterAction = opener?.closest?.("#master-table") && opener.matches("[data-action][data-type][data-id]")
        ? [opener.getAttribute("data-action"), opener.getAttribute("data-type"), opener.getAttribute("data-id"), opener.className]
        : null;
      return true;
    },
    focus() {
      const top = topModal();
      if (!higherModalOpen() && (!top || top === modal)) initialFocus?.focus();
    },
    close(restore = true) {
      const top = topModal();
      let target = opener;
      if (!target?.isConnected && masterAction && state.currentView === view) {
        target = [...(document.getElementById("master-table")?.querySelectorAll("[data-action][data-type][data-id]") || [])]
          .find((element) => element.getAttribute("data-action") === masterAction[0]
            && element.getAttribute("data-type") === masterAction[1]
            && element.getAttribute("data-id") === masterAction[2] && element.className === masterAction[3]);
      }
      if (restore && context && isEntityMutationContextCurrent(state, context) && !higherModalOpen()
          && state.currentView === view && target?.isConnected && target.getClientRects().length
          && (!top || top.contains(target))) target.focus();
      opener = null;
      context = null;
      view = null;
      masterAction = null;
    },
  };
}

export function createCsvImportGate() {
  let pending = null;
  return {
    begin(context) {
      if (pending && isSameMutationSession(pending, context)) return null;
      const request = { ...context };
      pending = request;
      return request;
    },
    finish(request) {
      if (pending === request) pending = null;
    },
  };
}

export function clearTeamCapacityFields(form) {
  if (!form) return;
  ["soeid", "display_name", "team_tag"].forEach((name) => {
    const field = form.querySelector(`[name="${name}"]`);
    if (field) field.value = "";
  });
  const capacity = form.querySelector('[name="capacity_fte_month"]');
  if (capacity) capacity.value = "1.00";
}

export function createContextualFormSaveGate({ state, form, submit }) {
  let pending = null;
  function reset() {
    if (!pending) return;
    const previous = pending;
    pending = null;
    form?.removeAttribute("aria-busy");
    if (submit) submit.disabled = previous.submitWasDisabled;
  }
  function isPending() {
    if (!pending) return false;
    if (state.authed === pending.authed && isEntityMutationContextCurrent(state, pending.context)) return true;
    reset();
    return false;
  }
  function begin() {
    if (isPending()) return null;
    const request = {
      context: captureEntityMutationContext(state),
      authed: state.authed,
      submitWasDisabled: !!submit?.disabled,
    };
    pending = request;
    if (submit) submit.disabled = true;
    form?.setAttribute("aria-busy", "true");
    return request;
  }
  function end(request) {
    if (pending === request) reset();
  }
  return { isPending, begin, end, reset };
}

export function createSessionBoundFetch({ fetchImpl, getBinding, handleMismatch }) {
  return async (input, options = {}) => {
    const binding = getBinding() || "";
    const headers = new Headers(options.headers || {});
    if (binding) headers.set("X-SIPM-Session", binding);
    const response = await fetchImpl(input, { ...options, headers });
    if (handleMismatch(response, binding)) {
      throw Object.assign(new Error("Request context changed."), { code: "REQUEST_CONTEXT_CHANGED" });
    }
    return response;
  };
}

const pendingByState = new WeakMap();

export function beginTaskMutations(state, taskIds) {
  const ids = new Set(taskIds.filter(Boolean));
  const pending = pendingByState.get(state) || new Set();
  for (const entry of pending) {
    if (!isEntityMutationContextCurrent(state, entry.context)) {
      pending.delete(entry);
    } else if ([...ids].some((id) => entry.ids.has(id))) {
      return null;
    }
  }
  const entry = { ids, context: captureEntityMutationContext(state) };
  pending.add(entry);
  pendingByState.set(state, pending);
  return () => {
    pending.delete(entry);
    if (!pending.size && pendingByState.get(state) === pending) pendingByState.delete(state);
  };
}

const pendingSolutionsByState = new WeakMap();

export function beginSolutionMutation(state, id) {
  const pending = pendingSolutionsByState.get(state) || new Map();
  const previous = pending.get(id);
  if (previous && previous.authed === state.authed && isEntityMutationContextCurrent(state, previous.context)) return null;
  const request = { context: captureEntityMutationContext(state), authed: state.authed };
  pending.set(id, request);
  pendingSolutionsByState.set(state, pending);
  return () => {
    if (pending.get(id) === request) pending.delete(id);
    if (!pending.size && pendingSolutionsByState.get(state) === pending) pendingSolutionsByState.delete(state);
  };
}

export function createContextualEntityMutationGate(state) {
  const pending = new Map();
  return (id) => {
    const previous = pending.get(id);
    if (previous && previous.authed === state.authed && isEntityMutationContextCurrent(state, previous.context)) return null;
    const request = { context: captureEntityMutationContext(state), authed: state.authed };
    pending.set(id, request);
    return () => {
      if (pending.get(id) === request) pending.delete(id);
    };
  };
}
