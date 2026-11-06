import { expect, it } from "vitest";
import { createContextualEntityMutationGate, registerMutationContextLifetime } from "../../js/utils/form-state.js";

it.each(["session", "space"])("keeps a replacement %s request owned after an old request releases", (changed) => {
  const state = { authed: true, user: { user_id: "u" }, activeSpace: { space_id: "s" } };
  const lifetime = { session: 1, space: 1 };
  registerMutationContextLifetime(state, () => lifetime);
  const begin = createContextualEntityMutationGate(state);
  const first = begin("one");
  lifetime[changed]++;
  const second = begin("one");
  first();
  expect(begin("one")).toBeNull();
  second();
  const third = begin("one");
  expect(third).toBeTypeOf("function");
  third();
});
it("keeps same-session refresh pending and allows unrelated IDs", () => {
  const state = { authed: true, user: { user_id: "u" }, activeSpace: { space_id: "s" } };
  registerMutationContextLifetime(state, () => ({ session: 1, space: 1 }));
  const begin = createContextualEntityMutationGate(state);
  const release = begin("one");
  state.user = { user_id: "u" }; state.activeSpace = { space_id: "s" };
  expect(begin("one")).toBeNull();
  const releaseOther = begin("two");
  expect(releaseOther).toBeTypeOf("function");
  releaseOther(); release();
});
