import { describe, expect, it } from 'vitest';
import { createPMDashboardState, renderPMDashboardView } from '../../js/routes/pm-dashboard/render.js';

function capacityLabel(users) {
  document.body.innerHTML = '<section id="view-pm-dashboard"><nav id="pm-dashboard-focus-nav"><label id="pm-focus-label-capacity"></label></nav></section>';
  const dashboard = createPMDashboardState();
  renderPMDashboardView(dashboard, {
    state: { activeSpace: { space_id: 's1' }, projects: [], solutions: [], tasks: [], users },
    els: {}, formatStatus: String,
  });
  return document.querySelector('#pm-focus-label-capacity').textContent;
}

describe('PM dashboard capacity summary', () => {
  it('shows no people when the active roster is empty', () => {
    expect(capacityLabel([])).toContain('0 people');
  });
  it('counts active roster members and excludes inactive users', () => {
    expect(capacityLabel([
      { soeid: 'a', display_name: 'A', is_active: true },
      { soeid: 'b', display_name: 'B', is_active: true },
      { soeid: 'c', display_name: 'C', is_active: false },
    ])).toContain('2 people');
    expect(capacityLabel([{ soeid: 'a', display_name: 'A' }])).toContain('1 person');
  });
});
