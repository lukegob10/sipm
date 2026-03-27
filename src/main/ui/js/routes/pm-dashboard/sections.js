import {
  SUBCOMPONENT_STATUS_ORDER,
  SOLUTION_STATUS_ORDER,
  clamp,
  dueDeltaLabel,
  esc,
  formatFteValue,
  healthTone,
  isoDateLabel,
  renderPMDashboardCapacityLink,
  renderPMDashboardOwnerLink,
  renderPMDashboardProjectLink,
  renderPMDashboardSolutionLink,
  renderPMDashboardTimelineLink,
  scoreTone,
  utilTone,
} from "./analytics.js";

export function renderPMDashboardSummarySection({
  els,
  activeSpaceLabel,
  portfolioHealthScore,
  activeSolutionsCount,
  atRiskSolutions,
  activeSubcomponentsCount,
  blockedSubcomponentsCount,
  unassignedSubcomponentsCount,
  overdueTotal,
  dueSoonTotal,
  totalGap,
  totalAllocated,
  totalCapacity,
  completionsThisMonth,
  formatFte,
}) {
  if (!els.pmDashboardSummary) return;
  els.pmDashboardSummary.innerHTML = `
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Current Space</div>
      <div class="pm-kpi-value">${esc(activeSpaceLabel)}</div>
      <div class="pm-kpi-meta">PM Command Center only shows active-space data</div>
    </article>
    <article class="pm-kpi-card pm-kpi-health ${healthTone(portfolioHealthScore)}">
      <div class="pm-kpi-label">Portfolio Health</div>
      <div class="pm-kpi-value">${portfolioHealthScore}</div>
      <div class="pm-kpi-meta">Composite risk-adjusted score</div>
    </article>
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Active Solutions</div>
      <div class="pm-kpi-value">${activeSolutionsCount}</div>
      <div class="pm-kpi-meta">${atRiskSolutions} currently at risk</div>
    </article>
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Open Tasks</div>
      <div class="pm-kpi-value">${activeSubcomponentsCount}</div>
      <div class="pm-kpi-meta">${blockedSubcomponentsCount} blocked, ${unassignedSubcomponentsCount} unassigned</div>
    </article>
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Schedule Pressure</div>
      <div class="pm-kpi-value">${overdueTotal + dueSoonTotal}</div>
      <div class="pm-kpi-meta">${overdueTotal} overdue, ${dueSoonTotal} due in 14 days</div>
    </article>
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Capacity Gap</div>
      <div class="pm-kpi-value ${totalGap < 0 ? "danger" : "positive"}">${totalGap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(totalGap), formatFte)}</div>
      <div class="pm-kpi-meta">${formatFteValue(totalAllocated, formatFte)} allocated / ${formatFteValue(totalCapacity, formatFte)} capacity</div>
    </article>
    <article class="pm-kpi-card">
      <div class="pm-kpi-label">Throughput (This Month)</div>
      <div class="pm-kpi-value">${completionsThisMonth}</div>
      <div class="pm-kpi-meta">Completed solutions + tasks</div>
    </article>
  `;
}

export function renderPMDashboardHealthSection({ els, projectSummaries, hrefFor }) {
  if (!els.pmDashboardHealth) return;
  if (!projectSummaries.length) {
    els.pmDashboardHealth.innerHTML = "<h3>Project Health</h3><p class='muted'>No projects in this space yet.</p>";
    return;
  }
  const rows = projectSummaries
    .slice(0, 12)
    .map((summary) => {
      const hotspots = [
        summary.redCount ? `<span class="pill danger">Red ${summary.redCount}</span>` : "",
        summary.amberCount ? `<span class="pill warn">Amber ${summary.amberCount}</span>` : "",
        summary.overdueCount ? `<span class="pill danger">Overdue ${summary.overdueCount}</span>` : "",
        summary.blockedCount ? `<span class="pill warn">Blocked ${summary.blockedCount}</span>` : "",
      ].filter(Boolean).join(" ");
      return `<tr>
        <td>${renderPMDashboardProjectLink(summary.projectName, summary.projectId)}<div class="muted">Next due: ${summary.nearestDue ? summary.nearestDue.toISOString().slice(0, 10) : "—"}</div></td>
        <td><span class="pill ${healthTone(summary.healthScore)}">${summary.healthScore}</span></td>
        <td>${summary.openSolutions}</td>
        <td>${summary.openSubcomponents}</td>
        <td>${hotspots || "<span class='muted'>None</span>"}</td>
      </tr>`;
    })
    .join("");
  els.pmDashboardHealth.innerHTML = `
    <div class="pm-card-header">
      <h3>Project Health</h3>
      <a href="${esc(hrefFor("master"))}" class="pm-card-link">Deliverables</a>
    </div>
    <div class="table pm-table-wrap">
      <table>
        <thead>
          <tr><th>Project</th><th>Health</th><th>Open Sol.</th><th>Open Tasks</th><th>Hotspots</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

export function renderPMDashboardRiskSection({ els, solutionRiskRows, hrefFor }) {
  if (!els.pmDashboardRisks) return;
  const rows = solutionRiskRows
    .slice(0, 12)
    .filter((row) => row.riskScore > 0)
    .map((row) => `<tr>
      <td>${renderPMDashboardSolutionLink(row.solutionName, row.solutionId)}<div class="muted">${esc(row.projectName)}</div></td>
      <td><span class="pill ${scoreTone(row.riskScore)}">${row.riskScore}</span></td>
      <td>${renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)}</td>
      <td>${isoDateLabel(row.dueDate)}</td>
      <td>${row.signals.map((signal) => `<span class="pm-signal">${esc(signal)}</span>`).join("") || "<span class='muted'>No strong signals</span>"}</td>
    </tr>`)
    .join("");
  els.pmDashboardRisks.innerHTML = `
    <div class="pm-card-header">
      <h3>Risk Radar</h3>
      <a href="${esc(hrefFor("master"))}" class="pm-card-link">Update Status</a>
    </div>
    ${rows
      ? `<div class="table pm-table-wrap"><table><thead><tr><th>Solution</th><th>Risk</th><th>Owner</th><th>Due</th><th>Signals</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : "<p class='muted'>No elevated solution risks detected.</p>"
    }
  `;
}

