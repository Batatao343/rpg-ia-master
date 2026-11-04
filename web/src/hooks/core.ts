import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type * as api from "../api";
import type { BannerState } from "../components/Banner";
import type { PendingOperation } from "../pendingOperation";
import type { GameResponse, LogEntry, SaveSummary } from "../types";

export const LS_KEY = "cronicas_game_id";

export type Screen = "bootstrap" | "auth" | "saves" | "create" | "simulator" | "play" | "account";

/**
 * Estado compartilhado do `App` (SPEC-383 §3.1). Montado a cada render, sem memo: os hooks leem o valor
 * do render atual, exatamente como as funções do `App` liam antes da extração. Todo ref que mais de um hook
 * usa nasce no `App` e desce por aqui; nenhum hook devolve ref.
 */
export type AppCore = {
  screen: Screen; setScreen: Dispatch<SetStateAction<Screen>>;
  data: GameResponse | null; setData: Dispatch<SetStateAction<GameResponse | null>>;
  log: LogEntry[]; setLog: Dispatch<SetStateAction<LogEntry[]>>;
  busy: boolean; setBusy: Dispatch<SetStateAction<boolean>>;
  thinking: boolean; setThinking: Dispatch<SetStateAction<boolean>>;
  banner: BannerState | null; setBanner: Dispatch<SetStateAction<BannerState | null>>;
  pending: PendingOperation | null; setPending: Dispatch<SetStateAction<PendingOperation | null>>;
  saves: SaveSummary[]; setSaves: Dispatch<SetStateAction<SaveSummary[]>>;
  continueData: GameResponse | null; setContinueData: Dispatch<SetStateAction<GameResponse | null>>;
  authRequired: boolean; setAuthRequired: Dispatch<SetStateAction<boolean>>;
  authConfig: api.AuthConfig | undefined; setAuthConfig: Dispatch<SetStateAction<api.AuthConfig | undefined>>;
  accountBalance: string | null; setAccountBalance: Dispatch<SetStateAction<string | null>>;
  session: MutableRefObject<number>;
  owner: MutableRefObject<string>;
  gameId: MutableRefObject<string | null>;
  logSeq: MutableRefObject<number>;
  accountReturn: MutableRefObject<Screen>;
  deletionInProgress: MutableRefObject<boolean>;
  accountBalanceGeneration: MutableRefObject<number>;
  accountBalanceAbort: MutableRefObject<AbortController | null>;
  pushLog: (text: string, role: "player" | "narrator", type: LogEntry["type"]) => void;
};
