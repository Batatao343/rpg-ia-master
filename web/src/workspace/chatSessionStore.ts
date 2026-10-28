// SPEC-204 R7/R8: rascunho, scroll e reação por game_id — só em memória da página (§8 P3).
export interface ChatSession {
  draft: string;
  scrollTop: number | null;
  atBottom: boolean;
  reactionCardId?: string;
}

const sessions = new Map<string, ChatSession>();
const EMPTY: ChatSession = { draft: "", scrollTop: null, atBottom: true };

export function getChatSession(gameId: string | null | undefined): ChatSession {
  return { ...EMPTY, ...(gameId ? sessions.get(gameId) : undefined) };
}

export function setChatSession(gameId: string | null | undefined, patch: Partial<ChatSession>): void {
  if (!gameId) return;
  sessions.set(gameId, { ...getChatSession(gameId), ...patch });
}

/** SPEC-347 R11.2: reabrir um save abre o Livro no fim (a memória de rolagem serve à troca de superfície). */
export function resetBookScroll(gameId: string | null | undefined): void {
  setChatSession(gameId, { scrollTop: null, atBottom: true });
}

export function forgetChatSession(gameId: string): void { sessions.delete(gameId); }
export function forgetAllChatSessions(): void { sessions.clear(); }
