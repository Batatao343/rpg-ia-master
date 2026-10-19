import { isAndroidClient } from './native/platform';
import { BUILD_ID } from './build';
import { reportClientError } from './lib/clientErrors';
import { isCodeLike, messageFor, rateLimitNotice, STALE_PAGE_MESSAGE } from './lib/errorMessages';

export { rateLimitNotice, STALE_PAGE_MESSAGE };

export class HttpError extends Error {
  constructor(public status: number, public code: string, detail: string,
    public retryAfterSeconds?: number, public requestId?: string) { super(detail); }
}

/** SPEC-243 R4: id de correlacao gerado no cliente (o servidor aceita [A-Za-z0-9._:-]{8,64}).
 *  12 hex (48 bits): curto para ditar ao suporte e buscavel inteiro nos logs da Vercel. */
export function newRequestId(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  const raw = c?.randomUUID ? c.randomUUID().replace(/-/g, "")
    : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
  return raw.slice(0, 12).padEnd(12, "0");
}

let refreshing: Promise<void> | null = null;
let authVersion = 0;

function optionsWithAuth(opts: RequestInit): RequestInit {
  const headers = new Headers(opts.headers);
  if (!headers.has("X-Request-ID")) headers.set("X-Request-ID", newRequestId());
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (isAndroidClient()) headers.set('X-RPG-Client', 'android');
  headers.set('X-RPG-Build', BUILD_ID);   // SPEC-261 R2: cliente x servidor no access log
  if (!['GET', 'HEAD', 'OPTIONS'].includes((opts.method || 'GET').toUpperCase())) {
    const csrf = document.cookie.split('; ').find(row => row.startsWith('rpg_csrf='))?.split('=')[1];
    if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf));
  }
  return { ...opts, headers, credentials: 'include' };
}

/** SPEC-235 R4: FastAPI `detail` may be a string, an object or a 422 list of {loc,msg}. */
export function formatDetail(detail: unknown, fallback: string): { code: string; message: string } {
  if (typeof detail === 'string') return { code: detail, message: detail || fallback };
  if (Array.isArray(detail)) {
    const parts = detail.map(item => {
      if (typeof item === 'string') return item;
      if (!item || typeof item !== 'object') return '';
      const row = item as { msg?: unknown; loc?: unknown };
      const where = Array.isArray(row.loc) ? row.loc.slice(1).join('.') : '';
      const msg = typeof row.msg === 'string' ? row.msg : '';
      return where && msg ? `${where}: ${msg}` : msg || where;
    }).filter(Boolean);
    const message = parts.join('; ') || fallback;
    return { code: 'validation_error', message };
  }
  if (detail && typeof detail === 'object') {
    const row = detail as { code?: unknown; msg?: unknown; message?: unknown };
    const message = typeof row.message === 'string' ? row.message
      : typeof row.msg === 'string' ? row.msg : JSON.stringify(detail);
    return { code: typeof row.code === 'string' ? row.code : message, message };
  }
  return { code: fallback, message: fallback };
}

/** SPEC-220 R10: Origin/CSRF => 403; é página desatualizada, não sessão expirada. */
export const STALE_PAGE_CODES = new Set(['csrf_invalid', 'origin_denied']);

async function errorFor(response: Response, sentRequestId?: string): Promise<HttpError> {
  const fallback = response.statusText || 'Falha na requisição';
  let formatted = { code: fallback, message: fallback };
  let retryAfter: number | undefined;
  let requestId = response.headers?.get?.('X-Request-ID') || sentRequestId || undefined;
  try {
    const body = await response.json();
    formatted = formatDetail(body.detail, fallback);
    // SPEC-242: ``code`` estavel do envelope; o codigo derivado do detail vence quando ja e um codigo.
    if (!isCodeLike(formatted.code) && isCodeLike(body.code)) formatted = { ...formatted, code: body.code };
    if (typeof body.request_id === 'string' && body.request_id) requestId = body.request_id;
    if (typeof body.retry_after_seconds === 'number') retryAfter = body.retry_after_seconds;
  } catch { /* non-JSON */ }
  if (retryAfter === undefined) {
    const header = Number(response.headers?.get?.('Retry-After'));
    if (Number.isFinite(header) && header > 0) retryAfter = header;
  }
  if (response.status === 429 || response.status === 503) {
    const notice = rateLimitNotice(formatted.code, retryAfter);
    if (notice) return new HttpError(response.status, formatted.code, notice, retryAfter, requestId);
  }
  if (response.status === 403 && STALE_PAGE_CODES.has(formatted.code)) {
    formatted = { code: formatted.code, message: STALE_PAGE_MESSAGE };
  }
  // SPEC-243 R2: codigo cru nunca vira mensagem; prosa do servidor (pt-BR) e preservada.
  const message = messageFor(formatted.code, formatted.message, retryAfter);
  return new HttpError(response.status, formatted.code, message, retryAfter, requestId);
}

