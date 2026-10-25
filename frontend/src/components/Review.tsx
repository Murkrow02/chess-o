import { useEffect, useMemo, useRef, useState } from "react";
import type { DrawShape } from "chessground/draw";
import type { Key } from "chessground/types";
import { Chess } from "chessops/chess";
import { parseFen } from "chessops/fen";
import { parseSan } from "chessops/san";
import { makeUci } from "chessops/util";
import { api, type AheadState } from "../lib/api";
import { evalLabel, uciSquares } from "../lib/chess";
import { t } from "../lib/i18n";
import { playMove, playVerdict, setSound, soundOn } from "../lib/sound";
import { useStore } from "../lib/store";
import type { Facts, Score } from "../lib/types";
import { useCoach } from "../lib/useCoach";
import { Board, type BoardMove } from "./Board";
import { ClassIcon, classIconSvg } from "./ClassIcon";
import { EvalBar } from "./EvalBar";
import { EvalGraph } from "./EvalGraph";
import { Giacomino, moodFor, type Mood } from "./Giacomino";
import { MoveList } from "./MoveList";
import { Summary } from "./Summary";
import { Icon } from "./Icon";
import { Ask } from "./Ask";

function sanToUci(fen: string, san: string): string | null {
  const pos = Chess.fromSetup(parseFen(fen).unwrap()).unwrap();
  const move = parseSan(pos, san);
  return move ? makeUci(move) : null;
}

const badge = (square: Key, cls: Facts["classification"]): DrawShape => ({
  orig: square,
  customSvg: {
    html: `<svg width="100" height="100" viewBox="0 0 100 100"><g transform="translate(62 -6) scale(1.6)">${classIconSvg(cls).replace(/^<svg[^>]*>|<\/svg>$/g, "")}</g></svg>`,
  },
});

const arrow = (uci: string, brush: string): DrawShape => {
  const [orig, dest] = uciSquares(uci);
  return { orig, dest, brush };
};

const BAD = ["inaccuracy", "mistake", "miss", "blunder"];

