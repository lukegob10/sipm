export function renderWorkbench(ctx) {
  const { state } = ctx;
  state.workbench?.render?.();
}
