import { safeStorage } from './safeStorage';
// Cookies carry credentials. This store contains only the player's pending command.
export interface PendingOperation {
  version: 1; owner: string; game_id: string; operation_id: string;
  payload: { input_text: string; game_id: string; [key: string]: unknown };
  request_hash: string; created_at: number;
  /** SPEC-235 R6: persisted in memory only (storage blocked); lost on reload. */
  volatile?: boolean;
}
const PREFIX = 'valoria:pending:v1:';
const key = (owner: string, game: string) => PREFIX + owner + ':' + game;

export function loadPending(owner: string, game: string): PendingOperation | null {
  try {
    const row = JSON.parse(safeStorage.get(key(owner, game)) || 'null');
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
  // Storage blocked: keep going in memory (identity survives retries, not a reload).
  if (!safeStorage.set(key(owner, game), JSON.stringify(row))) row.volatile = true;
  return row;
}

/** SPEC-235 R2: a definitive API refusal means the pending command can never be retried as-is. */
const TRANSIENT_CODES = new Set(['operation_in_progress', 'stale_version', 'game_busy']);
export function shouldClearPending(status: number, code: string): boolean {
  if (status === 400 || status === 404 || status === 422) return true;
  if (status === 409) return !TRANSIENT_CODES.has(code);
  return false;
}

export function clearPending(owner: string, game: string) { safeStorage.remove(key(owner, game)); }
/** SPEC-320 P1-1: só apaga se o pending gravado ainda é desta operação (fluxo antigo nunca pisa no turno novo). */
export function clearPendingIfOwn(owner: string, game: string, operationId: string): boolean {
  if (loadPending(owner, game)?.operation_id !== operationId) return false;
  clearPending(owner, game);
  return true;
}
export function clearOwner(owner: string) {
  safeStorage.keys().filter(k => k.startsWith(PREFIX + owner + ':')).forEach(k => safeStorage.remove(k));
}
