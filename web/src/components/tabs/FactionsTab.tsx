import type { FactionView } from "../../types";

const STABILITY_CLASS: Record<string, string> = {
  "estável": "is-stable", "instável": "is-unstable", "em colapso": "is-collapsing",
};

export function FactionsTab({ factions }: { factions: FactionView[] }) {
  if (!factions.length) {
    return (
      <div>
        <h3 className="hud__label">Fações</h3>
        <p className="combat-empty">Os poderes deste mundo ainda se movem nas sombras.</p>
      </div>
    );
  }
  const standingLabel: Record<string, string> = { hostil: "Hostil", desconfiado: "Desconfiada", neutro: "Neutra", amistoso: "Amistosa", aliado: "Aliada" };
  return (
    <div>
      <h3 className="hud__label">Poderes que você conhece ({factions.length})</h3>
      <ul className="factions">
        {factions.map((f) => {
          const hasProg = f.progress !== null && f.progress !== undefined;
          const prog = Math.max(0, Math.min(100, f.progress ?? 0));
          const recent = (f.recent_changes ?? []).slice(-3).reverse();
          return (
            <li key={f.id} className={"faction faction--" + f.standing_label + (f.completed ? " is-done" : "")}>
              <div className="faction__top">
                <span className="faction__name">{f.name}</span>
                <span className={"faction__disp faction__disp--" + f.standing_label}>
                  {standingLabel[f.standing_label] ?? f.standing_label}
                </span>
              </div>
              {f.knows_goal ? (
                <p className="faction__goal">{f.goal}</p>
              ) : (
                <p className="faction__goal faction__goal--unknown">Plano desconhecido — descubra com quem sabe.</p>
              )}
              {hasProg ? (
                <div className="faction__track" title={`${prog}% rumo ao objetivo (intel${f.intel_stale ? " antiga" : ""})`}>
                  <div className="faction__fill" style={{ transform: `scaleX(${prog / 100})` }} />
                </div>
              ) : null}
              <p className="faction__meta">
                {f.completed ? "Objetivo cumprido" : hasProg ? `${prog}% · ${f.region}` : f.region}
                {f.intel_stale ? " · intel pode estar desatualizada" : ""}
              </p>
              <div className={"faction__stability " + (STABILITY_CLASS[f.stability_label] ?? "")}>
                <span className="faction__stability-label">{f.stability_label}</span>
              </div>
              {f.membership && (
                <p className="faction__membership" data-testid="faction-membership">
                  {f.membership.rank_name ? `${f.membership.rank_name} · ` : ""}
                  {f.membership.standing_label}
                  {f.membership.perks.length > 0 ? ` · ${f.membership.perks.join(", ")}` : ""}
                </p>
              )}
              {recent.length > 0 && (
                <p className="faction__history">
                  {recent.map((h, i) => (
                    <span key={i}>
                      {h.text}
                      {i < recent.length - 1 ? " · " : ""}
                    </span>
                  ))}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
