import { useEffect, useRef, useState } from "react";
import { stream } from "../lib/api";
import { t } from "../lib/i18n";
import { playBubble } from "../lib/sound";
import { Icon } from "./Icon";

interface Turn { role: "player" | "coach"; text: string; streaming?: boolean }

// Conversations per move for the session, so stepping away and back keeps them.
const threads = new Map<string, Turn[]>();

/** Follow-up questions about the move on screen. `base` is the ask endpoint, `intro` the explanation shown above. */
export function Ask({ base, intro }: { base: string; intro: string }) {
  const [turns, setTurns] = useState<Turn[]>(() => threads.get(base) ?? []);
  const [question, setQuestion] = useState("");
  const close = useRef<(() => void) | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns(threads.get(base) ?? []);
    setQuestion("");
    return () => close.current?.();
  }, [base]);

  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ block: "nearest" });  // never jump on an empty thread
  }, [turns]);

  const save = (next: Turn[]) => {
    threads.set(base, next);
    setTurns(next);
  };

  const busy = turns.some((x) => x.streaming);

  const send = () => {
    const q = question.trim();
    if (!q || busy) return;
    const history = [{ role: "coach", text: intro }, ...turns].slice(-6).map(({ role, text }) => ({ role, text }));
    let list: Turn[] = [...turns, { role: "player", text: q }, { role: "coach", text: "", streaming: true }];
    save(list);
    setQuestion("");
    const patch = (fn: (last: Turn) => Turn) => {
      list = [...list.slice(0, -1), fn(list[list.length - 1])];
      save(list);
    };
    let first = true;
    const params = new URLSearchParams({ q, h: JSON.stringify(history) });
    close.current = stream(`${base}${base.includes("?") ? "&" : "?"}${params}`, {
      onEvent: (event, data) => {
        if (event === "token") {
          if (first) { first = false; playBubble(); }
          patch((last) => ({ ...last, text: last.text + data }));
        } else if (event === "replace") patch((last) => ({ ...last, text: data.text }));
        else if (event === "done") patch((last) => ({ ...last, text: last.text.trim(), streaming: false }));
      },
      onError: () => patch((last) => ({ ...last, text: last.text || t("ask.failed"), streaming: false })),
    }, ["token", "replace", "done"]);
  };

  return (
    <div className="ask">
      {turns.map((turn, i) => (
        <p key={i} className={`turn ${turn.role} ${turn.streaming ? "streaming" : ""}`}>
          {turn.text || (turn.streaming ? <span className="dots" aria-label={t("review.thinking")}><i /><i /><i /></span> : null)}
        </p>
      ))}
      <div ref={end} />
      <form onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300}
          placeholder={t("ask.placeholder")} aria-label={t("ask.placeholder")} />
        <button className="primary icon-only" disabled={!question.trim() || busy} title={t("ask.send")} aria-label={t("ask.send")}>
          <Icon name="send" />
        </button>
      </form>
    </div>
  );
}
