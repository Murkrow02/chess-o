// Short synthesized sounds (WebAudio), so no third-party audio files are needed.
let ctx: AudioContext | null = null;
let enabled = (() => {
  try {
    return localStorage.getItem("chesso.sound") !== "off";
  } catch {
    return true;
  }
})();

export const soundOn = () => enabled;
export function setSound(on: boolean) {
  enabled = on;
  try {
    localStorage.setItem("chesso.sound", on ? "on" : "off");
  } catch {
    /* private mode: keep it for this session only */
  }
}

function tone(freq: number, dur: number, type: OscillatorType, gain: number, delay = 0, slide?: number) {
  ctx ??= new AudioContext();
  const t0 = ctx.currentTime + delay;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (slide) osc.frequency.exponentialRampToValueAtTime(slide, t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.005);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

// A wooden "tock": a quick pitch drop with a sine body and a little triangle click.
const knock = (pitch: number, gain = 0.35) => {
  tone(pitch, 0.09, "sine", gain, 0, pitch * 0.55);
  tone(pitch * 3.1, 0.025, "triangle", gain * 0.25);
};

export function playMove(kind: { capture?: boolean; check?: boolean; castle?: boolean }) {
  if (!enabled) return;
  if (kind.check) {
    knock(260);
    tone(880, 0.12, "sine", 0.08, 0.05);
  } else if (kind.capture) {
    knock(190, 0.45);
    knock(240, 0.25);
  } else if (kind.castle) {
    knock(230);
    setTimeout(() => knock(250), 90);
  } else {
    knock(230);
  }
}

export function playVerdict(cls: string) {
  if (!enabled) return;
  if (cls === "brilliant" || cls === "great") {
    [660, 830, 990].forEach((f, i) => tone(f, 0.16, "sine", 0.07, i * 0.07));
  } else if (cls === "blunder") {
    tone(220, 0.35, "sine", 0.09, 0.05, 140); // a sad bubble sinking
  }
}

/** A bubble pop for the coach. */
export function playBubble() {
  if (!enabled) return;
  tone(500, 0.07, "sine", 0.05, 0, 1100);
}
