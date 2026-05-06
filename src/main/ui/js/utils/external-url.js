export function safeExternalUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  if (url.protocol !== "https:") return "";
  if (url.hostname.toLowerCase() !== "github.com") return "";
  if (url.search || url.hash) return "";
  const parts = url.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts.length !== 2) return "";
  return `https://github.com/${parts[0]}/${parts[1].replace(/\.git$/, "")}`;
}

