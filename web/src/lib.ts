// Utilitários de apresentação portados do app.js vanilla.
import type { Speaker } from "./types";

// Markdown mínimo e seguro: escapa HTML, depois aplica **negrito** e *itálico*.
// O retorno é HTML já escapado — seguro para dangerouslySetInnerHTML.
export function mdLite(text: string): string {
  const esc = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)([^*]+?)\*/g, "$1<em>$2</em>");
}

// "espada_velha" -> "Espada Velha"
export function prettyItem(id: string): string {
  return String(id)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const FALLBACK_HINTS = [
  "erro ai",
  "indisponível",
  "narrador está indisponível",
  "transação falhou",
];

export function looksDegraded(text: string): boolean {
  const t = (text || "").toLowerCase();
  return FALLBACK_HINTS.some((h) => t.includes(h));
}

export function pct(cur: number, max: number): number {
  return max > 0 ? Math.max(0, Math.min(100, (cur / max) * 100)) : 0;
}

/** SPEC-202: entrada de histórico (speaker_*) → Speaker; ausente = legado. */
export function speakerFromHistory(entry: { speaker_kind?: string; speaker_id?: string; speaker_name?: string }): Speaker | null {
  const kind = entry.speaker_kind;
  if (kind !== "narrator" && kind !== "npc" && kind !== "system") return null;
  return { kind, id: entry.speaker_id || "", name: entry.speaker_name || "" };
}

/** Rótulo de quem falou. Com `speaker` NPC nomeado → nome canônico; narrador
 *  numa rota de NPC (ausente/mediação) → "Narrador"; sem speaker → legado por tipo. */
export const roleLabel = (role: "player" | "narrator", type: string, speaker?: Speaker | null): string =>
  role === "player"
    ? "Você"
    : speaker?.kind === "npc" && speaker.name
      ? speaker.name
      : speaker && speaker.kind !== "npc" && type === "NPC"
        ? "Narrador"
        : type === "NPC"
      ? "Diálogo"
      : type === "COMBAT"
        ? "Combate"
        : type === "LOOT"
          ? "Espólio"
          : "Narrador";
