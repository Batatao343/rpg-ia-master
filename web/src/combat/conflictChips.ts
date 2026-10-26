import type { CombatBlock } from "../types";

/** SPEC-325 R14/R15/R16: chips de objeto e de ordem a aliado, e a nota de reforço. Frases que o
 *  servidor reconhece sem LLM (combat_intents.object_step / companion_order). Cada grupo só existe
 *  quando a API manda o campo (a flag está `on`). */
export const OBJECT_TEXT = (label: string, name: string) => `${label} ${name}.`;
export const ORDER_TEXT = (name: string, verb: string) => `${name}, ${verb}.`;
export const ORDER_VERBS: [string, string][] = [
  ["atacar", "Atacar"], ["proteger", "Proteger"], ["curar", "Curar"], ["recuar", "Recuar"],
];
export const REINFORCEMENT_NOTE = "Passos se aproximam: reforços a caminho.";

export interface ConflictChip { key: string; data: string; label: string; text: string; title: string }

export function objectChips(combat: CombatBlock | undefined | null): ConflictChip[] {
  return (combat?.scene?.objects ?? []).flatMap((o) => o.interactions.map((it) => ({
    key: `obj-${o.id}-${it.label}`, data: o.id, label: `${it.label} ${o.name}`,
    text: OBJECT_TEXT(it.label, o.name),
    title: `Usar ${o.name} (${it.label}). O efeito só se revela depois do uso.`,
  })));
}

export function orderChips(combat: CombatBlock | undefined | null): ConflictChip[] {
  return (combat?.companion_orders ?? []).flatMap((a) => ORDER_VERBS.map(([verb, label]) => ({
    key: `order-${a.id}-${verb}`, data: `${a.id}:${verb}`, label: `${a.name}: ${label}`,
    text: ORDER_TEXT(a.name, verb),
    title: `Ordenar a ${a.name}: ${verb}. Ele pode recusar se contrariar seus valores.`,
  })));
}

export const reinforcementNote = (combat: CombatBlock | undefined | null): string | null =>
  combat?.reinforcement_warning ? REINFORCEMENT_NOTE : null;
