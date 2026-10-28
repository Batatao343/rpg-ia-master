// SPEC-354 Etapa 7: prints "depois" (RPG_SPEC354_PRINTS=1). Não é gate. Também cobre `retrato_marcador_sem_flag`.
import { readFileSync } from "node:fs";
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

const REAL = JSON.parse(readFileSync(new URL("./fixtures/spec354/save-real.json", import.meta.url), "utf-8"));
const OUT = "../docs/spec354/depois";
const base = { ator_id: "player", ator_nome: "Ayla", lado: "heroi", carta_id: "golpe", carta_nome: "Golpe do Véu", alvo_id: "e1", alvo_nome: "Saqueador", origem: "turno", rotulo: null, resultado: "acerto", dano: 5, efeito: null };
const log = [base, { ...base, ator_id: "e1", ator_nome: "Saqueador", lado: "inimigo", alvo_id: "player", alvo_nome: "Ayla", resultado: "erro", dano: null },
  { ...base, carta_id: null, carta_nome: "Sangrando", alvo_id: null, alvo_nome: null, rotulo: "Dano contínuo", resultado: "efeito", dano: 1, efeito: "−1 Vitalidade" }];

function withMarkers(state: ReturnType<typeof armDeck>) {
  for (const e of state.combat.enemies) (e as unknown as Record<string, unknown>).retrato = { estado: "marcador", src: null, familia: "bruto", icone: "combat", alt: `Retrato de ${e.name}`, proprio: false, gerar: null };
}

for (const [label, viewport, touch] of [["1440", { width: 1440, height: 900 }, false], ["390", { width: 390, height: 844 }, true]] as const) {
  test.describe(`retrato sem flag ${label}`, () => {
    test.use({ viewport, hasTouch: touch, isMobile: touch });
    test(`retrato_marcador_sem_flag_${label}`, async ({ page, backend }) => {
      const state = armDeck(backend, { roundLog: log });
      withMarkers(state);
      await openCombat(page);
      await expect(page.locator(".tchip__portrait")).toHaveCount(2);
      if (process.env.RPG_SPEC354_PRINTS) await page.screenshot({ path: `${OUT}/${label}-registro-dois-inimigos.png` });
    });
  });
}

test.describe("prints extras", () => {
  test.skip(!process.env.RPG_SPEC354_PRINTS, "prints sob demanda (RPG_SPEC354_PRINTS=1)");
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  test("390-arena-aliado", async ({ page, backend }) => {
    const state = armDeck(backend, { roundLog: log });
    state.combat.scene.positions.push({ participant_id: "npc_ketil", participant_name: "npc_ketil", zone_id: "ponte", distance: "proximo", posture: "neutro", concealment: "visivel", engaged_with: [], engaged_names: [] } as never);
    await openCombat(page);
    await page.screenshot({ path: `${OUT}/390-arena-aliado.png` });
  });
});

for (const [label, viewport, touch] of [["1440", { width: 1440, height: 900 }, false], ["390", { width: 390, height: 844 }, true]] as const) {
  test.describe(`prints ${label}`, () => {
    test.skip(!process.env.RPG_SPEC354_PRINTS, "prints sob demanda (RPG_SPEC354_PRINTS=1)");
    test.use({ viewport, hasTouch: touch, isMobile: touch, reducedMotion: "no-preference" });

    test(`${label}-reaberto`, async ({ page, backend }) => {
      const gid = REAL.saves[0].game_id;
      backend.saves = REAL.saves; backend.states.clear(); backend.states.set(gid, structuredClone(REAL.state));
      backend.histories.clear(); backend.histories.set(gid, REAL.history);
      await page.goto("/");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Batatof/ }).dispatchEvent("click");
      await expect(page.locator("article.msg")).toHaveCount(REAL.history.length);
      if (touch) await page.locator("nav.mtabbar").getByRole("button", { name: "Crônica" }).dispatchEvent("click");
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `${OUT}/${label}-reaberto.png` });
    });

    test(`${label}-pos-combate`, async ({ page, backend }) => {
      const state = armDeck(backend, { roundLog: log });
      delete (state.combat as { pilhas?: unknown }).pilhas;
      state.combat.active = false; state.combat.phase = "ended"; state.combat.outcome = "victory"; state.combat.enemies = []; state.combat.round = 3;
      state.turn_outcome = { receipt_id: "rc-5", turn: 5, xp_delta: 50, level_delta: 0, gold_delta: 20, items_gained: [], quests_completed: [], source: "combat" } as never;
      state.combat_result = { encounter_id: "game-a:0:1", outcome: "victory", participants: [{ participant_id: "e1", species_label: "Saqueador", final_status: "morto" }],
        xp_event_ref: "rc-5", loot_ref: null, ended_round: 3, result_event_id: "res-5" } as never;
      backend.histories.get("game-a")!.push({ id: "a-final", turn: 5, epoch: 1, role: "narrator", text: "O último saqueador tomba sobre a ponte e a névoa devolve o silêncio ao vale.", type: "STORY" });
      await page.goto("/");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).dispatchEvent("click");
      const tab = page.getByRole("tab", { name: "Combate" });
      await page.waitForTimeout(1500);
      if (await tab.first().isVisible().catch(() => false)) await tab.first().dispatchEvent("click");
      else if (touch) await page.locator("nav.mtabbar").getByRole("button", { name: /^Combate/ }).dispatchEvent("click");
      await expect(page.getByText("A última rodada", { exact: true })).toBeVisible();
      await page.screenshot({ path: `${OUT}/${label}-pos-combate.png` });
    });
  });
}

test.describe("print fila 390", () => {
  test.skip(!process.env.RPG_SPEC354_PRINTS, "prints sob demanda (RPG_SPEC354_PRINTS=1)");
  test.use({ viewport: { width: 390, height: 640 }, hasTouch: true, isMobile: true });
  test("390-fila", async ({ page, backend }) => {
    armDeck(backend, { nonlethal: true, roundLog: log });
    await openCombat(page);
    for (const id of ["golpe", "corte"]) {
      await page.locator(`.deck-card[data-card="${id}"]`).dispatchEvent("click");
      await page.locator("button[data-target='e1']").dispatchEvent("click").catch(() => {});
      await page.locator("[data-play-confirm]").dispatchEvent("click");
    }
    await page.locator("[data-spare]").dispatchEvent("click");
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/390-fila.png` });
  });
});
