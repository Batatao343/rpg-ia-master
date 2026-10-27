import { useEffect, useState, type ReactNode } from "react";
import type { Glossary, HandCard, PilesView } from "../../types";
import { Icon } from "../../design/icons";
import { BLOCK_TEXT, keywordRules, type BlockReason } from "../../combat/deck";
import { RuleText } from "./KeywordTip";

const PILES = [["compra", "Compra"], ["descarte", "Descarte"], ["exaurida", "Exaurida"]] as const;
export const EXAURIDA_NOTE = "Exaurida: cartas gastas que só voltam depois do conflito ou de um descanso.";
export const EMPTY_HAND_NOTE = "Sua mão está vazia nesta rodada. Recorra às manobras abaixo, ou passe a vez.";
export const BLOCKED_HAND_NOTE = "Nenhuma carta responde agora. Recorra às manobras abaixo, ou passe a vez.";

/** SPEC-334 R2/R3 + SPEC-342: a mão do Baralho de Conflito. Substitui `CardHand` quando o servidor manda `pilhas`.
 *  O título traz o Fôlego (`head`); cada carta traz o texto completo no `aria-describedby` (sr-only). */
export function Hand({ piles, glossary, reasons, armedIndex, busy, onPlay, head, onStuck }: {
  piles: PilesView;
  glossary: Glossary;
  reasons: BlockReason[];
  armedIndex: number | null;
  busy: boolean;
  onPlay: (card: HandCard, index: number, trigger: HTMLElement) => void;
  head?: ReactNode;
  /** R16: mão vazia ou toda bloqueada → o contêiner abre as manobras. */
  onStuck?: (stuck: boolean) => void;
}) {
  const [openPile, setOpenPile] = useState<(typeof PILES)[number][0] | null>(null);
  const empty = piles.mao.length === 0;
  const allBlocked = !empty && piles.mao.every((_, i) => !!reasons[i]);
  const stuck = empty || allBlocked;
  useEffect(() => { onStuck?.(stuck); }, [stuck, onStuck]);
  const counts = PILES.map(([k, label]) => `${label} ${piles[k]}`).join(" · ");
  return (
    <section className="deck-hand" aria-labelledby="deck-hand-title" data-aim-safe>
      <div className="deck-hand__head">
        <h3 id="deck-hand-title" className="section-label">Sua mão</h3>
        {head}
        <button type="button" className="btn btn--ghost btn--sm deck-hand__piles" aria-expanded={openPile !== null}
          aria-controls="deck-pile-list" onClick={() => setOpenPile((cur) => (cur ? null : "compra"))}>
          <span>Pilhas <Icon name={openPile ? "caret-up" : "caret-down"} /></span>
          <span className="deck-hand__counts">{counts}</span>
        </button>
      </div>
      {openPile && (
        <div id="deck-pile-list" className="deck-hand__list" role="group" aria-label="Conteúdo das pilhas (por nome, nunca a ordem)">
          <p>
            {PILES.map(([k, label]) => (
              <button key={k} type="button" aria-pressed={openPile === k} onClick={() => setOpenPile(k)}>{label}</button>
            ))}
          </p>
          {openPile === "exaurida" && <p className="deck-hand__note">{EXAURIDA_NOTE}</p>}
          <ul>
            {(piles.listas?.[openPile] ?? []).map((c, i) => <li key={`${c.id}-${i}`}>{c.name}</li>)}
            {!(piles.listas?.[openPile] ?? []).length && <li>Nada aqui.</li>}
          </ul>
        </div>
      )}
      {stuck && <p className="deck-hand__stuck" role="note">{empty ? EMPTY_HAND_NOTE : BLOCKED_HAND_NOTE}</p>}
      <div className="deck-hand__rail">
        {piles.mao.map((card, index) => {
          const reason = reasons[index] ?? null;
          const armed = armedIndex === index;
          const rules = keywordRules(card.texto ?? "", glossary);
          const plain = (card.texto ?? "").replace(/\*\*/g, "");
          const descId = `deck-card-${index}-rules`;
          const desc = [plain, ...rules, reason ? `Indisponível: ${BLOCK_TEXT[reason]}.` : ""].filter(Boolean).join(" ");
          return (
            <button key={`${card.id}-${index}`} type="button" className={`combat-card deck-card${reason ? " is-dim" : ""}${armed ? " is-aiming" : ""}`}
              data-card={card.id} aria-pressed={armed} aria-disabled={reason ? true : undefined}
              aria-keyshortcuts={index < 5 ? String(index + 1) : undefined}
              aria-describedby={descId}
              aria-label={`${card.name}, ${card.custo_folego} de Fôlego${card.custo_entropia ? `, ${card.custo_entropia} de Entropia` : ""}`}
              disabled={busy && !reason}
              onClick={(e) => { if (!busy) onPlay(card, index, e.currentTarget); }}>
              <span className="combat-card__top">
                <span className="deck-card__pips" title="Custo de Fôlego" aria-hidden="true">{"●".repeat(card.custo_folego) || "○"} {card.custo_folego}</span>
                {card.custo_entropia > 0 && <span className="combat-card__cost" title="Custo de Entropia" aria-hidden="true">{card.custo_entropia}E</span>}
              </span>
              <span className="combat-card__name">{card.name}</span>
              {card.texto && <span className="combat-card__desc" aria-hidden="true"><RuleText texto={card.texto} glossary={glossary} /></span>}
              {reason && <span className="combat-card__state" aria-hidden="true">{BLOCK_TEXT[reason]}</span>}
              <span id={descId} className="sr-only">{desc}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
