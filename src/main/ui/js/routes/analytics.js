const analyticsState = {
  days: 7,
  scope: "current",
  selectedSpaceId: "",
  loading: false,
  error: "",
  summary: null,
  routes: null,
  performance: null,
  requestId: 0,
  lastQueryKey: "",
};

function esc(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numberOrDash(value) {
  return value == null || value === "" ? "--" : String(value);
}

function scopeSpaceOptions(ctx) {
  return (ctx.state?.spaces || [])
    .map((space) => {
      const selected = analyticsState.selectedSpaceId === space.space_id ? " selected" : "";
      return `<option value="${esc(space.space_id)}"${selected}>${esc(space.name || space.space_id)}</option>`;
    })
    .join("");
}

function queryKey(ctx) {
  return [
    analyticsState.days,
    analyticsState.scope,
    analyticsState.selectedSpaceId,
    ctx.state?.activeSpace?.space_id || "",
  ].join("|");
}

function requestQueryString() {
  const params = new URLSearchParams();
  params.set("days", String(analyticsState.days));
  if (analyticsState.scope === "all") {
    params.set("all_spaces", "true");
  } else if (analyticsState.scope === "space" && analyticsState.selectedSpaceId) {
    params.set("space_id", analyticsState.selectedSpaceId);
  }
  return params.toString();
}

function ensureScopeDefaults(ctx) {
  const spaces = ctx.state?.spaces || [];
  const activeSpaceId = ctx.state?.activeSpace?.space_id || "";
  if (!analyticsState.selectedSpaceId || !spaces.some((space) => space.space_id === analyticsState.selectedSpaceId)) {
    analyticsState.selectedSpaceId = activeSpaceId || spaces[0]?.space_id || "";
  }
  if (analyticsState.scope === "space" && !analyticsState.selectedSpaceId) {
    analyticsState.scope = "current";
  }
}

function tableRows(rows, renderRow, emptyMessage, columnCount) {
  if (!Array.isArray(rows) || !rows.length) {
    return `<tr><td colspan="${columnCount}" class="muted">${esc(emptyMessage)}</td></tr>`;
  }
  return rows.map(renderRow).join("");
}

async function loadAnalytics(ctx, options = {}) {
  ensureScopeDefaults(ctx);
  const nextQueryKey = queryKey(ctx);
  if (!options.force && !analyticsState.error && analyticsState.lastQueryKey === nextQueryKey && analyticsState.summary) {
    return;
  }
  const requestId = analyticsState.requestId + 1;
  analyticsState.requestId = requestId;
  analyticsState.loading = true;
  analyticsState.error = "";
  renderAnalytics(ctx);
  const startedAt = performance.now();
  try {
    const query = requestQueryString();
    const suffix = query ? `?${query}` : "";
    const dashboard = await ctx.api(`/analytics/dashboard${suffix}`);
    if (analyticsState.requestId !== requestId) return;
    analyticsState.summary = dashboard?.summary || null;
    analyticsState.routes = dashboard?.routes || null;
    analyticsState.performance = dashboard?.performance || null;
    analyticsState.lastQueryKey = nextQueryKey;
  } catch (err) {
    if (analyticsState.requestId !== requestId) return;
    analyticsState.error = err?.message || "Failed to load usage analytics.";
  } finally {
    if (analyticsState.requestId === requestId) {
      analyticsState.loading = false;
      renderAnalytics(ctx);
      if (typeof ctx.noteRouteDataLoaded === "function") {
        ctx.noteRouteDataLoaded(performance.now() - startedAt);
      }
    }
  }
}

function bindAnalyticsControls(root, ctx) {
  if (root._analyticsBound) return;
  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    if (target.name === "analytics-days") {
      analyticsState.days = Number(target.value) || 7;
      void loadAnalytics(ctx, { force: true });
      return;
    }
    if (target.name === "analytics-scope") {
      analyticsState.scope = target.value || "current";
      void loadAnalytics(ctx, { force: true });
      return;
    }
    if (target.name === "analytics-space") {
      analyticsState.selectedSpaceId = target.value || "";
      if (analyticsState.scope !== "space") analyticsState.scope = "space";
      void loadAnalytics(ctx, { force: true });
    }
  });
  root.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-analytics-action]");
    if (!button) return;
    if (button.getAttribute("data-analytics-action") === "reload") {
      void loadAnalytics(ctx, { force: true });
    }
  });
  root._analyticsBound = true;
}

