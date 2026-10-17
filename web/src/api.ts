// Cliente da API FastAPI. Mesma origem em produção; via proxy do Vite em dev.
import type {
  CreateOptions,
  CreatePayload,
  CombatSimulatorOptions,
  CombatSimulatorPayload,
  ActionOptions,
  GameResponse,
  OnboardingData,
  PlayerCodex,
  PrologueResponse,
  SaveSummary,
  WorldMapData,
  VisualResponse,
} from "./types";

import { formatDetail, http, HttpError, uploadAudio } from "./http";
import { setClientLatencyReport } from "./lib/turnLatency";
export { HttpError } from "./http";
export { refreshSessionOnce } from "./http";

export async function transcribeAudio(audio: Blob, signal: AbortSignal, uploaded: () => void): Promise<string> {
  const result = await uploadAudio(audio, crypto.randomUUID(), signal, uploaded);
  return result.text;
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await http(path, opts);
  return res.status === 204 ? undefined as T : res.json() as Promise<T>;
}

export interface AuthConfig {
  required: boolean;
  authenticated: boolean;
  user_id?: string;
  lifecycle_available?: boolean;
  client_latency_report?: boolean;
  email_confirmation_required?: boolean;
  captcha?: { required: boolean; site_key: string | null; provider: "turnstile"; mode?: "app" | "gotrue" };
}
export interface AuthResponse { authenticated: boolean; csrf_token?: string; message?: string }
export const getAuthConfig = () => req<AuthConfig>("/auth/config").then((config) => {
  setClientLatencyReport(config.client_latency_report === true);   // SPEC-200 R10
  return config;
});
export const login = (email: string, password: string, captchaToken?: string) =>
  req<AuthResponse>("/auth/login", {
    method: "POST", body: JSON.stringify({ email, password,
      ...(captchaToken ? { captcha_token: captchaToken } : {}) }),
  });

export const signup = (email: string, password: string, captchaToken?: string) =>
  req<AuthResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, ...(captchaToken ? { captcha_token: captchaToken } : {}) }),
  });
// SPEC-220 R1: sob /auth/refresh para receber o cookie de refresh (path /auth/refresh)
// e revogá-lo no servidor mesmo com o access vencido.
export const logout = () => req<void>("/auth/refresh/logout", { method: "POST" });
export const requestPasswordReset = (email: string, captchaToken?: string) =>
  req<{ message: string }>("/auth/reset/request", { method: "POST",
    body: JSON.stringify({ email, ...(captchaToken ? { captcha_token: captchaToken } : {}) }) });
export const requestEmailVerification = (email: string, captchaToken?: string) =>
  req<{ message: string }>("/auth/verify/request", { method: "POST",
    body: JSON.stringify({ email, ...(captchaToken ? { captcha_token: captchaToken } : {}) }) });
export const confirmEmailVerification = (tokenHash: string) =>
  req<AuthResponse>("/auth/verify", { method: "POST",
    body: JSON.stringify({ token_hash: tokenHash, type: "signup" }) });
export const confirmPasswordReset = (tokenHash: string, newPassword: string) =>
  req<{ authenticated: false; message: string }>("/auth/reset/confirm", { method: "POST",
    body: JSON.stringify({ token_hash: tokenHash, new_password: newPassword }) });
export const reauthenticate = (password: string, captchaToken?: string) =>
  req<{ recent: boolean }>("/auth/reauth", { method: "POST", body: JSON.stringify({ password,
    ...(captchaToken ? { captcha_token: captchaToken } : {}) }) });
export const exportAccount = async (): Promise<Blob> => (await http("/account/export")).blob();
// SPEC-207: pacote ZIP de auditoria da campanha (owner-only, exige prova recente).
export const exportGameAudit = async (game_id: string): Promise<Blob> =>
  (await http("/game/" + encodeURIComponent(game_id) + "/audit-export", { method: "POST" })).blob();
export const deleteAccount = () => req<{ status: "deleted" | "deleting" }>("/account/delete", {
  method: "POST", body: JSON.stringify({ confirmation: "EXCLUIR" }),
});

export const getOptions = () => req<CreateOptions>("/data/options");

export const getCombatSimulatorOptions = () =>
  req<CombatSimulatorOptions>("/data/combat-simulator");

