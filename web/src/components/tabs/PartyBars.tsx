import { pct } from "../../lib";

export function PartyBars({ party }: { party: import("../../types").PartyMember[] }) {
  const shown = party;
  if (!shown.length) return null;
  return (
    <div className="partyblock">
      <h3 className="hud__label hud__label--sub">Companheiros</h3>
      <ul className="party">
        {shown.map((m, i) => (
          <li key={`${m.name}-${i}`} className={"party__member" + (m.status === "morto" ? " is-dead" : "") + (!m.active ? " is-waiting" : "")}>
            <div className="party__top">
              <span>{m.name}{!m.active && m.status !== "morto" ? " (esperando)" : ""}{m.status === "morto" ? " †" : ""}</span>
              <span>{`${m.vitalidade}/${m.max_vitalidade}`}</span>
            </div>
            {m.approval_label && (
              <div className="party__mood">
                {m.approval_label}{m.bond_label ? ` · ${m.bond_label}` : ""}
              </div>
            )}
            <div className="party__track">
              <div className="party__fill"
                   style={{ transform: `scaleX(${pct(m.vitalidade, m.max_vitalidade) / 100})` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
