import { describe, expect, it, vi } from "vitest";

import { openCalendarModal, renderCalendar } from "../../js/routes/calendar.js";
import { createCalendarRouteController } from "../../js/routes/calendar/interactions.js";
import { registerMutationContextLifetime } from "../../js/utils/form-state.js";

describe("calendar route", () => {
  it("renders an agenda representation for compact viewports", () => {
    document.body.innerHTML = `<div id="calendar-grid"></div><div id="calendar-agenda"></div>`;
    const ctx = {
      state: { calendarMonth: "2026-05" },
      els: {
        calendarGrid: document.getElementById("calendar-grid"),
        calendarAgenda: document.getElementById("calendar-agenda"),
      },
      filteredSolutionsForCalendar: () => [{
        solution_id: "solution-1",
        solution_name: "May Launch",
        due_date: "2026-05-14",
        status: "active",
      }],
      filteredTasksForCalendar: () => [],
      formatStatus: (status) => status,
    };

    renderCalendar(ctx);

    expect(ctx.els.calendarAgenda.textContent).toContain("May Launch");
    expect(ctx.els.calendarAgenda.querySelector("[data-calendar-agenda-day='14']")).not.toBeNull();
    const dayAction = ctx.els.calendarGrid.querySelector('.calendar-cell[data-day="14"] .calendar-open-day');
    expect(dayAction.tagName).toBe("BUTTON");
    expect(dayAction.getAttribute("aria-label")).toContain("May 14, 2026");
  });

  it("opens the calendar day from its native header action", () => {
    document.body.innerHTML = '<div id="calendar-grid" class="calendar"></div>';
    const state = { calendarMonth: "2026-05", calendarFilters: {}, projects: [], solutions: [], tasks: [] };
    const els = { calendarGrid: document.getElementById("calendar-grid") };
    const openCalendarModal = vi.fn();
    const controller = createCalendarRouteController({
      state,
      els,
      calendarViewStateKey: "calendar-test",
      writeStoredJson: vi.fn(),
      readStoredJsonState: vi.fn(() => ({ value: {}, recovered: false })),
      activeSpaceScopedStorageKey: (key) => key,
      bindDebouncedInput: vi.fn(),
      renderCalendar: vi.fn(),
      openProjectForm: vi.fn(),
      openSolutionModal: vi.fn(),
      fillTaskForm: vi.fn(),
      getRouteModule: () => ({ openCalendarModal }),
      ensureRouteModule: vi.fn(),
      filteredSolutionsForCalendar: () => [],
      filteredTasksForCalendar: () => [],
      formatStatus: (status) => status,
    });
    renderCalendar({
      state,
      els,
      filteredSolutionsForCalendar: () => [],
      filteredTasksForCalendar: () => [],
      formatStatus: (status) => status,
    });
    controller.bindCalendarRouteControls();

    els.calendarGrid.querySelector(".calendar-open-day").click();

    expect(openCalendarModal).toHaveBeenCalledWith(1, expect.objectContaining({ state, els }));
  });

  it.each(["session", "space", "refresh"])("keeps pending owner input scoped after %s", (changed) => {
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" },
      calendarMonth: new Date(2026, 4, 1), calendarFilters: { owner: "", project: "" }, projects: [], solutions: [], tasks: [] };
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(state, () => lifetime);
    let onInput;
    let onChange;
    const writeStoredJson = vi.fn();
    const render = vi.fn();
    const controller = createCalendarRouteController({
      state, els: { calendarFilterOwner: document.createElement("input") }, calendarViewStateKey: "calendar-test",
      writeStoredJson, readStoredJsonState: vi.fn(() => ({ value: {}, recovered: false })),
      activeSpaceScopedStorageKey: (key) => key,
      bindDebouncedInput: (_element, change, _delay, input) => { onInput = input; onChange = change; },
      renderCalendar: render, openProjectForm: vi.fn(), openSolutionModal: vi.fn(), fillTaskForm: vi.fn(),
      getRouteModule: vi.fn(), ensureRouteModule: vi.fn(),
      filteredSolutionsForCalendar: () => [], filteredTasksForCalendar: () => [], formatStatus: (status) => status,
    });
    controller.bindCalendarRouteControls();
    onInput?.("private old filter");
    expect(controller.getPendingOwner()).toBe("private old filter");
    if (changed === "refresh") {
      state.user = { user_id: "user-1" };
      state.activeSpace = { space_id: "space-1" };
    } else {
      lifetime[changed] += 1;
    }
    expect(controller.getPendingOwner()).toBe(changed === "refresh" ? "private old filter" : null);
    onChange("private old filter");
    expect(state.calendarFilters.owner).toBe(changed === "refresh" ? "private old filter" : "");
    expect(writeStoredJson).toHaveBeenCalledTimes(changed === "refresh" ? 1 : 0);
    expect(render).toHaveBeenCalledTimes(changed === "refresh" ? 1 : 0);
  });

  it.each(["refresh", "space"])("restores the correct month and pending owner across %s", (change) => {
    const state = { authed: true, user: { user_id: "user-1" }, activeSpace: { space_id: "space-1" },
      calendarMonth: new Date(2026, 4, 1), calendarFilters: { owner: "", project: "" }, projects: [], solutions: [], tasks: [] };
    const lifetime = { session: 1, space: 1 };
    registerMutationContextLifetime(state, () => lifetime);
    let onInput;
    let onChange;
    const month = document.createElement("input");
    month.type = "month";
    const controller = createCalendarRouteController({
      state, els: { calendarFilterOwner: document.createElement("input"), calendarMonthInput: month }, calendarViewStateKey: "calendar-test",
      writeStoredJson: vi.fn(), readStoredJsonState: () => ({ value: state.activeSpace.space_id === "space-1"
        ? { month: "2026-05", filters: { owner: "", project: "" } }
        : { month: "2026-10", filters: { owner: "new owner", project: "" } }, recovered: false }),
      activeSpaceScopedStorageKey: (key) => key,
      bindDebouncedInput: (_element, changeCallback, _delay, input) => { onInput = input; onChange = changeCallback; },
      renderCalendar: vi.fn(), openProjectForm: vi.fn(), openSolutionModal: vi.fn(), fillTaskForm: vi.fn(),
      getRouteModule: vi.fn(), ensureRouteModule: vi.fn(),
      filteredSolutionsForCalendar: () => [], filteredTasksForCalendar: () => [], formatStatus: (status) => status,
    });
    controller.bindCalendarRouteControls();
    onInput("unsaved filter");
    state.user = { user_id: "user-1" };
    if (change === "space") {
      state.activeSpace = { space_id: "space-2" };
      lifetime.space += 1;
    } else {
      state.activeSpace = { space_id: "space-1" };
    }
    controller.restoreCalendarViewState();
    onChange("unsaved filter");
    expect(state.calendarFilters.owner).toBe(change === "refresh" ? "unsaved filter" : "new owner");
    expect(month.value).toBe(change === "refresh" ? "2026-05" : "2026-10");
    expect(state.calendarMonth.getMonth()).toBe(change === "refresh" ? 4 : 9);
  });

  it.each([["0001-02", "0001-02-28", 28], ["0004-02", "0004-02-29", 29], ["0099-02", "0099-02-28", 28], ["9999-12", "9999-12-31", 31]])(
    "renders the correct days and items for %s", (month, due, day) => {
      document.body.innerHTML = '<div id="grid"></div><div id="agenda"></div>';
      const ctx = { state: { calendarMonth: month }, els: { calendarGrid: document.getElementById("grid"), calendarAgenda: document.getElementById("agenda") },
        filteredSolutionsForCalendar: () => [{ solution_id: "one", solution_name: "Dated work", due_date: due, status: "active" }],
        filteredTasksForCalendar: () => [], formatStatus: (status) => status };
      renderCalendar(ctx);
      expect(ctx.els.calendarGrid.querySelectorAll(".calendar-cell[data-day]")).toHaveLength(day);
      expect(ctx.els.calendarGrid.querySelector(`[data-day="${day}"]`).textContent).toContain("Dated work");
      expect(ctx.els.calendarGrid.querySelector(".calendar-month-label").textContent).toContain(String(Number(month.slice(0, 4))));
    }
  );

  it("opens an early-year day without shifting it into the twentieth century", () => {
    document.body.innerHTML = '<div id="modal" class="hidden"></div><div id="title"></div><div id="list"></div>';
    const ctx = { state: { calendarMonth: "0004-02", projects: [], solutions: [] },
      els: { calendarModal: document.getElementById("modal"), calendarModalTitle: document.getElementById("title"), calendarModalList: document.getElementById("list") },
      filteredSolutionsForCalendar: () => [{ solution_name: "Leap-year launch", due_date: "0004-02-29", status: "active" }],
      filteredTasksForCalendar: () => [], formatStatus: (status) => status };
    openCalendarModal(29, ctx);
    expect(ctx.els.calendarModalTitle.textContent).toMatch(/February 29, 4$/);
    expect(ctx.els.calendarModalList.textContent).toContain("Leap-year launch");
  });

  it("navigates early years and rejects months outside the supported range", () => {
    document.body.innerHTML = '<input type="month" id="month"><button id="prev"></button><button id="next"></button>';
    const state = { calendarMonth: new Date(), calendarFilters: {}, projects: [], solutions: [], tasks: [] };
    const month = document.getElementById("month");
    const writeStoredJson = vi.fn();
    const controller = createCalendarRouteController({ state,
      els: { calendarMonthInput: month, calendarPrev: document.getElementById("prev"), calendarNext: document.getElementById("next") },
      calendarViewStateKey: "test", writeStoredJson,
      readStoredJsonState: () => ({ value: { month: "0001-01", filters: {} }, recovered: false }),
      activeSpaceScopedStorageKey: (key) => key, bindDebouncedInput: vi.fn(), renderCalendar: vi.fn() });
    controller.bindCalendarRouteControls();
    controller.restoreCalendarViewState();
    expect(month.value).toBe("0001-01");
    document.getElementById("prev").click();
    expect(month.value).toBe("0001-01");
    month.value = "0099-12";
    month.dispatchEvent(new Event("change"));
    expect(state.calendarMonth.getFullYear()).toBe(99);
    document.getElementById("next").click();
    expect(month.value).toBe("0100-01");
    month.value = "9999-12";
    month.dispatchEvent(new Event("change"));
    document.getElementById("next").click();
    expect(month.value).toBe("9999-12");
    month.value = "10000-01";
    month.dispatchEvent(new Event("change"));
    expect(month.value).toBe("9999-12");
    expect(writeStoredJson.mock.calls.at(-1)[1].month).toBe("9999-12");
  });

  it("opens day modal when restored calendar month is stored as a string", () => {
    document.body.innerHTML = `
      <div id="calendar-modal" class="hidden"></div>
      <div id="calendar-modal-title"></div>
      <div id="calendar-modal-list"></div>
    `;

    const ctx = {
      state: {
        calendarMonth: "2026-05",
        projects: [],
        solutions: [],
      },
      els: {
        calendarModal: document.getElementById("calendar-modal"),
        calendarModalTitle: document.getElementById("calendar-modal-title"),
        calendarModalList: document.getElementById("calendar-modal-list"),
      },
      filteredSolutionsForCalendar: () => [
        {
          solution_id: "solution-1",
          solution_name: "May Launch",
          due_date: "2026-05-14",
          status: "active",
        },
      ],
      filteredTasksForCalendar: () => [],
      formatStatus: (status) => status,
    };

    expect(() => openCalendarModal(14, ctx)).not.toThrow();
    expect(ctx.els.calendarModal.classList.contains("hidden")).toBe(false);
    expect(ctx.els.calendarModalTitle.textContent).toContain("2026");
    expect(ctx.els.calendarModalList.textContent).toContain("May Launch");
  });
});
