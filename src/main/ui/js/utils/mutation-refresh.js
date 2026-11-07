import { captureEntityMutationContext, isEntityMutationContextCurrent } from "./form-state.js";

// Only collections updated locally from these mutation responses need reconciliation.
export function mutationCollections(path, method) {
  if (!["POST", "PUT", "PATCH", "DELETE"].includes(String(method || "GET").toUpperCase())) return [];
  const parts = String(path || "").split("?")[0].split("/").filter(Boolean);
  if (parts[0] === "programs") return ["programs", "projects"];
  if (parts[0] === "projects") return parts[2] === "solutions" ? ["solutions"] : ["projects"];
  if (parts[0] === "solutions") {
    if (parts[2] === "tasks") return ["tasks"];
    if (parts.length <= 2) return ["solutions"];
  }
  if (parts[0] === "tasks") return ["tasks"];
  if (parts[0] === "teams") return ["teams"];
  if (parts[0] === "users" && parts[1] === "by-soeid") return ["users"];
  return [];
}

export async function requestWithMutationReconciliation({ state, path, options, request, getStore, schedule }) {
  const store = getStore();
  const entities = store ? mutationCollections(path, options?.method) : [];
  const context = entities.length ? captureEntityMutationContext(state) : null;
  const before = new Map(entities.map((entity) => [entity, store.entityReadSnapshot(entity)]));
  const result = await request(path, options);
  if (!context || !isEntityMutationContextCurrent(state, context) || getStore() !== store) return result;
  if (entities.some((entity) => ["programs", "projects", "solutions", "tasks"].includes(entity))) {
    store.invalidateRepositoryInventory?.();
  }
  // The caller applies the mutation response in a microtask. Check again on
  // the next turn, including reads completed while that response propagated.
  schedule(() => {
    if (!isEntityMutationContextCurrent(state, context) || getStore() !== store) return;
    for (const entity of entities) {
      const previous = before.get(entity);
      const current = store.entityReadSnapshot(entity);
      if (previous.pending || current.pending || previous.version !== current.version) {
        void store.refreshFromServer(entity);
      }
    }
  });
  return result;
}
