import { useEffect, useState } from "react";
import { api, type Profile as P } from "../lib/api";
import { t } from "../lib/i18n";
import { CLASSES } from "../lib/types";
import { ClassIcon } from "./ClassIcon";
import { Giacomino } from "./Giacomino";

export function Profile() {
  const [p, setP] = useState<P | null>(null);
  useEffect(() => {
    api.profile().then(setP).catch(() => undefined);
  }, []);
  if (!p) return <div className="loading"><Giacomino mood="thinking" /></div>;

  const maxLoss = Math.max(1, ...p.by_phase.map((x) => x.avg_loss));
  const maxTheme = Math.max(1, ...p.by_theme.map((x) => x.count));
  return (
    <div className="profile">
      <h1>{t("profile.title")}</h1>
      <p className="muted">{t("profile.intro")}</p>
      {p.games === 0 ? (
        <div className="coach-row"><Giacomino mood="neutral" /><div className="bubble"><p>{t("profile.empty")}</p></div></div>
      ) : (
        <>
          <div className="stats">
            <div><strong>{p.games}</strong><span>{t("profile.games")}</span></div>
            <div><strong>{p.avg_accuracy ?? "–"}</strong><span>{t("profile.avgAccuracy")}</span></div>
          </div>
          <section>
            <h2>{t("profile.byPhase")}</h2>
            <p className="muted">{t("profile.lost")}</p>
            {p.by_phase.map((x) => (
              <div className="hbar" key={x.phase}>
                <span className="hbar-label">{t(`phases.${x.phase}`)}</span>
                <span className="hbar-track"><span style={{ width: `${(x.avg_loss / maxLoss) * 100}%` }} /></span>
                <span className="hbar-val">{x.avg_loss}</span>
              </div>
            ))}
          </section>
          {p.by_theme.length > 0 && (
            <section>
              <h2>{t("profile.byTheme")}</h2>
              {p.by_theme.map((x) => (
                <div className="hbar" key={x.theme}>
                  <span className="hbar-label">{t(`themes.${x.theme}`)}</span>
                  <span className="hbar-track"><span style={{ width: `${(x.count / maxTheme) * 100}%` }} /></span>
                  <span className="hbar-val">{x.count}</span>
                </div>
              ))}
            </section>
          )}
          <section className="count-grid">
            {CLASSES.map((c) => (
              <div key={c}><ClassIcon cls={c} size={22} /><strong>{p.counts[c] ?? 0}</strong><span>{t(`classes.${c}`)}</span></div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
