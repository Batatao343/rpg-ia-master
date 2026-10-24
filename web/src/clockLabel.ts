import type { WorldBlock } from "./types";

/** SPEC-307 R17: relógio do HUD. Com `date` (calendário de Valoria) mostra a data completa;
 * senão o texto legado "Dia N · Período". O chip de estação regional (D8) só aparece onde a
 * região tem rótulo próprio. */
export function clockLabel(w: Pick<WorldBlock, "day" | "period" | "date"> | undefined | null): string {
  if (!w?.period) return "Dia 1 · Amanhecer";
  const head = w.date?.label ? `${w.date.label} · ${w.period}` : `Dia ${w.day} · ${w.period}`;
  return w.date?.label && w.date.season_chip ? `${head} · ${w.date.season_chip}` : head;
}
