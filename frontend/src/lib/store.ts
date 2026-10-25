import { create } from "zustand";
import { api, stream } from "./api";
import type { Analysis, GameInfo, Side } from "./types";

export type View = "home" | "review" | "drills" | "profile";
export type Mode = "summary" | "review" | "retry" | "explore";

export interface ExploreMove { san: string; uci: string; fen: string }

interface State {
  view: View;
  gameId: string | null;
  game: GameInfo | null;
  analysis: Analysis | null;
  progress: { phase: string; done: number; total: number } | null;
  liveWins: (number | null)[];
  error: string | null;
  side: Side | null;
  ply: number;
  mode: Mode;
  showBest: boolean;
  orientation: Side;
  keyOnly: boolean;
  explore: { basePly: number; moves: ExploreMove[]; cursor: number } | null;
  retry: { ply: number; hintLevel: number; hintSquare?: string; pieceSquare?: string; verdict?: string; text?: string } | null;
  talk: boolean;  // false: no LLM text, Giacomino reacts with faces and icons only

  go: (view: View) => void;
  openGame: (id: string) => Promise<void>;
  setSide: (side: Side | null) => void;
  setPly: (ply: number) => void;
  step: (delta: number) => void;
  setMode: (mode: Mode) => void;
  toggleBest: () => void;
  flip: () => void;
  startKeyMoments: () => void;
  pushExplore: (m: ExploreMove) => void;
  exploreCursor: (cursor: number) => void;
  setRetry: (r: State["retry"]) => void;
  setTalk: (on: boolean) => void;
}

const talkSaved = (() => {
  try {
    return localStorage.getItem("chesso.talk") !== "off";
  } catch {
    return true;
  }
})();

let closeAnalysis: (() => void) | null = null;

export const useStore = create<State>((set, get) => ({
  view: "home",
  gameId: null,
  game: null,
  analysis: null,
  progress: null,
  liveWins: [],
  error: null,
  side: null,
  ply: 0,
  mode: "summary",
  showBest: false,
  orientation: "white",
  keyOnly: false,
  explore: null,
  retry: null,
  talk: talkSaved,

  go: (view) => {
    set({ view });
    if (view !== "review") location.hash = view === "home" ? "" : `#/${view}`;
  },

  openGame: async (id) => {
    closeAnalysis?.();
    location.hash = `#/game/${id}`;
    set({ view: "review", gameId: id, game: null, analysis: null, progress: null, liveWins: [], error: null,
      ply: 0, mode: "summary", explore: null, retry: null, showBest: false, keyOnly: false });
    const data = await api.game(id);
    const side = (data as { side?: Side | null }).side ?? null;
    set({ game: data.game, side, orientation: side ?? "white", liveWins: new Array(data.game.moves.length + 1).fill(null) });
    if (data.facts) {
      set({ analysis: data as Analysis });
      return;
    }
    closeAnalysis = stream(`/api/games/${id}/analyze`, {
      onEvent: (event, payload) => {
        if (get().gameId !== id) return;
        if (event === "progress") set({ progress: payload });
        else if (event === "eval") {
          const wins = [...get().liveWins];
          wins[payload.index] = payload.win;
          set({ liveWins: wins });
        } else if (event === "analysis") set({ analysis: payload, progress: null });
      },
      onError: () => {
        if (!get().analysis) set({ error: "network" });
      },
    }, ["progress", "eval", "analysis"]);
  },

  setSide: (side) => {
    const id = get().gameId;
    set({ side, orientation: side ?? get().orientation });
    if (id) api.setSide(id, side).catch(() => undefined);
  },

  setPly: (ply) => {
    const n = get().game?.moves.length ?? 0;
    set({ ply: Math.max(0, Math.min(n, ply)), explore: null, retry: null, showBest: false,
      mode: get().mode === "summary" ? "summary" : "review" });
  },

  step: (delta) => {
    const s = get();
    if (s.explore) {
      const cursor = Math.max(0, Math.min(s.explore.moves.length, s.explore.cursor + delta));
      if (cursor === 0 && delta < 0 && s.explore.cursor === 0) set({ explore: null, mode: "review" });
      else set({ explore: { ...s.explore, cursor } });
      return;
    }
    if (s.keyOnly && s.analysis) {
      const keys = s.analysis.summary.key_moments;
      const target = delta > 0 ? keys.find((k) => k > s.ply) : [...keys].reverse().find((k) => k < s.ply);
      if (target !== undefined) get().setPly(target);
      return;
    }
    get().setPly(s.ply + delta);
  },

  setMode: (mode) => set({ mode, explore: mode === "explore" ? get().explore : null,
    retry: mode === "retry" ? get().retry : null }),
  toggleBest: () => set({ showBest: !get().showBest }),
  flip: () => set({ orientation: get().orientation === "white" ? "black" : "white" }),

  startKeyMoments: () => {
    const keys = get().analysis?.summary.key_moments ?? [];
    set({ mode: "review", keyOnly: true });
    get().setPly(keys[0] ?? 1);
  },

  pushExplore: (m) => {
    const s = get();
    const base = s.explore ?? { basePly: s.retry ? s.retry.ply - 1 : s.ply, moves: [], cursor: 0 };
    const moves = [...base.moves.slice(0, base.cursor), m];
    set({ explore: { ...base, moves, cursor: moves.length }, mode: "explore", retry: null, showBest: false });
  },

  exploreCursor: (cursor) => {
    const e = get().explore;
    if (e) set({ explore: { ...e, cursor } });
  },

  setRetry: (retry) => set({ retry, mode: retry ? "retry" : "review", explore: null, showBest: false }),

  setTalk: (on) => {
    try {
      localStorage.setItem("chesso.talk", on ? "on" : "off");
    } catch {
      /* private mode: keep it for this session only */
    }
    set({ talk: on });
  },
}));
