import { Fragment, useEffect, useRef } from "react";
import { t } from "../lib/i18n";
import { useStore } from "../lib/store";
import type { Cls, Facts, Move } from "../lib/types";
import { ClassIcon } from "./ClassIcon";

// "Best" and the quiet grades would put an icon on nearly every move; keep the list readable.
const QUIET: Cls[] = ["best", "excellent", "good"];

export function MoveList({ moves, facts }: { moves: Move[]; facts?: Facts[] }) {
  const { ply, setPly, explore, exploreCursor, analysis } = useStore();
  const box = useRef<HTMLDivElement>(null);
  const keys = new Set(analysis?.summary.key_moments ?? []);

  useEffect(() => {
    box.current?.querySelector(".mv.active")?.scrollIntoView({ block: "nearest" });
  }, [ply, explore?.cursor]);

  // Group by move number, read from each move's resulting FEN (works for games set up from a FEN too).
  const rows = new Map<number, { white?: Move; black?: Move }>();
  for (const m of moves) {
    const [, turn, , , , full] = m.fen.split(" ");
    const whiteMoved = turn === "b";
    const number = whiteMoved ? Number(full) : Number(full) - 1;
    const row = rows.get(number) ?? {};
    row[whiteMoved ? "white" : "black"] = m;
    rows.set(number, row);
  }

  const cell = (m: Move | undefined) => {
    if (!m) return <span className="mv empty" />;
    const f = facts?.[m.ply - 1];
    const cls = f?.classification;
    return (
      <button className={`mv ${m.ply === ply && !explore ? "active" : ""} ${cls ? `c-${cls}` : ""}`}
        onClick={() => setPly(m.ply)}>
        {cls && !QUIET.includes(cls) && <ClassIcon cls={cls} size={15} title={t(`classes.${cls}`)} />}
        <span className="san">{m.san}</span>
        {keys.has(m.ply) && <span className="key-dot" title={t("review.keyMoment")} />}
      </button>
    );
  };

  const variation = (afterPly: number) => {
    if (!explore || explore.basePly !== afterPly) return null;
    return (
      <div className="variation">
        {explore.moves.map((m, i) => (
          <button key={i} className={`vmv ${explore.cursor === i + 1 ? "active" : ""}`} onClick={() => exploreCursor(i + 1)}>
            {m.san}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div className="move-list" ref={box}>
      {variation(0)}
      {[...rows.entries()].map(([number, row]) => (
        <Fragment key={number}>
          <div className="mv-row">
            <span className="mv-num">{number}.</span>
            {row.white ? cell(row.white) : <span className="mv empty">…</span>}
            {cell(row.black)}
          </div>
          {row.white && variation(row.white.ply)}
          {row.black && variation(row.black.ply)}
        </Fragment>
      ))}
    </div>
  );
}
