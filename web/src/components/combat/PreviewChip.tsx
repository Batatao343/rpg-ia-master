import type { PreviewResult } from "../../types";
import { previewLine } from "../../combat/deck";

export type PreviewState = { status: "idle" } | { status: "loading" } | { status: "error" } | { status: "ok"; result: PreviewResult };

/** SPEC-334 R4: prévia do SEU lado (chance/dano). `role=status` anuncia ao leitor de tela (R8). */
export function PreviewChip({ state }: { state: PreviewState }) {
  if (state.status === "idle") return null;
  const text = state.status === "loading" ? "Calculando…"
    : state.status === "error" ? "Prévia indisponível — a jogada continua valendo."
      : previewLine(state.result);
  return (
    <p className="preview-chip" role="status" aria-live="polite" data-preview={state.status}>
      <span className="preview-chip__k">Prévia</span> {text}
    </p>
  );
}
