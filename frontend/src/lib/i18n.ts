// UI strings live in src/locales/<lang>.json. To add a language, copy en.json,
// translate the values and set VITE_LOCALE (or add it to the picker).
const files = import.meta.glob<{ default: Record<string, unknown> }>("../locales/*.json", { eager: true });
const locales: Record<string, Record<string, unknown>> = {};
for (const [path, mod] of Object.entries(files)) {
  locales[path.split("/").pop()!.replace(".json", "")] = mod.default;
}

const lang = (import.meta.env.VITE_LOCALE as string | undefined) ?? "en";
const dict = locales[lang] ?? locales.en;

export function t(key: string, vars?: Record<string, string | number>): string {
  let value: unknown = dict;
  for (const part of key.split(".")) value = (value as Record<string, unknown> | undefined)?.[part];
  let text = typeof value === "string" ? value : key;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}
