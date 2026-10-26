import type { CardView } from "../../types";
import { Icon, type IconName } from "../../design/icons";

const FREQ_LABEL: Record<string, string> = {
  livre: "livre", turno: "1× turno", cena: "1× cena",
  descanso_curto: "1× descanso curto", descanso_longo: "1× descanso longo",
};
const TYPE_LABEL: Record<string, string> = {
  ativa: "Ação", reacao: "Reação", passiva: "Passiva", virtude: "Virtude",
};
const TYPE_ICON: Record<string, IconName> = { ativa: "card-active", reacao: "card-reaction", passiva: "card-passive", virtude: "card-virtue" };

export interface DeckCardProps {
  card: CardView;
  /** Carta pode ser (des)preparada? Passivas e Virtudes são somente leitura. */
  preparable: boolean;
  /** Razão textual pela qual o toggle está indisponível agora (servidor ou limite). */
  blockedReason?: string;
  evolvable?: boolean;
  onToggle?: (card: CardView) => void;
  onEvolve?: () => void;
}

/** SPEC-209 R1/R15: carta do Acervo. Todos os números vêm do servidor; sem arte inventada —
 *  só ícone/selo por tipo. A carta INTEIRA é o controle (clique, Enter ou Espaço). */
export function DeckCard({ card, preparable, blockedReason, evolvable, onToggle, onEvolve }: DeckCardProps) {
  const blocked = preparable && !!blockedReason;
  const costDiffers = card.base_cost != null && card.base_cost !== card.cost;
  const state = card.prepared ? "Preparada" : preparable ? "No Acervo" : "Sempre em vigor";
  const typeLabel = TYPE_LABEL[card.type] ?? card.type;
  const head = (
    <>
      <span className="deck-card__top">
        <span className="deck-card__type" aria-hidden><Icon name={TYPE_ICON[card.type] ?? "unique"} /></span>
        <span className="deck-card__kind">{typeLabel}</span>
        <span className="deck-card__cost" title="Custo de Entropia">
          {card.cost}E{costDiffers ? <small> (base {card.base_cost})</small> : null}
        </span>
      </span>
      <span className="deck-card__name">{card.name}</span>
      <span className="deck-card__desc">{card.description || card.effect_kind.replace(/_/g, " ")}</span>
      <span className="deck-card__meta">
        <span className="deck-card__chip">{FREQ_LABEL[card.frequency] ?? card.frequency}</span>
        {card.spent && <span className="deck-card__chip is-spent">Gasta</span>}
        {card.has_rupture && <span className="deck-card__chip is-rupture">Ruptura</span>}
        {card.evolved && <span className="deck-card__chip is-evolved">Caminho {card.evolved}</span>}
        {card.subclass && <span className="deck-card__chip">{card.subclass}</span>}
      </span>
      <span className="deck-card__state">
        {state}{blocked ? ` · ${blockedReason}` : ""}
      </span>
    </>
  );
  const hint = blocked ? `, indisponível: ${blockedReason}`
    : card.prepared ? ", Enter para tirar da preparação" : ", Enter para preparar";
  return (
    <li className={"deck-card" + (card.prepared ? " is-prepared" : "") + (card.spent ? " is-spent" : "")}
      data-card-id={card.id}>
      {preparable && onToggle ? (
        <button type="button" className="deck-card__btn" data-deck-card
          data-effect={blocked ? "card.blocked" : "choice.select"}
          data-effect-state={blocked ? "blocked" : card.prepared ? "selected" : "idle"}
          aria-pressed={card.prepared}
          aria-disabled={blocked || undefined}
          aria-label={`${card.name}, ${typeLabel}, ${card.cost} de Entropia, ${state}${hint}`}
          onClick={() => { if (!blocked) onToggle(card); }}>
          {head}
        </button>
      ) : (
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- carta estática (não interativa) precisa ser alcançável pelo teclado para a navegação por setas do Acervo
        <div className="deck-card__btn is-static" data-deck-card tabIndex={0}
          aria-label={`${card.name}, ${typeLabel}, ${state}`}>
          {head}
        </div>
      )}
      {evolvable && !card.evolved && onEvolve && (
        <button type="button" className="deck-card__evolve" onClick={onEvolve}>Evoluir</button>
      )}
    </li>
  );
}
