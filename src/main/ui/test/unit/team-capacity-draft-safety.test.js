import { expect, it, vi } from "vitest";
import { createTeamCapacityRouteController } from "../../js/routes/team-capacity/interactions.js";

function harness() {
  document.body.innerHTML = '<form id="capacity"><input name="soeid" value="target"><input name="display_name" value="Target"><input name="team_tag" value="Team"><input name="capacity_fte_month" value="1"></form><button id="delete">Deactivate</button><table><tbody id="list"><tr data-soeid="other"><td>Other</td></tr></tbody></table>';
  const state = { authed: true, user: { user_id: "admin" }, activeSpace: { space_id: "one", space_name: "One" }, teamCapacity: {}, users: [{ soeid: "target", display_name: "Target" }], capacitySelectedSoeid: "target", currentView: "team-capacity" };
  const els = { capacityUserForm: document.getElementById("capacity"), capacityUserDelete: document.getElementById("delete"), capacityUserList: document.getElementById("list") };
  const api = vi.fn();
  const showConfirmModal = vi.fn();
  const setCapacityUserFormStatus = vi.fn();
  const handleAuthError = vi.fn(() => false);
  const controller = createTeamCapacityRouteController({
    state, els, api, showConfirmModal, setCapacityUserFormStatus, handleAuthError,
    applyEntityData: vi.fn((_key, value) => { state.users = value; }), renderTeamCapacity: vi.fn(), populateSelects: vi.fn(),
    writeStoredJson: vi.fn(), readStoredJsonState: () => ({ value: {}, recovered: false }), activeSpaceScopedStorageKey: () => "key",
    bindDebouncedInput: vi.fn(), clearCapacityUserFormStatus: vi.fn(), userCapacityFteMonth: () => 1,
    formatFte: () => "1.00", numberOr: (value) => Number(value), timestampLabel: () => "now",
  });
  controller.bindTeamCapacityControls();
  return { state, els, api, controller, showConfirmModal, setCapacityUserFormStatus, handleAuthError };
}


it("does not discard a roster draft already present when refresh starts", async () => {
 const h=harness();const field=h.els.capacityUserForm.querySelector('[name="team_tag"]');field.value='Unsaved';field.dispatchEvent(new Event('input',{bubbles:true}));
 h.api.mockResolvedValue([{soeid:'target',display_name:'Target',team_tag:'Server'}]);
 await h.controller.loadTeamCapacityData({force:true}); expect(field.value).toBe('Unsaved');
});
it("does not discard an existing draft when the same member name blurs", () => {
 const h=harness();const field=h.els.capacityUserForm.querySelector('[name="team_tag"]');field.value='Unsaved';field.dispatchEvent(new Event('input',{bubbles:true}));
 h.els.capacityUserForm.querySelector('[name="display_name"]').dispatchEvent(new Event('blur')); expect(field.value).toBe('Unsaved');
});
it("rejects blank capacity rather than setting zero", () => {
 const h=harness();h.els.capacityUserForm.querySelector('[name="capacity_fte_month"]').value='';
 h.els.capacityUserForm.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})); expect(h.api).not.toHaveBeenCalled();
});

it('does not select an arbitrary member when names are duplicated', () => {
 const h=harness();
 h.state.users=[{soeid:'first',display_name:'Alex'}, {soeid:'second',display_name:'Alex'}];
 h.state.capacitySelectedSoeid='';
 const form=h.els.capacityUserForm;
 const name=form.querySelector('[name="display_name"]');name.value='Alex';name.dispatchEvent(new Event('input',{bubbles:true}));
 name.dispatchEvent(new Event('blur'));
 expect(form.querySelector('[name="soeid"]').value).toBe('');
 form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 expect(h.api).not.toHaveBeenCalled();
});

it.each(['cancel','space change','newer edit'])('preserves a draft when member switch is interrupted by %s', async (scenario) => {
 const h=harness();h.state.users.push({soeid:'other',display_name:'Other',team_tag:'Other team'});
 const field=h.els.capacityUserForm.querySelector('[name="team_tag"]');field.value='Unsaved';field.dispatchEvent(new Event('input',{bubbles:true}));
 let finish;h.showConfirmModal.mockReturnValue(new Promise(r=>{finish=r;}));
 h.els.capacityUserList.querySelector('tr').click();expect(h.showConfirmModal).toHaveBeenCalledOnce();
 if(scenario==='space change')h.state.activeSpace={space_id:'two'};
 if(scenario==='newer edit'){field.value='Newer';field.dispatchEvent(new Event('input',{bubbles:true}));}
 finish(scenario!=='cancel');await Promise.resolve();await Promise.resolve();
 expect(field.value).toBe(scenario==='newer edit'?'Newer':'Unsaved');
 expect(h.els.capacityUserForm.querySelector('[name="soeid"]').value).toBe('target');
});

it('selects the requested member after confirming discard', async () => {
 const h=harness();h.state.users.push({soeid:'other',display_name:'Other',team_tag:'Other team'});
 const field=h.els.capacityUserForm.querySelector('[name="team_tag"]');field.value='Unsaved';field.dispatchEvent(new Event('input',{bubbles:true}));
 h.showConfirmModal.mockResolvedValue(true);h.els.capacityUserList.querySelector('tr').click();
 await vi.waitFor(()=>expect(h.els.capacityUserForm.querySelector('[name="soeid"]').value).toBe('other'));
 expect(field.value).toBe('Other team');
});

it('restores original member after typing another name and cancelling draft discard', async () => {
 const h=harness();h.state.users.push({soeid:'other',display_name:'Other',team_tag:'Other team'});
 const form=h.els.capacityUserForm, name=form.querySelector('[name="display_name"]'), team=form.querySelector('[name="team_tag"]');
 team.value='Unsaved';team.dispatchEvent(new Event('input',{bubbles:true}));
 let finish;h.showConfirmModal.mockReturnValue(new Promise(r=>{finish=r;}));
 for(const value of ['O','Ot','Oth','Othe','Other']) { name.value=value;name.dispatchEvent(new Event('input',{bubbles:true})); }
 expect(h.showConfirmModal).toHaveBeenCalledOnce();finish(false);await Promise.resolve();await Promise.resolve();
 expect(name.value).toBe('Target');expect(form.querySelector('[name="soeid"]').value).toBe('target');expect(h.state.capacitySelectedSoeid).toBe('target');expect(team.value).toBe('Unsaved');
});
