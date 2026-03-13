function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function dateParts(value) {
  if (!value) return null;
  const raw = String(value).trim();
  const dateOnly = raw.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateOnly)) {
    const [yearText, monthText, dayText] = dateOnly.split("-");
    const year = Number(yearText);
    const month = Number(monthText) - 1;
    const day = Number(dayText);
    if (Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)) {
      return { year, month, day };
    }
  }
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return { year: d.getFullYear(), month: d.getMonth(), day: d.getDate() };
}

function sortByName(items, fieldName) {
  return [...(items || [])].sort((a, b) => String(a?.[fieldName] || "").localeCompare(String(b?.[fieldName] || "")));
}

function renderCalendarPreviewTitle(item, type, titleField) {
  const title = item?.[titleField] || "Untitled";
  if (type === "solution" && item?.solution_id) {
    return `<button type="button" class="calendar-preview-link" data-calendar-preview-action="open-solution" data-solution-id="${esc(item.solution_id)}">${esc(title)}</button>`;
  }
  return esc(title);
}

function renderPreviewItems(items, type, titleField, formatStatus) {
  if (!items.length) return "";
  const maxVisible = 2;
  const visible = items.slice(0, maxVisible);
  const rows = visible
    .map((item) => {
      return `<div class="calendar-item ${type}">
        <div class="calendar-item-title">${renderCalendarPreviewTitle(item, type, titleField)}</div>
        <div class="calendar-item-meta">${esc(formatStatus(item?.status))}</div>
      </div>`;
    })
    .join("");
  const more = items.length > maxVisible
    ? `<div class="calendar-more">+${items.length - maxVisible} more</div>`
    : "";
  return `${rows}${more}`;
}

function actionButtonMarkup(action, attrName, attrValue, label) {
  if (!attrValue) return "";
  return `<div class="modal-item-actions">
    <button type="button" class="calendar-modal-action-link modal-item-action" data-calendar-action="${action}" ${attrName}="${esc(attrValue)}">${esc(label)}</button>
  </div>`;
}

function itemsForDay(items, date) {
  return (items || []).filter((item) => {
    const due = dateParts(item?.due_date);
    if (!due) return false;
    return due.year === date.getFullYear() && due.month === date.getMonth() && due.day === date.getDate();
  });
}

export function renderCalendar(ctx) {
  const {
    state,
    els,
    filteredSolutionsForCalendar,
    filteredSubcomponentsForCalendar,
    formatStatus,
  } = ctx;
  if (!els.calendarGrid) return;

  const baseMonth = state.calendarMonth ? new Date(state.calendarMonth) : new Date();
  const year = baseMonth.getFullYear();
  const month = baseMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startWeekday = firstDay.getDay();

  const solutions = sortByName(filteredSolutionsForCalendar(), "solution_name");
  const subcomponents = sortByName(filteredSubcomponentsForCalendar(), "subcomponent_name");

  const itemsByDay = {};
  for (let day = 1; day <= daysInMonth; day += 1) {
    itemsByDay[day] = { solutions: [], subcomponents: [] };
  }

  solutions.forEach((item) => {
    const due = dateParts(item?.due_date);
    if (!due || due.year !== year || due.month !== month) return;
    itemsByDay[due.day]?.solutions.push(item);
  });
  subcomponents.forEach((item) => {
    const due = dateParts(item?.due_date);
    if (!due || due.year !== year || due.month !== month) return;
    itemsByDay[due.day]?.subcomponents.push(item);
  });

  const cells = [];
  for (let i = 0; i < startWeekday; i += 1) cells.push(null);
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const weekdayRow = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    .map((label) => `<div class="calendar-weekday">${label}</div>`)
    .join("");

  const today = new Date();
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) {
    const weekCells = cells.slice(i, i + 7);
    weeks.push(
      `<div class="calendar-week">${weekCells
        .map((day) => {
          if (!day) return `<div class="calendar-cell empty"></div>`;
          const dayItems = itemsByDay[day] || { solutions: [], subcomponents: [] };
          const total = dayItems.solutions.length + dayItems.subcomponents.length;
          const count = total ? `<span class="calendar-count">${total}</span>` : "";
          const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
          const todayClass = isToday ? " today" : "";
          const solutionPreview = renderPreviewItems(dayItems.solutions, "solution", "solution_name", formatStatus);
          const subcomponentPreview = renderPreviewItems(dayItems.subcomponents, "subcomponent", "subcomponent_name", formatStatus);
          const streams = [
            solutionPreview
              ? `<div class="calendar-stream calendar-stream-solutions"><div class="calendar-stream-label">Solutions</div>${solutionPreview}</div>`
              : "",
            subcomponentPreview
              ? `<div class="calendar-stream calendar-stream-subcomponents"><div class="calendar-stream-label">Subcomponents</div>${subcomponentPreview}</div>`
              : "",
          ]
            .filter(Boolean)
            .join("");
          return `<div class="calendar-cell${todayClass}" data-day="${day}">
            <div class="calendar-date-row">
              <div class="calendar-date">${day}</div>
              ${count}
            </div>
            ${streams}
          </div>`;
        })
        .join("")}</div>`
    );
  }

  const monthLabel = `${firstDay.toLocaleString("default", { month: "long" })} ${year}`;
  els.calendarGrid.innerHTML = `
    <div class="calendar-month-label">${monthLabel}</div>
    <div class="calendar-weekdays">${weekdayRow}</div>
    ${weeks.join("")}
  `;
}

