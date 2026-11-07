import { captureEntityMutationContext, isSameMutationSession } from "../../utils/form-state.js";

export const AGENT_BULK_REVIEW_LIMIT = 50;

const contextsByState = new WeakMap();

function sameContextIdentity(left, right) {
  if (!left || !right || !isSameMutationSession(left, right) || left.spaceId !== right.spaceId) return false;
  return left.spaceGeneration !== undefined && right.spaceGeneration !== undefined
    ? left.spaceGeneration === right.spaceGeneration
    : left.spaceRef === right.spaceRef;
}

export function captureAgentChangeRequestContext(state, activeSpaceId) {
  const identity = {
    ...captureEntityMutationContext(state),
    spaceId: String(activeSpaceId() || state.activeSpace?.space_id || ""),
  };
  const previous = contextsByState.get(state);
  const generation = sameContextIdentity(previous, identity)
    ? previous.generation
    : (previous?.generation || 0) + 1;
  const context = { ...identity, generation };
  contextsByState.set(state, context);
  return context;
}

export function sameAgentChangeRequestContext(left, right) {
  return sameContextIdentity(left, right) && left.generation === right.generation;
}

export function clearAgentChangeRequestData(state) {
  state.agentChangeRequests = [];
  state.agentChangeRequestPendingCount = 0;
  state.agentChangeRequestFailedCount = 0;
  state.agentChangeRequestsLoaded = false;
  state.agentChangeRequestsError = "";
  state.agentChangeRequestsContext = null;
  state.agentChangeRequestSelectedIds = new Set();
  state.agentChangeRequestSelectedOperationIds = {};
  state.agentChangeRequestActiveId = "";
  state.agentChangeRequestModalId = "";
}
