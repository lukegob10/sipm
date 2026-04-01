export function createSpaceSwitcherController({
  state,
  els,
  normalize,
  normalizeSpaceRole,
  escapeAttr,
  esc,
  userIsGlobalAdmin,
  syncRoleAwareNavigation,
  onSwitchActiveSpace,
}) {
  function currentSpaceRoleLabel(ctx = state.activeSpace) {
    if (!ctx) return "";
    if (ctx.is_global_admin) return "Global Admin";
    const role = normalizeSpaceRole(ctx.space_role || "member")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
    return role || "Member";
  }

  function clearSpaceFeedback() {
    if (state.spaceFeedback?.timeoutId) {
      clearTimeout(state.spaceFeedback.timeoutId);
    }
    state.spaceFeedback = { text: "", tone: "", timeoutId: null };
  }

  function renderSpaceSwitcher() {
    const active = state.activeSpace;
    if (els.spaceSwitcherTrigger) {
      els.spaceSwitcherTrigger.disabled = !state.authed || state.spaceSwitching || !(state.spaces || []).length;
      els.spaceSwitcherTrigger.setAttribute("aria-expanded", state.spaceSwitcherOpen ? "true" : "false");
      els.spaceSwitcherTrigger.classList.toggle("is-busy", !!state.spaceSwitching);
    }
    if (els.spaceSwitcherCurrent) {
      els.spaceSwitcherCurrent.textContent = state.authed
        ? (active?.space_name || active?.space_id || "No active space")
        : "Sign in";
    }
    if (els.spaceSwitcherMeta) {
      const meta = !state.authed
        ? ""
        : (state.spaceSwitching ? "Switching" : (active ? currentSpaceRoleLabel(active) : ""));
      els.spaceSwitcherMeta.textContent = meta || "Role";
      els.spaceSwitcherMeta.classList.toggle("hidden", !meta);
    }
    if (els.spaceSwitcherPanel) {
      els.spaceSwitcherPanel.classList.toggle("hidden", !state.spaceSwitcherOpen || !state.authed);
    }
    if (els.spaceSwitcherFeedback) {
      els.spaceSwitcherFeedback.textContent = state.spaceFeedback?.text || "";
      els.spaceSwitcherFeedback.className = "form-notice";
      if (state.spaceFeedback?.tone === "success") els.spaceSwitcherFeedback.classList.add("notice-success");
      if (state.spaceFeedback?.tone === "error") els.spaceSwitcherFeedback.classList.add("notice-error");
    }
    const renderList = (
      container,
      spaces,
      { emptyText = "No spaces available", currentId = active?.space_id || "" } = {}
    ) => {
      if (!container) return;
      if (!spaces.length) {
        container.innerHTML = `<p class="muted space-switcher-empty">${emptyText}</p>`;
        return;
      }
      container.innerHTML = spaces.map((space) => {
        const isCurrent = space.space_id === currentId;
        const roleLabel = isCurrent
          ? currentSpaceRoleLabel(active)
          : (userIsGlobalAdmin() ? "Global Admin" : "Accessible");
        return `<button
          type="button"
          class="space-switcher-option${isCurrent ? " is-current" : ""}"
          data-space-switch="${escapeAttr(space.space_id)}"
          ${isCurrent || state.spaceSwitching ? "disabled" : ""}
        >
          <span class="space-switcher-option-main">
            <strong>${esc(space.name || space.space_id)}</strong>
            <span class="space-switcher-option-meta">${esc(space.slug || "Workspace")}</span>
          </span>
          <span class="space-switcher-option-side">
            <span class="pill ${isCurrent ? "" : "muted"}">${esc(roleLabel)}</span>
            ${isCurrent ? "<span class='pill positive'>Current</span>" : ""}
          </span>
        </button>`;
      }).join("");
    };
    const query = normalize(state.spaceSwitcherQuery);
    const activeId = active?.space_id || "";
    const visibleSpaces = (state.spaces || []).filter((space) => {
      if (!query) return true;
      return [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query));
    });
    const recentSpaceIds = state.spaceRecentIds.filter((spaceId) => spaceId && spaceId !== activeId);
    const recentSpaces = recentSpaceIds
      .map((spaceId) => (state.spaces || []).find((space) => space.space_id === spaceId))
      .filter(Boolean)
      .filter((space, index, list) => list.findIndex((item) => item.space_id === space.space_id) === index)
      .filter((space) => !query || [space.name, space.slug, space.space_id].some((value) => normalize(value).includes(query)));
    renderList(els.spaceSwitcherCurrentList, active ? [{
      space_id: active.space_id,
      name: active.space_name || active.space_id,
      slug: "",
    }] : [], { emptyText: "No active space", currentId: activeId });
    renderList(els.spaceSwitcherRecentList, recentSpaces, { emptyText: "No recent spaces yet", currentId: activeId });
    renderList(els.spaceSwitcherAllList, visibleSpaces, { emptyText: "No matching spaces", currentId: activeId });
    if (typeof syncRoleAwareNavigation === "function") {
      syncRoleAwareNavigation();
    }
  }

  function setSpaceFeedback(message, tone = "info", autoClearMs = 0) {
    clearSpaceFeedback();
    if (!message) {
      renderSpaceSwitcher();
      return;
    }
    state.spaceFeedback = { text: message, tone, timeoutId: null };
    if (autoClearMs > 0) {
      state.spaceFeedback.timeoutId = setTimeout(() => {
        clearSpaceFeedback();
        renderSpaceSwitcher();
      }, autoClearMs);
    }
    renderSpaceSwitcher();
  }

  function spaceNameForId(spaceId) {
    const id = String(spaceId || "").trim();
    if (!id) return "";
    const match = (state.spaces || []).find((space) => space.space_id === id);
    if (match?.name) return match.name;
    if ((state.activeSpace?.space_id || "") === id) return state.activeSpace?.space_name || id;
    return id;
  }

  function bindSpaceSwitcher() {
    const closeSwitcher = ({ returnFocus = false } = {}) => {
      if (!state.spaceSwitcherOpen) return;
      state.spaceSwitcherOpen = false;
      state.spaceSwitcherQuery = "";
      if (els.spaceSwitcherSearch) els.spaceSwitcherSearch.value = "";
      renderSpaceSwitcher();
      if (returnFocus) els.spaceSwitcherTrigger?.focus();
    };
    const openSwitcher = () => {
      if (!state.authed || state.spaceSwitching || !(state.spaces || []).length) return;
      state.spaceSwitcherOpen = true;
      renderSpaceSwitcher();
      window.setTimeout(() => {
        els.spaceSwitcherSearch?.focus();
        els.spaceSwitcherSearch?.select();
      }, 0);
    };
    const visibleOptions = () => Array.from(
      els.spaceSwitcherPanel?.querySelectorAll(".space-switcher-option:not([disabled])") || []
    );
    const moveFocus = (delta) => {
      const options = visibleOptions();
      if (!options.length) return;
      const currentIndex = options.indexOf(document.activeElement);
      const nextIndex = currentIndex === -1
        ? (delta > 0 ? 0 : options.length - 1)
        : (currentIndex + delta + options.length) % options.length;
      options[nextIndex]?.focus();
    };

    if (els.spaceSwitcherTrigger && !els.spaceSwitcherTrigger._bound) {
      els.spaceSwitcherTrigger.addEventListener("click", (event) => {
        event.stopPropagation();
        if (state.spaceSwitcherOpen) closeSwitcher();
        else openSwitcher();
      });
      els.spaceSwitcherTrigger.addEventListener("keydown", (event) => {
        if (!["Enter", " ", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        openSwitcher();
      });
      els.spaceSwitcherTrigger._bound = true;
    }
    if (els.spaceSwitcherClose && !els.spaceSwitcherClose._bound) {
      els.spaceSwitcherClose.addEventListener("click", () => closeSwitcher({ returnFocus: true }));
      els.spaceSwitcherClose._bound = true;
    }
    if (els.spaceSwitcherSearch && !els.spaceSwitcherSearch._bound) {
      els.spaceSwitcherSearch.addEventListener("input", () => {
        state.spaceSwitcherQuery = els.spaceSwitcherSearch.value || "";
        renderSpaceSwitcher();
      });
      els.spaceSwitcherSearch.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          closeSwitcher({ returnFocus: true });
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          moveFocus(1);
        }
      });
      els.spaceSwitcherSearch._bound = true;
    }
    if (els.spaceSwitcherPanel && !els.spaceSwitcherPanel._bound) {
      els.spaceSwitcherPanel.addEventListener("click", async (event) => {
        event.stopPropagation();
        const button = event.target.closest("button[data-space-switch]");
        if (!button) return;
        const targetSpaceId = button.getAttribute("data-space-switch") || "";
        if (!targetSpaceId || typeof onSwitchActiveSpace !== "function") return;
        await onSwitchActiveSpace(targetSpaceId);
      });
      els.spaceSwitcherPanel.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          closeSwitcher({ returnFocus: true });
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          moveFocus(1);
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          moveFocus(-1);
          return;
        }
        if (event.key === "Home") {
          event.preventDefault();
          visibleOptions()[0]?.focus();
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          const options = visibleOptions();
          options[options.length - 1]?.focus();
        }
      });
      els.spaceSwitcherPanel._bound = true;
    }
    if (!document._spaceSwitcherCloseBound) {
      document.addEventListener("click", (event) => {
        if (!state.spaceSwitcherOpen) return;
        const shell = els.spaceSwitcherShell;
        if (shell?.contains(event.target)) return;
        closeSwitcher();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        if (state.spaceSwitcherOpen) {
          event.preventDefault();
          closeSwitcher({ returnFocus: true });
        }
      });
      document._spaceSwitcherCloseBound = true;
    }
  }

  return {
    bindSpaceSwitcher,
    clearSpaceFeedback,
    currentSpaceRoleLabel,
    renderSpaceSwitcher,
    setSpaceFeedback,
    spaceNameForId,
  };
}
