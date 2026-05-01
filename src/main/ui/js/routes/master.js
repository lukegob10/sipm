import { bindMasterTableInteractions, buildMasterTable } from "./master/table.js";

export function renderMasterFilters(ctx) {
  const { els } = ctx;
  const root = els.masterFilters;
  if (!root) return;
  // Filters are rendered inside the deliverables table so headers, filters,
  // and row data share one horizontal scroll container and stay aligned.
  root.innerHTML = "";
}

export function renderMasterTable(ctx) {
  const { els, renderMasterQuickstart, updateBulkSelectionCount } = ctx;
  if (!els.masterTable) return;
  const { html, rowCount } = buildMasterTable(ctx);
  if (typeof renderMasterQuickstart === "function") {
    renderMasterQuickstart(rowCount);
  }
  els.masterTable.innerHTML = html;
  bindMasterTableInteractions(ctx, {
    rerenderMasterTable: () => renderMasterTable(ctx),
  });
  updateBulkSelectionCount();
}

export function render(ctx) {
  renderMasterFilters(ctx);
  renderMasterTable(ctx);
}
