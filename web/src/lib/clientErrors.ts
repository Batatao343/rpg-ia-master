// SPEC-244: captura de erros do cliente -> POST /telemetry/client-error (beacon redigido).
// Nunca envia mensagem de erro, texto do jogador, URL com query ou e-mail: so nome da classe,
// codigo fechado, rota da API em template, request_id, build e frames `arquivo:linha:coluna`.
import { BUILD_ID } from '../build';
import { isAndroidClient } from '../native/platform';

export type ClientErrorKind = 'render' | 'unhandled' | 'network' | 'sse' | 'native';

export interface ClientErrorInput {
  kind: ClientErrorKind;
  error?: unknown;
  code?: string;
  route?: string;
  requestId?: string;
}

export interface ClientErrorPayload {
  kind: ClientErrorKind;
  error_name: string;
  code?: string;
  route?: string;
  request_id?: string;
  build?: string;
  client: 'web' | 'android';
  stack: string[];
  ts: number;
}

const ENDPOINT = '/telemetry/client-error';
const MAX_PER_SESSION = 20;
const DEDUPE_MS = 60_000;
const MAX_FRAMES = 8;

let sent = 0;
const lastSent = new Map<string, number>();
let sending = false;

/** Testes: zera dedupe/teto da sessao. */
export function resetClientErrors(): void {
  sent = 0;
  lastSent.clear();
  sending = false;
}

const NAME_RE = /^[A-Za-z_$][A-Za-z0-9_$.]{0,59}$/;
const CODE_RE = /^[a-z0-9_.:-]{1,64}$/;
const RID_RE = /^[A-Za-z0-9._:-]{8,64}$/;
const BUILD_RE = /^(?:[0-9a-f]{7}|dev)\+\d{12}$/;

/** Rota da API sem query e sem ids: UUIDs/numeros/hex longos viram `{id}`. */
export function routeTemplate(path: string | undefined): string | undefined {
  if (!path) return undefined;
  let p = String(path);
  try { if (/^https?:/i.test(p)) p = new URL(p).pathname; } catch { return undefined; }
  p = p.split(/[?#]/)[0];
  p = p.split('/').map(seg => (/^[0-9a-f-]{16,}$/i.test(seg) || /^\d+$/.test(seg)) ? '{id}' : seg).join('/');
  return /^\/[A-Za-z0-9_/{}.-]{0,120}$/.test(p) ? p : undefined;
}

/** Frames `arquivo:linha:coluna` do bundle; descarta a mensagem, origem, query e qualquer outra coisa. */
export function sanitizeStack(stack: unknown): string[] {
  if (typeof stack !== 'string') return [];
  const frames: string[] = [];
  for (const line of stack.split('\n')) {
    const m = line.match(/((?:https?:\/\/[^/\s)]+)?\/?[^\s()?#@]*?\.(?:m?js|tsx?|jsx))(?:\?[^\s:)]*)?:(\d{1,7})(?::(\d{1,7}))?/);
    if (!m) continue;
    let file = m[1].replace(/^https?:\/\/[^/]+/, '').replace(/^\/+/, '');
    file = file.split('/').slice(-2).join('/');
    const frame = `${file}:${m[2]}${m[3] ? `:${m[3]}` : ''}`;
    if (/^[A-Za-z0-9_./-]{1,120}:\d{1,7}(?::\d{1,7})?$/.test(frame)) frames.push(frame);
    if (frames.length >= MAX_FRAMES) break;
  }
  return frames;
}

export function buildPayload(input: ClientErrorInput, now = Date.now()): ClientErrorPayload {
  const err = input.error as { name?: unknown; stack?: unknown } | undefined;
  const rawName = typeof err?.name === 'string' ? err.name : (input.error === undefined ? 'Error' : typeof input.error);
  const payload: ClientErrorPayload = {
    kind: input.kind,
    error_name: NAME_RE.test(rawName) ? rawName : 'Error',
    client: isAndroidClient() ? 'android' : 'web',
    stack: sanitizeStack(err?.stack),
    ts: now,
  };
  if (input.code && CODE_RE.test(input.code)) payload.code = input.code;
  const route = routeTemplate(input.route);
  if (route) payload.route = route;
  if (input.requestId && RID_RE.test(input.requestId)) payload.request_id = input.requestId;
  if (BUILD_RE.test(BUILD_ID)) payload.build = BUILD_ID;
  return payload;
}

function transmit(body: string): void {
  const nav = (globalThis as { navigator?: { sendBeacon?: (url: string, data: Blob) => boolean } }).navigator;
  if (nav?.sendBeacon && typeof Blob !== 'undefined') {
    // sendBeacon pode LANCAR (Blob application/json nao e CORS-safelisted em alguns Chromium): cai no fetch.
    try {
      if (nav.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }))) return;
    } catch { /* fallback abaixo */ }
  }
  const f = (globalThis as { fetch?: typeof fetch }).fetch;
  if (f) void f(ENDPOINT, { method: 'POST', body, keepalive: true, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' } }).catch(() => { /* beacon nunca gera beacon */ });
}

/** Envia (no maximo 20/sessao; mesma assinatura <= 1x/min). Nunca lanca, nunca recursa. */
export function reportClientError(input: ClientErrorInput, now = Date.now()): boolean {
  if (sending) return false;
  sending = true;
  try {
    if (sent >= MAX_PER_SESSION) return false;
    const payload = buildPayload(input, now);
    const signature = [payload.kind, payload.error_name, payload.code, payload.route, payload.stack[0]].join('|');
    const last = lastSent.get(signature);
    if (last !== undefined && now - last < DEDUPE_MS) return false;
    lastSent.set(signature, now);
    sent++;
    transmit(JSON.stringify(payload));
    return true;
  } catch {
    return false;
  } finally {
    sending = false;
  }
}

/** `error`/`unhandledrejection` globais (instalar uma vez no boot). */
export function installGlobalErrorHandlers(target: Pick<Window, 'addEventListener'> = window): void {
  target.addEventListener('error', (event: Event) => {
    const e = event as ErrorEvent;
    if (!e.error && !e.message) return;   // erro de carga de recurso (img/script) nao e excecao JS
    reportClientError({ kind: 'unhandled', error: e.error ?? { name: 'Error' } });
  });
  target.addEventListener('unhandledrejection', (event: Event) => {
    const reason = (event as PromiseRejectionEvent).reason;
    if (reason && typeof reason === 'object' && (reason as { name?: string }).name === 'AbortError') return;
    reportClientError({ kind: 'unhandled', error: reason });
  });
}
