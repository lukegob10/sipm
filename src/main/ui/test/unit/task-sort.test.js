import { describe, expect, it } from "vitest";

import { nextTaskNameSort, sortTasksByName } from "../../js/utils/task-sort.js";

describe("solution task sorting", () => {
  const tasks = [
    { task_id: "3", task_name: "Task 10" },
    { task_id: "1", task_name: "alpha" },
    { task_id: "2", task_name: "Task 2" },
  ];

  it("preserves the source order in the default state", () => {
    const result = sortTasksByName(tasks, "default");

    expect(result.map((task) => task.task_id)).toEqual(["3", "1", "2"]);
    expect(result).not.toBe(tasks);
  });

  it("sorts task names A–Z using natural, case-insensitive order", () => {
    expect(sortTasksByName(tasks, "name-asc").map((task) => task.task_id)).toEqual(["1", "2", "3"]);
  });

  it("sorts task names Z–A without mutating the source list", () => {
    expect(sortTasksByName(tasks, "name-desc").map((task) => task.task_id)).toEqual(["3", "2", "1"]);
    expect(tasks.map((task) => task.task_id)).toEqual(["3", "1", "2"]);
  });

  it("cycles normal, A–Z, Z–A, and back to normal", () => {
    expect(nextTaskNameSort("default")).toBe("name-asc");
    expect(nextTaskNameSort("name-asc")).toBe("name-desc");
    expect(nextTaskNameSort("name-desc")).toBe("default");
  });
});
