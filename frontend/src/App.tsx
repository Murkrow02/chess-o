import { useEffect, useState } from "react";
import { api } from "./lib/api";
import { t } from "./lib/i18n";
import { useStore, type View } from "./lib/store";
import { Icon, type IconName } from "./components/Icon";
import { applyTheme, loadTheme, nextTheme } from "./lib/theme";
import { Drills } from "./components/Drills";
import { Home } from "./components/Home";
import { Profile } from "./components/Profile";
import { Review } from "./components/Review";

function route() {
  const st = useStore.getState();
  const m = location.hash.match(/^#\/game\/(\w+)/);
  if (m) {
    if (st.gameId !== m[1]) st.openGame(m[1]);
    else useStore.setState({ view: "review" });
    return;
  }
  const view = location.hash.replace("#/", "") as View;
  useStore.setState({ view: ["drills", "profile"].includes(view) ? view : "home" });
}

export function App() {
  const { view, go, gameId } = useStore();
  const [due, setDue] = useState(0);
  const [theme, setTheme] = useState(loadTheme);

  useEffect(() => applyTheme(theme), [theme]);

  useEffect(() => {
    route();
    window.addEventListener("hashchange", route);
    return () => window.removeEventListener("hashchange", route);
  }, []);

  useEffect(() => {
    api.drillsStats().then((s) => setDue(s.due)).catch(() => undefined);
  }, [view]);

  const tab = (v: View, label: string, icon: IconName, badge?: number) => (
    <button className={view === v ? "on" : ""} onClick={() => (v === "review" && gameId ? (location.hash = `#/game/${gameId}`) : go(v))}>
      <Icon name={icon} />
      {label}
      {badge ? <span className="badge">{badge}</span> : null}
    </button>
  );

  return (
    <div className="app">
      <nav className="topbar">
        <button className="brand" onClick={() => go("home")} aria-label={t("nav.newGame")}>
          <img src="/favicon.svg" alt="" width="26" height="26" />
          <span>{t("app.name")}</span>
        </button>
        <div className="tabs-top">
          {tab("home", t("nav.newGame"), "plus")}
          {gameId && tab("review", t("nav.review"), "board")}
          {tab("drills", t("nav.drills"), "target", due)}
          {tab("profile", t("nav.profile"), "user")}
          <button className="theme-btn" onClick={() => setTheme(nextTheme(theme))}
            title={t(`nav.theme.${theme}`)} aria-label={t("nav.themeTitle")}>
            <Icon name={theme === "auto" ? "monitor" : theme === "light" ? "sun" : "moon"} />
          </button>
        </div>
      </nav>
      <main>
        {view === "home" && <Home />}
        {view === "review" && <Review />}
        {view === "drills" && <Drills />}
        {view === "profile" && <Profile />}
      </main>
    </div>
  );
}
