/** Detalhe técnico (custo em US$ etc.) só aparece com `?debug=1` na URL (SPEC-323 R3). */
export function debugEnabled(search: string = typeof window === "undefined" ? "" : window.location.search): boolean {
  return new URLSearchParams(search).get("debug") === "1";
}
