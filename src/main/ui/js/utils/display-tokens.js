export function escDisplay(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function normalizeDisplayToken(value) {
  return String(value ?? "").trim().toLowerCase();
}

export function formatStatusLabel(value, fallback = "\u2014") {
  const text = String(value ?? "").trim();
  if (!text) return fallback;
  return text
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function statusTone(value) {
  const status = normalizeDisplayToken(value);
  if (status === "active" || status === "in_progress" || status === "complete") return "positive";
  if (status === "on_hold") return "warn";
  if (status === "abandoned") return "danger";
  return "muted";
}

export function ragTone(value) {
  const rag = normalizeDisplayToken(value);
  if (rag === "green") return "positive";
  if (rag === "amber") return "warn";
  if (rag === "red") return "danger";
  return "muted";
}

export function ragLabel(value) {
  const rag = normalizeDisplayToken(value);
  if (rag === "green") return "Green";
  if (rag === "amber") return "Amber";
  if (rag === "red") return "Red";
  return "Unknown";
}

export function statusPillMarkup(value, label = formatStatusLabel(value), extraClass = "") {
  const classToken = extraClass ? ` ${escDisplay(extraClass)}` : "";
  return `<span class="pill status-pill ${statusTone(value)}${classToken}" data-status-state="${escDisplay(normalizeDisplayToken(value))}">${escDisplay(label)}</span>`;
}

export function ragPillMarkup(value, extraClass = "") {
  const rag = normalizeDisplayToken(value);
  const classToken = extraClass ? ` ${escDisplay(extraClass)}` : "";
  return `<span class="pill rag-pill rag-${escDisplay(rag || "unknown")} ${ragTone(rag)}${classToken}" data-rag-state="${escDisplay(rag || "unknown")}">${escDisplay(ragLabel(rag))}</span>`;
}
