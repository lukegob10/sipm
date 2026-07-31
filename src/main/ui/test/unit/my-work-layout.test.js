import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderMyWork } from "../../js/routes/my-work.js";
import {
  DEFAULT_PLAN_WIDTH,
  MAX_PLAN_WIDTH,
  MIN_PLAN_WIDTH,
  MY_WORK_LAYOUT_STORAGE_KEY,
  normalizeMyWorkPlanLayout,
  readStoredMyWorkPlanLayout,
} from "../../js/routes/my-work/layout.js";

function taskRecord() {
  return {
    task: {
      task_id: "task-1",
      task_name: "Keep the workspace flexible",
      status: "in_progress",
      priority: 1,
      description: "Preserve the task context while changing the Plan width.",
    },
    program_name: "Developer Experience",
    project_name: "Developer Mode",
    solution_name: "My Work",
    private_bucket: "today",
    private_sort_rank: 100,
  };
}

function context() {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  const records = [taskRecord()];
  return {
    state: {
      users: [],
      myWork: {
        records,
        loading: false,
        error: "",
        selectedTaskId: "task-1",
        search: "",
        repository: "",
      },
    },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    api: vi.fn(),
    escapeHtml: (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;"),
    formatStatus: (value) => String(value).replaceAll("_", " "),
    renderExternalRepoLink: (url, options) => `<a href="${url}">${options.label}</a>`,
    setView: vi.fn(),
    showCompletedOperationalWork: () => false,
  };
}

function dispatchPointer(target, type, { clientX, pointerId = 1 }) {
  const event = new MouseEvent(type, { bubbles: true, button: 0, clientX });
  Object.defineProperty(event, "pointerId", { value: pointerId });
  target.dispatchEvent(event);
}

describe("My Work Plan layout", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    window.localStorage.clear();
  });

  it("normalizes malformed and out-of-range stored layout preferences", () => {
    expect(normalizeMyWorkPlanLayout({ collapsed: "yes", width: -20 })).toEqual({
      collapsed: false,
      width: MIN_PLAN_WIDTH,
    });
    expect(normalizeMyWorkPlanLayout({ collapsed: true, width: 200 })).toEqual({
      collapsed: true,
      width: MAX_PLAN_WIDTH,
    });
    window.localStorage.setItem(MY_WORK_LAYOUT_STORAGE_KEY, "not-json");
    expect(readStoredMyWorkPlanLayout()).toEqual({ collapsed: false, width: DEFAULT_PLAN_WIDTH });
  });

  it("renders an accessible expanded Plan with direct size controls", () => {
    const ctx = context();
    renderMyWork(ctx);

    const layout = ctx.els.myWorkRoot.querySelector(".my-work-layout");
    const resizer = ctx.els.myWorkRoot.querySelector("[data-my-work-plan-resizer]");
    expect(layout.style.getPropertyValue("--my-work-plan-width")).toBe(`${DEFAULT_PLAN_WIDTH}%`);
    expect(resizer.getAttribute("role")).toBe("separator");
    expect(resizer.getAttribute("aria-valuenow")).toBe(String(DEFAULT_PLAN_WIDTH));
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-plan-size='smaller']")).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-plan-size='larger']")).toBeTruthy();
  });

  it("resizes from buttons and the keyboard, clamps the width, and persists it", () => {
    const ctx = context();
    renderMyWork(ctx);
    const root = ctx.els.myWorkRoot;
    const resizer = root.querySelector("[data-my-work-plan-resizer]");

    root.querySelector("[data-my-work-plan-size='smaller']").click();
    expect(resizer.getAttribute("aria-valuenow")).toBe(String(DEFAULT_PLAN_WIDTH - 4));

    resizer.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
    expect(resizer.getAttribute("aria-valuenow")).toBe(String(MAX_PLAN_WIDTH));
    expect(root.querySelector("[data-my-work-plan-size='larger']").disabled).toBe(true);
    expect(JSON.parse(window.localStorage.getItem(MY_WORK_LAYOUT_STORAGE_KEY))).toEqual({
      collapsed: false,
      width: MAX_PLAN_WIDTH,
    });
  });

  it("resizes by dragging the separator", () => {
    const ctx = context();
    renderMyWork(ctx);
    const root = ctx.els.myWorkRoot;
    const layout = root.querySelector(".my-work-layout");
    const resizer = root.querySelector("[data-my-work-plan-resizer]");
    layout.getBoundingClientRect = () => ({ left: 100, width: 1000 });

    dispatchPointer(resizer, "pointerdown", { clientX: 680 });
    dispatchPointer(resizer, "pointermove", { clientX: 700 });
    dispatchPointer(resizer, "pointerup", { clientX: 700 });

    expect(layout.style.getPropertyValue("--my-work-plan-width")).toBe("60%");
    expect(document.body.classList.contains("my-work-plan-is-resizing")).toBe(false);
    expect(JSON.parse(window.localStorage.getItem(MY_WORK_LAYOUT_STORAGE_KEY)).width).toBe(60);
  });

  it("collapses and restores the Plan without losing the selected task", () => {
    const ctx = context();
    renderMyWork(ctx);
    ctx.els.myWorkRoot.querySelector("[data-my-work-plan-toggle]").click();

    expect(ctx.els.myWorkRoot.querySelector(".my-work-layout").classList).toContain("is-plan-collapsed");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-plan-resizer]")).toBeNull();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-detail").textContent).toContain("Keep the workspace flexible");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-plan-toggle]").getAttribute("aria-expanded")).toBe("false");

    ctx.els.myWorkRoot.querySelector("[data-my-work-plan-toggle]").click();
    expect(ctx.els.myWorkRoot.querySelector(".my-work-layout").classList).not.toContain("is-plan-collapsed");
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-plan-resizer]")).toBeTruthy();
    expect(ctx.state.myWork.selectedTaskId).toBe("task-1");
  });
});
