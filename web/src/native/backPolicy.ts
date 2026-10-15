export type BackDecision = 'ignore' | 'back' | 'minimize';

/** Android hardware/gesture back. Never exits while an action is in flight or pending. */
export function decideBack(screen: string, busy: boolean, hasPending: boolean): BackDecision {
  if (busy) return 'ignore';
  if (screen === 'account' || screen === 'simulator') return 'back';
  if (screen === 'play' && hasPending) return 'ignore';
  return 'minimize';
}
