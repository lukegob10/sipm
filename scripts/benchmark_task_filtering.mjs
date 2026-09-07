// Compare complete task filtering against a recorded pre-change revision.
// Usage: node scripts/benchmark_task_filtering.mjs <baseline-git-revision>
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cpus, platform, release } from "node:os";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

import { tasksWorkbenchRows } from "../src/main/ui/js/routes/tasks-workbench/filters.js";

const baselineRef = process.argv[2];
if (!baselineRef) throw new Error("Usage: node scripts/benchmark_task_filtering.mjs <baseline-git-revision>");
const root = fileURLToPath(new URL("../", import.meta.url));
const git = (...args) => execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();
const baselineRevision = git("rev-parse", "--verify", `${baselineRef}^{commit}`);
const modulePath = "src/main/ui/js/routes/tasks-workbench/filters.js";
const sortUrl = new URL("../src/main/ui/js/utils/task-sort.js", import.meta.url).href;
const baselineSource = git("show", `${baselineRevision}:${modulePath}`)
  .replace('"../../utils/task-sort.js"', JSON.stringify(sortUrl));
const { tasksWorkbenchRows: baselineRows } = await import(
  `data:text/javascript;base64,${Buffer.from(baselineSource).toString("base64")}`
);

function createContext(size, search) {
  const projects = Array.from({ length: Math.ceil(size / 20) }, (_, index) => ({
    project_id: `project-${index}`, project_name: `Project ${index}`,
  }));
  const solutions = Array.from({ length: Math.ceil(size / 5) }, (_, index) => ({
    solution_id: `solution-${index}`, solution_name: `Solution ${index}`,
  }));
  return {
    state: {
      projects,
      solutions,
      tasks: Array.from({ length: size }, (_, index) => ({
        task_id: `task-${index}`,
        task_name: `Task ${size - index}`,
        project_id: projects[index % projects.length].project_id,
        solution_id: solutions[index % solutions.length].solution_id,
        assignee: index % 7 ? `User ${index % 40}` : "",
        assignee_user_soeid: index % 7 ? `user-${index % 40}` : "",
        status: index % 10 ? "in_progress" : "complete",
        priority: index % 5 + 1,
        due_date: index % 3 ? `2026-09-${String(index % 28 + 1).padStart(2, "0")}` : "",
        description: `${index % 4 ? "Routine" : "Release"} delivery work. ${"Representative task description. ".repeat(8)}`,
        acceptance_criteria: "Reviewed by the delivery owner and checked in the test workspace.",
        done_criteria: "All acceptance checks pass.",
        is_overdue: index % 11 === 0,
        is_due_soon: index % 3 === 0,
        is_stale: index % 13 === 0,
        blocked: index % 17 === 0,
        urgency_score: index % 101,
      })),
      user: { display_name: "User 1", soeid: "user-1" },
      tasksWorkbench: { filters: { search }, preset: "all", sort: "default", visibleIds: [] },
    },
    // Match the application's server-provided actionability branch.
    deriveTaskActionability: (task) => ({
      is_overdue: !!task.is_overdue,
      is_due_soon: !!task.is_due_soon,
      is_stale: !!task.is_stale,
      urgency_score: Number(task.urgency_score || 0),
    }),
    normalize: (value) => String(value || "").trim().toLowerCase(),
    isCompletedTaskStatus: (status) => ["complete", "abandoned"].includes(status),
    numberOr: (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback,
    showCompletedOperationalWork: () => false,
    requestsClosedStatuses: (status) => ["complete", "abandoned"].includes(status),
  };
}

function countParentIdReads(run, size) {
  const ctx = createContext(size, "");
  let count = 0;
  for (const [rows, key] of [[ctx.state.projects, "project_id"], [ctx.state.solutions, "solution_id"]]) {
    for (const row of rows) {
      const id = row[key];
      Object.defineProperty(row, key, { get: () => { count += 1; return id; } });
    }
  }
  run(ctx);
  return count;
}

function measure(run, ctx) {
  const start = performance.now();
  run(ctx);
  return performance.now() - start;
}

function summarize(samples) {
  const sorted = [...samples].sort((a, b) => a - b);
  const percentile = (p) => Number(sorted[Math.ceil(sorted.length * p) - 1].toFixed(3));
  return {
    p50Ms: percentile(0.5), p75Ms: percentile(0.75), p95Ms: percentile(0.95),
    samplesMs: samples.map((sample) => Number(sample.toFixed(3))),
  };
}

const report = {
  baselineRevision,
  candidateRevision: git("rev-parse", "HEAD"),
  candidateSource: "working tree",
  node: process.version,
  os: `${platform()} ${release()}`,
  cpu: cpus()[0]?.model,
  measuredAt: new Date().toISOString(),
  iterations: 30,
  warmups: 5,
  note: "Synthetic CPU-only full filtering; excludes network and DOM. Alternating before/after order; timings are diagnostic, not assertions.",
  results: [],
};
for (const size of [100, 1000, 10000]) {
  for (const search of ["", "release"]) {
    const beforeContext = createContext(size, search);
    const afterContext = createContext(size, search);
    const expected = baselineRows(beforeContext);
    assert.deepEqual(tasksWorkbenchRows(afterContext), expected);
    assert.deepEqual(afterContext.state.tasksWorkbench.visibleIds, beforeContext.state.tasksWorkbench.visibleIds);
    for (let index = 0; index < report.warmups; index += 1) {
      baselineRows(beforeContext);
      tasksWorkbenchRows(afterContext);
    }
    const before = [];
    const after = [];
    for (let index = 0; index < report.iterations; index += 1) {
      if (index % 2 === 0) {
        before.push(measure(baselineRows, beforeContext));
        after.push(measure(tasksWorkbenchRows, afterContext));
      } else {
        after.push(measure(tasksWorkbenchRows, afterContext));
        before.push(measure(baselineRows, beforeContext));
      }
    }
    report.results.push({
      tasks: size,
      projects: beforeContext.state.projects.length,
      solutions: beforeContext.state.solutions.length,
      scenario: search ? "search" : "all",
      visible: expected.visibleRows.length,
      before: summarize(before),
      after: summarize(after),
    });
  }
}
// Instrument only after timing so accessors do not affect measured code optimization.
for (const size of [100, 1000, 10000]) {
  const parentIdReads = {
    before: countParentIdReads(baselineRows, size),
    after: countParentIdReads(tasksWorkbenchRows, size),
  };
  for (const result of report.results.filter((result) => result.tasks === size)) result.parentIdReads = parentIdReads;
}
console.log(JSON.stringify(report, null, 2));
