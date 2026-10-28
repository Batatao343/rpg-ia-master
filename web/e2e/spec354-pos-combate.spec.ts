// SPEC-354 R4: depois do conflito, o painel de Combate mostra "O desfecho" (última narração) e "A última rodada".
import { test, expect } from "./fixtures";
import { armDeck } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

const FINAL = "O último saqueador tomba sobre a ponte e a névoa devolve o silêncio ao vale.";
const base = { ator_id: "player", ator_nome: "Ayla", lado: "heroi", carta_id: "golpe", carta_nome: "Golpe do Véu", alvo_id: "e1", alvo_nome: "Saqueador", origem: "turno", rotulo: null, resultado: "acerto", dano: 9, efeito: null };

for (const [label, viewport, touch] of [["1440", { width: 1440, height: 900 }, false], ["390", { width: 390, height: 844 }, true]] as const) {
  test.describe(`pós-combate ${label}`, () => {
    test.use({ viewport, hasTouch: touch, isMobile: touch });

    test(`pos_combate_mostra_desfecho_e_rodada_${label}`, async ({ page, backend }) => {
      const state = armDeck(backend, { roundLog: [base, { ...base, ator_id: "e1", ator_nome: "Saqueador", lado: "inimigo", alvo_id: "player", alvo_nome: "Ayla", resultado: "erro", dano: null }] });
      delete (state.combat as { pilhas?: unknown }).pilhas;
      state.combat.active = false; state.combat.phase = "ended"; state.combat.outcome = "victory"; state.combat.enemies = []; state.combat.round = 3;
      state.world.turn_count = 5;
      state.turn_outcome = { receipt_id: "rc-5", turn: 5, xp_delta: 50, level_delta: 0, gold_delta: 20, items_gained: [], quests_completed: [], source: "combat" } as never;
      state.combat_result = { encounter_id: "game-a:0:1", outcome: "victory", participants: [{ participant_id: "e1", species_label: "Saqueador", final_status: "morto" }],
        xp_event_ref: "rc-5", loot_ref: null, ended_round: 3, result_event_id: "res-5" } as never;
      backend.histories.get("game-a")!.push({ id: "a-final", turn: 5, epoch: 1, role: "narrator", text: FINAL, type: "STORY" });
      await page.goto("/");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).dispatchEvent("click");
      await expect(page.locator("article.msg").last()).toContainText("silêncio");
      const tab = page.getByRole("tab", { name: "Combate" });
      if (await tab.count()) await tab.dispatchEvent("click");
      else await page.locator("nav.mtabbar").getByRole("button", { name: /^Combate/ }).dispatchEvent("click");
      await expect(page.getByText("O desfecho", { exact: true })).toBeVisible();
      await expect(page.locator("[data-desfecho-narracao]")).toContainText("silêncio ao vale");
      await expect(page.getByText("A última rodada", { exact: true })).toBeVisible();
      await expect(page.locator("[data-ultima-rodada] [data-roundboard]")).toContainText("O que se jogou na rodada final");
      const read = page.getByRole("button", { name: "Ler na Crônica" });
      if (touch) expect((await measure(read)).h).toBeGreaterThanOrEqual(43.5);
      const cont = page.getByRole("button", { name: "Continuar" });
      const c = await measure(cont);
      expect(c.free && c.inView, JSON.stringify(c)).toBe(true);
      await read.dispatchEvent("click");
      await expect(page.locator("section.story")).toBeVisible();
    });
  });
}