export const newCombatSimulator = (payload: CombatSimulatorPayload) =>
  req<GameResponse>("/game/combat-simulator", {
    method: "POST",
    body: JSON.stringify({ ...payload, action_id: crypto.randomUUID() }),
  });

// spec onboarding-valoria: lore curado do wizard de criação (estático)
export const getOnboarding = () => req<OnboardingData>("/data/onboarding");

// spec inicio-personalizado: prólogo confirmável (1 chamada SMART no servidor)
export const postPrologue = (payload: CreatePayload) =>
  req<PrologueResponse>("/game/prologue", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getMap = () => req<WorldMapData>("/data/map");

export const newGame = (payload: CreatePayload) =>
  req<GameResponse>("/game/new", {
    method: "POST",
    body: JSON.stringify({ ...payload, action_id: crypto.randomUUID() }),
  });

export const sendAction = (input_text: string, game_id: string | null, options: ActionOptions = {}) =>
  req<GameResponse>("/game/action", {
    method: "POST",
    body: JSON.stringify({ input_text, game_id, ...options }),
  });

// spec checkpoints-morte (D2): resolve a tela de morte —
// "continue" restaura do checkpoint, "accept" encerra em memorial.
export const resolveDeath = (game_id: string | null, choice: "continue" | "accept") =>
  req<GameResponse>("/game/death", {
    method: "POST",
    body: JSON.stringify({ game_id, choice, action_id: crypto.randomUUID() }),
  });

// spec streaming-turno-sse (R4): turno via SSE — fases reais do grafo enquanto
// o LLM pensa. POST não funciona com EventSource nativo, então o parser de
// `event:`/`data:` é manual sobre fetch + ReadableStream. Qualquer falha antes
// do evento `state` deve levar o chamador ao fallback (POST clássico).
export interface StreamHandlers {
  onPhase?: (node: string) => void;
  onRoute?: (route: string) => void;
  onChunk?: (chunk: string, done: boolean) => void;
  onVisual?: (visual: VisualResponse) => void;
  /** SPEC-200: primeiro byte do corpo SSE lido (ack percebido). */
  onAck?: () => void;
  /** SPEC-200: TODOS os eventos decodificados, inclusive `accepted`. */
  onEvent?: (name: string, payload: unknown) => void;
}

export async function sendActionStream(
  input_text: string,
  game_id: string | null,
  handlers: StreamHandlers = {},
  options: ActionOptions = {},
): Promise<GameResponse> {
  const res = await http("/game/action/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_text, game_id, ...options }),
  });
  if (!res.ok || !res.body) throw new Error("stream indisponível: " + res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "";
  let finalState: GameResponse | null = null;

  const handleEvent = (name: string, data: string) => {
    const payload = JSON.parse(data);
    handlers.onEvent?.(name, payload);
    if (name === "error") {
      // SPEC-205: detail estruturado (ex.: invalid_target) preserva code/mensagem.
      if (payload.detail && typeof payload.detail === "object") {
        const formatted = formatDetail(payload.detail, "erro no stream");
        throw new HttpError(Number(payload.code || 500), formatted.code, formatted.message);
      }
      throw new HttpError(Number(payload.code || 500), "stream_error", payload.detail || "erro no stream");
    }
    if (name === "phase") handlers.onPhase?.(payload.node);
    else if (name === "route") handlers.onRoute?.(payload.route);
    else if (name === "narrative") handlers.onChunk?.(payload.chunk, payload.done);
    else if (name === "visual") handlers.onVisual?.(payload as VisualResponse);
    else if (name === "state") finalState = payload as GameResponse;
  };

  let acked = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!acked) { acked = true; handlers.onAck?.(); }
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).replace(/\r$/, "");
      buffer = buffer.slice(nl + 1);
      if (line.startsWith("event: ")) eventName = line.slice(7).trim();
      else if (line.startsWith("data: ") && eventName) {
        handleEvent(eventName, line.slice(6));
        eventName = "";
      }
      // linhas vazias e comentários (`: ping`) são ignorados
    }
  }
  if (!finalState) throw new Error("stream terminou sem estado final");
  return finalState;
}

export const getState = (game_id: string) =>
  req<GameResponse>("/game/state?game_id=" + encodeURIComponent(game_id));

