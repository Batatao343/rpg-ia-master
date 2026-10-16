import type { CardView } from "../types";

interface Props {
  cards: CardView[];
  selected?: string;
  disabled?: boolean;
  onSelect: (cardId?: string) => void;
}

/** SPEC-205 R17: reação em um clique (sem fieldset); `reaction_card_id` segue no payload. */
export function ReactionPrompt({ cards, selected, disabled, onSelect }: Props) {
  const reactions = cards.filter((card) => card.type === "reacao");
  if (!reactions.length) return null;

  return (
    <section className="reaction-prompt" role="group" aria-label="Reação preparada para esta rodada" data-aim-safe>
      <p className="reaction-prompt__title">Reação preparada para esta rodada</p>
      <div className="reaction-prompt__choices">
        <button type="button" className={!selected ? "is-selected" : ""} aria-pressed={!selected}
          disabled={disabled} onClick={() => onSelect(undefined)}>
          Passar
        </button>
        {reactions.map((card) => (
          <button key={card.id} type="button" className={selected === card.id ? "is-selected" : ""}
            aria-pressed={selected === card.id} disabled={disabled || !card.ready}
            title={card.trigger ? `Gatilho: ${card.trigger.replace(/_/g, " ")}` : undefined}
            onClick={() => onSelect(card.id)}>
            {card.name} · {card.cost}E
          </button>
        ))}
      </div>
    </section>
  );
}
