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
  return `Updated ${new Date(value).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`;
}

function inventoryRows(ctx, records) {
  return records.map((record) => {
    const attachmentParts = [];
    if (record.solution_attachment_count) {
      attachmentParts.push(`${record.solution_attachment_count} Solution attachment${record.solution_attachment_count === 1 ? "" : "s"}`);
    }
    if (record.task_override_count) {
      attachmentParts.push(`${record.task_override_count} Task override${record.task_override_count === 1 ? "" : "s"}`);
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
          <span class="repository-reference-count"><strong>${record.task_count}</strong> task${record.task_count === 1 ? "" : "s"}</span>
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
  inventory.loading = true;
  inventory.error = "";
  try {
    inventory.records = await ctx.api("/repository-inventory");
  } catch (err) {
    inventory.records = [];
    inventory.error = err.message || "Repository inventory could not be loaded.";
  } finally {
    inventory.loading = false;
    renderRepositories(ctx);
  }
}

function bindInteractions(ctx) {
  const root = ctx.els.repositoryInventoryRoot;
  const inventory = inventoryState(ctx.state);
  root.querySelector("[data-repository-search]")?.addEventListener("input", (event) => {
    inventory.search = event.target.value;
    renderRepositories(ctx);
    root.querySelector("[data-repository-search]")?.focus();
  });
}

export function renderRepositories(ctx) {
  const root = ctx.els.repositoryInventoryRoot;
  if (!root) return;
  const inventory = inventoryState(ctx.state);
  if (inventory.records === null && !inventory.loading) {
    root.innerHTML = '<div class="repository-inventory-loading"><span class="spinner" aria-hidden="true"></span><p>Loading repository inventory…</p></div>';
    void refreshInventory(ctx);
    return;
  }
  if (inventory.loading) return;

  const search = inventory.search.trim().toLowerCase();
  const records = (inventory.records || []).filter((record) => !search || searchableText(record).includes(search));
  root.innerHTML = `
    <div class="repository-inventory-toolbar">
      <label class="repository-inventory-search"><span>Search repositories and entities</span><input type="search" data-repository-search value="${ctx.escapeHtml(inventory.search)}" placeholder="Repository, Program, Project, or Solution" /></label>
      <div class="repository-inventory-summary"><strong>${records.length}</strong><span>unique repositor${records.length === 1 ? "y" : "ies"}</span></div>
    </div>
    ${inventory.error ? `<div class="route-error-card"><strong>Repositories unavailable</strong><p>${ctx.escapeHtml(inventory.error)}</p></div>` : ""}
    ${!inventory.error && !(inventory.records || []).length ? '<div class="repository-inventory-empty"><h2>No repositories attached</h2><p>Add a GitHub repository URL to a Solution or Task to include it here.</p></div>' : `
      <div class="repository-inventory-table-wrap">
        <table class="repository-inventory-table">
          <thead><tr><th>Repository</th><th>Programs</th><th>Projects</th><th>Solutions</th><th>Referenced tasks</th><th>Attached via</th></tr></thead>
          <tbody>${records.length ? inventoryRows(ctx, records) : '<tr><td colspan="6" class="repository-inventory-no-match">No repositories match this search.</td></tr>'}</tbody>
        </table>
      </div>`}
  `;
  bindInteractions(ctx);
}

export function render(ctx) {
  renderRepositories(ctx);
}
