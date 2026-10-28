import { useState } from "react";
import type { LojaCartasView } from "../../types";
import { useGlossary } from "../../combat/useGlossary";
import { DESTINO_LABEL, RARITY_LABEL, shopOfferState, type RewardSender } from "../../cardRewards";
import { RuleText } from "./KeywordTip";

interface Props {
  loja: LojaCartasView;
  busy: boolean;
  onBuy: RewardSender;
}

/** SPEC-357 R14: Técnicas à venda no mercador do local. Preço, destino e bloqueio vêm do servidor. */
export function LojaCartasPanel({ loja, busy, onBuy }: Props) {
  const glossary = useGlossary();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const locked = busy || pending;

  async function buy(cardId: string) {
    if (locked) return;
    setPending(true);
    try {
      const out = await onBuy({ kind: "loja", card_id: cardId });
      setMessage(out.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="espolio loja" aria-label="Técnicas à venda">
      <h3 className="espolio__title section-label">Técnicas à venda</h3>
      <p className="espolio__lead">
        {loja.merchant_name} · a prateleira muda em {loja.renova_em_dias} {loja.renova_em_dias === 1 ? "dia" : "dias"}.
        {loja.motivo ? ` ${loja.motivo}` : ""}
      </p>
      <ul className="espolio__offers">
        {loja.ofertas.map((card) => {
          const st = shopOfferState(card);
          return (
            <li key={card.id}>
              <article className={`combat-card espolio__card espolio__card--${card.raridade}`} aria-label={card.name}>
                <div className="espolio__top">
                  <h4>{card.name}</h4>
                  <span className="espolio__rarity">{RARITY_LABEL[card.raridade] ?? card.raridade}</span>
                </div>
                <p className="espolio__cost">Fôlego {card.custo_folego}{card.custo_entropia ? ` · Entropia ${card.custo_entropia}` : ""}</p>
                {card.texto && <p className="espolio__rules"><RuleText texto={card.texto} glossary={glossary} /></p>}
                {card.descricao && <p className="espolio__flavor">{card.descricao}</p>}
                <p className="loja__price" data-loja-price={card.id}>
                  {card.preco} de ouro{!card.conhecida && ` · ${DESTINO_LABEL[card.destino] ?? card.destino}`}
                </p>
                <button className="btn btn--primary" type="button" disabled={locked || !st.enabled}
                  data-loja-buy={card.id} onClick={() => buy(card.id)}>
                  {st.label}
                </button>
              </article>
            </li>
          );
        })}
      </ul>
      <p className="espolio__msg" role="status" aria-live="polite">{message}</p>
    </section>
  );
}
