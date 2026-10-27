import { useState } from "react";
import type { EspolioPendente } from "../../types";
import { useGlossary } from "../../combat/useGlossary";
import { RARITY_LABEL, refuseLabel, type RewardSender } from "../../cardRewards";
import { RuleText } from "./KeywordTip";

interface Props {
  espolio: EspolioPendente;
  busy: boolean;
  onChoose: RewardSender;
}


/** SPEC-333 R1/R3: depois do conflito, 1 de 3 Cartas — ou ouro. Não interrompe a narração:
 *  o painel fica na aba Combate e pode esperar (expira no próximo conflito). */
export function EspolioPanel({ espolio, busy, onChoose }: Props) {
  const glossary = useGlossary(); // SPEC-342 R19.1
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const locked = busy || pending;

  async function choose(cardId: string | null) {
    if (locked) return;
    setPending(true);
    try {
      const out = await onChoose({ kind: "espolio", card_id: cardId });
      if (!out.ok) setMessage(out.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="espolio" aria-label="Espólio de Cartas">
      <h3 className="espolio__title section-label">Espólio</h3>
      <p className="espolio__lead">
        {espolio.origem === "objetivo" ? "O objetivo foi cumprido." : "A luta acabou."} Escolha uma técnica para o seu Baralho.
      </p>
      <ul className="espolio__offers">
        {espolio.ofertas.map((card) => (
          <li key={card.id}>
          <article className={`combat-card espolio__card espolio__card--${card.raridade}`} aria-label={card.name}>
            <div className="espolio__top">
              <h4>{card.name}</h4>
              <span className="espolio__rarity">{RARITY_LABEL[card.raridade] ?? card.raridade}</span>
            </div>
            <p className="espolio__cost">Fôlego {card.custo_folego}{card.custo_entropia ? ` · Entropia ${card.custo_entropia}` : ""}</p>
            {card.texto && <p className="espolio__rules"><RuleText texto={card.texto} glossary={glossary} /></p>}
            {card.descricao && <p className="espolio__flavor">{card.descricao}</p>}
            <button className="btn btn--primary" type="button" disabled={locked || card.conhecida}
              data-espolio-pick={card.id} onClick={() => choose(card.id)}>
              {card.conhecida ? "Você já conhece" : `Levar ${card.name}`}
            </button>
          </article>
          </li>
        ))}
      </ul>
      <button className="btn btn--ghost espolio__refuse" type="button" disabled={locked}
        data-espolio-refuse onClick={() => choose(null)}>
        {refuseLabel(espolio.recusa_ouro)}
      </button>
      <p className="espolio__msg" role="status" aria-live="polite">{message}</p>
    </section>
  );
}
