// SPEC-342: fixture do combate por Baralho (payload com as flags `on`) e utilidades de conferência.
import type { Page } from "@playwright/test";
import { expect, type DeterministicBackend } from "./fixtures";
import type { HandCard } from "../src/types";

export const HAND: HandCard[] = [
  { id: "golpe", name: "Golpe do Véu", custo_folego: 1, custo_entropia: 0, jogavel: true, alvo: "inimigo", texto: "**Sangria** 2. Causa 3 de dano." },
  { id: "corte", name: "Corte Largo", custo_folego: 1, custo_entropia: 0, jogavel: true, alvo: "inimigo", texto: "Causa 4 de dano a um inimigo próximo." },
  { id: "folego", name: "Fôlego Fundo", custo_folego: 0, custo_entropia: 0, jogavel: true, alvo: "si", texto: "Recupera o ritmo. **Rachadura** não vale aqui." },
  { id: "cura", name: "Bênção Curta", custo_folego: 1, custo_entropia: 0, jogavel: true, alvo: "aliado", texto: "Cura 3 de Vitalidade." },
  { id: "pesada", name: "Golpe Pesado", custo_folego: 2, custo_entropia: 0, jogavel: true, alvo: "inimigo", texto: "Causa 7 de dano." },
];

export interface DeckOpts {
  hand?: HandCard[];
  enemies?: Array<[string, string]>;
  intent?: boolean;
  scene?: boolean;
  nonlethal?: boolean;
  loot?: boolean;
  forge?: boolean;
}

/** Combate por Baralho com 2 inimigos, 5 cartas na mão e (opcional) presságios, cena, objetivo e "Sem matar". */
export function armDeck(backend: DeterministicBackend, o: DeckOpts = {}) {
  const hand = o.hand ?? HAND;
  const state = backend.armCombat("game-a", o.enemies ?? [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  const ids = state.combat.enemies.map((e) => e.id);
  const [base] = state.player_stats.cards;
  state.combat.cards = hand.map((c) => ({
    ...base, id: c.id, name: c.name, description: c.texto ?? "", type: "ativa" as const,
    target_kind: c.alvo === "inimigo" ? "enemy" as const : "self" as const,
    valid_targets: c.alvo === "inimigo" ? ids : ["player"], invalid_reason: null,
  }));
  state.combat.basic_actions = [
    { kind: "attack", valid_targets: ids, invalid_reason: null, cost: 0 },
    { kind: "maneuver", maneuver: "guardar", valid_targets: [], invalid_reason: null, cost: 0 },
    { kind: "flee", valid_targets: [], invalid_reason: null, cost: 0 },
  ];
  state.combat.pilhas = {
    mao: hand, compra: 8, descarte: 2, exaurida: 1, folego: 3, folego_max: 3, folego_emprestado: 0, pacto_max: 2,
    listas: { compra: [{ id: "x", name: "Estocada" }], descarte: [{ id: "y", name: "Aparar" }], exaurida: [{ id: "z", name: "Ruína" }] },
  };
  state.combat.mech_log = ["Você · Golpe do Véu → Saqueador · 2d10 6 + 7 +2 = 15 vs 12 · acerto · 5 dano", "Saqueador · Talho → Você · 2d10 4 + 3 = 7 vs 11 · erro"];
  if (o.intent !== false) {
    state.combat.pressagios_publicos = [{ actor_id: "e1", tipo: "ataque", alvo_id: "player", valor_estimado: null, faixa: [4, 8], carta_nome: "Talho", sinal: "ergue a lâmina" }];
  }
  if (o.scene !== false) {
    state.combat.cena = { cartas: [{ id: "nevoa", nome: "Névoa Cinza do Ermo", sabor: "No Ermo o frio é o Abismo drenando calor." }], relogio: { desde: 5, teto: 12, rodada: 1, ativo: false } };
    state.combat.objetivo = { tipo: "sobreviver_n_rodadas", n: 6, rodada: 1, resultado: null };
    state.combat.pressagios_cena = [{ id: "nevoa", nome: "Névoa Cinza do Ermo", pressagio: "a névoa engole os contornos", quando: "fim_rodada", rodada: 2 }];
  }
  if (o.nonlethal !== false) state.combat.nonlethal_available = true;
  return state;
}

export async function openCombat(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
  const tab = page.getByRole("tab", { name: "Combate" });
  if (await tab.count()) await tab.click();
  else {
    const m = page.getByRole("button", { name: /^Combate/ });
    if (await m.count()) await m.click();
  }
  await expect(page.locator(".deck-combat")).toBeVisible();
}

export const actions = (b: DeterministicBackend) => b.requests.filter((r) => r.path.startsWith("/game/action"));
export const panel = (page: Page) => page.locator("#ws-panel-combate, [aria-label='Combate'][role='region']").first();
