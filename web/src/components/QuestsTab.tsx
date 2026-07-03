import type { Quest, QuestBlock } from "../types";

const STATUS_LABEL: Record<Quest["status"], string> = {
  active: "Ativa",
  completed: "Concluída",
  failed: "Fracassada",
};

export function QuestsTab({ quest }: { quest: QuestBlock | undefined }) {
  const main = quest?.main;
  const side = quest?.side ?? [];

  return (
    <div>
      <p className="hud__label">Missão principal</p>
      {main ? (
        <div className="quest quest--main">
          {main.arc_title && <p className="quest__arc">{main.arc_title}</p>}
          <p className="quest__title">{main.objective || main.climax || "Sem objetivo definido no momento."}</p>
          {main.total > 0 && (
            <div className="quest__track" title={`${main.current_step}/${main.total}`}>
              <div className="quest__fill" style={{ width: (main.total ? (main.current_step / main.total) * 100 : 0) + "%" }} />
            </div>
          )}
        </div>
      ) : (
        <p className="combat-empty">A campanha ainda não foi planejada.</p>
      )}

      <p className="hud__label" style={{ marginTop: "1rem" }}>Missões ({side.length})</p>
      {side.length ? (
        <ul className="quests">
          {side.map((q) => (
            <li key={q.id} className={"quest quest--" + q.status}>
              <div className="quest__top">
                <span className="quest__title">{q.title}</span>
                <span className={"quest__status quest__status--" + q.status}>{STATUS_LABEL[q.status]}</span>
              </div>
              {q.description && <p className="quest__desc">{q.description}</p>}
              <p className="quest__meta">
                {[q.origin_name && `de ${q.origin_name}`, q.reward_hint].filter(Boolean).join(" · ") || "—"}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="combat-empty">Nenhuma missão registrada — ainda.</p>
      )}
    </div>
  );
}
