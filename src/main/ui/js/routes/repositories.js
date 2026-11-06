import { captureEntityMutationContext, isEntityMutationContextCurrent } from "../utils/form-state.js";

function inventoryState(state) {
  if (!state.repositoryInventory) {
    state.repositoryInventory = {
      records: null,
      loading: false,
      error: "",
      search: "",
    };
  }
  return state.repositoryInventory;
}

function searchableText(record) {
  return [
    record.repository_name,
    record.github_repo_url,
    ...(record.program_names || []),
    ...(record.project_names || []),
    ...(record.solution_names || []),
  ].map((value) => String(value || "").toLowerCase()).join(" ");
}

function entityNames(ctx, names, emptyLabel) {
  const values = Array.isArray(names) ? names : [];
  if (!values.length) return `<span class="muted">${emptyLabel}</span>`;
  return values.map((value) => `<span>${ctx.escapeHtml(value)}</span>`).join("");
}

function updatedLabel(value) {
  if (!value) return "Update time unavailable";
  const raw = String(value);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(raw) && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw)
    ? `${raw}Z` : raw;
  const date = new Date(normalized);
  if (!Number.isFinite(date.getTime())) return "Update time unavailable";
  return `Updated ${date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`;
}

function inventoryRows(ctx, records) {
  return records.map((record) => {
    const attachmentParts = [];
    if (record.solution_attachment_count) {
      attachmentParts.push(`${ctx.escapeHtml(record.solution_attachment_count)} Solution attachment${record.solution_attachment_count === 1 ? "" : "s"}`);
    }
    if (record.task_override_count) {
      attachmentParts.push(`${ctx.escapeHtml(record.task_override_count)} Task override${record.task_override_count === 1 ? "" : "s"}`);
    }
    return `
      <tr>
        <td class="repository-inventory-repo-cell">
          ${ctx.renderExternalRepoLink(record.github_repo_url, {
            label: record.repository_name,
            className: "repository-inventory-repo-link",
          })}
          <span class="repository-inventory-url">${ctx.escapeHtml(record.github_repo_url)}</span>
          <span class="repository-inventory-updated">${ctx.escapeHtml(updatedLabel(record.last_updated_at))}</span>
        </td>
        <td><div class="repository-entity-list">${entityNames(ctx, record.program_names, "No Program")}</div></td>
        <td><div class="repository-entity-list">${entityNames(ctx, record.project_names, "No Project")}</div></td>
        <td><div class="repository-entity-list">${entityNames(ctx, record.solution_names, "No Solution")}</div></td>
        <td>
          <span class="repository-reference-count"><strong>${ctx.escapeHtml(record.task_count)}</strong> task${record.task_count === 1 ? "" : "s"}</span>
        </td>
        <td>
          <span class="repository-inventory-source">${ctx.escapeHtml(attachmentParts.join(" · ") || "Inherited references")}</span>
        </td>
      </tr>
    `;
  }).join("");
}

async function refreshInventory(ctx) {
  const inventory = inventoryState(ctx.state);
  if (inventory.loading) return;
  const requestId = (Number(inventory.loadRequestId) || 0) + 1;
  const context = captureEntityMutationContext(ctx.state);
  const authed = ctx.state.authed;
  inventory.loadRequestId = requestId;
  inventory.loading = true;
  inventory.error = "";
  // Clearing session data resets loading even before a replacement request starts.
  const isCurrentRequest = () => ctx.state.repositoryInventory === inventory
    && inventory.loading && inventory.loadRequestId === requestId
    && ctx.state.authed === authed
    && isEntityMutationContextCurrent(ctx.state, context);
  try {
    const records = await ctx.api("/repository-inventory");
    if (!isCurrentRequest()) return;
    if (!Array.isArray(records) || records.some((record) => !record || typeof record !== "object" || Array.isArray(record)
      || ["github_repo_url", "repository_name"].some((key) => typeof record[key] !== "string" || !record[key].trim())
      || ["program_names", "project_names", "solution_names"].some((key) => !Array.isArray(record[key]) || record[key].some((value) => typeof value !== "string"))
      || ["solution_count", "task_count", "solution_attachment_count", "task_override_count"].some((key) => !Number.isSafeInteger(record[key]) || record[key] < 0)
      || (record.last_updated_at != null && typeof record.last_updated_at !== "string"))) {
      throw new Error("Repository inventory returned an invalid response.");
    }
    inventory.records = records;
  } catch (err) {
    if (!isCurrentRequest()) return;
    inventory.records = [];
    inventory.error = err.message || "Repository inventory could not be loaded.";
  } finally {
    if (isCurrentRequest()) {
      inventory.loading = false;
      renderRepositories(ctx);
    }
  }
}

