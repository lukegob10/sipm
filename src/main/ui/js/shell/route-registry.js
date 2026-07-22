const ROUTE_ENTRIES = [
  ["my-work", {
    section: "Personal",
    label: "My Work",
    title: "My Work",
    data: ["users"],
    prefetch: "tasks-workbench",
  }],
  ["master", {
    section: "Work",
    label: "Deliverables",
    title: "Deliverables",
    data: ["phases", "programs", "projects", "solutions", "tasks"],
    prefetch: "dashboard",
  }],
  ["tasks-workbench", {
    section: "Work",
    label: "Tasks",
    title: "Tasks",
    data: ["programs", "projects", "solutions", "tasks", "users"],
    prefetch: "team-capacity",
  }],
  ["repositories", {
    section: "Work",
    label: "Repositories",
    title: "Repositories",
    data: [],
    prefetch: "tasks-workbench",
  }],
  ["pm-dashboard", {
    section: "Insight",
    label: "PM Command Center",
    title: "PM Command Center",
    data: ["programs", "projects", "solutions", "tasks", "users"],
    prefetch: "kanban",
  }],
  ["dashboard", {
    section: "Insight",
    label: "Dashboard",
    title: "Dashboard",
    data: ["programs", "projects", "solutions", "users"],
    prefetch: "pm-dashboard",
  }],
  ["program-dashboard", {
    section: "Insight",
    label: "Program Dashboard",
    title: "Program Dashboard",
    data: ["phases", "programs", "projects", "solutions"],
    prefetch: "tasks-workbench",
  }],
  ["kanban", {
    section: "Insight",
    label: "Kanban",
    title: "Kanban",
    data: ["phases", "programs", "projects", "solutions"],
    prefetch: "team-capacity",
  }],
  ["calendar", {
    section: "Insight",
    label: "Calendar",
    title: "Calendar",
    data: ["programs", "projects", "solutions"],
    prefetch: "team-capacity",
  }],
  ["gantt", {
    section: "Insight",
    label: "Roadmap",
    title: "Roadmap",
    data: ["programs", "projects", "solutions", "tasks"],
    prefetch: "tasks-workbench",
  }],
  ["spaces", {
    section: "Admin",
    label: "Spaces",
    title: "Space Governance",
    data: ["users"],
    prefetch: "access",
  }],
  ["team-capacity", {
    section: "Admin",
    label: "Team Capacity",
    title: "Team Capacity",
    data: ["users"],
    prefetch: "spaces",
  }],
  ["analytics", {
    section: "Admin",
    label: "Usage Analytics",
    title: "Usage Analytics",
    data: [],
    prefetch: "master",
  }],
  ["access", {
    section: "Admin",
    label: "Platform Access",
    title: "Platform Access",
    data: ["users"],
    prefetch: "analytics",
    domView: "spaces",
    navView: "spaces",
  }],
];

export const ROUTES = Object.freeze(Object.fromEntries(
  ROUTE_ENTRIES.map(([id, definition]) => [id, Object.freeze({ id, domView: id, navView: id, ...definition })])
));

export const KNOWN_VIEWS = Object.freeze(ROUTE_ENTRIES.map(([id]) => id));

export const VIEW_DATA_REQUIREMENTS = Object.freeze(Object.fromEntries(
  ROUTE_ENTRIES.map(([id, definition]) => [id, Object.freeze([...(definition.data || [])])])
));

export const VIEW_PREFETCH_TARGET = Object.freeze(Object.fromEntries(
  ROUTE_ENTRIES.map(([id, definition]) => [id, definition.prefetch])
));

export function normalizeRouteView(view) {
  const candidate = String(view || "").trim().toLowerCase();
  if (candidate === "settings") return "team-capacity";
  return Object.hasOwn(ROUTES, candidate) ? candidate : "master";
}

export function routeDefinition(view) {
  return ROUTES[normalizeRouteView(view)];
}
