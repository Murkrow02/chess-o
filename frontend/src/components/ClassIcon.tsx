import type { Cls } from "../lib/types";

// Original glyphs on round badges. Colours follow the usual annotation conventions
// (teal !!, blue !, green best, amber ?!, orange ?, red ??) so they read instantly.
export const CLASS_COLOR: Record<Cls, string> = {
  brilliant: "#1fbfa8",
  great: "#5a8fe0",
  best: "#7fb23f",
  excellent: "#93bd57",
  good: "#8aa58c",
  book: "#a58a6a",
  inaccuracy: "#e8b73f",
  mistake: "#ec8a2d",
  miss: "#e5604f",
  blunder: "#d23a37",
};

const text = (s: string) =>
  `<text x="12" y="16.6" text-anchor="middle" font-size="${s.length > 1 ? 12 : 14}" font-weight="800" ` +
  `font-family="Inter, system-ui, sans-serif" fill="#fff" letter-spacing="${s.length > 1 ? -1 : 0}">${s}</text>`;

// Glyphs as SVG markup, shared by the React badge and the on-board badge.
const GLYPH: Record<Cls, string> = {
  brilliant: text("!!"),
  great: text("!"),
  inaccuracy: text("?!"),
  mistake: text("?"),
  blunder: text("??"),
  // five-point star
  best: `<path d="M12 5.2l2 4.3 4.6.5-3.4 3.1.9 4.6L12 15.4l-4.1 2.3.9-4.6L5.4 10l4.6-.5z" fill="#fff"/>`,
  // thumbs up
  excellent:
    `<path d="M7 11h2.2v6.4H7zM10.2 17.4V11l2.6-4.2c.9 0 1.5.7 1.3 1.6l-.5 2.1h3c.9 0 1.5.8 1.3 1.6l-1 4.1c-.2.7-.8 1.2-1.5 1.2z" fill="#fff"/>`,
  // check mark
  good: `<path d="M7.3 12.4l3 3 6.4-6.6" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
  // open book
  book:
    `<path d="M5.5 8c2.3-.6 4.6-.3 6.5 1 1.9-1.3 4.2-1.6 6.5-1v8.6c-2.3-.6-4.6-.3-6.5 1-1.9-1.3-4.2-1.6-6.5-1z M12 9v8.6" stroke="#fff" stroke-width="1.6" fill="none" stroke-linejoin="round"/>`,
  // a ring with its dot outside: the target was missed
  miss: `<g fill="none" stroke="#fff" stroke-width="2"><circle cx="11" cy="13" r="4.2"/><circle cx="17" cy="7" r="1.3" fill="#fff" stroke="none"/></g>`,
};

const badge = (cls: Cls) =>
  `<circle cx="12" cy="12" r="11" fill="${CLASS_COLOR[cls]}" stroke="rgba(0,0,0,.22)" stroke-width="1"/>${GLYPH[cls]}`;

export function ClassIcon({ cls, size = 20, title }: { cls: Cls; size?: number; title?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label={title ?? cls} className="class-icon"
      dangerouslySetInnerHTML={{ __html: badge(cls) }} />
  );
}

/** The badge as an SVG string, for chessground's custom shapes on the board. */
export const classIconSvg = (cls: Cls) => `<svg viewBox="0 0 24 24">${badge(cls)}</svg>`;
