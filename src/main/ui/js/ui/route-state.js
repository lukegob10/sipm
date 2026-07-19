function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderRouteState({
  kind = "empty",
  kicker = "No data",
  title,
  message = "",
} = {}) {
  const safeKind = ["empty", "loading", "error", "restricted", "success"].includes(kind) ? kind : "empty";
  const messageMarkup = message ? `<p>${escapeHtml(message)}</p>` : "";
  return `<div class="route-state route-state-${safeKind}" role="${safeKind === "error" ? "alert" : "status"}">
    <span class="route-state-kicker">${escapeHtml(kicker)}</span>
    <strong>${escapeHtml(title || "Nothing to show")}</strong>
    ${messageMarkup}
  </div>`;
}
