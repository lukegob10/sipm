import { describe, expect, it, vi } from 'vitest';
import { renderKanban } from '../../js/routes/kanban.js';
import { registerMutationContextLifetime } from '../../js/utils/form-state.js';

function setup(move) {
  document.body.innerHTML = '<div id="view-kanban"><div id="board"></div></div>';
  const state = { authed: true, currentView: 'kanban', user: { user_id: 'u1' }, activeSpace: { space_id: 's1' }, phases: [{ phase_id: 'a', phase_name: 'A', sequence: 1 }, { phase_id: 'b', phase_name: 'B', sequence: 2 }], projects: [{ project_id: 'p', project_name: 'Project' }] };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const ctx = { state, els: { kanbanBoard: document.querySelector('#board') }, filteredSolutionsForKanban: () => [{ solution_id: 'x', project_id: 'p', solution_name: 'Item', current_phase: 'a' }], phaseDisplayName: (id) => id, formatStatus: String, moveKanbanSolutionToPhase: move };
  renderKanban(ctx);
  return { state, lifetime, ctx };
}

describe('Kanban ownership', () => {
  it('keeps phase control focus and keyboard intent on a same-context refresh', () => {
    const h = setup(vi.fn());
    const select = h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]');
    select.focus();
    select.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    renderKanban(h.ctx);
    const replacement = h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]');
    expect(document.activeElement).toBe(replacement);
    expect(replacement.dataset.kanbanKeyboardSelection).toBe('true');
    expect([...replacement.options].map((option) => option.value)).toEqual(['a', 'b']);
  });
  it.each(['session', 'space', 'view'])('does not carry phase focus through a %s change on refresh', (change) => {
    const h = setup(vi.fn());
    h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]').focus();
    if (change === 'session') h.lifetime.session += 1;
    if (change === 'space') h.lifetime.space += 1;
    if (change === 'view') h.state.currentView = 'calendar';
    renderKanban(h.ctx);
    expect(document.activeElement).toBe(document.body);
  });
  it('does not act on a board rendered before the session changes', () => {
    const move = vi.fn();
    const h = setup(move);
    h.lifetime.session += 1;
    const select = h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]');
    select.focus();
    select.value = 'b';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    expect(move).not.toHaveBeenCalled();
  });

  it('does not begin a drag on a board rendered before the session changes', () => {
    const move = vi.fn();
    const h = setup(move);
    h.lifetime.session += 1;
    h.ctx.els.kanbanBoard.querySelector('[data-kanban-draggable]').dispatchEvent(new Event('dragstart', { bubbles: true }));
    h.ctx.els.kanbanBoard.querySelector('[data-phase-id="b"]').dispatchEvent(new Event('drop', { bubbles: true, cancelable: true }));
    expect(move).not.toHaveBeenCalled();
  });

  it.each(['session', 'space', 'view'])('does not drop a previous drag after %s changes', (change) => {
    const move = vi.fn();
    const h = setup(move);
    const card = h.ctx.els.kanbanBoard.querySelector('[data-kanban-draggable]');
    card.dispatchEvent(new Event('dragstart', { bubbles: true }));
    if (change === 'session') h.lifetime.session += 1;
    if (change === 'space') h.lifetime.space += 1;
    if (change === 'view') h.state.currentView = 'calendar';
    const target = h.ctx.els.kanbanBoard.querySelector('[data-phase-id="b"]');
    target.dispatchEvent(new Event('drop', { bubbles: true, cancelable: true }));
    expect(move).not.toHaveBeenCalled();
  });
  it('permits the drag after same-session token refresh replaces objects', () => {
    const move = vi.fn();
    const h = setup(move);
    h.ctx.els.kanbanBoard.querySelector('[data-kanban-draggable]').dispatchEvent(new Event('dragstart', { bubbles: true }));
    h.state.user = { user_id: 'u1' };
    h.state.activeSpace = { space_id: 's1' };
    h.ctx.els.kanbanBoard.querySelector('[data-phase-id="b"]').dispatchEvent(new Event('drop', { bubbles: true, cancelable: true }));
    expect(move).toHaveBeenCalledWith('x', 'b');
  });
  it('restores keyboard focus after same-session token refresh', async () => {
    let resolve;
    const move = vi.fn(() => new Promise((done) => { resolve = done; }));
    const h = setup(move);
    const select = h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]');
    select.focus();
    select.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    select.value = 'b';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    h.state.user = { user_id: 'u1' };
    h.state.activeSpace = { space_id: 's1' };
    renderKanban(h.ctx);
    resolve(true);
    await Promise.resolve();
    await Promise.resolve();
    expect(document.activeElement).toBe(h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]'));
  });
  it.each(['session', 'space', 'view'])('does not restore focus after %s changes', async (change) => {
    let resolve;
    const move = vi.fn(() => new Promise((done) => { resolve = done; }));
    const h = setup(move);
    const select = h.ctx.els.kanbanBoard.querySelector('[data-kanban-phase-select]');
    select.focus();
    select.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    select.value = 'b';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    if (change === 'session') h.lifetime.session += 1;
    if (change === 'space') h.lifetime.space += 1;
    if (change === 'view') h.state.currentView = 'calendar';
    renderKanban(h.ctx);
    expect(document.activeElement).toBe(document.body);
    resolve(false);
    await Promise.resolve();
    await Promise.resolve();
    expect(document.activeElement).toBe(document.body);
  });
});
