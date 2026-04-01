import {
  UNASSIGNED_TEAM_ID,
  VALID_EFFORT_FILTERS,
  VALID_TOP_PANELS,
  STORAGE_KEY_PREFIX,
  boardState,
  currentMonthToken,
  defaultBoardData,
  defaultDetailDraft,
  defaultDrafts,
} from "./state.js";
import { clearFlashItems } from "./common.js";

export function storageKey(spaceId) {
  const scope = String(spaceId || "no-space").trim().toLowerCase() || "no-space";
  return `${STORAGE_KEY_PREFIX}:${scope}`;
}

export function readStoredState(spaceId) {
  try {
    const raw = window.localStorage.getItem(storageKey(spaceId));
    if (!raw) return { value: {}, recovered: false };
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return { value: parsed, recovered: false };
    return { value: {}, recovered: true };
  } catch {
    return { value: {}, recovered: true };
  }
}

export function persistViewState() {
  try {
    window.localStorage.setItem(
      storageKey(boardState.spaceId),
      JSON.stringify({
        month: boardState.month || currentMonthToken(),
        teamFilter: boardState.teamFilter || "all",
        effortFilter: boardState.effortFilter || "all",
        search: boardState.search || "",
        personSearch: boardState.personSearch || "",
        selectedTaskId: boardState.selectedTaskId || "",
        topPanel: boardState.topPanel || "",
      })
    );
  } catch {
    // Ignore persistence failures.
  }
}

export function restoreViewState(spaceId) {
  const { value: stored, recovered } = readStoredState(spaceId);
  boardState.month = isValidMonthToken(stored.month) ? String(stored.month) : currentMonthToken();
  boardState.teamFilter = String(stored.teamFilter || "all");
  boardState.effortFilter = String(stored.effortFilter || "all");
  boardState.search = String(stored.search || "");
  boardState.personSearch = String(stored.personSearch || "");
  boardState.selectedTaskId = String(stored.selectedTaskId || "");
  boardState.topPanel = String(stored.topPanel || "");
  if (recovered || !Object.keys(stored || {}).length) persistViewState();
}

export function normalizePersistedBoardFilters() {
  let changed = false;
  if (!isValidMonthToken(boardState.month)) {
    boardState.month = currentMonthToken();
    changed = true;
  }
  const validTeamIds = new Set((boardState.data.teams || []).map((team) => String(team?.id || "")).filter(Boolean));
  if (
    boardState.teamFilter === UNASSIGNED_TEAM_ID
    || (boardState.teamFilter !== "all" && !validTeamIds.has(String(boardState.teamFilter || "")))
  ) {
    boardState.teamFilter = "all";
    changed = true;
  }
  if (!VALID_EFFORT_FILTERS.has(String(boardState.effortFilter || "all"))) {
    boardState.effortFilter = "all";
    changed = true;
  }
  if (!VALID_TOP_PANELS.has(String(boardState.topPanel || ""))) {
    boardState.topPanel = "";
    changed = true;
  }
  if (changed) persistViewState();
}

export function resetBoardState(spaceId) {
  boardState.spaceId = spaceId || "";
  boardState.loaded = false;
  boardState.loading = false;
  boardState.error = "";
  boardState.personSearch = "";
  boardState.topPanel = "";
  boardState.notice = { message: "", tone: "info" };
  boardState.undoStack = [];
  boardState.focusReturnTaskId = "";
  boardState.dragItem = null;
  boardState.drafts = defaultDrafts();
  boardState.detailDraft = defaultDetailDraft();
  boardState.data = defaultBoardData();
  clearFlashItems();
  restoreViewState(spaceId);
}

function isValidMonthToken(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}$/.test(raw)) return false;
  const month = Number(raw.slice(5, 7));
  return Number.isInteger(month) && month >= 1 && month <= 12;
}
