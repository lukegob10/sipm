export const DRAG_KIND_TASK = "task";
export const DRAG_KIND_PROJECT = "project";
export const DRAG_KIND_SOLUTION = "solution";
export const DRAG_KIND_PERSON = "person";
export const UNASSIGNED_TEAM_ID = "__unassigned__";
export const STORAGE_KEY_PREFIX = "sipm-planning-ui-v1";
export const FLASH_DURATION_MS = 2200;
export const VALID_EFFORT_FILTERS = new Set(["all", "small", "medium", "large"]);
export const VALID_TOP_PANELS = new Set(["", "filters", "create", "guide", "tools"]);

export function currentMonthToken() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function isValidMonthToken(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}$/.test(raw)) return false;
  const month = Number(raw.slice(5, 7));
  return Number.isInteger(month) && month >= 1 && month <= 12;
}

export function defaultBoardData() {
  return {
    teams: [],
    people: [],
    projects: [],
    solutions: [],
    tasks: [],
    allocations: [],
  };
}

export function defaultDrafts() {
  return {
    teamName: "",
    personName: "",
    personTeamId: "",
    personCapacity: "1.00",
    taskTitle: "",
    taskFte: "0.25",
  };
}

export function defaultDetailDraft() {
  return {
    workItemType: "",
    workItemId: "",
    taskId: "",
    title: "",
    fte: "0.25",
    assignmentTarget: "",
  };
}

export const boardState = {
  bound: false,
  ctx: null,
  spaceId: "",
  loaded: false,
  loading: false,
  pendingLoadOptions: null,
  error: "",
  month: currentMonthToken(),
  search: "",
  personSearch: "",
  effortFilter: "all",
  teamFilter: "all",
  selectedWorkItemType: "",
  selectedWorkItemId: "",
  selectedTaskId: "",
  notice: { message: "", tone: "info" },
  undoStack: [],
  flashItems: [],
  flashTimer: 0,
  focusReturnTaskId: "",
  topPanel: "",
  drafts: defaultDrafts(),
  detailDraft: defaultDetailDraft(),
  dragItem: null,
  data: defaultBoardData(),
};

let rerenderPlanningFn = null;

export function setPlanningRerender(fn) {
  rerenderPlanningFn = typeof fn === "function" ? fn : null;
}

export function rerenderPlanning() {
  if (typeof rerenderPlanningFn === "function") rerenderPlanningFn();
}
