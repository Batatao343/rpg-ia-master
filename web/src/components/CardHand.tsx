import type { CardView, EnemyView } from "../types";
import { planCard, REASON_TEXT } from "../combat/targeting";

interface Props {
  cards: CardView[];
  enemies: EnemyView[];
  busy: boolean;
  aimingCardId?: string | null;
  ruptureId: string | null;
  detailId: string;
  onToggleRupture: (cardId: string) => void;
  onGesture: (card: CardView, trigger: HTMLElement) => void;
  onDetail: (cardId: string | null) => void;
}

const FREQ_SHORT: Record<string, string> = {
  livre: "livre", turno: "1× turno", cena: "1× cena",
  descanso_curto: "1× descanso curto", descanso_longo: "1× descanso longo",
};

/** SPEC-205: a carta É o gesto. Com alvo → mira; sem alvo → um clique. Sem select, sem "Jogar". */
export function CardHand({ cards, enemies, busy, aimingCardId, ruptureId, detailId, onToggleRupture, onGesture, onDetail }: Props) {
  const activeCards = cards.filter((card) => card.type === "ativa");
  if (!activeCards.length) return null;
  return (
    <section className="card-hand" aria-labelledby="card-hand-title" data-aim-safe>
      <div className="card-hand__head">
        <div>
          <p className="card-hand__kicker">Cartas preparadas</p>
          <h2 id="card-hand-title">Sua mão</h2>
        </div>
      </div>
      <div className="card-hand__rail">
        {activeCards.map((card, index) => {
          const plan = planCard(card, enemies, busy);
          const rupturing = ruptureId === card.id;
          const blocked = plan.mode === "blocked";
          const aiming = aimingCardId === card.id;
          const reasonText = plan.reason ? REASON_TEXT[plan.reason] : "";
          const verb = plan.mode === "aim" ? "escolha o alvo" : "um clique";
          return (
            <div key={card.id} data-effect="card.resolve" data-effect-state={card.spent ? "resolved" : "ready"} className={`combat-card-wrap${card.spent ? " is-spent" : ""}${rupturing ? " is-rupture" : ""}${aiming ? " is-aiming" : ""}`}>
              <button type="button" className="combat-card" data-card={card.id}
                data-effect="card.arm" data-effect-state={aiming ? "armed" : blocked ? "blocked" : card.spent ? "spent" : "idle"}
                aria-pressed={aiming} aria-disabled={blocked || undefined}
                aria-describedby={detailId}
                aria-keyshortcuts={index < 9 ? String(index + 1) : undefined}
                aria-label={`Jogar Carta ${card.name}, ${card.cost} de Entropia${blocked && reasonText ? `, indisponível: ${reasonText}` : `, ${verb}`}`}
                onMouseEnter={() => onDetail(card.id)} onMouseLeave={() => onDetail(null)}
                onFocus={() => onDetail(card.id)} onBlur={() => onDetail(null)}
                onClick={(event) => { if (!blocked || aiming) onGesture(card, event.currentTarget); }}>
                <span className="combat-card__top">
                  <span className="combat-card__cost" title="Custo de Entropia">{card.cost}E</span>
                  <span className="combat-card__freq">{FREQ_SHORT[card.frequency] ?? card.frequency}</span>
                </span>
                <span className="combat-card__name">{card.name}</span>
                <span className="combat-card__desc">{card.description || card.effect_kind.replace(/_/g, " ")}</span>
                <span className="combat-card__state">
                  {blocked ? (reasonText || "Indisponível") : aiming ? "Mirando…" : plan.mode === "aim" ? "Escolha o alvo" : "Disponível"}
                  {card.evolved ? ` · Caminho ${card.evolved}` : ""}
                </span>
              </button>
              {card.has_rupture && (
                <button type="button" className="combat-card__rupture" aria-pressed={rupturing}
                  aria-disabled={busy || !card.rupture_ready || undefined}
                  onClick={() => { if (!busy && card.rupture_ready) onToggleRupture(card.id); }}>
                  {rupturing ? "Ruptura ligada" : "Ruptura"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