export function renderAnalytics(ctx) {
  const renderStartedAt = performance.now();
  const root = ctx.els?.analyticsRoot;
  if (!root) return;
  ensureScopeDefaults(ctx);
  bindAnalyticsControls(root, ctx);

  if (!ctx.usageAnalyticsEnabled?.()) {
    root.innerHTML = `
      <div class="analytics-empty">
        <h3>Usage Analytics Disabled</h3>
        <p class="muted">Enable <code>SIPM_USAGE_ANALYTICS_ENABLED=true</code> and apply the analytics schema migration before using this dashboard.</p>
      </div>
    `;
    ctx.noteViewRendered?.(performance.now() - renderStartedAt);
    return;
  }

  if (!ctx.state?.activeSpace?.is_global_admin) {
    root.innerHTML = `
      <div class="analytics-empty">
        <h3>Restricted View</h3>
        <p class="muted">Usage analytics is limited to global admins.</p>
      </div>
    `;
    ctx.noteViewRendered?.(performance.now() - renderStartedAt);
    return;
  }

  if (!analyticsState.loading && !analyticsState.summary && !analyticsState.error) {
    void loadAnalytics(ctx, { force: false });
  }

  const summary = analyticsState.summary?.summary || {};
  const performanceSummary = analyticsState.performance?.summary || {};
  const daily = analyticsState.summary?.daily || [];
  const topRoutes = analyticsState.routes?.top_routes || [];
  const topWorkflows = analyticsState.routes?.top_workflows || [];
  const failureHotspots = analyticsState.routes?.recent_failures || [];
  const slowestRoutes = analyticsState.performance?.routes || [];

  root.innerHTML = `
    <div class="analytics-stack">
      <div class="panel-toolbar analytics-toolbar">
        <div class="toolbar-group analytics-filter-group">
          <label class="inline-field">Window
            <select name="analytics-days">
              <option value="7"${analyticsState.days === 7 ? " selected" : ""}>7 days</option>
              <option value="30"${analyticsState.days === 30 ? " selected" : ""}>30 days</option>
              <option value="90"${analyticsState.days === 90 ? " selected" : ""}>90 days</option>
            </select>
          </label>
          <label class="inline-field">Scope
            <select name="analytics-scope">
              <option value="current"${analyticsState.scope === "current" ? " selected" : ""}>Current Space</option>
              <option value="all"${analyticsState.scope === "all" ? " selected" : ""}>All Spaces</option>
              <option value="space"${analyticsState.scope === "space" ? " selected" : ""}>Specific Space</option>
            </select>
          </label>
          <label class="inline-field analytics-space-select${analyticsState.scope === "space" ? "" : " disabled"}">Space
            <select name="analytics-space"${analyticsState.scope === "space" ? "" : " disabled"}>
              ${scopeSpaceOptions(ctx)}
            </select>
          </label>
        </div>
        <div class="toolbar-group">
          <span class="pill ${analyticsState.loading ? "warn" : "muted"}">${analyticsState.loading ? "Refreshing..." : "Ready"}</span>
          <button type="button" class="secondary" data-analytics-action="reload">Reload</button>
        </div>
      </div>
      ${analyticsState.error ? `<p class="form-notice notice-error">${esc(analyticsState.error)}</p>` : ""}
      <div class="analytics-card-grid">
        <div class="analytics-card"><span class="analytics-card-label">Sessions</span><strong>${numberOrDash(summary.sessions)}</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Active Users</span><strong>${numberOrDash(summary.active_users)}</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Route Views</span><strong>${numberOrDash(summary.route_views)}</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Workflow Actions</span><strong>${numberOrDash(summary.workflow_actions)}</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Failures</span><strong>${numberOrDash(summary.failure_count)}</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Combined Median / P95 Load</span><strong>${numberOrDash(summary.median_load_ms)} / ${numberOrDash(summary.p95_load_ms)} ms</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Page Load Median / P95</span><strong>${numberOrDash(performanceSummary.navigation_median_load_ms)} / ${numberOrDash(performanceSummary.navigation_p95_load_ms)} ms</strong></div>
        <div class="analytics-card"><span class="analytics-card-label">Route Transition Median / P95</span><strong>${numberOrDash(performanceSummary.route_transition_median_load_ms)} / ${numberOrDash(performanceSummary.route_transition_p95_load_ms)} ms</strong></div>
      </div>
      <div class="analytics-grid">
        <section class="panel analytics-panel">
          <div class="panel-header"><h3>Daily Traffic Trend</h3></div>
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Sessions</th>
                  <th>Users</th>
                  <th>Route Views</th>
                  <th>Workflow Actions</th>
                  <th>Failures</th>
                  <th>Combined Median / P95 Load</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows(
                  daily,
                  (row) => `<tr>
                    <td>${esc(row.date)}</td>
                    <td>${numberOrDash(row.sessions)}</td>
                    <td>${numberOrDash(row.active_users)}</td>
                    <td>${numberOrDash(row.route_views)}</td>
                    <td>${numberOrDash(row.workflow_actions)}</td>
                    <td>${numberOrDash(row.failure_count)}</td>
                    <td>${numberOrDash(row.median_load_ms)} / ${numberOrDash(row.p95_load_ms)} ms</td>
                  </tr>`,
                  "No traffic samples in the selected window.",
                  7
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel analytics-panel">
          <div class="panel-header"><h3>Top Routes</h3></div>
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>View</th>
                  <th>Route Views</th>
                  <th>Sessions</th>
                  <th>Users</th>
                  <th>Failures</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows(
                  topRoutes,
                  (row) => `<tr>
                    <td>${esc(row.view_key)}</td>
                    <td>${numberOrDash(row.route_views)}</td>
                    <td>${numberOrDash(row.unique_sessions)}</td>
                    <td>${numberOrDash(row.active_users)}</td>
                    <td>${numberOrDash(row.failure_count)}</td>
                  </tr>`,
                  "No route views recorded yet.",
                  5
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel analytics-panel">
          <div class="panel-header"><h3>Top Workflow Actions</h3></div>
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Action</th>
                  <th>Total</th>
                  <th>Success</th>
                  <th>Failure</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows(
                  topWorkflows,
                  (row) => `<tr>
                    <td>${esc(row.feature_key)}</td>
                    <td>${esc(row.action_key)}</td>
                    <td>${numberOrDash(row.total)}</td>
                    <td>${numberOrDash(row.success_count)}</td>
                    <td>${numberOrDash(row.failure_count)}</td>
                  </tr>`,
                  "No workflow telemetry recorded yet.",
                  5
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel analytics-panel">
          <div class="panel-header"><h3>Slowest Routes</h3></div>
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>View</th>
                  <th>Samples</th>
                  <th>Combined Median / P95 Load</th>
                  <th>Median Data / Render</th>
                  <th>CLS Avg</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows(
                  slowestRoutes,
                  (row) => `<tr>
                    <td>${esc(row.view_key)}</td>
                    <td>${numberOrDash(row.sample_count)}</td>
                    <td>${numberOrDash(row.median_load_ms)} / ${numberOrDash(row.p95_load_ms)} ms</td>
                    <td>${numberOrDash(row.median_data_load_ms)} / ${numberOrDash(row.median_render_ms)} ms</td>
                    <td>${numberOrDash(row.avg_cls_score)}</td>
                  </tr>`,
                  "No performance samples recorded yet.",
                  5
                )}
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel analytics-panel">
          <div class="panel-header"><h3>Recent Failure Hotspots</h3></div>
          <div class="table">
            <table>
              <thead>
                <tr>
                  <th>View</th>
                  <th>Feature</th>
                  <th>Action</th>
                  <th>Failures</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows(
                  failureHotspots,
                  (row) => `<tr>
                    <td>${esc(row.view_key)}</td>
                    <td>${esc(row.feature_key)}</td>
                    <td>${esc(row.action_key)}</td>
                    <td>${numberOrDash(row.failure_count)}</td>
                    <td>${esc(row.last_occurred_at || "--")}</td>
                  </tr>`,
                  "No recent failures recorded in the selected window.",
                  5
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  `;
  ctx.noteViewRendered?.(performance.now() - renderStartedAt);
}

export function render(ctx) {
  renderAnalytics(ctx);
}
