import { useCallback, useState } from "react";

export interface DeckArm { index: number; targetId?: string }

/** SPEC-342 R3.4: a carta do Baralho armada vive em `CombateTab`, para a Arena servir de ÚNICO seletor de alvo
 *  (manobra e carta). Só estado de UI; o motor revalida tudo. Exclusão mútua com `useTargeting` é do contêiner. */
export function useDeckArm() {
  const [armed, setArmed] = useState<DeckArm | null>(null);
  /** Arma a carta `index`; com 1 alvo válido só, ele já fica fixado (R3.5). */
  const arm = useCallback((index: number, targets: string[]) => setArmed({ index, targetId: targets.length === 1 ? targets[0] : undefined }), []);
  const setTarget = useCallback((targetId: string) => setArmed((cur) => (cur ? { ...cur, targetId } : cur)), []);
  const clearTarget = useCallback(() => setArmed((cur) => (cur ? { index: cur.index } : cur)), []);
  const disarm = useCallback(() => setArmed(null), []);
  return { armed, arm, setTarget, clearTarget, disarm };
}
