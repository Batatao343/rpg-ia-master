import type { CardView } from "../types";

interface Props {
  cards: CardView[];
  selected?: string;
  disabled?: boolean;
  onSelect: (cardId?: string) => void;
}

export function ReactionPrompt({ cards, selected, disabled, onSelect }: Props) {
  const reactions = cards.filter((card) => card.type === "reacao");
  if (!reactions.length) return null;

  return (
    <fieldset className="reaction-prompt" disabled={disabled}>
      <legend>Reação preparada para esta rodada</legend>
      <p>Se você virar alvo e o gatilho casar, o motor interrompe o ataque com sua escolha.</p>
      <div className="reaction-prompt__choices">
        <button
          type="button"
          className={!selected ? "is-selected" : ""}
          aria-pressed={!selected}
          onClick={() => onSelect(undefined)}
        >
          Passar
        </button>
        {reactions.map((card) => (
          <button
            key={card.id}
            type="button"
            className={selected === card.id ? "is-selected" : ""}
            aria-pressed={selected === card.id}
            disabled={disabled || !card.ready}
            title={card.trigger ? `Gatilho: ${card.trigger.replace(/_/g, " ")}` : undefined}
            onClick={() => onSelect(card.id)}
          >
            {card.name} · {card.cost}E
          </button>
        ))}
      </div>
    </fieldset>
  );
}
