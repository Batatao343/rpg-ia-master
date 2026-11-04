import { useEffect, useRef } from "react";
import { pct, prettyItem } from "../../lib";
import { SceneZones } from "../SceneZones";
import { WoundTrack } from "../WoundTrack";
import type { CombatBlock } from "../../types";
import { CondChips } from "./hudParts";
import { PartyBars } from "./PartyBars";

export function CombatTab({ c, hitKey, party, arena, deck }: {
  c: CombatBlock | undefined; hitKey: number; party: import("../../types").PartyMember[];
  /** SPEC-347 R5.4: modo Baralho — a faixa de cena já mostra a rodada (sem repetir no cabeçalho). */
  deck?: boolean;
  /** SPEC-205: a Arena (aba Combate) já mostra zonas e inimigos — evita duplicar. */
  arena?: boolean;
}) {
  if (!c || !c.active || !c.enemies.length) {
    return (
      <div>
        <p className="combat-empty">Nenhuma ameaça à vista. O aço descansa.</p>
        <PartyBars party={party} />
      </div>
    );
  }
  const cds = Object.entries(c.cooldowns || {});
  return (
    <div>
      <Combat c={c} hitKey={hitKey} cds={cds} arena={arena} deck={deck} />
      <PartyBars party={party} />
    </div>
  );
}

function Combat({ c, hitKey, cds, arena, deck }: { c: CombatBlock; hitKey: number; cds: [string, number][]; arena?: boolean; deck?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const el = ref.current;
    if (!el) return;
    el.classList.remove("is-hit");
    void el.offsetWidth;
    el.classList.add("is-hit");
  }, [hitKey]);

  return (
    <div className="combatblock" ref={ref}>
      <h3 className="hud__label">
        Combate{c.round && !deck ? <span className="muted"> · Rodada {c.round}</span> : null}
      </h3>

      <WoundTrack wounds={c.wounds} />
      {!arena && <SceneZones scene={c.scene} chase={c.chase} />}

      {!arena && <ul className="enemies">
        {c.enemies.map((e, i) => (
          <li key={`${e.name}-${i}`} className="enemy">
            <div className="enemy__top">
              <span>{e.name}</span>
              <span>{`${e.vitalidade}/${e.max_vitalidade}`}</span>
            </div>
            <div className="enemy__track">
              <div className="enemy__fill"
                   style={{ transform: `scaleX(${pct(e.vitalidade, e.max_vitalidade) / 100})` }} />
            </div>
            <p className="enemy__public">
              {e.esquiva != null ? `Esquiva ${e.esquiva}` : "Esquiva desconhecida"}
              {e.protecao != null ? ` · Proteção ${e.protecao}` : ""}
            </p>
            {e.revealed_cards.length > 0 && (
              <p className="enemy__intel">Cartas vistas: {e.revealed_cards.map((card) => card.name).join(", ")}</p>
            )}
            {e.revealed_resistances.length > 0 && (
              <p className="enemy__intel">Resistências vistas: {e.revealed_resistances.join(", ")}</p>
            )}
            {e.conditions.length > 0 && <CondChips conds={e.conditions} />}
          </li>
        ))}
      </ul>}

      {c.order.length > 0 && !arena && (
        <>
          <h3 className="hud__label hud__label--sub">Iniciativa</h3>
          <ol className="initiative">
            {c.order.map((o, i) => (
              <li key={i} className={"init " + (o.side === "hero" ? "init--hero" : "init--enemy")}>
                {o.name}
              </li>
            ))}
          </ol>
        </>
      )}

      {c.player_conditions.length > 0 && (
        <>
          <h3 className="hud__label hud__label--sub">Suas condições</h3>
          <CondChips conds={c.player_conditions} />
        </>
      )}

      {cds.length > 0 && (
        <>
          <h3 className="hud__label hud__label--sub">Recarga</h3>
          <div className="conds__row">
            {cds.map(([k, v]) => (
              <span key={k} className="cond-chip">{`${prettyItem(k)} (${v})`}</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
