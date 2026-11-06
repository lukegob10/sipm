import { describe, expect, it, vi } from "vitest";
import { createCalendarRouteController } from "../../js/routes/calendar/interactions.js";

function harness() {
  document.body.innerHTML = '<div id="calendar-grid"><div class="calendar-cell" data-day="14"><button>Day</button></div></div><div id="calendar-modal"><h3 id="title">Private date</h3><div id="items">Private item</div></div>';
  const els = {
    calendarGrid: document.querySelector("#calendar-grid"),
    calendarModal: document.querySelector("#calendar-modal"),
    calendarModalTitle: document.querySelector("#title"),
    calendarModalList: document.querySelector("#items"),
  };
  const state = { currentView: "calendar", user: { user_id: "u1" }, activeSpace: { space_id: "s1" }, calendarMonth: new Date(2026, 4, 1), calendarFilters: {}, projects: [], solutions: [], tasks: [] };
  let resolve;
  const loading = new Promise((done) => { resolve = done; });
  const openCalendarModal = vi.fn();
  const controller = createCalendarRouteController({
    state, els,
    getRouteModule: () => null,
    ensureRouteModule: () => loading,
    bindDebouncedInput: vi.fn(),
    filteredSolutionsForCalendar: () => [], filteredTasksForCalendar: () => [], formatStatus: String,
  });
  controller.bindCalendarRouteControls();
  return { state, els, controller, resolve: () => resolve({ openCalendarModal }), openCalendarModal };
}

describe("calendar modal ownership", () => {
  it.each(["session", "space", "route", "month", "reset"])("discards a pending lazy open after %s changes", async (change) => {
    const h = harness();
    h.els.calendarGrid.querySelector("button").click();
    if (change === "session") h.state.user = { user_id: "u2" };
    if (change === "space") h.state.activeSpace = { space_id: "s2" };
    if (change === "route") h.state.currentView = "master";
    if (change === "month") h.state.calendarMonth = new Date(2026, 5, 1);
    if (change === "reset") h.controller.resetForContext();
    h.resolve();
    await Promise.resolve();
    expect(h.openCalendarModal).not.toHaveBeenCalled();
  });

  it("clears visible private details when context changes", () => {
    const h = harness();
    h.controller.resetForContext();
    expect(h.els.calendarModal.classList.contains("hidden")).toBe(true);
    expect(h.els.calendarModalTitle.textContent).toBe("");
    expect(h.els.calendarModalList.textContent).toBe("");
  });

  it("opens the latest day after a lazy load in the same context", async () => {
    const h = harness();
    h.els.calendarGrid.querySelector("button").click();
    h.resolve();
    await Promise.resolve();
    expect(h.openCalendarModal).toHaveBeenCalledWith(14, expect.objectContaining({ state: h.state }));
  });
});

it("focuses the day dialog and returns focus on Escape without restoring it after a context reset", () => {
  document.body.innerHTML = '<div id="grid"><div class="calendar-cell" data-day="14"><button class="calendar-open-day">Day</button></div></div><div id="modal" class="hidden"><button id="close">Close</button></div><button id="elsewhere">Elsewhere</button>';
  const els = {
    calendarGrid: document.querySelector("#grid"),
    calendarModal: document.querySelector("#modal"),
    calendarModalClose: document.querySelector("#close"),
  };
  const state = { currentView: "calendar", user: { user_id: "u1" }, activeSpace: { space_id: "s1" }, calendarMonth: new Date(2026, 4, 1), calendarFilters: {} };
  const controller = createCalendarRouteController({
    state, els, bindDebouncedInput: vi.fn(),
    getRouteModule: () => ({ openCalendarModal: () => els.calendarModal.classList.remove("hidden") }),
  });
  controller.bindCalendarRouteControls();
  const opener = els.calendarGrid.querySelector("button");
  opener.focus();
  opener.click();
  expect(document.activeElement).toBe(els.calendarModalClose);
  const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
  els.calendarModalClose.dispatchEvent(escape);
  expect(escape.defaultPrevented).toBe(true);
  expect(els.calendarModal.classList.contains("hidden")).toBe(true);
  expect(document.activeElement).toBe(opener);

  opener.click();
  els.calendarGrid.innerHTML = '<div class="calendar-cell" data-day="14"><button class="calendar-open-day">Replacement day</button></div>';
  els.calendarModalClose.click();
  expect(document.activeElement).toBe(els.calendarGrid.querySelector("button"));

  els.calendarGrid.querySelector("button").click();
  document.querySelector("#elsewhere").focus();
  state.activeSpace = { space_id: "s2" };
  controller.resetForContext();
  expect(document.activeElement).toBe(document.querySelector("#elsewhere"));
});
