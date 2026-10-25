import { useState } from "react";
import type { BannerState } from "../components/Banner";
import { waitTier, type TurnStage } from "../turnWait";

export interface TurnStatusProps {
  /** Fases já cumpridas (✓, `--muted`). */
  phases: string[];
  /** Fase atual (`--ink`). */
  current: string | null;
  /** Ms desde o envio sem nenhum chunk de narração (0 quando já há texto). */
  elapsedMs: number;
  stage: TurnStage;
  /** Último erro do turno; fica aqui até o próximo envio (R10). */
  lastError?: BannerState | null;
  onKeepWaiting?: () => void;
  onRetry: () => void;
  /** Devolve o foco ao input quando um botão de espera some (P2-5). */
  onFocusInput?: () => void;
}

const REASSURE_TEXT = "A noite é longa; o narrador pondera…";

/** SPEC-320 R1–R3/R13. A ÚNICA região viva é o `<span role="status">` (só fase atual/aviso, sem reler o
 *  livro-razão); o livro-razão e os botões ficam fora dela e o erro é anunciado só pelo banner (`aria-hidden` aqui). */
export function TurnStatus({ phases, current, elapsedMs, stage, lastError, onKeepWaiting, onRetry, onFocusInput }: TurnStatusProps) {
  const [kept, setKept] = useState(false);
  const waiting = stage === "waiting";
  const tier = waiting ? waitTier(elapsedMs) : "none";
  const showLedger = (waiting || stage === "narrated") && (phases.length > 0 || !!current);
  const showRetryActions = tier === "retry" && !kept;
  const showError = stage === "idle" && !!lastError;

  const live = stage === "narrated" ? "registrando…"
    : stage === "failed-after-narration" ? "Não salvo. A narração acima ainda não foi registrada."
    : waiting ? [tier !== "none" ? REASSURE_TEXT : "", current ?? ""].filter(Boolean).join(" ") : "";

  const act = (fn?: () => void) => () => { fn?.(); onFocusInput?.(); };
  const visible = showLedger || waiting || stage === "failed-after-narration" || showError;

  return (
    <>
      <span className="sr-only" aria-live="polite" aria-atomic="true">{live}</span>
      {visible && (
        <div className="turn-status" data-stage={stage}>
          {showLedger && (
            <ul className="turn-status__ledger">
              {phases.map(p => <li key={p} className="turn-status__done"><span aria-hidden>✓ </span>{p}</li>)}
              {stage === "narrated"
                ? <li className="turn-status__current">registrando…</li>
                : current && <li className="turn-status__current">{current}</li>}
            </ul>
          )}
          {waiting && <span className="turn-status__ink" aria-hidden data-effect="turn.status.ink" />}
          {tier !== "none" && <p className="turn-status__note" aria-hidden>{REASSURE_TEXT}</p>}
          {showRetryActions && (
            <div className="turn-status__actions">
              <button type="button" className="btn btn--ghost"
                onClick={act(() => { setKept(true); onKeepWaiting?.(); })}>Continuar esperando</button>
              <button type="button" className="btn btn--ghost" onClick={act(onRetry)}>Tentar de novo</button>
            </div>
          )}
          {stage === "failed-after-narration" && (
            <>
              <p className="turn-status__note" aria-hidden>não salvo — a narração acima ainda não foi registrada.</p>
              <div className="turn-status__actions">
                <button type="button" className="btn btn--ghost" onClick={act(onRetry)}>Tentar de novo</button>
              </div>
            </>
          )}
          {showError && <p className="turn-status__error" aria-hidden>O último envio falhou; veja o aviso acima.</p>}
        </div>
      )}
    </>
  );
}
