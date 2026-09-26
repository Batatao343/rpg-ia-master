// Cookies carry credentials. This store contains only the player's pending command.
export interface PendingOperation {
  version: 1; owner: string; game_id: string; operation_id: string;
  payload: { input_text: string; game_id: string; [key: string]: unknown };
  request_hash: string; created_at: number;
}
const PREFIX = 'valoria:pending:v1:';
const key = (owner: string, game: string) => PREFIX + owner + ':' + game;

export function loadPending(owner: string, game: string): PendingOperation | null {
  try {
    const row = JSON.parse(localStorage.getItem(key(owner, game)) || 'null');
    if (row?.version !== 1 || row.owner !== owner || row.game_id !== game ||
        typeof row.operation_id !== 'string' || !/^[0-9a-f-]{36}$/i.test(row.operation_id) ||
        row.payload?.game_id !== game || typeof row.payload?.input_text !== 'string' ||
        typeof row.request_hash !== 'string' || !/^[0-9a-f]{64}$/.test(row.request_hash) ||
        typeof row.created_at !== 'number') return null;
    return row;
  } catch { return null; }
}

export async function preparePending(owner: string, game: string, input: string,
  options: Record<string, unknown>): Promise<PendingOperation> {
  const existing = loadPending(owner, game);
  if (existing) return existing; // user must resolve this operation before any new one
  const payload = { card_id: null, target_id: null, ruptura: false,
    reaction_card_id: null, action_kind: null, maneuver: null,
    ...options, input_text: input, game_id: game };
  delete (payload as Record<string, unknown>).action_id;
  const sorted = JSON.stringify(payload, Object.keys(payload).sort());
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(sorted));
  const row: PendingOperation = { version: 1, owner, game_id: game, operation_id: crypto.randomUUID(),
    payload, request_hash: Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join(''), created_at: Date.now() };
  // Do not send if persistence fails: reload must retain identity.
  localStorage.setItem(key(owner, game), JSON.stringify(row));
  return row;
}

export function clearPending(owner: string, game: string) { localStorage.removeItem(key(owner, game)); }
export function clearOwner(owner: string) {
  Object.keys(localStorage).filter(k => k.startsWith(PREFIX + owner + ':')).forEach(k => localStorage.removeItem(k));
}
