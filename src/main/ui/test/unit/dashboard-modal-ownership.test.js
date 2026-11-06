import { afterEach, expect, it } from "vitest";

import { createDashboardState } from "../../js/routes/dashboard/prefs.js";
import { applyModalConfig, closeDashboardConfigModal, isDashboardModalContextCurrent, openDashboardConfigModal, resetDashboardConfigForContext } from "../../js/routes/dashboard/modal.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";

afterEach(() => {
  document.body.innerHTML = "";
  localStorage.clear();
});

it("clears private modal contents and draft on a context reset", () => {
  const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
  registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
  const dashboard = createDashboardState();
  dashboard.ctx = { state };
  openDashboardConfigModal(dashboard, "main");
  dashboard.modalDrafts.main = { solution_ids: ["private-id"] };
  dashboard.sectionOptions = { main: [{ solutionName: "Private item" }] };
  document.getElementById("dashboard-config-solutions").textContent = "Private item";
  document.getElementById("dashboard-config-columns").textContent = "Private column";
  resetDashboardConfigForContext(dashboard);
  const modal = document.getElementById("dashboard-config-modal");
  expect(modal.classList.contains("hidden")).toBe(true);
  expect(modal.getAttribute("aria-hidden")).toBe("true");
  expect(modal.textContent).not.toContain("Private item");
  expect(modal.textContent).not.toContain("Private column");
  expect(dashboard.modalDrafts).toBeNull();
  expect(dashboard.modalSection).toBeNull();
  expect(dashboard.sectionOptions).toEqual({});
  expect(dashboard.ctx).toBeNull();
});

it("retains same-session drafts on refresh or an unsuccessful space switch, but rejects changed sessions/spaces", () => {
  const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const dashboard = createDashboardState();
  dashboard.ctx = { state };
  openDashboardConfigModal(dashboard, "main");
  state.user = { user_id: "user-1" };
  state.activeSpace = { space_id: "space-1" };
  lifetime.space += 1;
  expect(isDashboardModalContextCurrent(dashboard)).toBe(true);
  state.activeSpace = { space_id: "space-2" };
  expect(isDashboardModalContextCurrent(dashboard)).toBe(false);
  state.activeSpace = { space_id: "space-1" };
  lifetime.session += 1;
  expect(isDashboardModalContextCurrent(dashboard)).toBe(false);
});


it("restores the current dashboard button after Apply replaces its opener", () => {
  document.body.innerHTML = '<div id="view-dashboard"><button data-dashboard-action="open-config">Customize</button></div>';
  const state = { authed: true, currentView: "dashboard", user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
  registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
  const dashboard = createDashboardState();
  dashboard.ctx = { state };
  const opener = document.querySelector('[data-dashboard-action="open-config"]');
  openDashboardConfigModal(dashboard, "main", opener);
  applyModalConfig(dashboard, () => {
    document.getElementById("view-dashboard").innerHTML = '<button data-dashboard-action="open-config">Customize</button>';
    document.querySelector('[data-dashboard-action="open-config"]').getClientRects = () => [1];
  });
  expect(document.activeElement).toBe(document.querySelector('[data-dashboard-action="open-config"]'));
});

it("does not restore a stale dashboard opener after a space change", () => {
  document.body.innerHTML = '<button data-dashboard-action="open-config">Customize</button><button id="replacement">Replacement</button>';
  const state = { authed: true, currentView: "dashboard", user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" } };
  registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
  const dashboard = createDashboardState();
  dashboard.ctx = { state };
  const opener = document.querySelector('[data-dashboard-action="open-config"]');
  opener.getClientRects = () => [1];
  openDashboardConfigModal(dashboard, "main", opener);
  state.activeSpace = { space_id: "space-2" };
  document.getElementById("replacement").focus();
  closeDashboardConfigModal(dashboard);
  expect(document.activeElement.id).toBe("replacement");
});
