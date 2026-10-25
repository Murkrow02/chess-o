import { useEffect, useState } from "react";
import { api, type Drill } from "../lib/api";
import { uciSquares } from "../lib/chess";
import { t } from "../lib/i18n";
import { playMove, playVerdict } from "../lib/sound";
import { useStore } from "../lib/store";
import { Board, type BoardMove } from "./Board";
import { Giacomino } from "./Giacomino";
import { Icon } from "./Icon";

export function Drills() {
  const [queue, setQueue] = useState<Drill[] | null>(null);
  const [state, setState] = useState<"solve" | "right" | "wrong" | "shown">("solve");
  const [nonce, setNonce] = useState(0);
  const { openGame } = useStore();

  useEffect(() => {
    api.drillsDue().then(setQueue).catch(() => setQueue([]));
  }, []);

  if (!queue) return <div className="loading"><Giacomino mood="thinking" /></div>;
  const d = queue[0];

  const grade = async (g: number) => {
    await api.reviewDrill(d.id, g);
    setQueue(queue.slice(1));
    setState("solve");
  };

  const onMove = (m: BoardMove) => {
    playMove(m);
    if (m.uci === d.solution_uci) {
      playVerdict("great");
      setState("right");
    } else {
      setState("wrong");
      setTimeout(() => setNonce((x) => x + 1), 600);
    }
  };

  return (
    <div className="drills">
      <div className="board-col">
        {d ? (
          <Board fen={d.fen} orientation={d.side} onMove={state === "solve" || state === "wrong" ? onMove : undefined}
            nonce={nonce} shapes={state === "shown" || state === "right" ? [{ ...arrowOf(d.solution_uci), brush: "green" }] : []} />
        ) : <div className="board-placeholder" />}
      </div>
      <aside className="panel">
        <h1>{t("drills.title")}</h1>
        <p className="muted">{t("drills.intro")}</p>
        {!d ? (
          <div className="coach-row"><Giacomino mood="happy" /><div className="bubble"><p>{t("drills.none")}</p></div></div>
        ) : (
          <>
            <p className="due">{t("drills.due", { n: queue.length })}</p>
            <div className="coach-row">
              <Giacomino mood={state === "right" ? "wow" : state === "wrong" ? "worried" : "thinking"} />
              <div className="bubble">
                <p>
                  {state === "right" ? t("drills.correct") : state === "wrong" ? t("drills.wrong")
                    : state === "shown" ? `${d.solution_san}` : t("drills.find", { side: t(`home.${d.side}`) })}
                </p>
                <small className="muted">
                  <button className="link" onClick={() => openGame(d.game_id)}>{t("drills.from", { opponent: d.opponent })}</button>
                </small>
              </div>
            </div>
            {state === "solve" || state === "wrong" ? (
              <div className="actions"><button onClick={() => setState("shown")}><Icon name="eye" />{t("drills.reveal")}</button></div>
            ) : (
              <div className="actions grades">
                <button onClick={() => grade(0)}>{t("drills.again")}</button>
                <button onClick={() => grade(1)}>{t("drills.hard")}</button>
                <button className="primary" onClick={() => grade(2)}>{t("drills.good")}</button>
                <button onClick={() => grade(3)}>{t("drills.easy")}</button>
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
}

const arrowOf = (uci: string) => {
  const [orig, dest] = uciSquares(uci);
  return { orig, dest };
};
