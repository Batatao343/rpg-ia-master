import type { CombatResultView, TurnOutcome } from "../types";
import { OUTCOME_TITLES, casualtyLines, rewardLines } from "../combatOutcome";

interface Props {
  result: CombatResultView;
  outcome?: Partial<TurnOutcome> | null;
  /** Fecha SÓ este painel (ação local; não consome turno nem toca o composer). */
  onContinue: () => void;
}

/** SPEC-203 R8: desfecho mecânico do encontro. Componente isolado — o shell
 *  (SPEC-204) decide onde montá-lo; aqui não há layout de abas. */
export function CombatOutcomePanel({ result, outcome, onContinue }: Props) {
  const rewards = rewardLines(result, outcome);
  return (
    <section className={`combat-outcome combat-outcome--${result.outcome}`}
             role="region" aria-label="Desfecho do combate">
      <h2 className="combat-outcome__title">{OUTCOME_TITLES[result.outcome] ?? result.outcome}</h2>
      <ul className="combat-outcome__cast">
        {casualtyLines(result).map((line, i) => <li key={`${i}-${line}`}>{line}</li>)}
      </ul>
      {rewards.length > 0 && (
        <ul className="combat-outcome__rewards" aria-label="Ganhos do combate">
          {rewards.map((line) => <li key={line}>{line}</li>)}
        </ul>
      )}
      <button className="btn btn--primary combat-outcome__continue" type="button" onClick={onContinue}>
        Continuar
      </button>
    </section>
  );
}
