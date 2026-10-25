import { useEffect, useState } from "react";
import { stream } from "./api";
import { playBubble } from "./sound";
import type { Facts } from "./types";

export interface CoachText {
  text: string;
  streaming: boolean;
  offline: boolean;
  sources: { title: string; source: string; url?: string; license?: string }[];
  facts?: Facts;
}

const EMPTY: CoachText = { text: "", streaming: false, offline: false, sources: [] };
const cache = new Map<string, CoachText>();

/** Stream the coach's words for `url`, caching finished texts for the session. */
export function useCoach(url: string | null): CoachText {
  const [state, setState] = useState<CoachText>(() => (url && cache.get(url)) || EMPTY);

  useEffect(() => {
    if (!url) {
      setState(EMPTY);
      return;
    }
    const hit = cache.get(url);
    if (hit) {
      setState(hit);
      return;
    }
    let current: CoachText = { ...EMPTY, streaming: true };
    setState(current);
    let first = true;
    const update = (patch: Partial<CoachText>) => {
      current = { ...current, ...patch };
      setState(current);
    };
    const close = stream(url, {
      onEvent: (event, data) => {
        if (event === "token") {
          if (first) {
            first = false;
            playBubble();
          }
          update({ text: current.text + data });
        } else if (event === "replace") update({ text: data.text, offline: Boolean(data.offline) });
        else if (event === "sources") update({ sources: data });
        else if (event === "facts") update({ facts: data });
        else if (event === "done") {
          update({ streaming: false, text: current.text.trim() });
          cache.set(url, current);
        }
      },
      onError: () => update({ streaming: false }),
    }, ["token", "replace", "sources", "facts", "done"]);
    return close;
  }, [url]);

  return state;
}
