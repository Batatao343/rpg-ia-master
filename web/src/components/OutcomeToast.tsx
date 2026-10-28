import { useEffect, useRef, useState } from "react";
import type { TurnOutcome } from "../types";
import { isNewReceipt, outcomeLines } from "../outcomeToast";

const SHOW_MS = 4500;

/** SPEC-199: chip mecânico com os ganhos do turno (XP/ouro/itens/missões). */
export function OutcomeToast({ outcome, suppress = false }: { outcome?: TurnOutcome | null; suppress?: boolean }) {
  const seen = useRef<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const first = useRef(true);

  useEffect(() => {
    const id = outcome?.receipt_id ?? null;
    // A 1ª projeção da sessão (reload/continuar) só registra o recibo, sem animar.
    if (first.current) { first.current = false; seen.current = id; return; }
    if (suppress) { seen.current = id; return; } // SPEC-354 R7.1: o desfecho já mostra os ganhos; recibo visto
    if (!isNewReceipt(outcome, seen.current)) { seen.current = id ?? seen.current; return; }
    seen.current = id;
    setLines(outcomeLines(outcome));
    const t = window.setTimeout(() => setLines([]), SHOW_MS);
    return () => window.clearTimeout(t);
  }, [outcome, suppress]);

  return (
    <div className="outcome-toast" aria-live="polite" aria-atomic="true">
      {(suppress ? [] : lines).map((l) => <span key={l} className="outcome-chip">{l}</span>)}
    </div>
  );
}
