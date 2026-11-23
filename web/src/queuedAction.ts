// SPEC-427: fila de uma ação (RPG_ACTION_QUEUE). Lógica pura, sem React: quando enfileirar, o que fazer quando o
// turno fecha (esperar, enviar, devolver ao rascunho) e os textos. O envio em si é do hook `useQueuedAction`.
import type { GameResponse } from "./types";
import type { TurnStage, TurnWait } from "./turnWait";

let enabled = false;
/** `/auth/config` → `action_queue === true` (qualquer outro valor desliga). Mesmo padrão de `setClientLatencyReport`. */
export function setActionQueueEnabled(on: boolean): void { enabled = on === true; }
export function actionQueueEnabled(): boolean { return enabled; }

export interface QueuedAction {
  text: string;
  /** `turn.seq` do turno em que a ação entrou na fila. */
  seq: number;
  gid: string;
  combatResultId: string | null;
  choiceId: string | null;
}

/** O que o compositor sabe do turno e do jogo (sem `pendingStored`/`online`, lidos só na hora de decidir). */
export interface QueueBase {
  enabled: boolean;
  busy: boolean;
  stage: TurnStage;
  seq: number;
  delivered: boolean;
  error: boolean;
  gid: string | null;
  blocked: boolean;
  fighting: boolean;
  simulation: boolean;
  deckLocked: boolean;
  combatResultId: string | null;
  choiceId: string | null;
  deathOrOver: boolean;
}
export interface QueueSnapshot extends QueueBase { pendingStored: boolean; online: boolean }

export type ReturnReason =
  | "resumed" | "unsaved" | "turn-error" | "narration-changed" | "combat-started" | "combat-result"
  | "death" | "level-choice" | "pending" | "offline" | "left" | "sent-elsewhere";

export type QueueDecision = { kind: "wait" } | { kind: "send" } | { kind: "return"; reason: ReturnReason };

export function queueBase(data: GameResponse | null, turn: TurnWait, busy: boolean, blocked: boolean, deckLocked: boolean): QueueBase {
  const result = data?.combat_result as { result_event_id?: string } | undefined;
  return {
    enabled: actionQueueEnabled(), busy, stage: turn.stage, seq: turn.seq, delivered: turn.delivered, error: !!turn.error,
    gid: data?.game_id ?? null, blocked, fighting: !!data?.combat?.active, simulation: !!data?.combat_simulation?.enabled,
    deckLocked, combatResultId: result?.result_event_id ?? null, choiceId: (data?.player_stats?.pending_choices ?? []).map((c) => c.id).join(",") || null, // lista inteira (P3-2)
    deathOrOver: !!data?.death_pending || !!data?.game_over,
  };
}

/** R4: só em `narrated` (narração entregue, `state` ainda não), com a flag ligada e o compositor livre. */
export function canEnqueue(s: QueueBase, text: string): boolean {
  return s.enabled && s.busy && s.stage === "narrated" && !!s.gid && !s.blocked && !s.fighting
    && !s.simulation && !s.deckLocked && text.trim() !== "";
}

/** R4/R5: o botão primário vira "Pôr na fila" (habilitado) neste estado do turno. */
export function queueButtonActive(s: QueueBase): boolean {
  return s.enabled && s.busy && s.stage === "narrated" && !s.blocked && !s.fighting && !s.simulation;
}

/** R8–R10. `send` só com o sinal positivo `delivered`, turno fechado e nenhuma condição de devolução.
 *  Prioridade: j, f, e, g/h, a, b, c, d, i, k. */
export function decideQueued(q: QueuedAction, s: QueueSnapshot): QueueDecision {
  if (s.seq !== q.seq) return { kind: "return", reason: "resumed" };
  if (s.busy) return { kind: "wait" };
  const back = (reason: ReturnReason): QueueDecision => ({ kind: "return", reason });
  if (s.stage === "failed-after-narration") return back("unsaved");
  if (s.stage !== "idle") return { kind: "wait" };
  if (s.error) return back("turn-error");
  if (!s.delivered) return back("narration-changed");
  if (s.fighting) return back("combat-started");
  if (s.combatResultId !== q.combatResultId) return back("combat-result");
  if (s.deathOrOver) return back("death");
  if (s.choiceId !== q.choiceId) return back("level-choice");
  if (s.pendingStored) return back("pending");
  if (!s.online) return back("offline");
  return { kind: "send" };
}

/** R10.1: a fila vem primeiro (foi escrita antes); campo vazio fica só com a fila. */
export function mergeDraft(queued: string, draft: string): string {
  return draft.trim() === "" ? queued : `${queued}\n${draft}`;
}

const REASONS: Record<ReturnReason, string> = {
  resumed: "o turno foi retomado",
  unsaved: "o turno não foi registrado",
  "turn-error": "o turno falhou",
  "narration-changed": "a narração mudou",
  "combat-started": "começou um combate",
  "combat-result": "o combate mudou a cena",
  death: "a Roda do Abismo aguarda sua escolha",
  "level-choice": "há uma escolha de nível",
  pending: "há uma ação pendente",
  offline: "sem conexão",
  left: "você saiu da partida",
  "sent-elsewhere": "outro envio saiu antes",
};

export function returnNote(reason: ReturnReason): string {
  return `A ação na fila não foi enviada: ${REASONS[reason]}. O texto voltou ao campo.`;
}

export const QUEUED_ANNOUNCE = "Ação na fila: será enviada quando o turno for registrado.";
export const QUEUED_REPLACED = "Ação na fila substituída.";
export const QUEUE_REMOVED = "Ação tirada da fila; o texto voltou ao campo.";
