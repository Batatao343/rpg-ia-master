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
