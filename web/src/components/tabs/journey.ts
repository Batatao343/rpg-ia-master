import type { ChronicleChapter } from "../../types";

/** R11: marcos de evolução já públicos na crônica (nível e subclasse) — sem log novo. */
const EVOLUTION = /alcançou o nível|subclasse .* foi escolhida/i;
export function evolutionHistory(chapters: ChronicleChapter[] | undefined): string[] {
  const out: string[] = [];
  for (const chapter of chapters ?? []) {
    for (const entry of chapter.entries ?? []) {
      if (entry.kind === "milestone" && EVOLUTION.test(entry.text)) out.push(entry.text);
    }
  }
  return out.reverse().slice(0, 12);
}
