import { describe, expect, it, vi } from 'vitest';
import { createSpaceGovernanceController } from '../../js/routes/spaces/interactions.js';

function harness() {
  const state = { user: { user_id: 'user' }, activeSpace: { space_id: 'a' }, currentView: 'spaces',
    spaceMembersBySpace: {}, spaceMembersLoadedBySpace: {}, spaceMembersErrorBySpace: {} };
  const api = vi.fn();
  const controller = createSpaceGovernanceController({ state, api, els: {}, activeSpaceId: () => state.activeSpace?.space_id,
    userIsGlobalAdmin: () => true, isSpaceGovernanceView: () => false });
  return { state, api, controller };
}

describe('membership load failures', () => {
  it('keeps a failed forced refresh distinguishable from an empty list and clears it after retry', async () => {
    const { state, api, controller } = harness();
    api.mockResolvedValueOnce([{ membership_id: 'old' }]).mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce([{ membership_id: 'new' }]);
    await controller.refreshSpaceMembers('a', { force: true });
    await expect(controller.refreshSpaceMembers('a', { force: true })).rejects.toThrow('unavailable');
    expect(state.spaceMembersErrorBySpace.a).toBe(true);
    expect(state.spaceMembersBySpace.a).toEqual([{ membership_id: 'old' }]);
    await controller.refreshSpaceMembers('a', { force: true });
    expect(state.spaceMembersErrorBySpace.a).toBeUndefined();
    expect(state.spaceMembersBySpace.a).toEqual([{ membership_id: 'new' }]);
  });

  it('does not let a late failure poison a replacement session', async () => {
    const { state, api, controller } = harness();
    let rejectOld;
    api.mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }))
      .mockResolvedValueOnce([{ membership_id: 'new' }]);
    const old = controller.refreshSpaceMembers('a', { force: true });
    state.user = { user_id: 'user' };
    await controller.refreshSpaceMembers('a', { force: true });
    rejectOld(new Error('old failure'));
    await old;
    expect(state.spaceMembersErrorBySpace.a).toBeUndefined();
    expect(state.spaceMembersBySpace.a).toEqual([{ membership_id: 'new' }]);
  });
});
