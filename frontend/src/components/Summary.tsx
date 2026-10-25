import { t } from "../lib/i18n";
import { useStore } from "../lib/store";
import { CLASSES, type Analysis, type Side } from "../lib/types";
import { ClassIcon } from "./ClassIcon";
import { EvalGraph } from "./EvalGraph";
import { Giacomino } from "./Giacomino";
import { Icon } from "./Icon";

function verdictText(a: Analysis, side: Side | null): string {
  const s = a.summary;
  const opening = s.opening ? `${s.opening.name}. ` : "";
  const turning = s.key_moments[0];
  const f = turning ? a.facts[turning - 1] : null;
  const turn = f ? t("summary.turn", { move: `${f.move_number}${f.color === "white" ? "." : "..."} ${f.san}` }) : "";
  if (side) {
    const mine = s.accuracy[side] ?? 0;
    const theirs = s.accuracy[side === "white" ? "black" : "white"] ?? 0;
    const mood = mine >= theirs + 5 ? "better" : mine + 5 < theirs ? "worse" : "close";
    return `${opening}${t(`summary.${mood}`)}${turn}`;
  }
  return `${opening}${t("summary.neutral", { white: s.accuracy.white ?? "–", black: s.accuracy.black ?? "–" })}${turn}`;
}

export function Summary({ analysis }: { analysis: Analysis }) {
  const { side, setSide, setMode, setPly, startKeyMoments, ply } = useStore();
  const s = analysis.summary;
  const sides: Side[] = ["white", "black"];

  return (
    <div className="summary">
      <div className="coach-row">
        <Giacomino mood="happy" />
        <div className="bubble"><p>{verdictText(analysis, side)}</p></div>
      </div>

      <div className="side-pick" role="radiogroup" aria-label={t("home.youAre")}>
        <span>{t("home.youAre")}</span>
        {(["white", "black", null] as (Side | null)[]).map((v) => (
          <button key={String(v)} role="radio" aria-checked={side === v} className={side === v ? "on" : ""}
            onClick={() => setSide(v)}>
            {v ? t(`home.${v}`) : t("home.neither")}
          </button>
        ))}
      </div>

      <EvalGraph wins={analysis.wins} facts={analysis.facts} ply={ply} onPick={(p) => { setMode("review"); setPly(p); }} />

      <table className="sum-table">
        <thead>
          <tr>
            <th />
            {sides.map((c) => (
              <th key={c} className={side === c ? "me" : ""}>
                <span className={`pawn-chip ${c}`} />
                {s.players[c].name}
                {s.players[c].elo && <small> {s.players[c].elo}</small>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="acc-row">
            <td>{t("summary.accuracy")}</td>
            {sides.map((c) => <td key={c}><span className={`acc ${c}`}>{s.accuracy[c] ?? "–"}</span></td>)}
          </tr>
          <tr>
            <td title={t("summary.estimateHint")}>{t("summary.estimate")}</td>
            {sides.map((c) => <td key={c} className="est">{s.players[c].rating_estimate ?? "–"}</td>)}
          </tr>
          {CLASSES.map((cls) => (
            <tr key={cls} className="cls-row">
              <td><ClassIcon cls={cls} size={18} /> {t(`classes.${cls}`)}</td>
              {sides.map((c) => (
                <td key={c} className={`c-${cls} ${s.players[c].counts[cls] ? "" : "zero"}`}>{s.players[c].counts[cls]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="sum-actions">
        <button className="primary big" onClick={() => { setMode("review"); setPly(1); }}><Icon name="play" />{t("summary.start")}</button>
        {s.key_moments.length > 0 && (
          <button className="ghost" onClick={startKeyMoments}><Icon name="key" />{t("summary.keyMoments")} ({s.key_moments.length})</button>
        )}
      </div>
    </div>
  );
}
