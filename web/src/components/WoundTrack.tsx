import { pct } from "../lib";
import type { WoundTrackView } from "../types";

const SEVERITIES = ["leve", "grave", "critico"] as const;

export function WoundTrack({ wounds, compact = false }: { wounds: WoundTrackView; compact?: boolean }) {
  return (
    <section className={`wound-track${compact ? " is-compact" : ""}`} aria-label="Vitalidade e Ferimentos">
      <div className="wound-track__vitality">
        <span>Vitalidade</span>
        <strong>{wounds.vitality}/{wounds.max_vitality}</strong>
      </div>
      <div className="wound-track__bar" aria-hidden>
        <span style={{ width: `${pct(wounds.vitality, wounds.max_vitality)}%` }} />
      </div>
      <div className="wound-track__severities">
        {SEVERITIES.map((severity) => {
          const entries = wounds.by_severity[severity] ?? [];
          const slots = wounds.slots[severity] ?? entries.length;
          return (
            <div key={severity} className={`wound-severity wound-severity--${severity}`}>
              <span className="wound-severity__label">{severity === "critico" ? "Crítico" : severity}</span>
              <div className="wound-severity__slots" role="list" aria-label={`${entries.length} de ${slots} Ferimentos ${severity}`}>
                {Array.from({ length: Math.max(slots, entries.length) }, (_, index) => {
                  const wound = entries[index];
                  const region = String(wound?.regiao ?? wound?.region ?? "");
                  return <span role="listitem" key={index} className={wound ? "is-filled" : ""} title={region || "Espaço livre"}>{region || "·"}</span>;
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
