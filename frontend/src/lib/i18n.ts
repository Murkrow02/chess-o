// UI strings live in src/locales/<lang>.json. To add a language, copy en.json and translate
// the values: it shows up in the language picker on its own (its name comes from app.language).
const files = import.meta.glob<{ default: Record<string, unknown> }>("../locales/*.json", { eager: true });
const locales: Record<string, Record<string, unknown>> = {};
for (const [path, mod] of Object.entries(files)) {
  locales[path.split("/").pop()!.replace(".json", "")] = mod.default;
}

const KEY = "chesso.lang";

function initial(): string {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && locales[saved]) return saved;
  } catch {
    /* storage blocked: fall back to the browser language */
  }
  const browser = navigator.language.slice(0, 2);
  if (locales[browser]) return browser;
  return (import.meta.env.VITE_LOCALE as string | undefined) ?? "en";
}

export const lang = initial();
const dict = locales[lang] ?? locales.en;
document.documentElement.lang = lang;
// The backend reads this cookie so Giacomino answers in the same language (EventSource cannot send headers).
document.cookie = `chesso_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;

export const languages = Object.entries(locales).map(([code, d]) => ({
  code, name: String((d.app as Record<string, unknown> | undefined)?.language ?? code),
}));

/** Switch language. Every string is read at render time, so a reload applies it everywhere. */
export function setLang(code: string): void {
  try {
    localStorage.setItem(KEY, code);
  } catch {
    /* without storage the choice lasts only for this page */
  }
  document.cookie = `chesso_lang=${code}; path=/; max-age=31536000; SameSite=Lax`;
  location.reload();
}

export function t(key: string, vars?: Record<string, string | number>): string {
  let value: unknown = dict;
  for (const part of key.split(".")) value = (value as Record<string, unknown> | undefined)?.[part];
  if (typeof value !== "string" && dict !== locales.en) {
    value = locales.en;
    for (const part of key.split(".")) value = (value as Record<string, unknown> | undefined)?.[part];
  }
  let text = typeof value === "string" ? value : key;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}
