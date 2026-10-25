import { evalLabel, winWhite } from "../lib/chess";
import type { Score, Side } from "../lib/types";

export function EvalBar({ score, orientation }: { score?: Score; orientation: Side }) {
  const w = score ? winWhite(score) : 50;
  const whiteAhead = w >= 50;
  return (
    <div className={`eval-bar ${orientation === "black" ? "flipped" : ""}`} aria-label={`Evaluation ${evalLabel(score)}`}>
      <div className="eval-white" style={{ height: `${w}%` }} />
      <span className={`eval-num ${whiteAhead ? "on-white" : "on-black"}`}>{evalLabel(score).replace("+", "")}</span>
    </div>
  );
}
