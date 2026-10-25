import { useMemo, useRef, useState } from "react";
import type { Cls, Facts } from "../lib/types";
import { CLASS_COLOR } from "./ClassIcon";

const W = 600;
const H = 100;
const MARKED: Cls[] = ["brilliant", "great", "miss", "mistake", "blunder"];

interface Props {
  wins: (number | null)[];
  facts?: Facts[];
  ply: number;
  onPick?: (ply: number) => void;
}

/** Win-probability area chart: White's share rises above the centre line, Black's below. */
export function EvalGraph({ wins, facts, ply, onPick }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const n = Math.max(1, wins.length - 1);
  const x = (i: number) => (i / n) * W;
  const y = (w: number) => H - (w / 100) * H;

  const area = useMemo(() => {
    let d = `M0 ${H}`;
    let last = 50;
    wins.forEach((w, i) => {
      last = w ?? last;
      d += ` L${x(i).toFixed(1)} ${y(last).toFixed(1)}`;
    });
    return `${d} L${W} ${H} Z`;
  }, [wins]);

  const pick = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    return Math.round(((clientX - r.left) / r.width) * n);
  };

  // Dots live outside the stretched SVG so they stay round at any width.
  return (
    <div className="eval-graph" onMouseMove={(e) => setHover(pick(e.clientX))} onMouseLeave={() => setHover(null)}
      onClick={(e) => onPick?.(pick(e.clientX))} role="slider" aria-label="Evaluation graph" aria-valuenow={ply}
      aria-valuemin={0} aria-valuemax={n} tabIndex={-1}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <rect width={W} height={H} className="eg-black" />
        <path d={area} className="eg-white" />
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="eg-mid" vectorEffect="non-scaling-stroke" />
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1="0" y2={H} className="eg-hover" vectorEffect="non-scaling-stroke" />}
        <line x1={x(ply)} x2={x(ply)} y1="0" y2={H} className="eg-cursor" vectorEffect="non-scaling-stroke" />
      </svg>
      {facts?.filter((f) => MARKED.includes(f.classification)).map((f) => (
        <span key={f.ply} className="eg-dot" title={`${f.move_number}${f.color === "white" ? "." : "..."} ${f.san}`}
          style={{ left: `${(x(f.ply) / W) * 100}%`, top: `${(y(wins[f.ply] ?? 50) / H) * 100}%`,
            background: CLASS_COLOR[f.classification] }} />
      ))}
    </div>
  );
}
