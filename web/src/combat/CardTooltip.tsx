import type { CardView } from "../types";
import { REASON_TEXT } from "./targeting";

const FREQ_LABEL: Record<string, string> = {
  livre: "livre (sem limite)",
  turno: "1× por turno",
  cena: "1× por cena",
  descanso_curto: "1× por descanso curto",
  descanso_longo: "1× por descanso longo",
};

/** SPEC-205 R13: painel de detalhe da carta (hover e foco). Fixo — nunca cobre outra carta.
 *  Todos os números vêm do payload do servidor. */
export function CardTooltip({ card, id }: { card: CardView | null; id: string }) {
  return (
    <div id={id} className="card-detail" data-aim-safe>
      {!card ? <p className="card-detail__hint">Passe o mouse ou foque uma carta para ver custo, limite e efeito.</p> : (
        <>
          <p className="card-detail__title"><strong>{card.name}</strong></p>
          <p>
            {`Custo: ${card.cost}E`}{card.base_cost !== undefined && card.base_cost !== card.cost ? ` (base ${card.base_cost}E)` : ""}
            {` · Limite: ${FREQ_LABEL[card.frequency] ?? card.frequency}`}
            {card.frequency !== "livre" ? (card.spent ? " — já usada" : " — disponível") : ""}
          </p>
          {card.trigger && <p>{`Gatilho: ${card.trigger.replace(/_/g, " ")}`}</p>}
          {card.description && <p>{card.description}</p>}
          {(card.invalid_reason || !card.ready) && (
            <p className="card-detail__reason">
              {`Indisponível: ${card.invalid_reason ? REASON_TEXT[card.invalid_reason] : card.spent ? "frequência esgotada" : "Entropia insuficiente"}`}
            </p>
          )}
        </>
      )}
    </div>
  );
}
