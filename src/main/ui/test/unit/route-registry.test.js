import { describe, expect, it } from "vitest";

import {
  KNOWN_VIEWS,
  ROUTES,
  VIEW_DATA_REQUIREMENTS,
  normalizeRouteView,
  routeDefinition,
} from "../../js/shell/route-registry.js";

describe("route registry", () => {
  it("provides one complete metadata definition for every route", () => {
    expect(KNOWN_VIEWS).toHaveLength(14);
    for (const view of KNOWN_VIEWS) {
      expect(ROUTES[view]).toMatchObject({ id: view });
      expect(ROUTES[view].section).toMatch(/^(Personal|Work|Insight|Admin)$/);
      expect(ROUTES[view].label).toBeTruthy();
      expect(ROUTES[view].title).toBeTruthy();
      expect(VIEW_DATA_REQUIREMENTS[view]).toBeInstanceOf(Array);
    }
  });

  it("keeps aliases and public naming in one source of truth", () => {
    expect(normalizeRouteView("settings")).toBe("team-capacity");
    expect(routeDefinition("gantt")).toMatchObject({ label: "Roadmap", title: "Roadmap" });
    expect(routeDefinition("repositories")).toMatchObject({ section: "Work", label: "Repositories" });
    expect(routeDefinition("access")).toMatchObject({ domView: "spaces", navView: "spaces" });
  });
});
