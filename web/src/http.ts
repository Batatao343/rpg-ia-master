import { isAndroidClient } from './native/platform';

export class HttpError extends Error {
  constructor(public status: number, public code: string, detail: string) { super(detail); }
}

let refreshing: Promise<void> | null = null;
let authVersion = 0;

function optionsWithAuth(opts: RequestInit): RequestInit {
  const headers = new Headers(opts.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (isAndroidClient()) headers.set('X-RPG-Client', 'android');
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

async function errorFor(response: Response): Promise<HttpError> {
  const fallback = response.statusText || 'Falha na requisição';
  let formatted = { code: fallback, message: fallback };
  try { formatted = formatDetail((await response.json()).detail, fallback); } catch { /* non-JSON */ }
  return new HttpError(response.status, formatted.code, formatted.message);
}

// SPEC-193: one-shot cookie-session refresh used by the native boot (never loops).
export async function refreshSessionOnce(): Promise<boolean> {
  try { return (await fetch('/auth/refresh', optionsWithAuth({ method: 'POST' }))).ok; } catch { return false; }
}

export async function http(path: string, opts: RequestInit = {}): Promise<Response> {
  const version = authVersion;
  let response = await fetch(path, optionsWithAuth(opts));
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
    response = await fetch(path, optionsWithAuth(opts));
  }
  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('rpg:auth-expired'));
    throw await errorFor(response);
  }
  return response;
}

/** Binary upload with an actual upload-complete event; never retries a billed operation. */
export function uploadAudio(audio: Blob, operationId: string, signal: AbortSignal,
  uploaded: () => void): Promise<{ operation_id: string; text: string; billing_status: string }> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Cancelado', 'AbortError')); return; }
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener('abort', abort);
    xhr.open('POST', '/account/transcriptions');
    xhr.withCredentials = true;
    xhr.timeout = 90_000;
    const options = optionsWithAuth({ method: 'POST', headers: {
      'Content-Type': audio.type, 'X-Operation-Id': operationId,
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
        const messages: Record<string, string> = {
          speech_disabled: 'Entrada de voz indisponível nesta sessão. Continue digitando.',
          speech_insufficient_balance: 'Saldo insuficiente para transcrever. Continue digitando.',
          speech_rate_limit: 'Muitas gravações seguidas. Aguarde um minuto ou continue digitando.',
          audio_bytes: 'Áudio muito grande. Grave uma ação mais curta.',
          audio_decoder_unavailable: 'Este navegador não conseguiu preparar o áudio para o servidor. Continue digitando.',
          audio_mime: 'Formato de áudio não aceito. Continue digitando.',
          audio_duration: 'Áudio longo demais. Grave até 60 segundos.',
        };
        const detail = messages[code] || (code.includes(' ') ? code : 'Não foi possível transcrever o áudio. Continue digitando.');
        reject(new HttpError(xhr.status, code, detail));
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
