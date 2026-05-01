import {
  DASHBOARD_SECTION_COLUMNS,
  DASHBOARD_SECTIONS,
  DASHBOARD_SECTION_TITLES,
  esc,
  dashboardActionButtonMarkup,
} from "./common.js";
import { cloneSectionDefaults, getSectionPrefs, updatePrefs, updateSectionPrefs } from "./prefs.js";

export function renderDashboardConfigButton() {
  return `<div class="dashboard-card-actions">${dashboardActionButtonMarkup(
    "open-config",
    "",
    "",
    "Customize Tables",
    "dashboard-card-action"
  )}</div>`;
}

export function renderDashboardConfigSectionTabs(activeSectionId) {
  return DASHBOARD_SECTIONS.map((sectionId) => {
    const activeClass = sectionId === activeSectionId ? " active" : "";
    return `<button type="button" class="tab${activeClass}" data-dashboard-action="switch-config-section" data-dashboard-section="${sectionId}">${esc(DASHBOARD_SECTION_TITLES[sectionId] || sectionId)}</button>`;
  }).join("");
}

export function ensureDashboardConfigModal() {
  if (typeof document === "undefined") return null;
  let modal = document.getElementById("dashboard-config-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "dashboard-config-modal";
  modal.className = "modal hidden";
  modal.setAttribute("aria-hidden", "true");
  modal.innerHTML = `
    <div class="modal-backdrop" data-dashboard-action="close-config"></div>
    <div class="modal-content dashboard-config-modal-content" role="dialog" aria-modal="true" aria-labelledby="dashboard-config-title">
      <div class="modal-header">
        <h3 id="dashboard-config-title">Customize Tables</h3>
        <button type="button" class="secondary" data-dashboard-action="close-config">Close</button>
      </div>
      <p id="dashboard-config-description" class="muted"></p>
      <div id="dashboard-config-section-tabs" class="modal-tabs dashboard-config-section-tabs" role="tablist" aria-label="Dashboard tables"></div>
      <div class="dashboard-config-layout">
        <section class="dashboard-config-panel">
          <div class="modal-section-title">Columns</div>
          <div id="dashboard-config-columns" class="dashboard-config-checklist"></div>
        </section>
        <section class="dashboard-config-panel">
          <div class="dashboard-config-list-head">
            <div class="modal-section-title">Solutions Included</div>
            <div class="dashboard-config-list-actions">
              <button type="button" class="dashboard-config-helper-link" data-dashboard-action="select-all-solutions">Select all</button>
              <button type="button" class="dashboard-config-helper-link" data-dashboard-action="clear-solutions">Clear</button>
            </div>
          </div>
          <div id="dashboard-config-solutions" class="dashboard-config-checklist dashboard-config-solutions"></div>
        </section>
      </div>
      <div class="form-actions">
        <button type="button" class="secondary" data-dashboard-action="reset-table-config">Reset</button>
        <button type="button" class="secondary" data-dashboard-action="close-config">Cancel</button>
        <button type="button" class="primary" data-dashboard-action="apply-table-config">Apply</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  return modal;
}

export function renderDashboardConfigModal(dashboardState, sectionId, options = {}) {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  if (!DASHBOARD_SECTIONS.includes(sectionId)) return;

  const columnDefsBySection = options.columnDefsBySection || {};
  const columnDefs = columnDefsBySection[sectionId] || {};
  const sectionPrefs = options.useDefaults ? cloneSectionDefaults(sectionId) : getSectionPrefs(dashboardState, sectionId);
  const selectedColumns = new Set(Array.isArray(sectionPrefs.columns) ? sectionPrefs.columns : []);
  const selectedSolutions = Array.isArray(sectionPrefs.solution_ids) ? new Set(sectionPrefs.solution_ids) : null;
  const sectionOptions = dashboardState.sectionOptions[sectionId] || [];

  const titleEl = modal.querySelector("#dashboard-config-title");
  const descriptionEl = modal.querySelector("#dashboard-config-description");
  const sectionTabsEl = modal.querySelector("#dashboard-config-section-tabs");
  const columnsEl = modal.querySelector("#dashboard-config-columns");
  const solutionsEl = modal.querySelector("#dashboard-config-solutions");
  if (!titleEl || !descriptionEl || !sectionTabsEl || !columnsEl || !solutionsEl) return;

  const activeSectionTitle = DASHBOARD_SECTION_TITLES[sectionId] || "Dashboard";
  titleEl.textContent = "Customize Tables";
  descriptionEl.textContent = `Editing ${activeSectionTitle}. Choose a table below, then reorder columns and pick which project solutions appear.`;
  sectionTabsEl.innerHTML = renderDashboardConfigSectionTabs(sectionId);

  const columnOrder = DASHBOARD_SECTION_COLUMNS[sectionId] || [];
  const modalColumnOrder = [
    ...[...selectedColumns].filter((columnId) => columnOrder.includes(columnId)),
    ...columnOrder.filter((columnId) => !selectedColumns.has(columnId)),
  ];
  columnsEl.innerHTML = modalColumnOrder
    .filter((columnId) => !!columnDefs[columnId])
    .map((columnId) => {
      const checked = selectedColumns.has(columnId) ? "checked" : "";
      const label = columnDefs[columnId].label;
      return `
        <div class="dashboard-config-item dashboard-config-column-item" data-column-id="${esc(columnId)}">
          <label class="dashboard-config-item-check">
            <input type="checkbox" name="dashboard-config-column" value="${esc(columnId)}" ${checked} />
            <span>${esc(label)}</span>
          </label>
          <div class="dashboard-config-item-move">
            <button type="button" class="secondary dashboard-config-move-btn" data-dashboard-action="move-column-up" data-column-id="${esc(columnId)}" aria-label="Move ${esc(label)} up">↑</button>
            <button type="button" class="secondary dashboard-config-move-btn" data-dashboard-action="move-column-down" data-column-id="${esc(columnId)}" aria-label="Move ${esc(label)} down">↓</button>
          </div>
        </div>
      `;
    })
    .join("");

  if (!sectionOptions.length) {
    solutionsEl.innerHTML = `<p class="dashboard-config-empty muted">No solutions available in this window.</p>`;
    return;
  }

  solutionsEl.innerHTML = sectionOptions
    .map((option) => {
      const checked = selectedSolutions ? selectedSolutions.has(option.solutionId) : true;
      return `
        <label class="dashboard-config-item dashboard-config-solution-item">
          <input type="checkbox" name="dashboard-config-solution" value="${esc(option.solutionId)}" ${checked ? "checked" : ""} />
          <span>
            <strong>${esc(option.solutionName)}</strong>
            <span class="dashboard-cell-meta">${esc(option.projectName)}</span>
          </span>
        </label>
      `;
    })
    .join("");
}

export function openDashboardConfigModal(dashboardState, sectionId) {
  const targetSection = DASHBOARD_SECTIONS.includes(sectionId)
    ? sectionId
    : dashboardState.prefs?.last_config_section || dashboardState.lastConfigSection || "main";
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  dashboardState.modalSection = targetSection;
  dashboardState.lastConfigSection = targetSection;
  updatePrefs(dashboardState, { last_config_section: targetSection });
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

export function closeDashboardConfigModal(dashboardState) {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  dashboardState.modalSection = null;
}

export function setAllModalSolutionChecks(checked) {
  const modal = ensureDashboardConfigModal();
  if (!modal) return;
  modal.querySelectorAll("input[name='dashboard-config-solution']").forEach((input) => {
    input.checked = checked;
  });
}

export function resetModalDraft(dashboardState, columnDefsBySection) {
  const sectionId = dashboardState.modalSection;
  if (!sectionId) return;
  renderDashboardConfigModal(dashboardState, sectionId, { useDefaults: true, columnDefsBySection });
}

export function moveModalColumn(direction, columnId) {
  const modal = ensureDashboardConfigModal();
  if (!modal || !columnId) return;

  const columnsEl = modal.querySelector("#dashboard-config-columns");
  if (!(columnsEl instanceof HTMLElement)) return;

  const items = Array.from(columnsEl.querySelectorAll(".dashboard-config-column-item"));
  const index = items.findIndex((item) => String(item.getAttribute("data-column-id") || "") === columnId);
  if (index < 0) return;

  if (direction === "up" && index > 0) {
    columnsEl.insertBefore(items[index], items[index - 1]);
    return;
  }
  if (direction === "down" && index < items.length - 1) {
    columnsEl.insertBefore(items[index + 1], items[index]);
  }
}

export function applyModalConfig(dashboardState, rerender) {
  const sectionId = dashboardState.modalSection;
  if (!sectionId) return;
  const modal = ensureDashboardConfigModal();
  if (!modal) return;

  const checkedColumns = Array.from(
    modal.querySelectorAll("input[name='dashboard-config-column']:checked")
  ).map((input) => String(input.value || "").trim());
  const checkedSolutions = Array.from(
    modal.querySelectorAll("input[name='dashboard-config-solution']:checked")
  ).map((input) => String(input.value || "").trim());
  const totalSolutions = modal.querySelectorAll("input[name='dashboard-config-solution']").length;

  const defaults = cloneSectionDefaults(sectionId);
  const columns = checkedColumns.length ? checkedColumns : defaults.columns;
  const solutionIds = totalSolutions === 0 || checkedSolutions.length === totalSolutions ? null : checkedSolutions;

  updateSectionPrefs(dashboardState, sectionId, {
    columns,
    solution_ids: solutionIds,
  });

  closeDashboardConfigModal(dashboardState);
  rerender();
}
