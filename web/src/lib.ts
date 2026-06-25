// Utilitários de apresentação portados do app.js vanilla.

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

export const roleLabel = (role: "player" | "narrator", type: string): string =>
  role === "player"
    ? "Você"
    : type === "NPC"
      ? "Diálogo"
      : type === "COMBAT"
        ? "Combate"
        : type === "LOOT"
          ? "Espólio"
          : "Narrador";