export function Review() {
  const s = useStore();
  const { game, analysis, ply, mode, explore, retry, showBest, orientation, side, progress, liveWins } = s;
  const [nonce, bump] = useState(0);
  const lastPly = useRef(ply);

  const moves = game?.moves ?? [];
  const facts = analysis?.facts;
  const f: Facts | undefined = ply > 0 ? facts?.[ply - 1] : undefined;
  const fenAt = (p: number) => (p === 0 ? game!.start_fen : moves[p - 1].fen);

  // Coach text for whatever is on screen.
  const coachUrl = useMemo(() => {
    if (!analysis || !game || !s.talk) return null;
    if (mode === "explore" && explore && explore.cursor > 0) {
      const m = explore.moves[explore.cursor - 1];
      const before = explore.cursor === 1 ? fenAt(explore.basePly) : explore.moves[explore.cursor - 2].fen;
      return `/api/coach/explore?fen=${encodeURIComponent(before)}&uci=${m.uci}${side ? `&side=${side}` : ""}`;
    }
    if (mode === "review" && ply > 0) return `/api/games/${game.id}/coach/${ply}?kind=${showBest && !f?.is_best ? "best" : "move"}`;
    return null;
  }, [analysis, game, mode, explore, ply, showBest, side, s.talk]);
  const coach = useCoach(coachUrl);
  const askBase = coachUrl && (mode === "explore"
    ? coachUrl.replace("/api/coach/explore?", "/api/coach/explore/ask?")
    : `/api/games/${game?.id}/ask/${ply}`);

  // Sounds when stepping through the game.
  useEffect(() => {
    if (!game || mode === "summary") return;
    if (ply > 0 && ply === lastPly.current + 1) {
      const m = moves[ply - 1];
      playMove({ capture: m.san.includes("x"), check: /[+#]/.test(m.san), castle: m.san.startsWith("O-O") });
      if (f) playVerdict(f.classification);
    }
    lastPly.current = ply;
  }, [ply, mode]);

  // Keyboard navigation.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea")) return;
      const st = useStore.getState();
      if (e.key === "ArrowRight") st.mode === "summary" ? (st.setMode("review"), st.setPly(1)) : st.step(1);
      else if (e.key === "ArrowLeft") st.step(-1);
      else if (e.key === "ArrowUp" || e.key === "Home") st.setPly(0);
      else if (e.key === "ArrowDown" || e.key === "End") st.setPly(moves.length);
      else if (e.key === "f") st.flip();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [moves.length]);

  if (!game) return <div className="loading"><Giacomino mood="thinking" /></div>;

  // What the board shows.
  let fen = fenAt(ply);
  let lastMove: [Key, Key] | undefined = ply > 0 ? uciSquares(moves[ply - 1].uci) : undefined;
  let score: Score | undefined = analysis ? analysis.evals[ply] : undefined;
  const shapes: DrawShape[] = [];

  if (mode === "retry" && retry) {
    fen = fenAt(retry.ply - 1);
    lastMove = retry.ply > 1 ? uciSquares(moves[retry.ply - 2].uci) : undefined;
    score = analysis?.evals[retry.ply - 1];
    if (retry.pieceSquare) shapes.push({ orig: retry.pieceSquare as Key, brush: "green" });
    if (retry.hintSquare) shapes.push({ orig: retry.hintSquare as Key, brush: "blue" });
  } else if (mode === "explore" && explore) {
    if (explore.cursor > 0) {
      const m = explore.moves[explore.cursor - 1];
      fen = m.fen;
      lastMove = uciSquares(m.uci);
      if (coach.facts && coach.facts.uci === m.uci) {
        score = coach.facts.eval_after;
        shapes.push(badge(lastMove[1], coach.facts.classification));
        if (!coach.facts.is_best && coach.facts.best_move_uci) shapes.push(arrow(coach.facts.best_move_uci, "green"));
      }
    } else {
      fen = fenAt(explore.basePly);
    }
  } else if (f) {
    if (showBest && !f.is_best && f.best_move_uci) {
      fen = f.fen_before;
      lastMove = ply > 1 ? uciSquares(moves[ply - 2].uci) : undefined;
      score = f.eval_before;
      shapes.push(arrow(f.best_move_uci, "green"), arrow(f.uci, "paleRed"));
    } else {
      shapes.push(badge(uciSquares(f.uci)[1], f.classification));
      if (BAD.includes(f.classification) && f.reply_pv_san[0]) {
        const reply = sanToUci(f.fen_after, f.reply_pv_san[0]);
        if (reply) shapes.push(arrow(reply, "red"));
      }
    }
  }

  const onBoardMove = async (m: BoardMove) => {
    playMove(m);
    if (mode === "retry" && retry) {
      const r = await api.retry(game.id, retry.ply, m.uci);
      playVerdict(r.verdict === "wrong" ? "mistake" : "great");
      s.setRetry({ ...retry, verdict: r.verdict, text: r.text });
      if (r.verdict === "wrong") setTimeout(() => bump((x) => x + 1), 700);
      return;
    }
    s.pushExplore({ san: m.san, uci: m.uci, fen: m.fen });
  };

  const header = (() => {
    if (mode === "explore" && explore && explore.cursor > 0) {
      const m = explore.moves[explore.cursor - 1];
      const cf = coach.facts?.uci === m.uci ? coach.facts : undefined;
      return { cls: cf?.classification, title: cf ? t(`verdict.${cf.classification}`, { san: m.san }) : `${t("review.exploring")}: ${m.san}`, ev: cf?.eval_after };
    }
    if (mode === "retry" && retry) {
      const rf = facts![retry.ply - 1];
      return { cls: undefined, title: t("review.retryPrompt", { san: rf.san }), ev: undefined };
    }
    if (f) {
      if (showBest && !f.is_best) return { cls: "best" as const, title: t("review.bestWas", { san: f.best_move_san ?? "" }), ev: f.eval_before };
      return { cls: f.classification, title: t(`verdict.${f.classification}`, { san: f.san }), ev: f.eval_after };
    }
    return null;
  })();

  const bubbleText = mode === "retry" && retry ? (retry.text ?? "") : ply === 0 && mode === "review" ? t("review.start") : coach.text;
  const thinking = coach.streaming && !coach.text;

  return (
    <div className="review">
      <div className="board-col">
        <PlayerStrip name={game.headers[orientation === "white" ? "Black" : "White"]} elo={game.headers[orientation === "white" ? "BlackElo" : "WhiteElo"]} color={orientation === "white" ? "black" : "white"} />
        <div className="board-row">
          <EvalBar score={score} orientation={orientation} />
          <Board fen={fen} orientation={orientation} lastMove={lastMove} shapes={shapes}
            onMove={analysis && mode !== "summary" ? onBoardMove : undefined} nonce={nonce} />
        </div>
        <PlayerStrip name={game.headers[orientation === "white" ? "White" : "Black"]} elo={game.headers[orientation === "white" ? "WhiteElo" : "BlackElo"]} color={orientation} />
      </div>

      <aside className="panel">
        {!analysis ? (
          <Progress progress={progress} wins={liveWins} />
        ) : mode === "summary" ? (
          <Summary analysis={analysis} />
        ) : (
          <>
            {!s.talk && mode !== "retry" ? (
              <Quiet mood={moodFor(header?.cls, false)} header={header}
                best={!showBest && f && !f.is_best && f.best_move_san ? t("review.bestWas", { san: f.best_move_san }) : undefined}
                start={ply === 0 && mode === "review" ? t("review.start") : undefined} />
            ) : <div className="coach-row">
              <Giacomino mood={mode === "retry" ? (retry?.verdict === "correct" ? "wow" : retry?.verdict === "wrong" ? "worried" : "thinking") : moodFor(header?.cls, thinking)} />
              <div className={`bubble ${header?.cls ? `b-${header.cls}` : ""}`} aria-live="polite">
                {header && (
                  <div className="bubble-head">
                    {header.cls && <ClassIcon cls={header.cls} size={22} />}
                    <strong>{header.title}</strong>
                    {header.ev && <span className="ev-chip">{evalLabel(header.ev)}</span>}
                  </div>
                )}
                <p className={coach.streaming ? "streaming" : ""}>
                  {bubbleText || (thinking ? <span className="dots" aria-label={t("review.thinking")}><i /><i /><i /></span> : null)}
                </p>
                {coach.offline && <small className="muted">{t("review.coachOffline")}</small>}
                {coach.sources.length > 0 && (
                  <details className="sources">
                    <summary>{t("review.sources")}</summary>
                    <ul>{coach.sources.map((src, i) => <li key={i}>{src.url ? <a href={src.url} target="_blank" rel="noreferrer">{src.title}</a> : src.title} {src.license && <span className="lic">({src.license})</span>}</li>)}</ul>
                  </details>
                )}
                {askBase && mode !== "retry" && !coach.streaming && coach.text && <Ask base={askBase} intro={coach.text} />}
              </div>
            </div>}
            <Actions f={f} />
            <MoveList moves={moves} facts={facts} />
            <EvalGraph wins={analysis.wins} facts={facts} ply={ply} onPick={s.setPly} />
          </>
        )}
        <NavBar />
      </aside>
    </div>
  );
}

function Actions({ f }: { f?: Facts }) {
  const s = useStore();
  const { mode, retry, explore, showBest, gameId } = s;
  if (mode === "retry" && retry) {
    const askHint = async () => {
      const level = retry.hintLevel + 1;
      const h = await api.hint(gameId!, retry.ply, level);
      s.setRetry({ ...retry, hintLevel: level, text: h.text, pieceSquare: h.piece_square, hintSquare: h.square });
    };
    return (
      <div className="actions">
        <button onClick={() => s.setRetry(null)}><Icon name="back" />{t("review.backToGame")}</button>
        {retry.verdict !== "correct" && retry.hintLevel < 3 && <button onClick={askHint}><Icon name="bulb" />{t("review.hint")} {retry.hintLevel + 1}/3</button>}
        <button className="primary" onClick={() => { s.setRetry(null); s.step(1); }}>{t("review.next")}<Icon name="next" /></button>
      </div>
    );
  }
  if (mode === "explore" && explore) {
    return (
      <div className="actions">
        <button onClick={() => s.setMode("review")}><Icon name="back" />{t("review.backToGame")}</button>
      </div>
    );
  }
  const canRetry = f && !f.is_best && ["inaccuracy", "mistake", "miss", "blunder", "good"].includes(f.classification);
  return (
    <div className="actions">
      <button disabled={!canRetry} onClick={() => f && s.setRetry({ ply: f.ply, hintLevel: 0 })}><Icon name="retry" />{t("review.retry")}</button>
      <button disabled={!f || f.is_best} onClick={s.toggleBest}><Icon name={showBest ? "eyeOff" : "bulb"} />{showBest ? t("review.hideBest") : t("review.showBest")}</button>
      <button className="primary" onClick={() => s.step(1)}>{t("review.next")}<Icon name="next" /></button>
    </div>
  );
}

type Header = { cls?: Facts["classification"] | "best"; title: string; ev?: Score } | null;

/** Giacomino without words: a big fish whose face and badge tell the verdict. */
function Quiet({ mood, header, best, start }: { mood: Mood; header: Header; best?: string; start?: string }) {
  return (
    <div className={`quiet ${header?.cls ? `b-${header.cls}` : ""}`} aria-live="polite">
      <div className="quiet-fish">
        <Giacomino mood={mood} size={168} />
        {header?.cls && <span className="quiet-badge"><ClassIcon cls={header.cls} size={40} /></span>}
      </div>
      {header && (
        <p className="quiet-verdict">
          <strong>{header.title}</strong>
          {header.ev && <span className="ev-chip">{evalLabel(header.ev)}</span>}
        </p>
      )}
      {best && <p className="quiet-best">{best}</p>}
      {start && <p className="quiet-best">{start}</p>}
    </div>
  );
}

/** Bubbles under the Next button: how many of the next moves Giacomino has already explained. */
function Ahead({ id, ply }: { id: string; ply: number }) {
  const [states, setStates] = useState<AheadState[]>([]);
  useEffect(() => {
    let live = true;
    let timer = 0;
    const poll = () => api.ahead(id, ply).then((r) => {
      if (!live) return;
      setStates(r.states);
      if (r.states.some((x) => x !== "ready")) timer = window.setTimeout(poll, 1500);
    }).catch(() => undefined);
    timer = window.setTimeout(poll, 400);  // the coach request for this move queues the look-ahead first
    return () => { live = false; clearTimeout(timer); };
  }, [id, ply]);
  if (!states.length) return null;
  const ready = states.filter((x) => x === "ready").length;
  return (
    <span className="ahead" title={t("review.ahead", { n: ready, total: states.length })}>
      {states.map((x, i) => <i key={i} className={x} />)}
    </span>
  );
}

function NavBar() {
  const s = useStore();
  const n = s.game?.moves.length ?? 0;
  const [sound, set] = useState(soundOn());
  return (
    <div className="navbar">
      <button aria-label={t("review.first")} onClick={() => s.setPly(0)}><Icon name="first" /></button>
      <button aria-label={t("review.prev")} onClick={() => s.step(-1)}><Icon name="prev" /></button>
      <button aria-label={t("review.next")} onClick={() => (s.mode === "summary" ? (s.setMode("review"), s.setPly(1)) : s.step(1))}>
        <Icon name="fwd" />{s.talk && s.game && s.analysis && s.mode === "review" && <Ahead id={s.game.id} ply={s.ply} />}
      </button>
      <button aria-label={t("review.last")} onClick={() => s.setPly(n)}><Icon name="last" /></button>
      <span className="spacer" />
      {s.analysis && s.mode !== "summary" && <button className="txt" title={t("review.summary")} aria-label={t("review.summary")} onClick={() => s.setMode("summary")}><Icon name="list" /></button>}
      <button className="txt" aria-pressed={sound} title={t(sound ? "review.soundOn" : "review.soundOff")} aria-label={t(sound ? "review.soundOn" : "review.soundOff")}
        onClick={() => { setSound(!sound); set(!sound); }}><Icon name={sound ? "soundOn" : "soundOff"} /></button>
      <button className="txt" aria-pressed={!s.talk} title={t(s.talk ? "review.talkOn" : "review.talkOff")} aria-label={t(s.talk ? "review.talkOn" : "review.talkOff")}
        onClick={() => s.setTalk(!s.talk)}><Icon name={s.talk ? "talkOn" : "talkOff"} /></button>
      <button className="txt" title={t("review.flip")} aria-label={t("review.flip")} onClick={s.flip}><Icon name="flip" /></button>
    </div>
  );
}

function PlayerStrip({ name, elo, color }: { name?: string; elo?: string; color: "white" | "black" }) {
  return (
    <div className="player-strip">
      <span className={`pawn-chip ${color}`} />
      <span className="pname">{name ?? "?"}</span>
      {elo && elo !== "?" && <span className="pelo">{elo}</span>}
    </div>
  );
}

function Progress({ progress, wins }: { progress: { phase: string; done: number; total: number } | null; wins: (number | null)[] }) {
  const pct = progress ? Math.round((progress.done / Math.max(1, progress.total)) * 100) : 0;
  return (
    <div className="progress">
      <div className="coach-row">
        <Giacomino mood="thinking" />
        <div className="bubble"><p>{t(`analyzing.${progress?.phase ?? "scan"}`)}…</p></div>
      </div>
      <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${pct}%` }} /></div>
      <EvalGraph wins={wins} ply={0} />
    </div>
  );
}
