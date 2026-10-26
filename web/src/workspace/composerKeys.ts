/** SPEC-321 R10: Enter envia, Shift+Enter quebra linha; durante a composição de IME (teclados Android,
 *  CJK) Enter confirma o texto e NUNCA envia. `keyCode 229` cobre WebViews que não mandam `isComposing`. */
export interface ComposerKeyEvent {
  key: string;
  shiftKey: boolean;
  isComposing?: boolean;
  keyCode?: number;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
}

export function shouldSubmitOnKey(e: ComposerKeyEvent): boolean {
  if (e.key !== "Enter") return false;
  if (e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return false;
  if (e.isComposing || e.keyCode === 229) return false;
  return true;
}

/** Altura (px) do textarea: cresce com o conteúdo até `maxLines` linhas e rola dali em diante. */
export function composerHeight(scrollHeight: number, lineHeightPx: number, paddingPx: number, maxLines = 4): number {
  const max = Math.round(lineHeightPx * maxLines + paddingPx);
  return Math.min(scrollHeight, max);
}