// SPEC-193: one-shot cookie-session refresh used by the native boot (never loops).
export async function refreshSessionOnce(): Promise<boolean> {
  try { return (await fetch('/auth/refresh', optionsWithAuth({ method: 'POST' }))).ok; } catch { return false; }
}

async function fetchWithId(path: string, opts: RequestInit): Promise<{ response: Response; requestId: string }> {
  const options = optionsWithAuth(opts);
  const requestId = new Headers(options.headers).get('X-Request-ID') || '';
  try {
    return { response: await fetch(path, options), requestId };
  } catch (error) {
    // Sem resposta: o id local ainda permite ao suporte procurar a requisicao no servidor. O erro
    // ORIGINAL segue (TypeError): o fluxo de fallback SSE->POST depende de nao ser um HttpError.
    if (error instanceof Error) (error as Error & { requestId?: string }).requestId = requestId;
    // SPEC-244 R2: fetch sem resposta (rede/CORS/offline). Cancelamento do usuario nao conta.
    if (!(error instanceof Error && error.name === 'AbortError')) {
      reportClientError({ kind: 'network', error, code: 'fetch_failed', route: path, requestId });
    }
    throw error;
  }
}

export async function http(path: string, opts: RequestInit = {}): Promise<Response> {
  const version = authVersion;
  const first = await fetchWithId(path, opts);
  let response = first.response;
  let sentId = first.requestId;
  if (response.status === 401 && !path.startsWith('/auth/')) {
    if (version === authVersion) {
      if (!refreshing) {
        refreshing = (async () => {
          const refreshed = await fetch('/auth/refresh', optionsWithAuth({ method: 'POST' }));
          if (!refreshed.ok) throw await errorFor(refreshed);
          authVersion++;
        })().finally(() => { refreshing = null; });
      }
      try { await refreshing; } catch (error) {
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('rpg:auth-expired'));
        throw error;
      }
    }
    const retry = await fetchWithId(path, opts);
    response = retry.response;
    sentId = retry.requestId;
  }
  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('rpg:auth-expired'));
    throw await errorFor(response, sentId);
  }
  return response;
}

/** Binary upload with an actual upload-complete event; never retries a billed operation. */
export function uploadAudio(audio: Blob, operationId: string, signal: AbortSignal,
  uploaded: () => void): Promise<{ operation_id: string; text: string; billing_status: string }> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Cancelado', 'AbortError')); return; }
    const xhr = new XMLHttpRequest();
    const sentId = newRequestId();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener('abort', abort);
    xhr.open('POST', '/account/transcriptions');
    xhr.withCredentials = true;
    xhr.timeout = 90_000;
    const options = optionsWithAuth({ method: 'POST', headers: {
      'Content-Type': audio.type, 'X-Operation-Id': operationId, 'X-Request-ID': sentId,
    } });
    new Headers(options.headers).forEach((value, key) => xhr.setRequestHeader(key, value));
    xhr.upload.onload = uploaded;
    xhr.onload = () => {
      cleanup();
      let body;
      try { body = JSON.parse(xhr.responseText); }
      catch { reject(new Error('Resposta de transcrição inválida. Continue digitando.')); return; }
      if (!body || typeof body !== 'object' || Array.isArray(body)) {
        reject(new Error('Resposta de transcrição inválida. Continue digitando.')); return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        if (xhr.status === 401) window.dispatchEvent(new Event('rpg:auth-expired'));
        const code = String(body.detail || 'speech_failed');
        const detail = messageFor(isCodeLike(code) ? code : 'speech_failed', code.includes(' ') ? code : undefined);
        const rid = xhr.getResponseHeader?.('X-Request-ID') || (typeof body.request_id === 'string' ? body.request_id : undefined);
        reject(new HttpError(xhr.status, code, detail, undefined, rid || sentId));
      } else if (typeof body.text !== 'string') {
        reject(new Error('Resposta de transcrição inválida. Continue digitando.'));
      } else resolve(body);
    };
    xhr.onerror = () => { cleanup(); reject(new Error('Não foi possível enviar o áudio. Continue digitando.')); };
    xhr.ontimeout = () => { cleanup(); reject(new Error('A transcrição demorou demais. Continue digitando.')); };
    xhr.onabort = () => { cleanup(); reject(new DOMException('Cancelado', 'AbortError')); };
    signal.addEventListener('abort', abort, { once: true });
    xhr.send(audio);
  });
}
