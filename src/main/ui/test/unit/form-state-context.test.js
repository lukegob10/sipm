import { describe, expect, it } from "vitest";
import {
  captureEntityMutationContext,
  createContextualFormSaveGate,
  createCsvImportGate,
  isEntityMutationContextCurrent,
  registerMutationContextLifetime,
} from "../../js/utils/form-state.js";

function harness() {
  const state = { authed: true, user: { user_id: "user" }, activeSpace: { space_id: "one" } };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  return { state, lifetime };
}

describe("mutation session ownership", () => {
  it("retains context and pending gates when the same session and space objects refresh", () => {
    const { state } = harness();
    const context = captureEntityMutationContext(state);
    const formGate = createContextualFormSaveGate({ state });
    const csvGate = createCsvImportGate();
    const formRequest = formGate.begin();
    const csvRequest = csvGate.begin(context);
    state.user = { user_id: "user" };
    state.activeSpace = { space_id: "one" };
    expect(isEntityMutationContextCurrent(state, context)).toBe(true);
    expect(formGate.begin()).toBeNull();
    expect(csvGate.begin(captureEntityMutationContext(state))).toBeNull();
    formGate.end(formRequest);
    csvGate.finish(csvRequest);
    expect(formGate.begin()).not.toBeNull();
    expect(csvGate.begin(captureEntityMutationContext(state))).not.toBeNull();
  });

  it("rejects an old context after a same-user same-space new session", () => {
    const { state, lifetime } = harness();
    const context = captureEntityMutationContext(state);
    const formGate = createContextualFormSaveGate({ state });
    const csvGate = createCsvImportGate();
    const oldForm = formGate.begin();
    const oldCsv = csvGate.begin(context);
    lifetime.session += 1;
    expect(isEntityMutationContextCurrent(state, context)).toBe(false);
    const newForm = formGate.begin();
    const newCsv = csvGate.begin(captureEntityMutationContext(state));
    expect(newForm).not.toBeNull();
    expect(newCsv).not.toBeNull();
    formGate.end(oldForm);
    csvGate.finish(oldCsv);
    expect(formGate.begin()).toBeNull();
    expect(csvGate.begin(captureEntityMutationContext(state))).toBeNull();
  });

  it("rejects old work after a space switch away and back", () => {
    const { state, lifetime } = harness();
    const context = captureEntityMutationContext(state);
    const formGate = createContextualFormSaveGate({ state });
    formGate.begin();
    lifetime.space += 1;
    state.activeSpace = { space_id: "two" };
    lifetime.space += 1;
    state.activeSpace = { space_id: "one" };
    expect(isEntityMutationContextCurrent(state, context)).toBe(false);
    expect(formGate.begin()).not.toBeNull();
  });

  it("retains reference-based isolation when no lifetime is registered", () => {
    const state = { authed: true, user: { user_id: "user" }, activeSpace: { space_id: "one" } };
    const context = captureEntityMutationContext(state);
    state.user = { user_id: "user" };
    expect(isEntityMutationContextCurrent(state, context)).toBe(false);
  });
});
