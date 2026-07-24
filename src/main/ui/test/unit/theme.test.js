import { afterEach, describe, expect, it } from "vitest";

import {
  applyThemeToDocument,
  LEGACY_THEME_STORAGE_KEY,
  normalizeTheme,
  persistThemePreference,
  readThemePreference,
  resolveTheme,
  THEME_STORAGE_KEY,
  themePresentation,
} from "../../js/ui/theme.js";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("style");
  document.body.className = "";
  document.body.removeAttribute("data-theme");
  document.head.innerHTML = "";
  localStorage.clear();
});

describe("theme preferences", () => {
  it("normalizes supported schemes and falls back to dark", () => {
    expect(normalizeTheme(" Midnight ")).toBe("midnight");
    expect(normalizeTheme("FOREST")).toBe("forest");
    expect(normalizeTheme("unknown")).toBe("dark");
  });

  it("resolves the system preference without changing named schemes", () => {
    expect(resolveTheme("forest", () => ({ matches: true }))).toBe("forest");
    expect(resolveTheme("system", () => ({ matches: true }))).toBe("light");
    expect(resolveTheme("system", () => ({ matches: false }))).toBe("dark");
  });

  it("migrates the legacy storage key when the preference is persisted", () => {
    localStorage.setItem(LEGACY_THEME_STORAGE_KEY, "midnight");

    expect(readThemePreference()).toBe("midnight");
    expect(persistThemePreference("midnight")).toBe(true);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("midnight");
    expect(localStorage.getItem(LEGACY_THEME_STORAGE_KEY)).toBeNull();
  });

  it("falls back safely when browser storage is unavailable", () => {
    const blockedStorage = {
      getItem() {
        throw new DOMException("Storage blocked", "SecurityError");
      },
      setItem() {
        throw new DOMException("Storage blocked", "SecurityError");
      },
    };

    expect(readThemePreference(blockedStorage)).toBe("dark");
    expect(persistThemePreference("forest", blockedStorage)).toBe(false);
  });

  it("applies one resolved theme class and updates native browser colors", () => {
    document.head.innerHTML = '<meta name="theme-color" content="#000000">';

    expect(applyThemeToDocument("midnight")).toEqual({ preference: "midnight", resolved: "midnight" });
    expect(document.body.classList.contains("theme-midnight")).toBe(true);
    expect(document.body.dataset.theme).toBe("midnight");
    expect(document.documentElement.dataset.theme).toBe("midnight");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(document.querySelector('meta[name="theme-color"]').content).toBe("#070812");

    applyThemeToDocument("light");
    expect(document.body.classList.contains("theme-midnight")).toBe(false);
    expect(document.body.classList.contains("theme-light")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("provides concise descriptions for the appearance preview", () => {
    expect(themePresentation("forest")).toEqual({
      label: "Forest",
      description: "Low-glare green surfaces with a calmer, natural tint.",
    });
  });
});
