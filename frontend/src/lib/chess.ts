import type { Key } from "chessground/types";
import type { Score } from "./types";

export function winWhite(s: Score): number {
  if (s.terminal === "checkmate") return (s.cp ?? 0) > 0 ? 100 : 0;
  if (s.mate !== undefined) return s.mate > 0 ? 100 : 0;
  const cp = Math.max(-10000, Math.min(10000, s.cp ?? 0));
  return 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1);
}

/** Engine evaluation as a short label, from White's point of view. */
export function evalLabel(s: Score | undefined): string {
  if (!s) return "";
  if (s.terminal === "checkmate") return (s.cp ?? 0) > 0 ? "1-0" : "0-1";
  if (s.terminal === "draw") return "½-½";
  if (s.mate !== undefined) return `${s.mate > 0 ? "" : "-"}M${Math.abs(s.mate)}`;
  const v = (s.cp ?? 0) / 100;
  return `${v > 0 ? "+" : ""}${v.toFixed(Math.abs(v) >= 10 ? 0 : 2)}`;
}

export function uciSquares(uci: string): [Key, Key] {
  return [uci.slice(0, 2) as Key, uci.slice(2, 4) as Key];
}

export const turnOf = (fen: string) => (fen.split(" ")[1] === "w" ? "white" : "black") as "white" | "black";
