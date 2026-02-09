export function renderAI(ctx) {
  const { state } = ctx;
  if (typeof state.aiRefreshGreeting === "function") {
    state.aiRefreshGreeting();
  }
}
