export function createShellContext(baseContext, overrides = {}) {
  return {
    ...baseContext,
    ...overrides,
  };
}

export function invalidateDataForSpaceContextChange({
  previousSpaceId,
  nextSpaceId,
  clearDataState,
  suppress = false,
} = {}) {
  const previous = String(previousSpaceId || "").trim();
  const next = String(nextSpaceId || "").trim();
  if (suppress || !previous || previous === next || typeof clearDataState !== "function") return false;
  clearDataState();
  return true;
}

export async function refreshSpaceContextData({
  loadSpaces,
  loadActiveSpace,
  applySpaceContext,
  reloadCurrentViewData,
  renderActiveView,
  isCurrent = () => true,
  options = {},
} = {}) {
  let context;
  try {
    context = await Promise.all([
      loadSpaces(),
      loadActiveSpace(),
    ]);
  } catch (err) {
    if (!isCurrent()) return false;
    throw err;
  }
  if (!isCurrent()) return false;
  const [spaces, activeSpace] = context;
  const dataInvalidated = applySpaceContext(spaces, activeSpace, options);
  if (!dataInvalidated) return false;

  const nextSpaceId = String(activeSpace?.space_id || "").trim();
  if (!nextSpaceId) {
    renderActiveView();
    return true;
  }

  await reloadCurrentViewData({
    force: true,
    preserveCapacitySelection: false,
  });
  return true;
}

export function normalizeMasterFilters(filters = {}) {
  const source = filters && typeof filters === "object" ? filters : {};
  const query = typeof source.query === "string" ? source.query : "";
  const changed = filters !== source
    || Object.keys(source).some((key) => key !== "query")
    || source.query !== query;
  return { filters: { query }, changed };
}
