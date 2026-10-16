// SPEC-206: helpers puros do selo de conhecimento do Codex (testados em Node).
import type { KnowledgeStamp, PlayerCodex } from "./types";

export type CodexCategory = "locations" | "factions" | "characters" | "creatures" | "secrets";

/** Contagem da aba: `meta.counts` (já filtrado no servidor) com fallback p/ `.length`. */
export function categoryCount(codex: PlayerCodex, category: CodexCategory): number {
  const fromMeta = codex.meta?.counts?.[category];
  return typeof fromMeta === "number" ? fromMeta : (codex[category]?.length ?? 0);
}

/** Tooltip montado SÓ com label + turnos (R13) — nenhum campo privado. */
export function knowledgeTooltip(stamp: KnowledgeStamp | undefined): string {
  if (!stamp) return "";
  const parts = [stamp.label];
  if (stamp.first_seen_turn != null) parts.push(`visto no turno ${stamp.first_seen_turn}`);
  if (stamp.last_updated_turn != null) parts.push(`atualizado no turno ${stamp.last_updated_turn}`);
  return parts.join(" · ");
}

/** Texto do selo; facção com intel antiga ganha sufixo discreto (D3). */
export function knowledgeBadgeText(stamp: KnowledgeStamp | undefined): string {
  if (!stamp) return "";
  return stamp.stale ? `${stamp.label} · pode estar desatualizado` : stamp.label;
}
