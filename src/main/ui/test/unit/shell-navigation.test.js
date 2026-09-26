import { beforeEach, describe, expect, it, vi } from "vitest";

import { createShellNavigationController } from "../../js/shell/navigation.js";

function buildHarness(compact = true) {
  document.body.innerHTML = `
    <div id="app-shell">
      <aside id="app-navigation"><button class="nav-btn" data-view="master">Deliverables</button></aside>
      <button id="shell-nav-toggle" aria-expanded="false"></button>
      <button id="shell-nav-backdrop" class="hidden"></button>
      <div id="account-menu-shell">
        <button id="account-menu-toggle" aria-expanded="false"></button>
        <div id="account-menu-panel"><button id="theme-toggle">Theme</button></div>
      </div>
    </div>
  `;
  let compactShell = compact;
  const listeners = new Map();
  const windowRef = {
    matchMedia: vi.fn(() => ({ matches: compactShell })),
    addEventListener: vi.fn((type, listener) => listeners.set(type, listener)),
    dispatchEvent(event) {
      listeners.get(event.type)?.(event);
    },
  };
  const els = {
    appShell: document.getElementById("app-shell"),
    appNavigation: document.getElementById("app-navigation"),
    shellNavToggle: document.getElementById("shell-nav-toggle"),
    shellNavBackdrop: document.getElementById("shell-nav-backdrop"),
    navButtons: document.querySelectorAll(".nav-btn"),
    accountMenuShell: document.getElementById("account-menu-shell"),
    accountMenuToggle: document.getElementById("account-menu-toggle"),
    accountMenuPanel: document.getElementById("account-menu-panel"),
  };
  const controller = createShellNavigationController({ els, windowRef, documentRef: document });
  controller.bind();
  return {
    controller,
    els,
    resize(nextCompact) {
      compactShell = nextCompact;
      windowRef.dispatchEvent(new Event("resize"));
    },
  };
}

describe("shell navigation controller", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("opens the compact navigation and closes it after route selection", () => {
    const { els } = buildHarness();

    expect(els.appNavigation.hasAttribute("inert")).toBe(true);
    expect(els.appNavigation.getAttribute("aria-hidden")).toBe("true");

    els.shellNavToggle.click();
    expect(els.appShell.classList.contains("nav-open")).toBe(true);
    expect(els.appNavigation.hasAttribute("inert")).toBe(false);
    expect(els.appNavigation.getAttribute("aria-hidden")).toBe("false");
    expect(els.shellNavToggle.getAttribute("aria-expanded")).toBe("true");
    expect(els.shellNavBackdrop.classList.contains("hidden")).toBe(false);

    els.navButtons[0].focus();
    els.navButtons[0].click();
    expect(els.appShell.classList.contains("nav-open")).toBe(false);
    expect(els.appNavigation.hasAttribute("inert")).toBe(true);
    expect(els.shellNavToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(els.shellNavToggle);
  });

  it("keeps navigation closed outside the compact shell", () => {
    const { els } = buildHarness(false);
    els.shellNavToggle.click();
    expect(els.appShell.classList.contains("nav-open")).toBe(false);
  });

  it("exposes account menu state and closes it with Escape", () => {
    const { els } = buildHarness();

    els.accountMenuToggle.click();
    expect(els.accountMenuShell.classList.contains("is-open")).toBe(true);
    expect(els.accountMenuToggle.getAttribute("aria-expanded")).toBe("true");

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(els.accountMenuShell.classList.contains("is-open")).toBe(false);
    expect(els.accountMenuToggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(els.accountMenuToggle);
  });

  it("keeps compact navigation hidden from keyboard navigation after resizing", () => {
    const { els, resize } = buildHarness(false);
    expect(els.appNavigation.hasAttribute("inert")).toBe(false);

    els.navButtons[0].focus();
    resize(true);

    expect(els.appNavigation.hasAttribute("inert")).toBe(true);
    expect(els.appNavigation.getAttribute("aria-hidden")).toBe("true");
    expect(document.activeElement).toBe(els.shellNavToggle);

    els.shellNavToggle.click();
    expect(els.appNavigation.hasAttribute("inert")).toBe(false);
    resize(false);
    expect(els.appNavigation.hasAttribute("inert")).toBe(false);
    expect(els.appNavigation.getAttribute("aria-hidden")).toBe("false");
  });

  it("returns focus to the account toggle when a compact account action closes the menu", () => {
    const { els } = buildHarness();

    els.accountMenuToggle.click();
    const action = document.getElementById("theme-toggle");
    action.focus();
    action.click();

    expect(els.accountMenuShell.classList.contains("is-open")).toBe(false);
    expect(document.activeElement).toBe(els.accountMenuToggle);
  });

  it("preserves dialog focus opened by an account menu action", () => {
    const { els } = buildHarness();
    const dialog = document.createElement("div");
    const dialogInput = document.createElement("input");
    dialog.append(dialogInput);
    document.body.append(dialog);
    const action = document.getElementById("theme-toggle");
    action.addEventListener("click", () => dialogInput.focus());

    els.accountMenuToggle.click();
    action.focus();
    action.click();

    expect(els.accountMenuShell.classList.contains("is-open")).toBe(false);
    expect(document.activeElement).toBe(dialogInput);
  });
});
