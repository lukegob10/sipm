import { describe, expect, it, vi } from "vitest";

import { createGanttRouteController } from "../../js/routes/gantt/interactions.js";

function harness(window) {
  document.body.innerHTML = '<input type="date" id="from"><input type="date" id="to">';
  const state = {};
  const els = { ganttFrom: document.getElementById("from"), ganttTo: document.getElementById("to") };
  const writeStoredJson = vi.fn();
  const controller = createGanttRouteController({
    state, els, ganttViewStateKey: "gantt", writeStoredJson,
    readStoredJsonState: () => ({ value: { window, collapsed: [] }, recovered: false }),
    activeSpaceScopedStorageKey: (key) => key, renderGantt: vi.fn(),
  });
  controller.bindGanttRouteControls();
  return { state, els, controller, writeStoredJson };
}

describe("Gantt date controls", () => {
  it.each([
    [{ from: "0001-01-01", to: "0001-12-31" }],
    [{ from: "0004-02-28", to: "0004-03-01" }],
    [{ from: "0099-12-31", to: "0100-01-01" }],
    [{ from: "9999-01-01", to: "9999-12-31" }],
  ])("restores a valid date-only window %j", (window) => {
    const { state, els, controller, writeStoredJson } = harness(window);
    controller.restoreGanttViewState();
    expect(state.ganttWindow).toEqual(window);
    expect(els.ganttFrom.value).toBe(window.from);
    expect(els.ganttTo.value).toBe(window.to);
    expect(writeStoredJson).not.toHaveBeenCalled();
  });

  it.each([
    [{ from: "0000-01-01", to: "0001-01-01" }],
    [{ from: "0001-02-29", to: "0001-03-01" }],
    [{ from: "10000-01-01", to: "10000-12-31" }],
    [{ from: "0099-12-31", to: "0099-01-01" }],
  ])("recovers from an invalid stored range %j", (window) => {
    const { state, controller, writeStoredJson } = harness(window);
    controller.restoreGanttViewState();
    expect(state.ganttWindow).not.toEqual(window);
    expect(writeStoredJson).toHaveBeenCalledOnce();
  });
});