export function renderPMDashboardTimelineSection({
  els,
  timelineFocusRows,
  overdueTotal,
  dueSoonTotal,
  hrefFor,
}) {
  if (!els.pmDashboardTimeline) return;
  const rows = timelineFocusRows
    .map((row) => {
      const dueClass = row.days < 0 ? "danger" : row.days <= 7 ? "warn" : "muted";
      return `<tr>
        <td><span class="pm-item-kind">${esc(row.kind)}</span></td>
        <td>${renderPMDashboardTimelineLink(row)}<div class="muted">${esc(row.projectName)}${row.solutionName ? ` / ${esc(row.solutionName)}` : ""}</div></td>
        <td>${renderPMDashboardOwnerLink(row.owner, row.ownerAssigneeKey)}</td>
        <td>${isoDateLabel(row.dueDate)}</td>
        <td><span class="pill ${dueClass}">${esc(dueDeltaLabel(row.days))}</span></td>
      </tr>`;
    })
    .join("");
  els.pmDashboardTimeline.innerHTML = `
    <div class="pm-card-header">
      <h3>Delivery Timeline</h3>
      <a href="${esc(hrefFor("calendar"))}" class="pm-card-link">Calendar</a>
    </div>
    <p class="muted">Overdue: ${overdueTotal} | Due in 14 days: ${dueSoonTotal}</p>
    ${rows
      ? `<div class="table pm-table-wrap"><table><thead><tr><th>Type</th><th>Work Item</th><th>Owner</th><th>Due</th><th>Urgency</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : "<p class='muted'>No due dates in the next 30 days.</p>"
    }
  `;
}

export function renderPMDashboardCapacitySection({
  els,
  capacityRows,
  selectedCapacityMonth,
  capacityScopeLabel,
  totalCapacity,
  totalAllocated,
  totalGap,
  overloadedRows,
  hrefFor,
  formatFte,
}) {
  if (!els.pmDashboardCapacity) return;
  const rows = capacityRows
    .slice(0, 12)
    .map((row) => {
      const tone = utilTone(row.utilization, row.capacity, row.allocated);
      const width = clamp(
        row.capacity > 0 ? row.utilization : row.allocated > 0 ? 100 : 0,
        0,
        160
      );
      const utilLabel = row.capacity > 0 ? `${Math.round(row.utilization)}%` : row.allocated > 0 ? "n/a" : "0%";
      return `<tr>
        <td>${renderPMDashboardCapacityLink(row)}</td>
        <td>${formatFteValue(row.capacity, formatFte)}</td>
        <td>${formatFteValue(row.allocated, formatFte)}</td>
        <td class="${row.gap < 0 ? "danger" : "positive"}">${row.gap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(row.gap), formatFte)}</td>
        <td>
          <div class="pm-util-meter"><span class="${tone}" style="width:${width}%;"></span></div>
          <div class="muted">${utilLabel}</div>
        </td>
      </tr>`;
    })
    .join("");

  els.pmDashboardCapacity.innerHTML = `
    <div class="pm-card-header">
      <h3>Capacity and Allocation</h3>
      <div class="pm-card-controls">
        <label class="pm-scope-control">
          <span>Month</span>
          <input type="month" value="${esc(selectedCapacityMonth)}" data-pm-dashboard-action="set-capacity-month" aria-label="Select capacity month" />
        </label>
        <a href="${esc(hrefFor("planning"))}" class="pm-card-link">Planning</a>
      </div>
    </div>
    <p class="muted">${esc(capacityScopeLabel)}</p>
    <p class="muted">Source: Planning task assignments only.</p>
    <div class="pm-capacity-summary">
      <div><span>Total Capacity</span><strong>${formatFteValue(totalCapacity, formatFte)} FTE-mo</strong></div>
      <div><span>Allocated</span><strong>${formatFteValue(totalAllocated, formatFte)} FTE-mo</strong></div>
      <div><span>Gap</span><strong class="${totalGap < 0 ? "danger" : "positive"}">${totalGap >= 0 ? "+" : "-"}${formatFteValue(Math.abs(totalGap), formatFte)} FTE-mo</strong></div>
      <div><span>Overloaded</span><strong>${overloadedRows.length}</strong></div>
    </div>
    ${rows
      ? `<div class="table pm-table-wrap"><table><thead><tr><th>Assignee</th><th>Cap.</th><th>Alloc.</th><th>Gap</th><th>Load</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : "<p class='muted'>No allocations found for this scope.</p>"
    }
  `;
}

