import type { GameResponse } from "./types";

export interface Suggestion { id: string; label: string; text: string }

const MAX = 4;
const BEAT_MAX = 70;

/** SPEC-323 R10: sugestões fora do combate, só do estado atual (sem LLM, sem efeito mecânico). */
export function suggestionsFor(data: Partial<GameResponse> | null | undefined): Suggestion[] {
  if (!data || data.game_over || data.death_pending || data.combat?.active || data.combat_simulation?.enabled) return [];
  const out: Suggestion[] = [];
  const present = (data.npcs ?? []).filter(n => n.in_scene && n.status !== "morto").slice(0, 2);
  for (const n of present) out.push({ id: `npc:${n.name}`, label: `Falar com ${n.name}`, text: `Falo com ${n.name}` });
  const main = data.quest?.main;
  // A API redige os beats ("Etapa N"); o objetivo público é o único texto seguro.
  const beat = main?.objective?.trim();
  if (beat) {
    const short = beat.length > BEAT_MAX ? `${beat.slice(0, BEAT_MAX - 1).trimEnd()}…` : beat;
    out.push({ id: "objective", label: "Seguir objetivo", text: `Sigo o objetivo: ${short}` });
  }
  out.push({ id: "rest", label: "Descansar", text: "Descanso um pouco" });
  return out.slice(0, MAX);
}
