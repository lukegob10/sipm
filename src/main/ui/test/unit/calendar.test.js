import { describe, expect, it } from "vitest";

import { openCalendarModal, renderCalendar } from "../../js/routes/calendar.js";

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
