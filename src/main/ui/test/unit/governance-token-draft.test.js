import { expect, it, vi } from 'vitest';
import { createSpaceGovernanceRenderer } from '../../js/routes/spaces/render.js';
import { registerMutationContextLifetime } from '../../js/utils/form-state.js';

it('preserves a token form draft on same-context rerender but clears it for a replacement session', () => {
  document.body.innerHTML = '<div id="shell"></div>';
  const shell = document.getElementById('shell');
  const state = { user: { user_id: 'u' }, activeSpace: { space_id: 's' }, currentView: 'access',
    users: [], spaces: [], globalAdmins: [], globalAdminsLoaded: true, platformAccessPanel: 'api-tokens',
    apiTokensByUser: {}, apiTokensLoadedByUser: {}, spaceGovernanceNotice: {} };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const renderer = createSpaceGovernanceRenderer({ state, els: { spaceGovernanceShell: shell },
    normalize: String, normalizeSpaceRole: String, activeSpaceId: () => 's', userIsGlobalAdmin: () => true,
    currentSpaceRoleLabel: () => 'admin', canManageSpaceMembership: () => false, esc: String, escapeAttr: String,
    formatDateTime: String, effectiveDirectorySpaces: () => [], governanceSections: () => [],
    resolveGovernanceSection: () => 'platform-access', closeSpaceDirectoryModal: vi.fn(),
    refreshGlobalAdmins: vi.fn(), setSpaceGovernanceNotice: vi.fn() });
  renderer.renderGovernanceHub('platform-access');
  shell.querySelector('[name="soeid"]').value = 'target';
  shell.querySelector('[name="name"]').value = 'automation';
  renderer.renderGovernanceHub('platform-access');
  expect(shell.querySelector('[name="soeid"]').value).toBe('target');
  expect(shell.querySelector('[name="name"]').value).toBe('automation');
  lifetime.session += 1;
  state.user = { user_id: 'u' };
  renderer.renderGovernanceHub('platform-access');
  expect(shell.querySelector('[name="soeid"]').value).toBe('');
  expect(shell.querySelector('[name="name"]').value).toBe('');
});
