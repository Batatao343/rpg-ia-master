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

import { http, HttpError } from "./http";
export { HttpError } from "./http";

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await http(path, opts);
  return res.status === 204 ? undefined as T : res.json() as Promise<T>;
}

export const getAuthConfig = () => req<{ required: boolean; authenticated: boolean; user_id?: string }>("/auth/config");
export const login = (email: string, password: string) =>
  req<{ authenticated: boolean; csrf_token: string }>("/auth/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  });

export const signup = (email: string, password: string) =>
  req<{ authenticated: boolean; csrf_token: string }>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
export const logout = () => req<void>("/auth/logout", { method: "POST" });

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
    if (name === "error") throw new HttpError(Number(payload.code || 500), "stream_error", payload.detail || "erro no stream");
    if (name === "phase") handlers.onPhase?.(payload.node);
    else if (name === "route") handlers.onRoute?.(payload.route);
    else if (name === "narrative") handlers.onChunk?.(payload.chunk, payload.done);
    else if (name === "visual") handlers.onVisual?.(payload as VisualResponse);
    else if (name === "state") finalState = payload as GameResponse;
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
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

export interface HistoryEntry { id: string; turn: number; epoch: number; role: 'player' | 'narrator'; text: string; type: import('./types').LogEntry['type'] }
export const getHistory = (game: string, cursor?: string) => req<{
  entries: HistoryEntry[]; next_cursor: string | null; epoch: number; partial_history: boolean;
}>(`/game/history?game_id=${encodeURIComponent(game)}${cursor ? '&cursor=' + encodeURIComponent(cursor) : ''}`);
export const getOperation = (game: string, operation: string) => req<{
  status: string; response: GameResponse | null; request_hash?: string;
}>(`/game/${encodeURIComponent(game)}/operations/${encodeURIComponent(operation)}`);
export interface ArtStatus { status: string; placeholder: boolean; assets?: Array<{
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

export const confirmPlayerArt = (gameId: string, actionId: string, reformulation = false) =>
  req<{ status: string; generation_id?: string; placeholder: boolean }>(
    `/game/${encodeURIComponent(gameId)}/art/player/confirm`, {
      method: "POST",
      body: JSON.stringify({ action_id: actionId, reformulation }),
    },
  );
