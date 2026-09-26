const contextsByState = new WeakMap();

export function captureAgentChangeRequestContext(state, activeSpaceId) {
  const user = state.user || null;
  const space = state.activeSpace || null;
  const identity = {
    userId: String(user?.user_id || user?.soeid || user?.email || ""),
    spaceId: String(activeSpaceId() || state.activeSpace?.space_id || ""),
    userRef: user,
    spaceRef: space,
  };
  const previous = contextsByState.get(state);
  const generation = previous
    && previous.userId === identity.userId
    && previous.spaceId === identity.spaceId
    && previous.userRef === identity.userRef
    && previous.spaceRef === identity.spaceRef
    ? previous.generation
    : (previous?.generation || 0) + 1;
  const context = { ...identity, generation };
  contextsByState.set(state, context);
  return context;
}

export function sameAgentChangeRequestContext(left, right) {
  return !!left
    && !!right
    && left.userId === right.userId
    && left.spaceId === right.spaceId
    && left.userRef === right.userRef
    && left.spaceRef === right.spaceRef
    && left.generation === right.generation;
}

export function clearAgentChangeRequestData(state) {
  state.agentChangeRequests = [];
  state.agentChangeRequestPendingCount = 0;
  state.agentChangeRequestFailedCount = 0;
  state.agentChangeRequestsLoaded = false;
  state.agentChangeRequestsContext = null;
  state.agentChangeRequestSelectedIds = new Set();
  state.agentChangeRequestSelectedOperationIds = {};
  state.agentChangeRequestActiveId = "";
  state.agentChangeRequestModalId = "";
}
