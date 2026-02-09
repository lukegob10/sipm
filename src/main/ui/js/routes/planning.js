function monthStartKey(value) {
  const raw = String(value || "").slice(0, 10);
  if (!raw) return "";
  const parsed = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return "";
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-01`;
}

function monthInputValue(value) {
  const key = monthStartKey(value);
  return key ? key.slice(0, 7) : "";
}

function monthLabel(monthKey) {
  const parsed = new Date(`${monthKey}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return monthKey;
  return parsed.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function monthRange(fromDate, toDate) {
  const from = monthStartKey(fromDate);
  const to = monthStartKey(toDate);
  if (!from || !to) return [];
  const out = [];
  const cursor = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  while (cursor <= end) {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-01`;
    out.push({ key, label: monthLabel(key) });
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return out;
}

export function renderPlanning(ctx) {
  const {
    state,
    els,
    assigneeKeyFromAlloc,
    findUserBySoeid,
    assigneeLabelFromKey,
    allocationLabel,
    allocationMonthStart,
    allocationFteMonths,
    userCapacityFteMonth,
    formatFte,
    renderPlanningWindowSummary,
    renderPlanningRoster,
  } = ctx;

  if (!els.planningBoard) return;
  const selectedWindowId = els.planningWindowSelect?.value || "";
  let selectedWindow = state.planningWindows.find((w) => w.window_id === selectedWindowId);
  if (!selectedWindow && state.planningWindows.length && els.planningWindowSelect) {
    els.planningWindowSelect.value = state.planningWindows[0].window_id;
    selectedWindow = state.planningWindows[0];
  }
  if (selectedWindow && els.planningFrom && els.planningTo) {
    els.planningFrom.value = selectedWindow.start_date;
    els.planningTo.value = selectedWindow.end_date;
    const monthStartInput = els.allocationForm?.querySelector('[name="month_start"]');
    if (monthStartInput && !monthStartInput.value) {
      monthStartInput.value = monthInputValue(selectedWindow.start_date);
    }
  }
  if (!selectedWindow && !state.planningWindows.length) {
    if (els.planningKpis) els.planningKpis.innerHTML = "";
    els.planningBoard.innerHTML = "<p class='muted'>Create a planning window to begin.</p>";
    return;
  }

  const from = selectedWindow?.start_date || els.planningFrom?.value || "";
  const to = selectedWindow?.end_date || els.planningTo?.value || "";
  if (!from || !to) {
    if (els.planningKpis) els.planningKpis.innerHTML = "";
    els.planningBoard.innerHTML = "<p class='muted'>Select a planning window to view the timeline.</p>";
    return;
  }

  const searchTerm = (els.planningSearch?.value || "").toLowerCase();
  const teamTagFilter = (els.planningTeamTagFilter?.value || "").toLowerCase();
  const filterOver = !!els.planningFilterOver?.checked;
  const filterUnder = !!els.planningFilterUnder?.checked;
  const includeUnassigned = false;
  const fromMonth = monthStartKey(from);
  const toMonth = monthStartKey(to);

  const windowFiltered = state.allocations.filter((a) => {
    const allocMonth = allocationMonthStart(a);
    if (!allocMonth) return false;
    if (fromMonth && allocMonth < fromMonth) return false;
    if (toMonth && allocMonth > toMonth) return false;
    if (selectedWindowId && a.window_id !== selectedWindowId) return false;
    return true;
  });

  const loadSource = windowFiltered.filter((a) => {
    const key = assigneeKeyFromAlloc(a);
    if (!key || key === "unassigned") return includeUnassigned;
    const user = findUserBySoeid(key);
    if (teamTagFilter && !(user?.team_tag || "").toLowerCase().includes(teamTagFilter)) return false;
    return true;
  });

  const filtered = windowFiltered.filter((a) => {
    const key = assigneeKeyFromAlloc(a);
    if (!key || key === "unassigned") return includeUnassigned;
    const user = findUserBySoeid(key);
    if (teamTagFilter && !(user?.team_tag || "").toLowerCase().includes(teamTagFilter)) return false;
    if (searchTerm) {
      const assigneeLabel = assigneeLabelFromKey(key).toLowerCase();
      const itemLabel = allocationLabel(a).toLowerCase();
      if (!assigneeLabel.includes(searchTerm) && !itemLabel.includes(searchTerm)) return false;
    }
    return true;
  });

  const months = monthRange(from, to);
  filtered.forEach((a) => {
    const key = allocationMonthStart(a);
    if (!key || months.find((m) => m.key === key)) return;
    months.push({ key, label: monthLabel(key) });
  });
  months.sort((a, b) => (a.key < b.key ? -1 : 1));

  const memberMeta = {};
  state.users.forEach((u) => {
    const key = u.soeid;
    if (!key) return;
    memberMeta[key] = {
      capacity: userCapacityFteMonth(u),
      role: u.role || "",
      team: u.team_tag || "",
      name: u.display_name || key,
    };
  });

  const assigneesSet = new Set();
  state.users.forEach((u) => {
    if (!u.soeid) return;
    const matchesTeam = !teamTagFilter || (u.team_tag || "").toLowerCase().includes(teamTagFilter);
    const matchesSearch =
      !searchTerm ||
      (u.display_name || "").toLowerCase().includes(searchTerm) ||
      u.soeid.toLowerCase().includes(searchTerm);
    if (matchesTeam && matchesSearch) assigneesSet.add(u.soeid);
  });
  filtered.forEach((a) => {
    const key = assigneeKeyFromAlloc(a);
    if (key && key !== "unassigned") assigneesSet.add(key);
  });

  const loadByAssignee = new Map();
  loadSource.forEach((a) => {
    const key = assigneeKeyFromAlloc(a);
    if (!key) return;
    loadByAssignee.set(key, (loadByAssignee.get(key) || 0) + allocationFteMonths(a));
  });

  let assignees = Array.from(assigneesSet).filter(Boolean);
  assignees = assignees.filter((key) => {
    const meta = memberMeta[key] || { capacity: 1, role: "", team: "", name: assigneeLabelFromKey(key) };
    const load = loadByAssignee.get(key) || 0;
    const cap = meta.capacity || 1;
    if (filterOver || filterUnder) {
      const isOver = load > cap;
      const isUnder = load < cap;
      return (filterOver && isOver) || (filterUnder && isUnder);
    }
    return true;
  });
  assignees.sort((a, b) => assigneeLabelFromKey(a).localeCompare(assigneeLabelFromKey(b)));

  const totalCapacity = assignees.reduce((sum, key) => sum + (memberMeta[key]?.capacity || 1), 0);
  const totalAllocated = filtered.reduce((sum, a) => sum + allocationFteMonths(a), 0);
  const remaining = totalCapacity - totalAllocated;
  const overCount = assignees.filter((key) => (loadByAssignee.get(key) || 0) > (memberMeta[key]?.capacity || 1)).length;

  if (els.planningKpis) {
    els.planningKpis.innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Capacity</div><div class="kpi-value">${formatFte(totalCapacity)}</div><div class="kpi-label">FTE-mo</div></div>
      <div class="kpi-card"><div class="kpi-label">Allocated</div><div class="kpi-value">${formatFte(totalAllocated)}</div><div class="kpi-label">FTE-mo</div></div>
      <div class="kpi-card"><div class="kpi-label">Remaining</div><div class="kpi-value">${remaining >= 0 ? formatFte(remaining) : `-${formatFte(Math.abs(remaining))}`}</div><div class="kpi-label">FTE-mo</div></div>
      <div class="kpi-card"><div class="kpi-label">Over-allocated</div><div class="kpi-value">${overCount}</div><div class="kpi-label">assignees</div></div>
    `;
  }

  if (!months.length || !assignees.length) {
    els.planningBoard.innerHTML = "<p class='muted'>No allocations in this window.</p>";
    return;
  }

  const cycleLabel = selectedWindow
    ? `${selectedWindow.name} • ${selectedWindow.start_date} → ${selectedWindow.end_date}`
    : from && to
      ? `Custom Horizon • ${from} → ${to}`
      : "Planning Cycle";

  let html = `<div class="table compact"><table class="planning-table"><thead><tr><th>Assignee</th>${months
    .map((m) => `<th>${m.label}</th>`)
    .join("")}</tr></thead><tbody>`;

  const groups = {};
  assignees.forEach((key) => {
    const meta = memberMeta[key];
    const group = meta?.team || "No Team Tag";
    groups[group] = groups[group] || [];
    groups[group].push(key);
  });

  Object.keys(groups)
    .sort()
    .forEach((groupName) => {
      const groupKey = groupName || "No Team Tag";
      const isCollapsed = state.planningGroupCollapsed.has(groupKey);
      html += `<tr class="planning-group-row"><td colspan="${months.length + 1}">
        <button type="button" class="group-toggle" data-group="${groupKey}">
          <span class="group-caret">${isCollapsed ? "▶" : "▼"}</span>
          <span class="group-title">${groupKey}</span>
          <span class="group-count">${groups[groupName].length}</span>
        </button>
      </td></tr>`;

      groups[groupName].forEach((assigneeKey) => {
        const meta = memberMeta[assigneeKey] || { capacity: 1, role: "", team: "", name: assigneeLabelFromKey(assigneeKey) };
        const load = loadByAssignee.get(assigneeKey) || 0;
        const ratio = meta.capacity ? load / meta.capacity : 0;
        const tint =
          ratio > 1
            ? "rgba(219, 35, 11, 0.12)"
            : ratio >= 0.8
              ? "rgba(130, 154, 177, 0.12)"
              : "rgba(0, 58, 114, 0.06)";
        const badgeClass = ratio > 1 ? "over" : ratio >= 0.8 ? "warn" : "ok";
        const metaLine = [meta.role].filter(Boolean).join(" • ");
        html += `<tr class="planning-row${isCollapsed ? " hidden" : ""}" data-group="${groupKey}">
          <td>
            <div class="assignee-cell" style="background:${tint};">
              <div class="assignee-header">
                <div class="assignee-name">${meta.name}</div>
                <button type="button" class="row-add" data-assignee="${assigneeKey}" title="Add allocation">+</button>
              </div>
              <div class="assignee-meta">
                <span class="capacity-badge ${badgeClass}">${formatFte(load)} / ${formatFte(meta.capacity)} FTE-mo</span>
                ${metaLine ? `<span class="meta-divider">•</span>${metaLine}` : ""}
              </div>
            </div>
          </td>`;

        months.forEach((m) => {
          const cellAllocs = filtered.filter(
            (a) => assigneeKeyFromAlloc(a) === assigneeKey && allocationMonthStart(a) === m.key
          );
          const cellHtml = cellAllocs
            .map((a) => {
              const allocFte = allocationFteMonths(a);
              const widthPct = Math.max(16, Math.min(100, (allocFte / Math.max(meta.capacity || 1, 0.1)) * 100));
              const label = allocationLabel(a);
              const typeLabel =
                a.work_item_type === "project"
                  ? "Proj"
                  : a.work_item_type === "solution"
                    ? "Sol"
                    : "Task";
              return `<div class="alloc-chip" data-alloc-id="${a.allocation_id}" style="flex: 0 0 ${widthPct}%; max-width:${widthPct}%;" title="${label} • ${formatFte(allocFte)} FTE-mo">
                <div class="chip-text">
                  <div class="chip-title">${label}</div>
                  <div class="chip-meta">${typeLabel} • ${formatFte(allocFte)} FTE-mo</div>
                </div>
                <button type="button" class="chip-delete" data-alloc-id="${a.allocation_id}" aria-label="Delete allocation">×</button>
              </div>`;
            })
            .join("");
          html += `<td><div class="alloc-cell">${cellHtml || ""}</div></td>`;
        });
        html += "</tr>";
      });
    });

  html += "</tbody></table></div>";

  els.planningBoard.innerHTML = `
    <div class="planning-cycle">
      <div class="cycle-label">Planning Cycle <span class="pill">${cycleLabel}</span></div>
      ${html}
    </div>
  `;

  renderPlanningWindowSummary();
  renderPlanningRoster();
}