export function openCalendarModal(day, ctx) {
  const {
    state,
    els,
    filteredSolutionsForCalendar,
    filteredSubcomponentsForCalendar,
    formatStatus,
  } = ctx;
  if (!els.calendarModal) return;

  const baseMonth = state.calendarMonth || new Date();
  const date = new Date(baseMonth.getFullYear(), baseMonth.getMonth(), day || 1);
  const solutions = sortByName(itemsForDay(filteredSolutionsForCalendar(), date), "solution_name");
  const subcomponents = sortByName(itemsForDay(filteredSubcomponentsForCalendar(), date), "subcomponent_name");
  const projectsById = new Map((state.projects || []).map((project) => [project.project_id, project]));
  const solutionsById = new Map((state.solutions || []).map((solution) => [solution.solution_id, solution]));

  if (els.calendarModalTitle) {
    els.calendarModalTitle.textContent = date.toLocaleDateString(undefined, {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }
  if (els.calendarModalList) {
    const solutionSection = solutions.length
      ? `<div class="modal-section">
          <div class="modal-section-title">Solutions (${solutions.length})</div>
          ${solutions
            .map((item) => {
              const projectName = projectsById.get(item.project_id)?.project_name || "—";
              const action = [
                actionButtonMarkup("open-project", "data-project-id", item.project_id, "Open Project"),
                actionButtonMarkup("open-solution", "data-solution-id", item.solution_id, "Open Solution"),
              ]
                .filter(Boolean)
                .join("");
              return `<div class="modal-item solution">
                <div class="modal-item-title">${esc(item.solution_name)}</div>
                <div class="modal-item-meta">
                  Project ${esc(projectName)} • ${esc(formatStatus(item.status))} • Owner ${esc(item.owner || "—")} • Assignee ${esc(item.assignee || "—")} • Due ${esc(item.due_date || "—")}
                </div>
                ${action}
              </div>`;
            })
            .join("")}
        </div>`
      : "";
    const subcomponentSection = subcomponents.length
      ? `<div class="modal-section">
          <div class="modal-section-title">Subcomponents (${subcomponents.length})</div>
          ${subcomponents
            .map((item) => {
              const projectName = projectsById.get(item.project_id)?.project_name || "—";
              const solutionName = solutionsById.get(item.solution_id)?.solution_name || "—";
              const action = [
                actionButtonMarkup("open-project", "data-project-id", item.project_id, "Open Project"),
                actionButtonMarkup("open-subcomponent", "data-subcomponent-id", item.subcomponent_id, "Open Work Item"),
              ]
                .filter(Boolean)
                .join("");
              return `<div class="modal-item subcomponent">
                <div class="modal-item-title">${esc(item.subcomponent_name)}</div>
                <div class="modal-item-meta">
                  Project ${esc(projectName)} • Solution ${esc(solutionName)} • ${esc(formatStatus(item.status))} • Assignee ${esc(item.assignee || "—")} • Due ${esc(item.due_date || "—")}
                </div>
                ${action}
              </div>`;
            })
            .join("")}
        </div>`
      : "";
    const html = [solutionSection, subcomponentSection].filter(Boolean).join("");
    els.calendarModalList.innerHTML = html || `<div class="modal-empty">No solutions or subcomponents due on this day</div>`;
  }

  els.calendarModal.classList.remove("hidden");
}
