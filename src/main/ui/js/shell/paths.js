export const APP_CONTEXT_PATH = (() => {
  try {
    const modulePath = new URL(import.meta.url, window.location.href).pathname || "";
    const marker = "/js/";
    const idx = modulePath.lastIndexOf(marker);
    if (idx <= 0) return "";
    return modulePath.slice(0, idx).replace(/\/+$/, "");
  } catch {
    return "";
  }
})();

export const API_BASE = `${APP_CONTEXT_PATH}/api` || "/api";

export function buildAppUrl(path = "/") {
  let normalized = String(path || "/").trim() || "/";
  if (!normalized.startsWith("/")) normalized = `/${normalized}`;
  if (normalized === "/") {
    return APP_CONTEXT_PATH ? `${APP_CONTEXT_PATH}/` : "/";
  }
  return APP_CONTEXT_PATH ? `${APP_CONTEXT_PATH}${normalized}` : normalized;
}

export function buildApiUrl(path = "") {
  let normalized = String(path || "").trim();
  if (!normalized) return API_BASE;
  if (!normalized.startsWith("/")) normalized = `/${normalized}`;
  return `${API_BASE}${normalized}`;
}

export function buildWsUrl(path = "/ws") {
  const url = new URL(buildApiUrl(path), window.location.origin);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

export function buildResetPageUrl() {
  return new URL(buildAppUrl("/reset-password"), window.location.origin).toString();
}
