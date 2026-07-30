import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  bindSharedActions,
  renderSharedActionNotice,
  renderSharedActions,
} from "../../js/routes/my-work/shared-actions.js";

function record(overrides = {}) {
  return {
    task: {
      task_id: "task-1",
      task_name: "Focused task",
      status: "to_do",
      blocked: false,
      ...overrides,
    },
    needs_attention: false,
  };
}

function context() {
  document.body.innerHTML = '<div id="my-work-root"></div>';
  return {
    state: { myWork: {} },
    els: { myWorkRoot: document.getElementById("my-work-root") },
    api: vi.fn(),
    escapeHtml: (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;"),
    renderExternalRepoLink: vi.fn((url, options) => (
      url.startsWith("https://")
        ? `<a href="${url}" target="_blank" rel="noopener noreferrer" class="${options.className}">${options.label}</a>`
        : ""
    )),
    setView: vi.fn(),
  };
}

function renderAndBind(ctx, selectedRecord, options = {}) {
  const rerender = () => {
    ctx.els.myWorkRoot.innerHTML = `${renderSharedActionNotice(ctx)}${renderSharedActions(ctx, selectedRecord)}`;
    bindSharedActions(ctx, {
      record: selectedRecord,
      refresh: rerender,
      ...options,
    });
  };
  rerender();
  return rerender;
}

describe("My Work shared actions", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("renders only valid mutations for each shared task state", () => {
    const ctx = context();

    ctx.els.myWorkRoot.innerHTML = renderSharedActions(ctx, record());
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]')).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="show-block"]')).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="complete"]')).toBeNull();

    ctx.els.myWorkRoot.innerHTML = renderSharedActions(ctx, record({ status: "in_progress" }));
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="complete"]')).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]')).toBeNull();

    ctx.els.myWorkRoot.innerHTML = renderSharedActions(ctx, record({ status: "in_progress", blocked: true }));
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="unblock"]')).toBeTruthy();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="complete"]')).toBeNull();
    expect(ctx.els.myWorkRoot.querySelector('[data-my-work-action="show-block"]')).toBeNull();

    ctx.els.myWorkRoot.innerHTML = renderSharedActions(ctx, record({ status: "complete" }));
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-action]")).toBeNull();
    expect(ctx.els.myWorkRoot.querySelector("[data-my-work-open-tasks]")).toBeTruthy();
  });

  it("starts work through the shared task PATCH and merges the returned task", async () => {
    const ctx = context();
    const selectedRecord = record();
    ctx.api.mockResolvedValue({ ...selectedRecord.task, status: "in_progress" });
    renderAndBind(ctx, selectedRecord);

    ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').click();

    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith("/tasks/task-1", {
        method: "PATCH",
        body: JSON.stringify({ status: "in_progress" }),
      });
    });
    await vi.waitFor(() => expect(selectedRecord.task.status).toBe("in_progress"));
    expect(renderSharedActionNotice(ctx)).toContain("Task started.");
  });

  it("requires blocker context and sends a trimmed shared block payload", async () => {
    const ctx = context();
    const selectedRecord = record({ status: "in_progress" });
    ctx.api.mockImplementation(async (_path, options) => ({
      ...selectedRecord.task,
      ...JSON.parse(options.body),
      is_overdue: false,
    }));
    renderAndBind(ctx, selectedRecord);

    ctx.els.myWorkRoot.querySelector('[data-my-work-action="show-block"]').click();
    const form = ctx.els.myWorkRoot.querySelector("[data-my-work-block-form]");
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(ctx.api).not.toHaveBeenCalled();
    expect(form.querySelector("[data-my-work-block-feedback]").textContent).toContain("Add blocker context");

    const input = form.querySelector('[name="blocker_note"]');
    input.value = "  Waiting for production access  ";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => {
      expect(ctx.api).toHaveBeenCalledWith("/tasks/task-1", {
        method: "PATCH",
        body: JSON.stringify({
          blocked: true,
          blocker_note: "Waiting for production access",
        }),
      });
    });
    await vi.waitFor(() => expect(selectedRecord.needs_attention).toBe(true));
  });

  it.each([
    ["unblock", { status: "in_progress", blocked: true }, { blocked: false }, "Task unblocked."],
    ["complete", { status: "in_progress", blocked: false }, { status: "complete" }, "Task marked complete."],
  ])("runs the %s transition and retains a route-level result notice", async (action, taskFields, payload, message) => {
    const ctx = context();
    const selectedRecord = record(taskFields);
    const onTaskUpdated = vi.fn();
    ctx.api.mockResolvedValue({ ...selectedRecord.task, ...payload });
    renderAndBind(ctx, selectedRecord, { onTaskUpdated });

    ctx.els.myWorkRoot.querySelector(`[data-my-work-action="${action}"]`).click();

    await vi.waitFor(() => expect(ctx.api).toHaveBeenCalledWith("/tasks/task-1", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }));
    await vi.waitFor(() => expect(onTaskUpdated).toHaveBeenCalled());
    expect(renderSharedActionNotice(ctx)).toContain(message);
  });

  it("uses the safe repository renderer and opens the exact task in Tasks", () => {
    const ctx = context();
    const selectedRecord = record({
      effective_github_repo_url: "https://github.com/example/sipm",
    });
    const openTaskInWorkbench = vi.fn();
    renderAndBind(ctx, selectedRecord, { openTaskInWorkbench });

    const repoLink = ctx.els.myWorkRoot.querySelector(".my-work-action-link");
    expect(repoLink?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(ctx.renderExternalRepoLink).toHaveBeenCalledWith(
      "https://github.com/example/sipm",
      expect.objectContaining({ label: "Open Repository" }),
    );

    ctx.els.myWorkRoot.querySelector("[data-my-work-open-tasks]").click();
    expect(openTaskInWorkbench).toHaveBeenCalledWith(selectedRecord.task);
    expect(ctx.setView).not.toHaveBeenCalled();
  });

  it("surfaces API errors and leaves the task unchanged", async () => {
    const ctx = context();
    const selectedRecord = record();
    ctx.api.mockRejectedValue(new Error("Task is no longer assigned"));
    renderAndBind(ctx, selectedRecord);

    ctx.els.myWorkRoot.querySelector('[data-my-work-action="start"]').click();

    await vi.waitFor(() => {
      expect(renderSharedActionNotice(ctx)).toContain("Task is no longer assigned");
    });
    expect(selectedRecord.task.status).toBe("to_do");
    expect(ctx.state.myWork.sharedActions.pendingTaskId).toBe("");
  });
});
