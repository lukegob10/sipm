export function safeExternalUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  // Validate the original authority: URL normalizes explicit :443 away, while
  // the backend only accepts github.com without credentials or any port.
  if (!/^https:\/\/github\.com(?:\/|$)/i.test(raw)) return "";
  if (url.protocol !== "https:") return "";
  if (url.hostname.toLowerCase() !== "github.com") return "";
  if (url.search || url.hash) return "";
  // Python's URL parser treats a nonempty final-segment parameter as unsafe.
  if (/;[^/]+$/.test(url.pathname)) return "";
  const parts = url.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts.length !== 2) return "";
  const repo = parts[1].replace(/\.git$/, "");
  if (!repo) return "";
  return `https://github.com/${parts[0]}/${repo}`;
}

