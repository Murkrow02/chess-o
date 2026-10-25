import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { t } from "../lib/i18n";
import { useStore } from "../lib/store";
import type { Side } from "../lib/types";
import { Giacomino } from "./Giacomino";
import { Icon } from "./Icon";

type Imported = Awaited<ReturnType<typeof api.importGames>>[number];

const remember = (key: string, value?: string) => {
  try {
    if (value === undefined) return localStorage.getItem(key) ?? "";
    localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the form still works, it just forgets */
  }
  return value ?? "";
};

export function Home() {
  const { openGame } = useStore();
  const [tab, setTab] = useState<"paste" | "import">("paste");
  const [pgn, setPgn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [site, setSite] = useState(remember("chesso.site") || "chesscom");
  const [user, setUser] = useState(remember("chesso.user"));
  const [found, setFound] = useState<Imported[] | null>(null);
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof api.games>>>([]);
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.games().then(setRecent).catch(() => undefined);
  }, []);

  const analyze = async (text: string, side?: Side | null) => {
    setError(null);
    setBusy(true);
    try {
      const g = await api.createGame(text);
      if (side !== undefined) await api.setSide(g.id, side);
      await openGame(g.id);
    } catch (e) {
      setError(t("errors.pgn", { message: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  };

  const fetchGames = async () => {
    setError(null);
    setBusy(true);
    remember("chesso.site", site);
    remember("chesso.user", user);
    try {
      setFound(await api.importGames(site, user.trim()));
    } catch (e) {
      setError(t("errors.import", { message: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  };

  const readFile = async (f: File | undefined) => {
    if (f) setPgn(await f.text());
  };

  const sideOf = (g: Imported): Side | null => {
    const u = user.trim().toLowerCase();
    if (g.white.toLowerCase() === u) return "white";
    if (g.black.toLowerCase() === u) return "black";
    return null;
  };

  return (
    <div className="home">
      <header className="hero">
        <Giacomino mood="happy" size={132} />
        <div>
          <h1>{t("home.title")}</h1>
          <p className="muted">{t("app.tagline")}</p>
        </div>
      </header>

      <section className="intake">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "paste"} onClick={() => setTab("paste")}>{t("home.pasteTab")}</button>
          <button role="tab" aria-selected={tab === "import"} onClick={() => setTab("import")}>{t("home.importTab")}</button>
        </div>

        {tab === "paste" ? (
          <div className="paste" onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); readFile(e.dataTransfer.files[0]); }}>
            <textarea value={pgn} onChange={(e) => setPgn(e.target.value)} placeholder={t("home.pgnPlaceholder")}
              spellCheck={false} rows={9} />
            <div className="row">
              <button className="ghost" onClick={() => file.current?.click()}><Icon name="upload" />{t("home.upload")}</button>
              <input ref={file} type="file" accept=".pgn,text/plain" hidden onChange={(e) => readFile(e.target.files?.[0])} />
              <span className="spacer" />
              <button className="primary" disabled={!pgn.trim() || busy} onClick={() => analyze(pgn)}><Icon name="search" />{t("home.analyze")}</button>
            </div>
          </div>
        ) : (
          <div className="import">
            <form className="row" onSubmit={(e) => { e.preventDefault(); fetchGames(); }}>
              <select value={site} onChange={(e) => setSite(e.target.value)} aria-label={t("home.site")}>
                <option value="chesscom">Chess.com</option>
                <option value="lichess">Lichess</option>
              </select>
              <input value={user} onChange={(e) => setUser(e.target.value)} placeholder={t("home.username")} aria-label={t("home.username")} />
              <button className="primary" disabled={!user.trim() || busy}><Icon name="download" />{t("home.fetch")}</button>
            </form>
            {found && found.length === 0 && <p className="muted">{t("home.noGames")}</p>}
            {found && found.length > 0 && (
              <ul className="game-list">
                {found.map((g, i) => (
                  <li key={i}>
                    <button onClick={() => analyze(g.pgn, sideOf(g))} disabled={busy}>
                      <span className={`pawn-chip white`} /> {g.white}
                      <span className="vs">{g.result}</span>
                      <span className={`pawn-chip black`} /> {g.black}
                      <span className="spacer" />
                      <span className="muted">{g.speed}</span>
                      <span className="muted">{new Date(g.date).toLocaleDateString()}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </section>

      <section className="recent">
        <h2>{t("home.recent")}</h2>
        {recent.length === 0 ? <p className="muted">{t("home.empty")}</p> : (
          <ul className="game-list">
            {recent.map((g) => (
              <li key={g.id}>
                <button onClick={() => openGame(g.id)}>
                  <span className="pawn-chip white" /> {g.headers.White ?? "?"}
                  <span className="vs">{g.headers.Result ?? "*"}</span>
                  <span className="pawn-chip black" /> {g.headers.Black ?? "?"}
                  <span className="spacer" />
                  {g.summary && (
                    <span className="acc-pair">
                      <span className="acc white">{g.summary.accuracy.white ?? "–"}</span>
                      <span className="acc black">{g.summary.accuracy.black ?? "–"}</span>
                    </span>
                  )}
                  <span className="muted">{g.summary?.opening?.name ?? ""}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
