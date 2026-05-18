import { describe, expect, it } from "vitest";

import { openCalendarModal } from "../../js/routes/calendar.js";

describe("calendar route", () => {
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
      filteredSubcomponentsForCalendar: () => [],
      formatStatus: (status) => status,
    };

    expect(() => openCalendarModal(14, ctx)).not.toThrow();
    expect(ctx.els.calendarModal.classList.contains("hidden")).toBe(false);
    expect(ctx.els.calendarModalTitle.textContent).toContain("2026");
    expect(ctx.els.calendarModalList.textContent).toContain("May Launch");
  });
});
