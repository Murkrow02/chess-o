export type Cls =
  | "brilliant" | "great" | "best" | "excellent" | "good" | "book"
  | "inaccuracy" | "mistake" | "miss" | "blunder";

export const CLASSES: Cls[] = [
  "brilliant", "great", "best", "excellent", "good", "book", "inaccuracy", "mistake", "miss", "blunder",
];

export type Score = { cp?: number; mate?: number; terminal?: "checkmate" | "draw" };
export type Side = "white" | "black";

export interface Move { ply: number; san: string; uci: string; fen: string }

export interface GameInfo {
  id: string;
  headers: Record<string, string>;
  start_fen: string;
  moves: Move[];
}

export interface Facts {
  ply: number;
  move_number: number;
  color: Side;
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  eval_before: Score;
  eval_after: Score;
  win_before: number;
  win_after: number;
  win_delta: number;
  classification: Cls;
  is_best: boolean;
  best_move_san: string | null;
  best_move_uci: string | null;
  best_pv_san: string[];
  alt_lines: { san: string; score: Score; pv_san: string[] }[];
  reply_pv_san: string[];
  tactic_themes: string[];
  opening: { eco: string; name: string } | null;
  phase: string;
  is_key_moment: boolean;
}

export interface PlayerSummary {
  name: string;
  elo?: string;
  counts: Record<Cls, number>;
  avg_cp_loss: number;
  rating_estimate: number | null;
}

export interface Summary {
  accuracy: { white: number | null; black: number | null };
  players: Record<Side, PlayerSummary>;
  opening: { eco: string; name: string } | null;
  key_moments: number[];
  result: string;
}

export interface Analysis {
  game: GameInfo;
  facts: Facts[];
  wins: number[];
  evals: Score[];
  summary: Summary;
}

export interface Line { uci: string[]; san: string[]; score: Score; depth: number }
