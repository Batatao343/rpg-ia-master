import type { TurnOutcome } from "./types";

/** SPEC-199 R8: linhas mecânicas do ganho do turno (puro, testável em Node). */
export function outcomeLines(o: TurnOutcome | null | undefined): string[] {
  if (!o) return [];
  const out: string[] = [];
  if (o.xp_delta > 0) out.push(`+${o.xp_delta} XP`);
  if (o.level_delta > 0) out.push(o.level_after ? `Nível ${o.level_after}!` : "Novo nível!");
  if (o.gold_delta > 0) out.push(`+${o.gold_delta} ouro`);
  for (const it of o.items_gained ?? []) out.push(`+${it.qty} ${it.name}`);
  for (const q of o.quests_completed ?? []) out.push(`Missão concluída: ${q.title}`);
  return out;
}

/** Só anima quando o receipt_id é novo na sessão de UI (reload não repete). */
export function isNewReceipt(o: TurnOutcome | null | undefined, seen: string | null): boolean {
  return !!o && !!o.receipt_id && o.receipt_id !== seen && outcomeLines(o).length > 0;
}
