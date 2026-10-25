import { useCallback, useEffect, useState } from "react";
import { api, type Account, type StoredGame } from "../lib/api";
import { lang, t } from "../lib/i18n";
import { useStore } from "../lib/store";
import { Icon } from "./Icon";

const PAGE = 10;

function outcome(g: StoredGame): "win" | "loss" | "draw" {
  const r = g.headers.Result;
  if (r === "1-0") return g.side === "white" ? "win" : "loss";
  if (r === "0-1") return g.side === "black" ? "win" : "loss";
  return "draw";
}

function speed(tc: string | undefined): string {
  if (!tc) return "";
  if (tc.includes("/")) return t("chesscom.speed.daily");
  const [base, inc = 0] = tc.split("+").map(Number);
  const total = base + 40 * inc;  // the usual estimate for a game of 40 moves
  return t(`chesscom.speed.${total < 180 ? "bullet" : total < 600 ? "blitz" : "rapid"}`);
}

function ago(seconds: number): string {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 60) return t("chesscom.justNow");
  if (s < 3600) return t("chesscom.minutesAgo", { n: Math.round(s / 60) });
  if (s < 86400) return t("chesscom.hoursAgo", { n: Math.round(s / 3600) });
  return new Date(seconds * 1000).toLocaleDateString(lang);
}

/** One tap after a game ends: sync now, then open the newest game. Hidden until an account is linked. */
export function LatestButton() {
  const { openGame } = useStore();
  const [linked, setLinked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.account().then(({ account: a }) => setLinked(Boolean(a))).catch(() => undefined);
  }, []);

  if (!linked) return null;
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      const { account: a } = await api.syncAccount(true);
      const [latest] = await api.games({ player: a.username, limit: 1 });
      if (latest) await openGame(latest.id);
      else setError(t("chesscom.noGames"));
    } catch (e) {
      setError(t("errors.sync", { message: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="latest">
      <button className="primary big" onClick={go} disabled={busy}>
        <Icon name={busy ? "sync" : "play"} />{busy ? t("chesscom.fetchingLatest") : t("chesscom.latest")}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

/** The linked Chess.com account: link form, or the synced games with sync and unlink. */
export function ChessCom() {
  const { openGame } = useStore();
  const [account, setAccount] = useState<Account | null | undefined>(undefined);
  const [games, setGames] = useState<StoredGame[]>([]);
  const [shown, setShown] = useState(PAGE);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async (a: Account) => {
    setGames(await api.games({ player: a.username, limit: 200 }));
  }, []);

  const sync = useCallback(async (force: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.syncAccount(force);
      setAccount(r.account);
      await load(r.account);
      if (force) setNote(r.added ? t("chesscom.added", { n: r.added }) : t("chesscom.upToDate"));
    } catch (e) {
      setError(t("errors.sync", { message: (e as Error).message }));
    } finally {
      setBusy(false);
    }
  }, [load]);

  useEffect(() => {
    api.account().then(async ({ account: a }) => {
      setAccount(a);
      if (a) {
        await load(a).catch(() => undefined);
        sync(false); // the server skips it when the last check is recent
      }
    }).catch(() => setAccount(null));
  }, [load, sync]);

  const link = async () => {
    setBusy(true);
    setError(null);
    try {
      const { account: a } = await api.linkAccount(name.trim());
      setAccount(a);
      setBusy(false);
      await sync(true);
    } catch (e) {
      setError(t("errors.link", { message: (e as Error).message }));
      setBusy(false);
    }
  };

  const unlink = async () => {
    await api.unlinkAccount();
    setAccount(null);
    setGames([]);
    setNote(null);
  };

  if (account === undefined) return null;

  if (!account) {
    return (
      <section className="chesscom">
        <h2>{t("chesscom.linkTitle")}</h2>
        <p className="muted">{t("chesscom.linkIntro")}</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); link(); }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("chesscom.username")}
            aria-label={t("chesscom.username")} />
          <button className="primary" disabled={!name.trim() || busy}><Icon name="user" />{t("chesscom.link")}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>
    );
  }

  return (
    <section className="chesscom">
      <div className="account-head">
        {account.avatar ? <img src={account.avatar} alt="" width={40} height={40} /> : <span className="avatar-blank"><Icon name="user" /></span>}
        <div>
          <h2>{account.username}</h2>
          <p className="muted">{busy ? t("chesscom.syncing") : t("chesscom.synced", { when: ago(account.checked_at) })}</p>
        </div>
        <span className="spacer" />
        <button className="ghost" onClick={() => sync(true)} disabled={busy}><Icon name="sync" />{t("chesscom.sync")}</button>
        <button className="ghost" onClick={unlink} disabled={busy} title={t("chesscom.unlinkTitle")}><Icon name="unlink" />{t("chesscom.unlink")}</button>
      </div>
      {note && <p className="muted">{note}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {games.length === 0 ? <p className="muted">{busy ? "" : t("chesscom.noGames")}</p> : (
        <ul className="game-list">
          {games.slice(0, shown).map((g) => {
            const opp = g.side === "white" ? g.headers.Black : g.headers.White;
            const res = outcome(g);
            return (
              <li key={g.id}>
                <button onClick={() => openGame(g.id)}>
                  <span className={`pawn-chip ${g.side ?? "white"}`} title={t(`home.${g.side ?? "white"}`)} />
                  <span className={`outcome ${res}`}>{t(`chesscom.${res}`)}</span>
                  <span>{t("chesscom.vs", { name: opp ?? "?" })}</span>
                  <span className="spacer" />
                  {g.summary && g.side ? <span className={`acc ${g.side}`}>{g.summary.accuracy[g.side] ?? "–"}</span>
                    : <span className="badge-new">{t("chesscom.notReviewed")}</span>}
                  <span className="muted">{speed(g.headers.TimeControl)}</span>
                  <span className="muted">{new Date(g.created_at * 1000).toLocaleDateString(lang)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {games.length > shown && (
        <button className="ghost more" onClick={() => setShown(shown + PAGE)}>{t("chesscom.more")}</button>
      )}
    </section>
  );
}
