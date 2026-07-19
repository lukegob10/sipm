import { describe, expect, it } from "vitest";

import { sortTasksByName } from "../../js/utils/task-sort.js";

describe("solution task sorting", () => {
  const tasks = [
    { task_id: "3", task_name: "Task 10" },
    { task_id: "1", task_name: "alpha" },
    { task_id: "2", task_name: "Task 2" },
  ];

  it("sorts task names A–Z using natural, case-insensitive order", () => {
    expect(sortTasksByName(tasks, "name-asc").map((task) => task.task_id)).toEqual(["1", "2", "3"]);
  });

  it("sorts task names Z–A without mutating the source list", () => {
    expect(sortTasksByName(tasks, "name-desc").map((task) => task.task_id)).toEqual(["3", "2", "1"]);
    expect(tasks.map((task) => task.task_id)).toEqual(["3", "1", "2"]);
  });
});
