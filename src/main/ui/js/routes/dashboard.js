export function renderDashboard(ctx) {
  const { state, els, formatStatus } = ctx;
  const solutions = state.solutions || [];
  const users = state.users || [];
  const projects = state.projects || [];
  const projectNameById = new Map(projects.map((project) => [project.project_id, project.project_name || "—"]));
  const projectName = (projectId) => projectNameById.get(projectId) || "—";
  const now = new Date();
  const HOURS_PER_FTE_MONTH = 160;
  const HOURS_PER_FTE_CAPACITY = 40;

  const solutionFteValue = (solution) => {
    if (!solution) return "0.00";
    const byFte = Number(solution.capacity_fte_months);
    const byHours = Number(solution.capacity_hours);
    const fte = Number.isFinite(byFte)
      ? byFte
      : Number.isFinite(byHours)
        ? byHours / HOURS_PER_FTE_MONTH
        : 0;
    return fte.toFixed(2);
  };

  const userCapacityFteValue = (user) => {
    if (!user) return 0;
    const byFte = Number(user.capacity_fte_month);
    const byHours = Number(user.capacity_hours);
    if (Number.isFinite(byFte)) return Math.max(byFte, 0);
    if (Number.isFinite(byHours)) return Math.max(byHours, 0) / HOURS_PER_FTE_CAPACITY;
    return 1;
  };

  const quarterRange = (date) => {
    const year = date.getFullYear();
    const startMonth = Math.floor(date.getMonth() / 3) * 3;
    const start = new Date(year, startMonth, 1);
    const end = new Date(year, startMonth + 3, 0, 23, 59, 59, 999);
    return { start, end };
  };
  const currentQuarter = quarterRange(now);
  const lastQuarterEnd = new Date(currentQuarter.start.getTime() - 1);
  const lastQuarter = quarterRange(lastQuarterEnd);

  const totalSpaceCapacity = users
    .filter((user) => user && user.is_active !== false)
    .reduce((sum, user) => sum + userCapacityFteValue(user), 0);
  const allocatedCapacity = solutions
    .filter((solution) => {
      const status = String(solution?.status || "").toLowerCase();
      return status !== "complete" && status !== "abandoned";
    })
    .reduce((sum, solution) => sum + Number(solutionFteValue(solution)), 0);
  const allocationPct = totalSpaceCapacity > 0 ? (allocatedCapacity / totalSpaceCapacity) * 100 : 0;

  if (els.dashboardSpaceCapacity) {
    els.dashboardSpaceCapacity.innerHTML = `
      <div class="dashboard-capacity-lines">
        <div class="dashboard-capacity-line"><span>Total Space Capacity</span><strong>${totalSpaceCapacity.toFixed(2)} FTE-mo</strong></div>
        <div class="dashboard-capacity-line"><span>Allocated</span><strong>${allocatedCapacity.toFixed(2)} FTE-mo</strong></div>
        <div class="dashboard-capacity-line"><span>Allocation</span><strong>${allocationPct.toFixed(1)}%</strong></div>
      </div>
    `;
  }

  if (els.dashboardTopProjects) {
    if (!solutions.length) {
      els.dashboardTopProjects.innerHTML = "<p class='muted'>No solutions</p>";
    } else {
      const rows = solutions
        .slice()
        .sort((a, b) => {
          const projA = projectName(a.project_id);
          const projB = projectName(b.project_id);
          if (projA !== projB) return projA.localeCompare(projB);
          return (a.solution_name || "").localeCompare(b.solution_name || "");
        })
        .map(
          (s) =>
            `<tr><td>${s.solution_name || "—"}</td><td>${projectName(s.project_id)}</td><td>${solutionFteValue(s)}</td><td>${s.owner || "—"}</td><td>${s.due_date || "—"}</td><td>${formatStatus(s.status)}</td></tr>`
        )
        .join("");
      els.dashboardTopProjects.innerHTML = `
        <div class="table">
          <table>
            <thead>
              <tr><th>Solution</th><th>Project</th><th>FTE</th><th>Owner</th><th>Due</th><th>Status</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }
  }

  const completedLastQuarter = solutions.filter((s) => {
    if (s.status !== "complete") return false;
    const done = s.completed_at ? new Date(s.completed_at) : s.updated_at ? new Date(s.updated_at) : null;
    if (!done) return false;
    return done >= lastQuarter.start && done <= lastQuarter.end;
  });
  if (els.dashboardCompletedQuarter) {
    if (!completedLastQuarter.length) {
      els.dashboardCompletedQuarter.innerHTML = "<h3>Completed (Last Quarter)</h3><p class='muted'>No completions</p>";
    } else {
      const rows = completedLastQuarter
        .sort((a, b) => {
          const projA = projectName(a.project_id);
          const projB = projectName(b.project_id);
          if (projA !== projB) return projA.localeCompare(projB);
          return (a.solution_name || "").localeCompare(b.solution_name || "");
        })
        .slice(0, 10)
        .map((s) => {
          const completed = s.completed_at ? new Date(s.completed_at).toLocaleDateString() : "—";
          return `<tr><td>${projectName(s.project_id)}</td><td>${s.solution_name || "—"}</td><td>${solutionFteValue(s)}</td><td>${s.owner || "—"}</td><td>${completed}</td></tr>`;
        })
        .join("");
      els.dashboardCompletedQuarter.innerHTML = `
        <h3>Completed (Last Quarter)</h3>
        <div class="table"><table>
          <thead><tr><th>Project</th><th>Solution</th><th>FTE</th><th>Owner</th><th>Completed</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>`;
    }
  }

  const upcomingCurrentQuarter = solutions.filter((s) => {
    if (!s.due_date) return false;
    if (s.status === "complete" || s.status === "abandoned") return false;
    const due = new Date(s.due_date);
    return due >= currentQuarter.start && due <= currentQuarter.end;
  });
  if (els.dashboardUpcomingQuarter) {
    if (!upcomingCurrentQuarter.length) {
      els.dashboardUpcomingQuarter.innerHTML = "<h3>Upcoming (Current Quarter)</h3><p class='muted'>No upcoming due dates</p>";
    } else {
      const rows = upcomingCurrentQuarter
        .sort((a, b) => {
          const projA = projectName(a.project_id);
          const projB = projectName(b.project_id);
          if (projA !== projB) return projA.localeCompare(projB);
          return (a.solution_name || "").localeCompare(b.solution_name || "");
        })
        .slice(0, 10)
        .map((s) => {
          return `<tr><td>${projectName(s.project_id)}</td><td>${s.solution_name || "—"}</td><td>${solutionFteValue(s)}</td><td>${s.due_date}</td><td>${s.owner || "—"}</td></tr>`;
        })
        .join("");
      els.dashboardUpcomingQuarter.innerHTML = `
        <h3>Upcoming (Current Quarter)</h3>
        <div class="table"><table>
          <thead><tr><th>Project</th><th>Solution</th><th>FTE</th><th>Due</th><th>Owner</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>`;
    }
  }

  const backlogSolutions = solutions.filter((s) => {
    if (s.status === "complete" || s.status === "abandoned") return false;
    if (!s.due_date) return true;
    const due = new Date(s.due_date);
    return due > currentQuarter.end;
  });
  if (els.dashboardBacklog) {
    if (!backlogSolutions.length) {
      els.dashboardBacklog.innerHTML = "<h3>Backlog</h3><p class='muted'>No backlog items</p>";
    } else {
      const rows = backlogSolutions
        .sort((a, b) => {
          const projA = projectName(a.project_id);
          const projB = projectName(b.project_id);
          if (projA !== projB) return projA.localeCompare(projB);
          return (a.solution_name || "").localeCompare(b.solution_name || "");
        })
        .slice(0, 12)
        .map((s) => {
          return `<tr><td>${projectName(s.project_id)}</td><td>${s.solution_name || "—"}</td><td>${solutionFteValue(s)}</td><td>${s.owner || "—"}</td><td>${s.due_date || "—"}</td></tr>`;
        })
        .join("");
      els.dashboardBacklog.innerHTML = `
        <h3>Backlog</h3>
        <div class="table"><table>
          <thead><tr><th>Project</th><th>Solution</th><th>FTE</th><th>Owner</th><th>Due</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>`;
    }
  }
}
