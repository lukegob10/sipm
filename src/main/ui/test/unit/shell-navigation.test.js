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
  const windowRef = {
    matchMedia: vi.fn(() => ({ matches: compact })),
    addEventListener: vi.fn(),
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
  return { controller, els };
}

describe("shell navigation controller", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("opens the compact navigation and closes it after route selection", () => {
    const { els } = buildHarness();

    els.shellNavToggle.click();
    expect(els.appShell.classList.contains("nav-open")).toBe(true);
    expect(els.shellNavToggle.getAttribute("aria-expanded")).toBe("true");
    expect(els.shellNavBackdrop.classList.contains("hidden")).toBe(false);

    els.navButtons[0].click();
    expect(els.appShell.classList.contains("nav-open")).toBe(false);
    expect(els.shellNavToggle.getAttribute("aria-expanded")).toBe("false");
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
  });
});
