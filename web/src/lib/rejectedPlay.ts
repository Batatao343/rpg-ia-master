// SPEC-363 R21: canal mínimo entre o tratamento do 409 `invalid_target` (App) e a fila do Baralho (DeckCombat).
export interface RejectedPlay { playIndex?: number; cardId?: string }
type Listener = (play: RejectedPlay) => void;
const listeners = new Set<Listener>();

export function subscribeRejectedPlay(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export function publishRejectedPlay(play: RejectedPlay): void {
  for (const fn of [...listeners]) fn(play);
}
