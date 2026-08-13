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
  options = {},
} = {}) {
  const [spaces, activeSpace] = await Promise.all([
    loadSpaces(),
    loadActiveSpace(),
  ]);
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
