export function textValue(value) {
  return String(value ?? "").trim();
}

export function nullableTextValue(value) {
  const text = textValue(value);
  return text || null;
}

export function captureEntityMutationContext(state) {
  const user = state.user || null;
  const activeSpace = state.activeSpace || null;
  return {
    userId: String(user?.user_id || user?.soeid || user?.email || ""),
    spaceId: String(activeSpace?.space_id || ""),
    userRef: user,
    spaceRef: activeSpace,
  };
}

export function isEntityMutationContextCurrent(state, context) {
  const current = captureEntityMutationContext(state);
  return current.userId === context.userId
    && current.spaceId === context.spaceId
    && current.userRef === context.userRef
    && current.spaceRef === context.spaceRef;
}
