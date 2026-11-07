import { captureEntityMutationContext, isEntityMutationContextCurrent } from "./form-state.js";

export async function requestCsvImport({ state, file, kind, apiBase, fetchImpl, context = captureEntityMutationContext(state) }) {
  const isCurrent = () => isEntityMutationContextCurrent(state, context);
  try {
    const csvText = await file.text();
    if (!isCurrent()) return { stale: true };
    const headers = { "Content-Type": "text/csv" };
    if (context.spaceId) headers["X-Space-Id"] = context.spaceId;
    const response = await fetchImpl(`${apiBase}/${kind}/import`, {
      method: "POST", headers, body: csvText, credentials: "include",
    });
    if (!isCurrent()) return { stale: true };
    if (response.status === 401) return { unauthorized: true };
    if (!response.ok) {
      const detail = await response.text();
      if (!isCurrent()) return { stale: true };
      throw new Error(detail);
    }
    const data = await response.json();
    if (!isCurrent()) return { stale: true };
    return { data };
  } catch (err) {
    if (!isCurrent()) return { stale: true };
    throw err;
  }
}

export async function requestCsvExport({ state, kind, apiBase, fetchImpl, context = captureEntityMutationContext(state) }) {
  const isCurrent = () => isEntityMutationContextCurrent(state, context);
  if (!isCurrent()) return { stale: true };
  try {
    const headers = {};
    if (context.spaceId) headers["X-Space-Id"] = context.spaceId;
    const response = await fetchImpl(`${apiBase}/${kind}/export`, { credentials: "include", headers });
    if (!isCurrent()) return { stale: true };
    if (response.status === 401) return { unauthorized: true };
    if (!response.ok) {
      const detail = await response.text();
      if (!isCurrent()) return { stale: true };
      throw new Error(detail);
    }
    const blob = await response.blob();
    if (!isCurrent()) return { stale: true };
    return { blob };
  } catch (err) {
    if (!isCurrent()) return { stale: true };
    throw err;
  }
}
