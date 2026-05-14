import { describe, expect, it } from "vitest";

import { buildProjectPayload } from "../../js/entities/projects.js";
import { buildSolutionPayload } from "../../js/entities/solutions.js";
import { buildSubcomponentPayload } from "../../js/entities/subcomponents.js";

function formData(values) {
  const data = new FormData();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) data.set(key, value);
  });
  return data;
}

describe("entity payload builders", () => {
  it("normalizes project identifiers and nullable text fields", () => {
    const payload = buildProjectPayload(formData({
      project_name: "  Project Alpha  ",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: "   ",
      sponsor: "  Sponsor Name  ",
      sponsor_user_soeid: " tu12345 ",
      strategic_objective: "",
      priority: "2",
    }));

    expect(payload).toEqual({
      project_name: "Project Alpha",
      status: "active",
      description: " Keep spacing in long text ",
      success_criteria: null,
      sponsor: "Sponsor Name",
      sponsor_user_soeid: "tu12345",
      strategic_objective: null,
      priority: 2,
    });
  });

  it("builds solution payloads without unsupported FTE aliases or display-name SOEID fallback", () => {
    const payload = buildSolutionPayload(
      formData({
        solution_name: "  Solution One  ",
        github_repo_url: " https://github.com/org/repo ",
        version: " 1.0.0 ",
        status: "active",
        priority: "1",
        owner: "  Owner Name  ",
        owner_user_soeid: " on12345 ",
        assignee: "Assignee Display",
        assignee_user_soeid: "",
        capacity_hours: "0.5",
        rag_status: "amber",
      }),
      { hoursFromFteInput: (value) => Number(value) * 160 }
    );

    expect(payload.solution_name).toBe("Solution One");
    expect(payload.github_repo_url).toBe("https://github.com/org/repo");
    expect(payload.version).toBe("1.0.0");
    expect(payload.owner).toBe("Owner Name");
    expect(payload.owner_user_soeid).toBe("on12345");
    expect(payload.assignee).toBe("Assignee Display");
    expect(payload.assignee_user_soeid).toBeNull();
    expect(payload.capacity_hours).toBe(80);
    expect(payload).not.toHaveProperty("capacity_fte_months");
  });

  it("builds subcomponent payloads with repo trimming and blocked-note consistency", () => {
    const users = new Map([["eng123", { display_name: "Engineer One" }]]);
    const commonDeps = {
      findUserBySoeid: (soeid) => users.get(soeid),
      hoursFromFteInput: (value) => Number(value || 0) * 160,
      hoursFromNullableFteInput: (value) => (value ? Number(value) * 160 : null),
    };

    const blocked = buildSubcomponentPayload(
      formData({
        subcomponent_name: "  Task One  ",
        github_repo_url: " https://github.com/org/task ",
        status: "in_progress",
        priority: "2",
        assignee: " eng123 ",
        estimate_hours: "0.25",
        blocked: "on",
        blocker_note: " Waiting on access ",
        done_criteria: " Ship it ",
        capacity_hours: "0.5",
      }),
      commonDeps
    );

    expect(blocked.subcomponent_name).toBe("Task One");
    expect(blocked.github_repo_url).toBe("https://github.com/org/task");
    expect(blocked.assignee).toBe("Engineer One");
    expect(blocked.assignee_user_soeid).toBe("eng123");
    expect(blocked.blocker_note).toBe("Waiting on access");
    expect(blocked.estimate_hours).toBe(40);
    expect(blocked.capacity_hours).toBe(80);
    expect(blocked).not.toHaveProperty("estimate_fte_months");
    expect(blocked).not.toHaveProperty("capacity_fte_months");

    const unblocked = buildSubcomponentPayload(
      formData({
        subcomponent_name: "Task One",
        status: "in_progress",
        blocker_note: "Should not persist",
      }),
      commonDeps
    );
    expect(unblocked.blocked).toBe(false);
    expect(unblocked.blocker_note).toBeNull();
  });
});
