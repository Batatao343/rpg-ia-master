// SPEC-354 Etapa 7: prints "depois" (RPG_SPEC354_PRINTS=1). Não é gate. Também cobre `retrato_marcador_sem_flag`.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

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
