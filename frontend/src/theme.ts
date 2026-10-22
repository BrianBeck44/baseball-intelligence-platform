export const THEME_STORAGE_KEY = "bip-theme";

export type Theme = "light" | "dark";

export function getStoredTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
  } catch {
    // localStorage may be unavailable; fall back to the default theme.
  }
  return "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Theme still applies for this session if persistence fails.
  }
}

export function applyStoredTheme(): void {
  applyTheme(getStoredTheme());
}
