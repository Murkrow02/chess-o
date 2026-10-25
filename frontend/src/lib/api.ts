import type { Analysis, GameInfo, Line, Score } from "./types";

// Every call is relative, so the same build works behind any host or reverse proxy.
async function json<T>(res: Promise<Response>): Promise<T> {
  const r = await res;
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? r.statusText);
  }
  return r.json();
}

const post = (url: string, body: unknown) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export type AheadState = "ready" | "writing" | "queued" | "idle";

export const api = {
  createGame: (pgn: string) => json<GameInfo>(post("/api/games", { pgn })),
  game: (id: string) => json<Partial<Analysis> & { game: GameInfo }>(fetch(`/api/games/${id}`)),
  games: (params: { player?: string; analyzed?: boolean; limit?: number } = {}) =>
    json<StoredGame[]>(fetch(`/api/games?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]))}`)),
  account: () => json<{ account: Account | null }>(fetch("/api/account/chesscom")),
  linkAccount: (username: string) =>
    json<{ account: Account }>(fetch("/api/account/chesscom", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) })),
  unlinkAccount: () => json(fetch("/api/account/chesscom", { method: "DELETE" })),
  syncAccount: (force = false) =>
    json<{ account: Account; added: number }>(post(`/api/account/chesscom/sync?force=${force}`, {})),
  importGames: (site: string, user: string) =>
    json<{ pgn: string; white: string; black: string; result: string; date: number; speed: string; url: string }[]>(
      fetch(`/api/import/${site}/${encodeURIComponent(user)}`)),
  position: (fen: string, multipv = 3, depth?: number) =>
    json<{ lines: Line[] }>(post("/api/engine/position", { fen, multipv, depth })),
  setSide: (id: string, side: string | null) => json(post(`/api/games/${id}/side`, { side })),
  ahead: (id: string, ply: number) =>
    json<{ plies: number[]; states: AheadState[] }>(fetch(`/api/games/${id}/ahead/${ply}`)),
  hint: (id: string, ply: number, level: number) =>
    json<{ text: string; square?: string; piece_square?: string; uci?: string }>(fetch(`/api/games/${id}/hint/${ply}?level=${level}`)),
  retry: (id: string, ply: number, uci: string) =>
    json<{ verdict: "correct" | "close" | "wrong"; text: string; san: string; reply?: string; score: Score }>(
      post(`/api/games/${id}/retry/${ply}`, { uci })),
  drillsDue: () => json<Drill[]>(fetch("/api/drills/due")),
  drillsStats: () => json<{ total: number; due: number }>(fetch("/api/drills/stats")),
  reviewDrill: (id: number, grade: number) => json(post(`/api/drills/${id}/review`, { grade })),
  profile: () => json<Profile>(fetch("/api/profile")),
  clearData: () => json(fetch("/api/data", { method: "DELETE" })),
};

export interface StoredGame {
  id: string; headers: Record<string, string>; summary: Analysis["summary"] | null; created_at: number;
  side: "white" | "black" | null;
}

export interface Account {
  username: string; name: string | null; avatar: string | null; url: string | null;
  linked_at: number; last_end: number; checked_at: number;
}

export interface Drill {
  id: number; game_id: string; ply: number; fen: string; played_san: string;
  solution_uci: string; solution_san: string; classification: string; themes: string[]; phase: string;
  opponent: string; side: "white" | "black";
}

export interface Profile {
  games: number;
  avg_accuracy: number | null;
  by_phase: { phase: string; moves: number; avg_loss: number; mistakes: number }[];
  by_theme: { theme: string; count: number }[];
  counts: Record<string, number>;
}

export interface StreamHandlers {
  onEvent: (event: string, data: any) => void;
  onError?: (err: Event) => void;
}

/** Subscribe to a server-sent-events endpoint; returns a function that closes it. */
export function stream(url: string, { onEvent, onError }: StreamHandlers, events: string[]): () => void {
  const es = new EventSource(url);
  for (const name of events) {
    es.addEventListener(name, (e) => onEvent(name, JSON.parse((e as MessageEvent).data)));
  }
  es.addEventListener("done", () => es.close());
  es.onerror = (e) => {
    es.close();
    onError?.(e);
  };
  return () => es.close();
}
