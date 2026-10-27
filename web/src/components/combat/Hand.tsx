import { useState } from "react";
import type { Glossary, HandCard, PilesView } from "../../types";
import { BLOCK_TEXT, keywordRules, type BlockReason } from "../../combat/deck";
import { RuleText } from "./KeywordTip";

const PILES = [["compra", "Compra"], ["descarte", "Descarte"], ["exaurida", "Exaurida"]] as const;

/** SPEC-334 R2/R3: a mão do Baralho de Conflito. Substitui `CardHand` quando o servidor manda `pilhas`.
 *  Carta = nome, pips de Fôlego, Entropia (se houver) e o texto gerado com palavras-chave. */
export function Hand({ piles, glossary, reasons, armedIndex, busy, onPlay }: {
  piles: PilesView;
  glossary: Glossary;
  reasons: BlockReason[];
  armedIndex: number | null;
  busy: boolean;
  onPlay: (card: HandCard, index: number, trigger: HTMLElement) => void;
}) {
  const [openPile, setOpenPile] = useState<(typeof PILES)[number][0] | null>(null);
  return (
    <section className="deck-hand" aria-labelledby="deck-hand-title" data-aim-safe>
      <div className="deck-hand__head">
        <h2 id="deck-hand-title">Sua mão</h2>
        <button type="button" className="deck-hand__piles" aria-expanded={openPile !== null}
          aria-controls="deck-pile-list" onClick={() => setOpenPile((cur) => (cur ? null : "compra"))}>
          {PILES.map(([k, label]) => `${label} ${piles[k]}`).join(" · ")}
        </button>
      </div>
      {openPile && (
        <div id="deck-pile-list" className="deck-hand__list" role="group" aria-label="Conteúdo das pilhas (por nome, nunca a ordem)">
          <p>
            {PILES.map(([k, label]) => (
              <button key={k} type="button" aria-pressed={openPile === k} onClick={() => setOpenPile(k)}>{label}</button>
            ))}
          </p>
          <ul>
            {(piles.listas?.[openPile] ?? []).map((c, i) => <li key={`${c.id}-${i}`}>{c.name}</li>)}
            {!(piles.listas?.[openPile] ?? []).length && <li>Vazia.</li>}
          </ul>
        </div>
      )}
      <div className="deck-hand__rail">
        {piles.mao.map((card, index) => {
          const reason = reasons[index] ?? null;
          const armed = armedIndex === index;
          const rules = keywordRules(card.texto ?? "", glossary);
          const descId = `deck-card-${index}-rules`;
          return (
            <button key={`${card.id}-${index}`} type="button" className={`combat-card deck-card${reason ? " is-dim" : ""}${armed ? " is-aiming" : ""}`}
              data-card={card.id} aria-pressed={armed} aria-disabled={reason ? true : undefined}
              aria-keyshortcuts={index < 5 ? String(index + 1) : undefined}
              aria-describedby={rules.length ? descId : undefined}
              aria-label={`${card.name}, ${card.custo_folego} de Fôlego${card.custo_entropia ? `, ${card.custo_entropia} de Entropia` : ""}${reason ? `, indisponível: ${BLOCK_TEXT[reason]}` : ""}`}
              disabled={busy && !reason}
              onClick={(e) => { if (!busy) onPlay(card, index, e.currentTarget); }}>
              <span className="combat-card__top">
                <span className="deck-card__pips" title="Custo de Fôlego" aria-hidden="true">{"●".repeat(card.custo_folego) || "○"}</span>
                {card.custo_entropia > 0 && <span className="combat-card__cost" title="Custo de Entropia" aria-hidden="true">{card.custo_entropia}E</span>}
              </span>
              <span className="combat-card__name">{card.name}</span>
              {card.texto && <span className="combat-card__desc"><RuleText texto={card.texto} glossary={glossary} /></span>}
              {reason && <span className="combat-card__state">{BLOCK_TEXT[reason]}</span>}
              {rules.length > 0 && <span id={descId} className="sr-only">{rules.join(" ")}</span>}
            </button>
          );
        })}
      </div>
    </section>
  );
}
