import type { CombatResultView, TurnOutcome } from "./types";
import { outcomeLines } from "./outcomeToast";

/** SPEC-203 R8: textos do painel de desfecho (puro, testável em Node). */
export const OUTCOME_TITLES: Record<CombatResultView["outcome"], string> = {
  victory: "Vitória",
  fled: "Você escapou",
  surrendered_enemy: "O inimigo se rendeu",
  defeat: "Derrota",
  death: "Você tombou",
  expired: "O confronto se dissipou",
};

const STATUS_LABELS: Record<string, string> = {
  morto: "abatido", fugiu: "fugiu", rendido: "rendido", capturado: "capturado",
  ausente: "partiu", ativo: "de pé",
};

export function resultFrom(raw: unknown): CombatResultView | null {
  const r = raw as Partial<CombatResultView> | null | undefined;
  return r && r.result_event_id && r.outcome ? (r as CombatResultView) : null;
}

export function casualtyLines(result: CombatResultView): string[] {
  return result.participants.map(
    (p) => `${p.species_label} — ${STATUS_LABELS[p.final_status] ?? p.final_status}`);
}

/** Números SÓ do evento SPEC-199, e só quando o recibo é o do turno de término. */
export function rewardLines(result: CombatResultView, outcome?: Partial<TurnOutcome> | null): string[] {
  if (!outcome?.receipt_id || outcome.receipt_id !== result.xp_event_ref) return [];
  return outcomeLines(outcome as TurnOutcome);
}

export function shouldShowResult(result: CombatResultView | null, dismissedId: string | null): boolean {
  return !!result && result.result_event_id !== dismissedId;
}