function bindInteractions(ctx) {
  const root = ctx.els.repositoryInventoryRoot;
  const inventory = inventoryState(ctx.state);
  const context = captureEntityMutationContext(ctx.state);
  const authed = ctx.state.authed;
  const isCurrent = () => ctx.state.repositoryInventory === inventory
    && isEntityMutationContextCurrent(ctx.state, context) && ctx.state.authed === authed;
  root.querySelector("[data-repository-retry]")?.addEventListener("click", () => {
    if (!isCurrent() || inventory.loading) return;
    inventory.records = null;
    inventory.error = "";
    renderRepositories(ctx);
  });
  root.querySelector("[data-repository-search]")?.addEventListener("input", (event) => {
    if (!isCurrent()) return;
    const { selectionStart, selectionEnd, selectionDirection } = event.target;
    inventory.search = event.target.value;
    renderRepositories(ctx);
    const nextSearch = root.querySelector("[data-repository-search]");
    if (!nextSearch) return;
    try {
      nextSearch.focus({ preventScroll: true });
    } catch {
      nextSearch.focus();
    }
    if (selectionStart != null && selectionEnd != null) {
      try {
        nextSearch.setSelectionRange(selectionStart, selectionEnd, selectionDirection || "none");
      } catch {
        // Selection ranges are not supported by every browser for search inputs.
      }
    }
  });
}

export function renderRepositories(ctx) {
  const root = ctx.els.repositoryInventoryRoot;
  if (!root) return;
  const inventory = inventoryState(ctx.state);
  if (inventory.records === null && !inventory.loading) {
    const previous = root._repositoryRenderContext;
    const sameContext = previous && previous.inventory === inventory
      && previous.authed === ctx.state.authed && isEntityMutationContextCurrent(ctx.state, previous.context);
    const toolbar = sameContext ? root.querySelector(".repository-inventory-toolbar") : null;
    const retryFocused = sameContext && document.activeElement === root.querySelector("[data-repository-retry]");
    if (toolbar) {
      [...root.children].filter((child) => child !== toolbar).forEach((child) => child.remove());
      const summary = toolbar.querySelector(".repository-inventory-summary");
      if (summary) summary.textContent = "Refreshing...";
      const loading = document.createElement("div");
      loading.className = "repository-inventory-loading";
      loading.innerHTML = '<span class="spinner" aria-hidden="true"></span><p role="status" tabindex="-1" data-repository-loading-focus>Loading repository inventory…</p>';
      root.appendChild(loading);
      if (retryFocused) loading.querySelector("[data-repository-loading-focus]")?.focus({ preventScroll: true });
    } else {
      root._repositoryRenderContext = null;
      root.innerHTML = '<div class="repository-inventory-loading"><span class="spinner" aria-hidden="true"></span><p role="status">Loading repository inventory…</p></div>';
    }
    void refreshInventory(ctx);
    return;
  }
  if (inventory.loading) return;

  const search = inventory.search.trim().toLowerCase();
  const records = (inventory.records || []).filter((record) => !search || searchableText(record).includes(search));
  const previous = root._repositoryRenderContext;
  const focused = root.querySelector("[data-repository-search]");
  const restoreRetryFocus = previous && previous.inventory === inventory
    && isEntityMutationContextCurrent(ctx.state, previous.context) && previous.authed === ctx.state.authed
    && document.activeElement === root.querySelector("[data-repository-loading-focus]");
  const restoreSelection = previous && previous.inventory === inventory
    && isEntityMutationContextCurrent(ctx.state, previous.context) && previous.authed === ctx.state.authed
    && document.activeElement === focused
    ? { start: focused.selectionStart, end: focused.selectionEnd, direction: focused.selectionDirection } : null;
  root._repositoryRenderContext = { inventory, context: captureEntityMutationContext(ctx.state), authed: ctx.state.authed };
  root.innerHTML = `
    <div class="repository-inventory-toolbar">
      <label class="repository-inventory-search"><span>Search repositories and entities</span><input type="search" data-repository-search value="${ctx.escapeHtml(inventory.search)}" placeholder="Repository, Program, Project, or Solution" /></label>
      <div class="repository-inventory-summary">${inventory.error ? "" : `<strong>${records.length}</strong><span>unique repositor${records.length === 1 ? "y" : "ies"}</span>`}</div>
    </div>
    ${inventory.error ? `<div class="route-error-card"><strong>Repositories unavailable</strong><p>${ctx.escapeHtml(inventory.error)}</p><button type="button" class="secondary" data-repository-retry>Try again</button></div>` : ""}
    ${inventory.error ? "" : !(inventory.records || []).length ? '<div class="repository-inventory-empty"><h2>No repositories attached</h2><p>Add a GitHub repository URL to a Solution or Task to include it here.</p></div>' : `
      <div class="repository-inventory-table-wrap">
        <table class="repository-inventory-table">
          <thead><tr><th>Repository</th><th>Programs</th><th>Projects</th><th>Solutions</th><th>Referenced tasks</th><th>Attached via</th></tr></thead>
          <tbody>${records.length ? inventoryRows(ctx, records) : '<tr><td colspan="6" class="repository-inventory-no-match">No repositories match this search.</td></tr>'}</tbody>
        </table>
      </div>`}
  `;
  bindInteractions(ctx);
  if (restoreRetryFocus) {
    (root.querySelector("[data-repository-retry]") || root.querySelector("[data-repository-search]"))?.focus({ preventScroll: true });
  }
  if (restoreSelection) {
    const input = root.querySelector("[data-repository-search]");
    try {
      input?.focus({ preventScroll: true });
      if (restoreSelection.start != null && restoreSelection.end != null) {
        input?.setSelectionRange(restoreSelection.start, restoreSelection.end, restoreSelection.direction || "none");
      }
    } catch {
      input?.focus();
    }
  }
}

export function render(ctx) {
  renderRepositories(ctx);
}
