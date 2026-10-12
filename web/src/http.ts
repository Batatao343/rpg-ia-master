export class HttpError extends Error {
  constructor(public status: number, public code: string, detail: string) { super(detail); }
}

let refreshing: Promise<void> | null = null;
let authVersion = 0;

function optionsWithAuth(opts: RequestInit): RequestInit {
  const headers = new Headers(opts.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!['GET', 'HEAD', 'OPTIONS'].includes((opts.method || 'GET').toUpperCase())) {
    const csrf = document.cookie.split('; ').find(row => row.startsWith('rpg_csrf='))?.split('=')[1];
    if (csrf) headers.set('X-CSRF-Token', decodeURIComponent(csrf));
  }
  return { ...opts, headers, credentials: 'include' };
}

async function errorFor(response: Response): Promise<HttpError> {
  let detail = response.statusText || 'Falha na requisição';
  try { detail = String((await response.json()).detail || detail); } catch { /* non-JSON */ }
  return new HttpError(response.status, detail, detail);
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
