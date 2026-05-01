export function createShellContext(baseContext, overrides = {}) {
  return {
    ...baseContext,
    ...overrides,
  };
}
