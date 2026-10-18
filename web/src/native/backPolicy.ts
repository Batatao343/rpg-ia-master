export type BackDecision = 'ignore' | 'back' | 'minimize' | 'chat';

/** Android hardware/gesture back. Never exits while an action is in flight or pending.
 *  SPEC-216 R2: numa superfície mobile que não é o chat, voltar leva ao chat ANTES de sair. */
export function decideBack(screen: string, busy: boolean, hasPending: boolean, offChat = false): BackDecision {
  if (screen === 'play' && offChat) return 'chat';
  if (busy) return 'ignore';
  if (screen === 'account' || screen === 'simulator') return 'back';
  if (screen === 'play' && hasPending) return 'ignore';
  return 'minimize';
}
