import type { PreviewResult } from "../../types";
import { previewParts } from "../../combat/deck";

export type PreviewState = { status: "idle" } | { status: "pending" } | { status: "loading" } | { status: "error" } | { status: "ok"; result: PreviewResult };

/** SPEC-334 R4 + SPEC-342 R7.1: prévia do SEU lado (chance/dano). `role=status` anuncia ao leitor de tela.
 *  Sem borda: o número da chance é o destaque (a informação que decide a jogada). */
export function PreviewChip({ state }: { state: PreviewState }) {
  if (state.status === "idle") return null;
  const parts = state.status === "ok" ? previewParts(state.result) : null;
  const text = state.status === "loading" || state.status === "pending" ? "Lendo os sinais…"
    : state.status === "error" ? "Os sinais não se deixam ler agora — a jogada vale do mesmo jeito." : null;
  return (
    <p className="preview-chip" role="status" aria-live="polite" data-preview={state.status}>
      <span className="preview-chip__k">Seu golpe</span>{" "}
      {parts ? (
        <>
          <span className="preview-chip__num">{parts.chance}</span>
          {parts.rest && <span className="preview-chip__rest"> · {parts.rest}</span>}
        </>
      ) : text}
    </p>
  );
}
