// Cliente da API FastAPI. Mesma origem em produção; via proxy do Vite em dev.
import type {
  CreateOptions,
  CreatePayload,
  GameResponse,
  OnboardingData,
  PlayerCodex,
  PrologueResponse,
  SaveSummary,
  WorldMapData,
} from "./types";

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const getOptions = () => req<CreateOptions>("/data/options");

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
    body: JSON.stringify(payload),
  });

export const sendAction = (input_text: string, game_id: string | null) =>
  req<GameResponse>("/game/action", {
    method: "POST",
    body: JSON.stringify({ input_text, game_id }),
  });

// spec checkpoints-morte (D2): resolve a tela de morte —
// "continue" restaura do checkpoint, "accept" encerra em memorial.
export const resolveDeath = (game_id: string | null, choice: "continue" | "accept") =>
  req<GameResponse>("/game/death", {
    method: "POST",
    body: JSON.stringify({ game_id, choice }),
  });

// spec streaming-turno-sse (R4): turno via SSE — fases reais do grafo enquanto
// o LLM pensa. POST não funciona com EventSource nativo, então o parser de
// `event:`/`data:` é manual sobre fetch + ReadableStream. Qualquer falha antes
// do evento `state` deve levar o chamador ao fallback (POST clássico).
export interface StreamHandlers {
  onPhase?: (node: string) => void;
  onRoute?: (route: string) => void;
  onChunk?: (chunk: string, done: boolean) => void;
}

export async function sendActionStream(
  input_text: string,
  game_id: string | null,
  handlers: StreamHandlers = {},
): Promise<GameResponse> {
  const res = await fetch("/game/action/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_text, game_id }),
  });
  if (!res.ok || !res.body) throw new Error("stream indisponível: " + res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "";
  let finalState: GameResponse | null = null;

  const handleEvent = (name: string, data: string) => {
    const payload = JSON.parse(data);
    if (name === "error") throw new Error(payload.detail || "erro no stream");
    if (name === "phase") handlers.onPhase?.(payload.node);
    else if (name === "route") handlers.onRoute?.(payload.route);
    else if (name === "narrative") handlers.onChunk?.(payload.chunk, payload.done);
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

export const getCodex = (game_id: string) =>
  req<PlayerCodex>("/game/codex?game_id=" + encodeURIComponent(game_id));

// spec polish-sessao (R1/R2): lista e exclusão de campanhas salvas.
export const getSaves = () => req<SaveSummary[]>("/game/saves");

export const deleteSave = (game_id: string) =>
  req<{ ok: boolean }>("/game/save/" + encodeURIComponent(game_id), {
    method: "DELETE",
  });

// spec polish-sessao (R5): URL de download da crônica (.txt).
export const chronicleExportUrl = (game_id: string) =>
  "/game/chronicle/export?game_id=" + encodeURIComponent(game_id);

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
    body: JSON.stringify(payload),
  });

export const postLevelUp = (payload: {
  choice_id: string;
  ability_id?: string;
  attr?: string;
  game_id?: string | null;
}) =>
  req<LevelUpResult>("/game/levelup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
