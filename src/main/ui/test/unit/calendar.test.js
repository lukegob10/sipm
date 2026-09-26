import { describe, expect, it, vi } from "vitest";

import { openCalendarModal, renderCalendar } from "../../js/routes/calendar.js";
import { createCalendarRouteController } from "../../js/routes/calendar/interactions.js";

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
