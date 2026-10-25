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
}

/** SPEC-320 R1–R3/R13: ÚNICA região `role="status"` do turno, dentro do compositor. */
export function TurnStatus({ phases, current, elapsedMs, stage, lastError, onKeepWaiting, onRetry }: TurnStatusProps) {
  const [kept, setKept] = useState(false);
  const waiting = stage === "waiting";
  const tier = waiting ? waitTier(elapsedMs) : "none";
  const showLedger = (waiting || stage === "narrated") && (phases.length > 0 || !!current);

  return (
    <div className="turn-status" role="status" aria-live="polite" aria-atomic="true" data-stage={stage}>
      {showLedger && (
        <ul className="turn-status__ledger">
          {phases.map(p => <li key={p} className="turn-status__done"><span aria-hidden>✓ </span>{p}</li>)}
          {stage === "narrated"
            ? <li className="turn-status__current">registrando…</li>
            : current && <li className="turn-status__current">{current}</li>}
        </ul>
      )}
      {waiting && <span className="turn-status__ink" aria-hidden data-effect="turn.status.ink" />}
      {tier !== "none" && (
        <p className="turn-status__note">A noite é longa; o narrador pondera…</p>
      )}
      {tier === "retry" && !kept && (
        <div className="turn-status__actions">
          <button type="button" className="btn btn--ghost"
            onClick={() => { setKept(true); onKeepWaiting?.(); }}>Continuar esperando</button>
          <button type="button" className="btn btn--ghost" onClick={onRetry}>Tentar de novo</button>
        </div>
      )}
      {stage === "failed-after-narration" && (
        <>
          <p className="turn-status__note">não salvo — a narração acima ainda não foi registrada.</p>
          <div className="turn-status__actions">
            <button type="button" className="btn btn--ghost" onClick={onRetry}>Tentar de novo</button>
          </div>
        </>
      )}
      {stage === "idle" && lastError && (
        <p className="turn-status__error">{lastError.msg}</p>
      )}
    </div>
  );
}
