// SPEC-204: modelo puro do workspace (chat + UM painel de contexto). Sem React.
export type WorkspaceMode = "chat" | "split" | "context";
export type ContextTab = "codex" | "personagem" | "combate" | "bestiario" | "mapa";

export const CONTEXT_TABS: readonly ContextTab[] = ["codex", "personagem", "combate", "bestiario", "mapa"];
export const TAB_LABELS: Record<ContextTab, string> = {
  codex: "Codex", personagem: "Personagem", combate: "Combate", bestiario: "Bestiário", mapa: "Mapa",
};

export interface WorkspaceState {
  version: 1;
  mode: WorkspaceMode;
  /** Fração da largura útil dada ao chat (0..1). */
  ratio: number;
  tab: ContextTab;
  history: ContextTab[];
  cursor: number;
  /** Superfície única usada quando o split não cabe (R12) e destino de Ctrl+\. */
  lastSolo: "chat" | "context";
}

export type WorkspaceAction =
  | { type: "open_tab"; tab: ContextTab; single?: boolean }
  | { type: "set_mode"; mode: WorkspaceMode }
  | { type: "set_ratio"; ratio: number }
  | { type: "toggle_split" }
  | { type: "close_context"; single: boolean }
  | { type: "back" } | { type: "forward" }
  | { type: "combat_started" } | { type: "combat_ended" };

export const HISTORY_CAP = 50;
export const SPLIT_MIN_VIEWPORT = 1100;
export const MIN_CHAT_PX = 380;
export const MIN_CONTEXT_PX = 360;

export const DEFAULT_WORKSPACE: WorkspaceState = Object.freeze({
  version: 1, mode: "split", ratio: 0.5, tab: "personagem",
  history: ["personagem"], cursor: 0, lastSolo: "chat",
}) as WorkspaceState;

export function isContextTab(value: unknown): value is ContextTab {
  return typeof value === "string" && (CONTEXT_TABS as readonly string[]).includes(value);
}

function visit(s: WorkspaceState, tab: ContextTab): WorkspaceState {
  if (tab === s.tab) return s;
  let history = s.history.slice(0, s.cursor + 1).concat(tab);
  if (history.length > HISTORY_CAP) history = history.slice(history.length - HISTORY_CAP);
  return { ...s, tab, history, cursor: history.length - 1 };
}

function showContext(s: WorkspaceState): WorkspaceState {
  return s.mode === "chat" ? { ...s, mode: "split" } : s;
}

export function workspaceReducer(s: WorkspaceState, a: WorkspaceAction): WorkspaceState {
  switch (a.type) {
    case "open_tab": {
      const next = showContext(visit(s, a.tab));
      return a.single && next.lastSolo !== "context" ? { ...next, lastSolo: "context" } : next;
    }
    case "set_mode":
      if (a.mode === s.mode) return s;
      return a.mode === "split" ? { ...s, mode: "split" } : { ...s, mode: a.mode, lastSolo: a.mode };
    case "set_ratio": {
      if (!Number.isFinite(a.ratio)) return s;
      const ratio = Math.min(0.95, Math.max(0.05, a.ratio));
      return ratio === s.ratio ? s : { ...s, ratio };
    }
    case "toggle_split":
      return s.mode === "split" ? { ...s, mode: s.lastSolo } : { ...s, mode: "split" };
    case "close_context":
      // Tela estreita: preserva a preferência gravada (split) e só troca a superfície visível.
      if (a.single) return { ...s, mode: s.mode === "context" ? "split" : s.mode, lastSolo: "chat" };
      return { ...s, mode: "chat", lastSolo: "chat" };
    case "back": {
      if (s.cursor <= 0) return s;
      const cursor = s.cursor - 1;
      return showContext({ ...s, cursor, tab: s.history[cursor] });
    }
    case "forward": {
      if (s.cursor >= s.history.length - 1) return s;
      const cursor = s.cursor + 1;
      return showContext({ ...s, cursor, tab: s.history[cursor] });
    }
    case "combat_started": {
      const opened = visit(s, "combate");
      const base = s.mode === "chat" ? { ...opened, mode: "split" as const, ratio: 0.5 } : opened;
      return { ...base, lastSolo: "context" };
    }
    case "combat_ended":
      // D2: a aba Combate continua aberta mostrando o pós-combate até o jogador navegar.
      return s;
    default:
      return s;
  }
}

/** Limita a fração do chat aos mínimos em px; sem espaço para ambos, volta ao centro. */
export function clampRatio(ratio: number, totalPx: number, minChatPx = MIN_CHAT_PX, minCtxPx = MIN_CONTEXT_PX): number {
  if (!(totalPx > 0) || totalPx < minChatPx + minCtxPx) return 0.5;
  const min = minChatPx / totalPx;
  const max = 1 - minCtxPx / totalPx;
  const value = Number.isFinite(ratio) ? ratio : 0.5;
  return Math.round(Math.min(max, Math.max(min, value)) * 1000) / 1000;
}

/** R12: abaixo de 1100px só uma superfície por vez (a preferência split fica gravada). */
export function effectiveMode(s: WorkspaceState, viewportPx: number): WorkspaceMode {
  if (viewportPx < SPLIT_MIN_VIEWPORT && s.mode === "split") return s.lastSolo;
  return s.mode;
}
