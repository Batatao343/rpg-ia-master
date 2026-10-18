// SPEC-216: derivação PURA da superfície mobile sobre o estado de workspace da SPEC-204.
// Sem estado próprio: o que o jogador vê em < 900px é sempre `chat` OU uma aba de contexto.
import {
  CONTEXT_TABS, TAB_LABELS, effectiveMode, type ContextTab, type WorkspaceState,
} from "./workspaceModel";

/** Breakpoint mobile (SPEC-216 §8 P1): abaixo dele não há gaveta nem split, só a barra inferior. */
export const MOBILE_MAX_VIEWPORT = 900;

export type Surface = "chat" | ContextTab;
export const SURFACES: readonly Surface[] = ["chat", ...CONTEXT_TABS];
export const SURFACE_LABELS: Record<Surface, string> = { chat: "Chat", ...TAB_LABELS };

export function isMobileViewport(viewportPx: number): boolean {
  return viewportPx < MOBILE_MAX_VIEWPORT;
}

/** A única superfície visível. Reusa `effectiveMode` (nunca `split` abaixo de 1100px). */
export function mobileSurface(state: WorkspaceState, viewportPx: number): Surface {
  return effectiveMode(state, viewportPx) === "context" ? state.tab : "chat";
}

/** §8 P4: a troca automática para Combate só ocorre após a narração do início do encontro. */
export function shouldAutoOpenCombat(wasFighting: boolean, fighting: boolean, narrationRendered: boolean): boolean {
  return fighting && !wasFighting && narrationRendered;
}

// Ponte mínima App <-> Workspace para o botão "voltar" do Android (SPEC-216 R2).
interface BackBridge { offChat: () => boolean; toChat: () => void }
let bridge: BackBridge | null = null;
/** O Workspace registra como saber/voltar ao chat; devolve o disposer. */
export function registerBackBridge(next: BackBridge): () => void {
  bridge = next;
  return () => { if (bridge === next) bridge = null; };
}
/** Há uma superfície mobile que não é o chat aberta? */
export function offChatSurface(): boolean {
  return bridge ? bridge.offChat() : false;
}
/** Volta ao chat se estiver em outra superfície; false quando já está no chat. */
export function returnToChat(): boolean {
  if (!bridge || !bridge.offChat()) return false;
  bridge.toChat();
  return true;
}
