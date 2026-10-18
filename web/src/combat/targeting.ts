import type { ActionOptions, BasicActionView, CardView, EnemyView, InvalidReason } from "../types";

/** SPEC-205: lógica PURA do gesto (sem React, sem números locais). */

export const REASON_TEXT: Record<InvalidReason, string> = {
  not_prepared: "Carta não preparada",
  spent_frequency: "Já usada (frequência esgotada)",
  no_entropy: "Entropia insuficiente",
  cooldown: "Bloqueada por um efeito temporário",
  no_valid_target: "Sem alvo válido",
  target_dead: "Alvo já caiu",
  target_hidden: "Alvo oculto",
  out_of_zone: "Alvo fora de alcance",
  not_your_turn: "Não é a sua vez",
  combat_inactive: "Sem combate ativo",
};

export const BASIC_LABEL: Record<string, string> = {
  attack: "Ataque básico", pass: "Passar", flee: "Fugir",
  engajar: "Engajar", desengajar: "Desengajar", guardar: "Guardar",
  esconder: "Esconder-se", procurar: "Procurar",
};

export type AimSource =
  | { kind: "card"; cardId: string }
  | { kind: "basic"; key: string };

export type TargetingState =
  | { phase: "idle" }
  | { phase: "aiming"; source: AimSource }
  | { phase: "submitting" };

export type TargetingAction =
  | { type: "aim"; source: AimSource }
  | { type: "cancel" }
  | { type: "submit" }
  | { type: "release" };

export const IDLE: TargetingState = { phase: "idle" };

const sameSource = (a: AimSource, b: AimSource) =>
  a.kind === b.kind && (a.kind === "card" ? a.cardId === (b as typeof a).cardId : a.key === (b as typeof a).key);

export function targetingReducer(state: TargetingState, action: TargetingAction): TargetingState {
  switch (action.type) {
    case "aim":
      if (state.phase === "submitting") return state;           // busy: mira bloqueada (R14)
      if (state.phase === "aiming" && sameSource(state.source, action.source)) return IDLE;  // R3
      return { phase: "aiming", source: action.source };         // troca substitui
    case "cancel":
      return state.phase === "aiming" ? IDLE : state;
    case "submit":
      return state.phase === "aiming" ? { phase: "submitting" } : state;
    case "release":
      return state.phase === "submitting" ? IDLE : state;
  }
}

/** Como o gesto se comporta para uma carta ativa. */
export interface CardPlan {
  mode: "aim" | "direct" | "blocked";
  targets: string[];
  directTarget?: string;
  reason: InvalidReason | null;
}

export function planCard(card: CardView, enemies: EnemyView[], busy: boolean): CardPlan {
  if (card.valid_targets === undefined) {
    // Servidor antigo: comportamento anterior (R: degradação) — ready/target_kind + 1º alvo vivo.
    const blocked = busy || !card.ready;
    return { mode: blocked ? "blocked" : "direct", targets: [],
      directTarget: card.target_kind === "enemy" ? enemies[0]?.id : undefined,
      reason: card.ready ? null : "no_entropy" };
  }
  const reason = card.invalid_reason ?? (card.ready ? null : "no_entropy");
  if (busy || reason || card.valid_targets.length === 0) {
    return { mode: "blocked", targets: [], reason: reason ?? "no_valid_target" };
  }
  if (card.target_kind === "self" && card.valid_targets.length === 1) {
    return { mode: "direct", targets: card.valid_targets, directTarget: card.valid_targets[0], reason: null };
  }
  return { mode: "aim", targets: card.valid_targets, reason: null };
}

export function planBasic(action: BasicActionView, busy: boolean): CardPlan {
  if (busy || action.invalid_reason) {
    return { mode: "blocked", targets: [], reason: action.invalid_reason ?? null };
  }
  const targeted = action.kind === "attack" || (action.kind === "maneuver" && (action.maneuver === "engajar" || action.maneuver === "procurar"));
  if (!targeted) return { mode: "direct", targets: [], reason: null };
  if (action.valid_targets.length === 0) return { mode: "blocked", targets: [], reason: "no_valid_target" };
  if (action.valid_targets.length === 1) {   // P1: um único alvo executa direto
    return { mode: "direct", targets: action.valid_targets, directTarget: action.valid_targets[0], reason: null };
  }
  return { mode: "aim", targets: action.valid_targets, reason: null };
}

export const basicKey = (a: BasicActionView) => a.maneuver ?? a.kind;

export function cardPayload(card: CardView, targetId: string | undefined, targetName: string | undefined,
                            ruptura: boolean, reaction?: string): [string, ActionOptions] {
  const rupturing = ruptura && card.rupture_ready;
  const on = targetId && targetId !== "player" && targetName ? ` em ${targetName}` : "";
  const text = `${rupturing ? "Declaro Ruptura e uso" : "Uso"} ${card.name}${on}.`;
  return [text, {
    card_id: card.id,
    target_id: targetId && targetId !== "player" ? targetId : undefined,
    ruptura: rupturing,
    reaction_card_id: reaction || undefined,
  }];
}

export function basicPayload(action: BasicActionView, targetId: string | undefined,
                             targetName: string | undefined, reaction?: string): [string, ActionOptions] {
  const label = BASIC_LABEL[basicKey(action)] ?? basicKey(action);
  const text = targetId && targetName ? `${label} em ${targetName}${action.kind === "attack" ? "." : ""}` : label;
  return [text, { action_kind: action.kind, maneuver: action.maneuver, target_id: targetId,
    reaction_card_id: reaction || undefined }];
}
