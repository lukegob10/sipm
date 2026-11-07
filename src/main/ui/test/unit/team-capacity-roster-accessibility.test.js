import { describe, expect, it, vi } from "vitest";
import { renderTeamCapacity } from "../../js/routes/team-capacity.js";
import { createTeamCapacityRouteController } from "../../js/routes/team-capacity/interactions.js";

describe("team capacity roster selection", () => {
  it("distinguishes loading, failure, empty data, and retained stale data", () => {
    const root = document.createElement("div");
    const state = { activeSpace: { space_id: "s" }, users: [] };
    const ctx = { state, els: { capacityUserList: root }, userCapacityFteMonth: () => 1, formatFte: (n) => Number(n).toFixed(2), teamCapacityState: { loading: true } };
    renderTeamCapacity(ctx);
    expect(root.textContent).toContain("Loading roster...");
    expect(root.textContent).toContain("Loading team summary...");
    expect(root.textContent).not.toContain("No users found");
    ctx.teamCapacityState = { error: "Network error" };
    renderTeamCapacity(ctx);
    expect(root.textContent).toContain("Roster unavailable");
    expect(root.textContent).toContain("Team summary unavailable");
    expect(root.textContent).not.toContain("No users found");
    ctx.teamCapacityState = {};
    renderTeamCapacity(ctx);
    expect(root.textContent).toContain("No users found in the active space");
    state.users = [{ soeid: "u", display_name: "Member" }];
    ctx.teamCapacityState = { error: "Network error" };
    renderTeamCapacity(ctx);
    expect(root.textContent).toContain("showing previously loaded roster");
    expect(root.textContent).toContain("Member");
  });

  it("exposes a named keyboard-operable member button and retains focus after selection", () => {
    document.body.innerHTML = '<div id="roster"></div><form id="form"><input name="soeid"><input name="display_name"><input name="team_tag"><input name="capacity_fte_month"></form>';
    const state = { authed: true, user: { user_id: "admin" }, activeSpace: { space_id: "s" }, currentView: "team-capacity", teamCapacity: {}, users: [{ soeid: "ab1", display_name: 'Alex "A"', team_tag: "Team", capacity_fte_month: 0.5 }], capacitySelectedSoeid: "" };
    const els = { capacityUserList: document.getElementById("roster"), capacityUserForm: document.getElementById("form") };
    const display = () => renderTeamCapacity({ state, els, selectedSoeid: state.capacitySelectedSoeid, teamCapacityState: state.teamCapacity, userCapacityFteMonth: (u) => u.capacity_fte_month, formatFte: (n) => Number(n).toFixed(2) });
    const controller = createTeamCapacityRouteController({ state, els, renderTeamCapacity: display, userCapacityFteMonth: (u) => u.capacity_fte_month, formatFte: (n) => Number(n).toFixed(2), bindDebouncedInput: vi.fn(), clearCapacityUserFormStatus: vi.fn(), writeStoredJson: vi.fn(), activeSpaceScopedStorageKey: () => "key" });
    display(); controller.bindTeamCapacityControls();
    const button = () => els.capacityUserList.querySelector("[data-capacity-select]");
    expect(button().getAttribute("aria-label")).toBe('Select Alex "A" (ab1)');
    expect(button().getAttribute("aria-pressed")).toBe("false");
    button().focus(); button().click();
    expect(state.capacitySelectedSoeid).toBe("ab1");
    expect(els.capacityUserForm.querySelector('[name="team_tag"]').value).toBe("Team");
    expect(button().getAttribute("aria-pressed")).toBe("true");
    expect(document.activeElement).toBe(button());
  });
});
