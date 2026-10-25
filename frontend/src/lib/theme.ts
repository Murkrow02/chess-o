export type ThemeChoice = "auto" | "light" | "dark";

const KEY = "chesso.theme";
const ORDER: ThemeChoice[] = ["auto", "light", "dark"];

export function loadTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY) as ThemeChoice | null;
    return v && ORDER.includes(v) ? v : "auto";
  } catch {
    return "auto";
  }
}

/** "auto" leaves the choice to prefers-color-scheme; the CSS reads data-theme otherwise. */
export function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* storage blocked: the choice lasts until reload */
  }
}

export const nextTheme = (c: ThemeChoice) => ORDER[(ORDER.indexOf(c) + 1) % ORDER.length];