export interface HistoryEntry { id: string; turn: number; epoch: number; role: 'player' | 'narrator'; text: string; type: import('./types').LogEntry['type']; speaker_kind?: 'narrator' | 'npc' | 'system'; speaker_id?: string; speaker_name?: string; cost_milli?: string | null; technical_cost_usd?: string | null; technical_cost_basis?: string | null; technical_cost_exact?: boolean }
export const getHistory = (game: string, cursor?: string) => req<{
  entries: HistoryEntry[]; next_cursor: string | null; epoch: number; partial_history: boolean;
}>(`/game/history?game_id=${encodeURIComponent(game)}${cursor ? '&cursor=' + encodeURIComponent(cursor) : ''}`);
export const getOperation = (game: string, operation: string) => req<{
  status: string; response: GameResponse | null; request_hash?: string;
}>(`/game/${encodeURIComponent(game)}/operations/${encodeURIComponent(operation)}`);
export const getTurnCost = (game: string, operation: string) => req<{
  history_id: string | null; epoch?: number; cost_milli: string | null;
  technical_cost_usd: string | null; technical_cost_basis: string | null; technical_cost_exact: boolean;
}>(`/game/${encodeURIComponent(game)}/operations/${encodeURIComponent(operation)}/cost`);
export interface AccountBalance { available_milli: string; reserved_milli: string }
export interface AccountPoint { start: string; game: string; image: string; voice: string; total: string }
export interface AccountHistoryItem { id: string; created_at: string; category: 'game' | 'image' | 'voice'; operation: string }
export interface PurchaseItem { id: string; created_at: string; kind: 'purchase' | 'refund' | 'reversal'; amount_milli: string }
export interface AccountPage<T> { items: T[]; next_cursor: string | null }
export const getAccountBalance = (signal?: AbortSignal) => req<AccountBalance>('/account/balance', { signal });
export const getAccountSeries = (period: '24h' | '7d' | '30d', signal?: AbortSignal) => req<{ period: string; unit: 'milli_shard'; totals: Record<'game' | 'image' | 'voice', string>; points: AccountPoint[] }>(`/account/series?period=${period}`, { signal });
export const getAccountUsage = (cursor?: string, signal?: AbortSignal) => req<AccountPage<AccountHistoryItem>>(`/account/usage${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, { signal });
export const getAccountPurchases = (cursor?: string, signal?: AbortSignal) => req<AccountPage<PurchaseItem>>(`/account/purchases${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, { signal });
export interface CheckoutSku { sku_id: string; gross_brl: string; shard_milli: string }
export interface CheckoutOrder {
  order_id: string; status: 'created' | 'checkout_pending' | 'paid' | 'refunded' |
    'disputed' | 'reconciliation_required' | 'expired';
  sku_id: string; gross_brl: string; shard_milli: string;
}
export const getCheckoutSkus = (signal?: AbortSignal) => req<{ items: CheckoutSku[] }>('/account/checkout/skus', { signal });
export const createCheckout = (skuId: string, requestId: string) =>
  req<CheckoutOrder & { checkout_url: string | null }>('/account/checkout', {
    method: 'POST', body: JSON.stringify({ sku_id: skuId, request_id: requestId }),
  });
export const getCheckoutOrder = (orderId: string, signal?: AbortSignal) =>
  req<CheckoutOrder>(`/account/checkout/${encodeURIComponent(orderId)}`, { signal });
export const googlePlayBackend = {
  profile: () => req<{ obfuscated_account_id?: string; purchases_disabled?: boolean }>('/account/purchases/google/profile'),
  products: () => req<{ items: { product_id: string; sku_id: string; shard_milli: string }[] }>('/account/purchases/google/products'),
  verify: (b: { product_id: string; purchase_token: string; order_id?: string }) =>
    req<{ status: 'fulfilled' | 'pending'; shard_milli?: string; product_id?: string }>('/account/purchases/google/verify',
      { method: 'POST', body: JSON.stringify(b) }),
};
export interface ArtStatus { status: string; placeholder: boolean; financial_status?: string | null; credits_held?: boolean; assets?: Array<{
  asset_id: string; variant: string; url: string; width: number; height: number;
}> }
export const getArtStatus = (game: string, generation: string, signal?: AbortSignal) => req<ArtStatus>(
  `/game/${encodeURIComponent(game)}/art/${encodeURIComponent(generation)}`, { signal });

export const getCodex = (game_id: string) =>
  req<PlayerCodex>("/game/codex?game_id=" + encodeURIComponent(game_id));

// spec polish-sessao (R1/R2): lista e exclusão de campanhas salvas.
export const getSaves = () => req<SaveSummary[]>("/game/saves");

export const deleteSave = (game_id: string) =>
  req<{ ok: boolean }>("/game/save/" + encodeURIComponent(game_id), {
    method: "DELETE",
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });

// spec polish-sessao (R5): URL de download da crônica (.txt).
export const chronicleExportUrl = (game_id: string) =>
  "/game/chronicle/export?game_id=" + encodeURIComponent(game_id);

export const searchChronicle = (
  payload: { game_id: string; query: string; top_k?: number },
  signal?: AbortSignal,
) => req<import("./types").ChronicleSearchResponse>("/game/chronicle/search", {
  method: "POST",
  body: JSON.stringify(payload),
  signal,
});

// Fase 4.1: aplica UMA escolha de level up (validação é server-side).
export interface LevelUpResult {
  ok: boolean;
  player_stats: Partial<import("./types").PlayerStats> & {
    attributes?: Record<string, number>;
  };
}

// Fase 4.3: equipar/desequipar (validação server-side).
export const postEquip = (payload: {
  item_id?: string;
  unequip_slot?: string;
  game_id?: string | null;
}) =>
  req<{ ok: boolean }>("/game/equip", {
    method: "POST",
    body: JSON.stringify({ ...payload, action_id: crypto.randomUUID() }),
  });

// SPEC-209 R4: preparar/trocar Cartas fora de combate (regra 100% no servidor).
export interface PrepareCardsResult {
  ok: boolean;
  prepared_cards: string[];
  cards: import("./types").CardView[];
  prepared_slots: number;
}
export const postPrepareCards = (payload: { prepared: string[]; game_id?: string | null }) =>
  req<PrepareCardsResult>("/game/cards/prepare", {
    method: "POST",
    body: JSON.stringify({ ...payload, action_id: crypto.randomUUID() }),
  });

export const postLevelUp = (payload: {
  choice_id: string;
  card_id?: string;
  evolve_card_id?: string;
  caminho?: "A" | "B";
  virtude?: string;
  subclass_id?: string;
  virtue_card_id?: string;
  game_id?: string | null;
}) =>
  req<LevelUpResult>("/game/levelup", {
    method: "POST",
    body: JSON.stringify({ ...payload, action_id: crypto.randomUUID() }),
  });

export const postArtBrief = (payload: {
  name: string; race: string; class_name: string; region: string;
  appearance: string; visual_exclusions: string;
}) => req<{ brief: Record<string, unknown>; rendered_prompt: string; provider_called: false }>(
  "/game/art/brief", { method: "POST", body: JSON.stringify(payload) },
);

export interface ImageQuote {
  quote_id: string;
  type: "player" | "npc" | "scene";
  credits_milli: string;
  pricing_version: string;
  expires_at: string;
  reformulation: boolean;
}

export const requestImageQuote = (gameId: string, imageType: ImageQuote["type"] = "player", reformulation = false, offerId?: string) =>
  req<ImageQuote>(`/game/${encodeURIComponent(gameId)}/art/quote`, {
    method: "POST", body: JSON.stringify({ image_type: imageType, reformulation, offer_id: offerId }),
  });

export const confirmPlayerArt = (gameId: string, actionId: string, quoteId: string) =>
  req<{ status: string; generation_id?: string; type: ImageQuote["type"]; placeholder: boolean;
    art_generations?: { generation_id: string; type: ImageQuote["type"]; subject_id: string }[];
    art_offers?: { offer_id: string; type: "npc" | "scene" }[] }>(
    `/game/${encodeURIComponent(gameId)}/art/confirm`, {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, quote_id: quoteId, confirmed: true }),
    },
  );

// SPEC-200 R10: beacon (so roda se /auth/config sinalizar `client_latency_report`).
export const sendClientLatency = (body: import("./lib/turnLatency").LatencySummary) =>
  http("/telemetry/client-latency", { method: "POST", body: JSON.stringify(body) });
