import { beforeEach, expect, it, vi } from 'vitest';
let renderAnalytics;
let registerMutationContextLifetime;
beforeEach(async () => {
  vi.resetModules();
  ({ renderAnalytics } = await import('../../js/routes/analytics.js'));
  ({ registerMutationContextLifetime } = await import('../../js/utils/form-state.js'));
  document.body.innerHTML = '<div id="analytics-root"></div>';
});

function response(sessions) {
  return { summary: { summary: { sessions }, daily: [] }, routes: { top_routes: [], top_workflows: [], recent_failures: [] }, performance: { summary: {}, routes: [] } };
}

function setup(api) {
  const state = { authed: true, user: { user_id: 'admin' }, activeSpace: { space_id: 's1', is_global_admin: true }, spaces: [] };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const ctx = { state, els: { analyticsRoot: document.querySelector('#analytics-root') }, usageAnalyticsEnabled: () => true, api };
  return { state, lifetime, ctx };
}

it('keeps an in-flight result when the same session refreshes identity objects', async () => {
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const api = vi.fn().mockReturnValueOnce(pending).mockReturnValue(new Promise(() => {}));
  const { state, ctx } = setup(api);
  renderAnalytics(ctx);
  state.user = { user_id: 'admin' };
  state.activeSpace = { space_id: 's1', is_global_admin: true };
  finish(response(42));
  await vi.waitFor(() => expect(ctx.els.analyticsRoot.querySelector('.analytics-card strong')?.textContent).toBe('42'));
  expect(api).toHaveBeenCalledTimes(1);
  renderAnalytics(ctx);
  expect(api).toHaveBeenCalledTimes(1);
});

it.each(['session', 'space'])('rejects an old result after the %s lifetime changes', async (change) => {
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const api = vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(response(9));
  const { lifetime, ctx } = setup(api);
  renderAnalytics(ctx);
  lifetime[change] += 1;
  renderAnalytics(ctx);
  await vi.waitFor(() => expect(ctx.els.analyticsRoot.querySelector('.analytics-card strong')?.textContent).toBe('9'));
  finish(response(42));
  await Promise.resolve();
  await Promise.resolve();
  expect(ctx.els.analyticsRoot.querySelector('.analytics-card strong')?.textContent).toBe('9');
  expect(api).toHaveBeenCalledTimes(2);
});
