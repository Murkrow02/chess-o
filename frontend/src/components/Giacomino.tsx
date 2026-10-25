import { t } from "../lib/i18n";
import type { Cls } from "../lib/types";

export type Mood = "happy" | "wow" | "neutral" | "worried" | "shocked" | "smug" | "thinking";

export function moodFor(cls: Cls | undefined, thinking: boolean): Mood {
  if (thinking) return "thinking";
  switch (cls) {
    case "brilliant":
    case "great":
      return "wow";
    case "best":
    case "excellent":
      return "happy";
    case "inaccuracy":
    case "miss":
      return "smug";
    case "mistake":
      return "worried";
    case "blunder":
      return "shocked";
    default:
      return "neutral";
  }
}

// Pupil offset, brow angle and mouth per mood. The eye sits at (78, 42).
const FACE: Record<Mood, { pupil: [number, number]; pr: number; brow: string; mouth: string; lid?: boolean; tooth?: boolean }> = {
  neutral: { pupil: [2, 1], pr: 5, brow: "M66 22 L88 23", mouth: "M94 61 q5 3 10 0" },
  happy: { pupil: [2, 0], pr: 5.5, brow: "M66 23 Q77 17 88 22", mouth: "M92 58 q7 9 14 0 z", tooth: true },
  wow: { pupil: [1, -1], pr: 6.5, brow: "M66 19 Q77 13 88 18", mouth: "M99 61 m-5 0 a5 6 0 1 0 10 0 a5 6 0 1 0 -10 0" },
  worried: { pupil: [-1, 2], pr: 5, brow: "M66 20 L88 25", mouth: "M92 62 q3 -3 6 0 q3 3 6 0 q2 -2 4 0" },
  shocked: { pupil: [0, 0], pr: 3, brow: "M66 16 Q77 11 88 16", mouth: "M99 63 m-6 0 a6 7 0 1 0 12 0 a6 7 0 1 0 -12 0" },
  smug: { pupil: [3, 2], pr: 5, brow: "M66 24 L88 20", mouth: "M93 61 q6 2 11 -3", lid: true },
  thinking: { pupil: [3, -4], pr: 5, brow: "M66 21 Q77 17 88 21", mouth: "M99 61 m-2.5 0 a2.5 2.5 0 1 0 5 0 a2.5 2.5 0 1 0 -5 0" },
};

/** Giacomino: a small, slightly goofy fish with crooked glasses who knows a lot about chess. */
export function Giacomino({ mood = "neutral", size = 104 }: { mood?: Mood; size?: number }) {
  const f = FACE[mood];
  return (
    <svg className={`giacomino mood-${mood}`} width={size} height={size * 0.86} viewBox="0 0 124 106" role="img"
      aria-label={t("coach.looks", { mood })}>
      <g className="giacomino-body">
        {/* tail */}
        <path d="M30 52 L6 32 Q2 52 6 74 Z" fill="#2bb3a3" />
        {/* dorsal fin */}
        <path d="M46 26 Q60 4 84 18 Q66 20 58 30 Z" fill="#2bb3a3" />
        {/* body */}
        <path d="M24 54 C24 28 52 16 78 18 C102 20 116 36 116 54 C116 74 100 90 74 90 C48 90 24 80 24 54 Z" fill="#46d9c5" />
        {/* belly */}
        <path d="M40 72 C56 86 92 88 108 70 C100 84 84 90 72 90 C56 90 44 84 40 72 Z" fill="#ccf6ee" />
        {/* scales */}
        <path d="M42 46 q5 5 0 10 M50 40 q5 5 0 10 M50 56 q5 5 0 10" stroke="#2bb3a3" strokeWidth="2.2" fill="none"
          strokeLinecap="round" />
        {/* side fin */}
        <path className="giacomino-fin" d="M60 66 Q70 60 76 70 Q68 76 60 66 Z" fill="#2bb3a3" />
        {/* cheek */}
        <circle cx="96" cy="52" r="5" fill="#ff9e9e" opacity=".45" />
        {/* eye */}
        <circle cx="78" cy="42" r="11" fill="#fff" />
        <circle cx={78 + f.pupil[0]} cy={42 + f.pupil[1]} r={f.pr} fill="#14212b" />
        <circle cx={80 + f.pupil[0]} cy={40 + f.pupil[1]} r={1.6} fill="#fff" />
        {f.lid && <path d="M66 42 A12 12 0 0 1 90 42 Z" fill="#46d9c5" />}
        {/* crooked round glasses: the wise part */}
        <g transform="rotate(-7 78 42)" fill="none" stroke="#14212b" strokeWidth="2.4">
          <circle cx="78" cy="42" r="14" />
          <path d="M64 41 L46 37" strokeLinecap="round" />
        </g>
        {/* brow */}
        <path d={f.brow} stroke="#14212b" strokeWidth="3" fill="none" strokeLinecap="round" />
        {/* mouth */}
        <path d={f.mouth} stroke="#14212b" strokeWidth="2.6" fill={mood === "happy" ? "#14212b" : "none"}
          strokeLinecap="round" strokeLinejoin="round" />
        {/* one goofy tooth */}
        {f.tooth && <rect x="96.5" y="58" width="4" height="4" rx="1" fill="#fff" />}
      </g>
      <g className="giacomino-bubbles" fill="none" stroke="#7fe8da" strokeWidth="1.6">
        <circle cx="112" cy="40" r="3" />
        <circle cx="118" cy="26" r="4.2" />
        <circle cx="111" cy="12" r="2.4" />
      </g>
    </svg>
  );
}