export function renderPMDashboardStatusSection({
  els,
  solutions,
  subcomponents,
  ragCounts,
  solutionStatusCounts,
  subcomponentStatusCounts,
  formatStatus,
  hrefFor,
}) {
  if (!els.pmDashboardStatus) return;
  const solutionTotal = Math.max(1, solutions.length);
  const subcomponentTotal = Math.max(1, subcomponents.length);
  const ragTotal = Math.max(1, ragCounts.red + ragCounts.amber + ragCounts.green + ragCounts.unknown);

  const renderStatusRows = (counts, total, orderedKeys) =>
    orderedKeys
      .map((status) => {
        const count = counts.get(status) || 0;
        const width = Math.round((count / total) * 100);
        return `<li>
          <span>${esc(formatStatus(status))}</span>
          <strong>${count}</strong>
          <div class="pm-mini-meter"><span style="width:${width}%;"></span></div>
        </li>`;
      })
      .join("");

  els.pmDashboardStatus.innerHTML = `
    <div class="pm-card-header">
      <h3>Portfolio Flow</h3>
      <a href="${esc(hrefFor("kanban"))}" class="pm-card-link">Kanban</a>
    </div>
    <div class="pm-status-grid">
      <section>
        <h4>Solutions by Status</h4>
        <ul class="pm-status-list">${renderStatusRows(solutionStatusCounts, solutionTotal, SOLUTION_STATUS_ORDER)}</ul>
      </section>
      <section>
        <h4>Tasks by Status</h4>
        <ul class="pm-status-list">${renderStatusRows(subcomponentStatusCounts, subcomponentTotal, SUBCOMPONENT_STATUS_ORDER)}</ul>
      </section>
    </div>
    <h4>Active Solution RAG Mix</h4>
    <div class="pm-rag-stack" role="img" aria-label="RAG distribution for active solutions">
      <span class="rag-red" style="width:${Math.round((ragCounts.red / ragTotal) * 100)}%;"></span>
      <span class="rag-amber" style="width:${Math.round((ragCounts.amber / ragTotal) * 100)}%;"></span>
      <span class="rag-green" style="width:${Math.round((ragCounts.green / ragTotal) * 100)}%;"></span>
      <span class="rag-unknown" style="width:${Math.round((ragCounts.unknown / ragTotal) * 100)}%;"></span>
    </div>
    <div class="pm-rag-legend">
      <span><i class="dot red"></i>Red ${ragCounts.red}</span>
      <span><i class="dot amber"></i>Amber ${ragCounts.amber}</span>
      <span><i class="dot green"></i>Green ${ragCounts.green}</span>
      <span><i class="dot unknown"></i>Unknown ${ragCounts.unknown}</span>
    </div>
  `;
}

export function renderPMDashboardActionsSection({ els, actions, hrefFor }) {
  if (!els.pmDashboardActions) return;
  const actionRows = actions
    .slice(0, 6)
    .map((action) => `<li class="pm-action-row ${action.tone}">
      <div>
        <div class="pm-action-title">${esc(action.title)}</div>
        <div class="muted">${esc(action.detail)}</div>
      </div>
      <a href="${esc(action.href)}" class="pm-action-link">${esc(action.cta)}</a>
    </li>`)
    .join("");
  els.pmDashboardActions.innerHTML = `
    <div class="pm-card-header">
      <h3>Immediate Actions</h3>
    </div>
    <ul class="pm-actions-list">${actionRows}</ul>
    <div class="pm-quick-links">
      <a href="${esc(hrefFor("master"))}">Deliverables</a>
      <a href="${esc(hrefFor("planning"))}">Planning</a>
      <a href="${esc(hrefFor("subcomponents-workbench"))}">Subcomponents</a>
      <a href="${esc(hrefFor("calendar"))}">Calendar</a>
    </div>
  `;
}
