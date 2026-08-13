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
