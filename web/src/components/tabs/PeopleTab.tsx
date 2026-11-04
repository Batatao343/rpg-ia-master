import type { NpcView } from "../../types";

const ATTITUDE_LABEL: Record<string, string> = {
  hostil: "Hostil", desconfiado: "Desconfiado", neutro: "Neutro", amistoso: "Amistoso", leal: "Leal",
};

export function PeopleTab({ npcs }: { npcs: NpcView[] }) {
  if (!npcs.length) {
    return (
      <div>
        <h3 className="hud__label">Personagens</h3>
        <p className="combat-empty">Converse com quem cruzar seu caminho: os conhecidos aparecem aqui, com o que lembram de você.</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="hud__label">Conhecidos ({npcs.length})</h3>
      <ul className="people">
        {npcs.map((n, i) => {
          return (
            <li key={i} className="person">
              <div className="person__top">
                <span className="person__name">{n.name}</span>
                <span className={"person__rel person__rel--" + n.attitude_label}>
                  {ATTITUDE_LABEL[n.attitude_label] ?? n.attitude_label}
                </span>
              </div>
              <p className="person__meta">{[n.role, n.location].filter(Boolean).join(" · ") || "—"}</p>
              {n.last_memory && <p className="person__mem">“{n.last_memory}”</p>}
              {(n.recent_changes ?? []).slice(-3).map((c, j) => (
                <p key={j} className="person__change">{c.text}</p>
              ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
