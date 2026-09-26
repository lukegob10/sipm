function captureEntityMutationIdentity(state) {
  const user = state.user || null;
  const activeSpace = state.activeSpace || null;
  return {
    userId: String(user?.user_id || user?.soeid || user?.email || ""),
    spaceId: String(activeSpace?.space_id || ""),
    userRef: user,
    spaceRef: activeSpace,
  };
}

export function captureEntityMutationContext(state) {
  return captureEntityMutationIdentity(state);
}

export function isEntityMutationContextCurrent(state, context) {
  const current = captureEntityMutationIdentity(state);
  return current.userId === context.userId
    && current.spaceId === context.spaceId
    && current.userRef === context.userRef
    && current.spaceRef === context.spaceRef;
}
