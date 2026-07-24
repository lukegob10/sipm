export const THEME_PREFERENCES = Object.freeze([
  "dark",
  "midnight",
  "slate",
  "light",
  "system",
]);

export const THEME_STORAGE_KEY = "sipm-theme";
export const LEGACY_THEME_STORAGE_KEY = "jira-lite-theme";

const THEME_CLASSES = Object.freeze({
  light: "theme-light",
  midnight: "theme-midnight",
  slate: "theme-slate",
});

const THEME_META_COLORS = Object.freeze({
  dark: "#0b1118",
  midnight: "#070812",
  slate: "#0d1014",
  light: "#f5f6f8",
});

const THEME_PRESENTATIONS = Object.freeze({
  dark: {
    label: "Dark",
    description: "Slate surfaces with balanced contrast for everyday work.",
  },
  midnight: {
    label: "Midnight",
    description: "Deep indigo surfaces with stronger visual separation.",
  },
  slate: {
    label: "Slate",
    description: "Charcoal surfaces with a restrained sage accent.",
  },
  light: {
    label: "Light",
    description: "Bright neutral surfaces for well-lit environments.",
  },
  system: {
    label: "System",
    description: "Follows your device setting and switches between Dark and Light.",
  },
});

export function normalizeTheme(theme) {
  const normalized = String(theme || "").trim().toLowerCase();
  if (normalized === "forest") return "slate";
  return THEME_PREFERENCES.includes(normalized) ? normalized : "dark";
}

export function resolveTheme(theme, matchMedia = globalThis.window?.matchMedia?.bind(globalThis.window)) {
  const normalized = normalizeTheme(theme);
  if (normalized !== "system") return normalized;
  return matchMedia?.("(prefers-color-scheme: light)")?.matches ? "light" : "dark";
}

export function themePresentation(theme) {
  return THEME_PRESENTATIONS[normalizeTheme(theme)];
}

export function readThemePreference(storage) {
  try {
    const activeStorage = storage || globalThis.localStorage;
    const saved = activeStorage?.getItem?.(THEME_STORAGE_KEY)
      || activeStorage?.getItem?.(LEGACY_THEME_STORAGE_KEY)
      || "dark";
    return normalizeTheme(saved);
  } catch {
    return "dark";
  }
}

export function persistThemePreference(theme, storage) {
  const normalized = normalizeTheme(theme);
  try {
    const activeStorage = storage || globalThis.localStorage;
    activeStorage?.setItem?.(THEME_STORAGE_KEY, normalized);
    activeStorage?.removeItem?.(LEGACY_THEME_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function applyThemeToDocument(
  theme,
  {
    documentRef = globalThis.document,
    matchMedia = globalThis.window?.matchMedia?.bind(globalThis.window),
  } = {},
) {
  const preference = normalizeTheme(theme);
  const resolved = resolveTheme(preference, matchMedia);
  const body = documentRef?.body;
  const root = documentRef?.documentElement;

  if (body) {
    body.classList.remove(...Object.values(THEME_CLASSES));
    const themeClass = THEME_CLASSES[resolved];
    if (themeClass) body.classList.add(themeClass);
    body.dataset.theme = resolved;
  }

  if (root) {
    root.dataset.theme = resolved;
    root.style.colorScheme = resolved === "light" ? "light" : "dark";
  }

  documentRef?.querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_META_COLORS[resolved]);

  return { preference, resolved };
}
