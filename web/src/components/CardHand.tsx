import { useEffect, useState } from "react";
import type { ActionOptions, CardView, EnemyView } from "../types";

interface Props {
  cards: CardView[];
  enemies: EnemyView[];
  busy: boolean;
  reactionCardId?: string;
  onPlay: (text: string, options: ActionOptions) => void;
}

const FREQ_LABEL: Record<string, string> = {
  livre: "livre",
  turno: "1× turno",
  cena: "1× cena",
  descanso_curto: "1× descanso curto",
  descanso_longo: "1× descanso longo",
};

export function CardHand({ cards, enemies, busy, reactionCardId, onPlay }: Props) {
  const activeCards = cards.filter((card) => card.type === "ativa");
  const [targetId, setTargetId] = useState(enemies[0]?.id ?? "");
  const [ruptureId, setRuptureId] = useState<string | null>(null);

  useEffect(() => {
    if (!enemies.some((enemy) => enemy.id === targetId)) {
      setTargetId(enemies[0]?.id ?? "");
    }
  }, [enemies, targetId]);

  if (!activeCards.length) return null;

  return (
    <section className="card-hand" aria-labelledby="card-hand-title">
      <div className="card-hand__head">
        <div>
          <p className="card-hand__kicker">Cartas preparadas</p>
          <h2 id="card-hand-title">Sua mão</h2>
        </div>
        {enemies.length > 1 && (
          <label className="card-hand__target">
            Alvo
            <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
              {enemies.map((enemy) => (
                <option key={enemy.id} value={enemy.id}>{enemy.name}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="card-hand__rail">
        {activeCards.map((card) => {
          const rupturing = ruptureId === card.id;
          const disabled = busy || !card.ready;
          return (
            <article key={card.id} className={`combat-card${card.spent ? " is-spent" : ""}${rupturing ? " is-rupture" : ""}`}>
              <div className="combat-card__top">
                <span className="combat-card__cost" title="Custo de Entropia">{card.cost}E</span>
                <span className="combat-card__freq">{FREQ_LABEL[card.frequency] ?? card.frequency}</span>
              </div>
              <h3>{card.name}</h3>
              <p>{card.description || card.effect_kind.replace(/_/g, " ")}</p>
              <div className="combat-card__state">
                {card.spent ? "Gasta" : card.ready ? "Disponível" : "Sem Entropia"}
                {card.evolved ? ` · Caminho ${card.evolved}` : ""}
              </div>
              {card.has_rupture && (
                <button
                  type="button"
                  className="combat-card__rupture"
                  aria-pressed={rupturing}
                  disabled={busy || !card.rupture_ready}
                  onClick={() => setRuptureId((current) => current === card.id ? null : card.id)}
                >
                  {rupturing ? "Ruptura declarada" : "Declarar Ruptura"}
                </button>
              )}
              <button
                type="button"
                className="combat-card__play"
                disabled={disabled}
                onClick={() => {
                  setRuptureId(null);
                  onPlay(`${rupturing ? "Declaro Ruptura e uso" : "Uso"} ${card.name}.`, {
                    card_id: card.id,
                    target_id: card.target_kind === "enemy" ? targetId || undefined : undefined,
                    ruptura: rupturing,
                    reaction_card_id: reactionCardId || undefined,
                  });
                }}
              >
                {rupturing ? "Romper" : "Jogar Carta"}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
