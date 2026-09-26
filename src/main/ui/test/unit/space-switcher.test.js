import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createSpaceSwitcherController } from "../../js/shell/space-switcher.js";

function buildHarness(switchResult = true) {
  document.body.innerHTML = `
    <div id="space-switcher-shell">
      <button id="space-switcher-trigger" type="button"></button>
      <span id="space-switcher-current"></span>
      <span id="space-switcher-meta"></span>
      <div id="space-switcher-panel" class="hidden">
        <button id="space-switcher-close" type="button"></button>
        <input id="space-switcher-search" />
        <p id="space-switcher-feedback"></p>
        <div id="space-switcher-current-list"></div>
        <div id="space-switcher-recent-list"></div>
        <div id="space-switcher-all-list"></div>
      </div>
    </div>
  `;
  const state = {
    authed: true,
    activeSpace: { space_id: "space-a", space_name: "Space A", space_role: "member" },
    spaces: [
      { space_id: "space-a", name: "Space A", space_kind: "collaboration" },
      { space_id: "space-b", name: "Space B", space_kind: "collaboration" },
    ],
    spaceRecentIds: [],
    spaceFeedback: { text: "", tone: "", timeoutId: null },
    spaceSwitcherOpen: false,
    spaceSwitcherQuery: "",
    spaceSwitching: false,
    user: { user_id: "user-1", soeid: "USER1" },
  };
  const els = {
    spaceSwitcherShell: document.getElementById("space-switcher-shell"),
    spaceSwitcherTrigger: document.getElementById("space-switcher-trigger"),
    spaceSwitcherCurrent: document.getElementById("space-switcher-current"),
    spaceSwitcherMeta: document.getElementById("space-switcher-meta"),
    spaceSwitcherPanel: document.getElementById("space-switcher-panel"),
    spaceSwitcherClose: document.getElementById("space-switcher-close"),
    spaceSwitcherSearch: document.getElementById("space-switcher-search"),
    spaceSwitcherFeedback: document.getElementById("space-switcher-feedback"),
    spaceSwitcherCurrentList: document.getElementById("space-switcher-current-list"),
    spaceSwitcherRecentList: document.getElementById("space-switcher-recent-list"),
    spaceSwitcherAllList: document.getElementById("space-switcher-all-list"),
  };
  let controller;
  const onSwitchActiveSpace = async (spaceId) => {
    state.spaceSwitching = true;
    controller.renderSpaceSwitcher();
    await Promise.resolve();
    if (switchResult instanceof Error) {
      state.spaceSwitching = false;
      controller.renderSpaceSwitcher();
      throw switchResult;
    }
    if (switchResult) {
      state.activeSpace = { space_id: spaceId, space_name: "Space B", space_role: "member" };
      state.spaceSwitcherOpen = false;
    }
    state.spaceSwitching = false;
    controller.renderSpaceSwitcher();
    return switchResult;
  };
  controller = createSpaceSwitcherController({
    state,
    els,
    normalize: (value) => String(value || "").trim().toLowerCase(),
    normalizeSpaceRole: (role) => role,
    escapeAttr: (value) => String(value),
    esc: (value) => String(value),
    userIsGlobalAdmin: () => false,
    syncRoleAwareNavigation: () => {},
    onSwitchActiveSpace,
  });
  controller.bindSpaceSwitcher();
  controller.renderSpaceSwitcher();
  return { controller, els, state };
}

describe("space switcher controller", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("does not focus the search field if the switcher closes before its focus task", () => {
    const { els, state } = buildHarness();

    els.spaceSwitcherTrigger.click();
    expect(state.spaceSwitcherOpen).toBe(true);
    els.spaceSwitcherTrigger.focus();
    els.spaceSwitcherTrigger.click();
    vi.runAllTimers();

    expect(els.spaceSwitcherPanel.classList.contains("hidden")).toBe(true);
    expect(document.activeElement).toBe(els.spaceSwitcherTrigger);
  });

  it("returns focus to the trigger after a successful space switch", async () => {
    const { controller, els, state } = buildHarness(true);
    state.spaceSwitcherOpen = true;
    controller.renderSpaceSwitcher();
    const target = els.spaceSwitcherPanel.querySelector('[data-space-switch="space-b"]');
    target.focus();

    target.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(state.spaceSwitcherOpen).toBe(false);
    expect(document.activeElement).toBe(els.spaceSwitcherTrigger);
  });

  it("returns focus to the selected option after a failed space switch", async () => {
    const { controller, els, state } = buildHarness(false);
    state.spaceSwitcherOpen = true;
    controller.renderSpaceSwitcher();
    const target = els.spaceSwitcherPanel.querySelector('[data-space-switch="space-b"]');
    target.focus();

    target.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(state.spaceSwitcherOpen).toBe(true);
    expect(document.activeElement).toBe(
      els.spaceSwitcherPanel.querySelector('[data-space-switch="space-b"]')
    );
  });

  it("restores focus and reports an unexpected switch error without an unhandled rejection", async () => {
    const warning = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { controller, els, state } = buildHarness(new Error("switch failed"));
    state.spaceSwitcherOpen = true;
    controller.renderSpaceSwitcher();
    const target = els.spaceSwitcherPanel.querySelector('[data-space-switch="space-b"]');
    target.focus();

    target.click();
    await Promise.resolve();
    await Promise.resolve();

    expect(warning).toHaveBeenCalledWith("Space switch failed", expect.any(Error));
    expect(document.activeElement).toBe(
      els.spaceSwitcherPanel.querySelector('[data-space-switch="space-b"]')
    );
  });
});
