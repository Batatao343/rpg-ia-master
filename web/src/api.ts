// Cliente da API FastAPI. Mesma origem em produção; via proxy do Vite em dev.
import type {
  CreateOptions,
  CreatePayload,
  GameResponse,
  PlayerCodex,
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

export const getState = (game_id: string) =>
  req<GameResponse>("/game/state?game_id=" + encodeURIComponent(game_id));

export const getCodex = (game_id: string) =>
  req<PlayerCodex>("/game/codex?game_id=" + encodeURIComponent(game_id));

// Fase 4.1: aplica UMA escolha de level up (validação é server-side).
export interface LevelUpResult {
  ok: boolean;
  player_stats: Partial<import("./types").PlayerStats> & {
    attributes?: Record<string, number>;
  };
}

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
