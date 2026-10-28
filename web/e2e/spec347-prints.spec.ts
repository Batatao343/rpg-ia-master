// SPEC-347 Etapa 6: prints "depois" dos mesmos cenários do smoke (RPG_SPEC347_PRINTS=1). Não é gate.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, roundLog } from "./deck-342-helpers";

test.skip(!process.env.RPG_SPEC347_PRINTS, "prints sob demanda (RPG_SPEC347_PRINTS=1)");
const OUT = "../docs/spec347/depois";
const PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

test.describe("390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("390-previa-fila-registro", async ({ page, backend }) => {
    backend.unexpectedAllowed.push(/combat\/preview/);
    backend.previewDelayMs = 100;
    armDeck(backend, { roundLog: roundLog(6) });
    await openCombat(page);
    await page.screenshot({ path: `${OUT}/390-registro.png` });
    await page.locator('.deck-card[data-card="golpe"]').dispatchEvent("click");
    await page.locator("button[data-target='e1']").dispatchEvent("click");
    await expect(page.locator(".preview-chip[data-preview='ok']")).toBeVisible();
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${OUT}/390-previa.png` });
    await page.locator("[data-play-confirm]").dispatchEvent("click");
    await page.locator('.deck-card[data-card="corte"]').dispatchEvent("click");
    await page.locator("button[data-target='e1']").dispatchEvent("click");
    await page.locator("[data-play-confirm]").dispatchEvent("click");
    await page.waitForTimeout(250);
    await page.screenshot({ path: `${OUT}/390-fila.png` });
  });
});

test.describe("1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("1440-inicio-registro-retratos", async ({ page, backend }) => {
    const state = armDeck(backend, { zones: ["Veio de Calcário", "Boca do Abismo"], roundLog: roundLog(4) });
    const common = { familia: "bruto", icone: "combat", proprio: false, gerar: null };
    (state.combat.enemies[0] as unknown as Record<string, unknown>).retrato = { ...common, estado: "marcador", src: null, alt: "Retrato de Saqueador" };
    (state.combat.enemies[1] as unknown as Record<string, unknown>).retrato = { ...common, estado: "pronto", src: PIXEL, alt: "Retrato de Bandoleiro" };
    await openCombat(page);
    await page.screenshot({ path: `${OUT}/1440-inicio-3-zonas.png` });
    await page.screenshot({ path: `${OUT}/1440-registro.png` });
    await page.screenshot({ path: `${OUT}/1440-retratos.png` });
  });

  test("1440-pos-combate", async ({ page, backend }) => {
    backend.unexpectedAllowed.push(/combat\/preview/);
    armDeck(backend, { enemies: [["e1", "Saqueador"]] });
    await openCombat(page);
    await page.keyboard.press("1");
    await page.locator("[data-play-confirm]").press("Enter");
    await page.locator("[data-end-turn]").dispatchEvent("click");
    await expect(page.locator(".combat-outcome__continue")).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/1440-pos-combate.png` });
  });

  test("1440-tooltip-espolio-forja", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.player_stats.espolio_pendente = { id: "esp1", origem: "vitoria", recusa_ouro: 5, ofertas: [
      { id: "c1", name: "Estocada", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "Causa 2. **Sangria** 1.", descricao: "", conhecida: false },
      { id: "c3", name: "Corte", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "Causa 3. **Sangria** 2.", descricao: "", conhecida: false },
    ] } as never;
    state.player_stats.forja = {
      permitido: true, motivo: "", baralho_min: 3,
      baralho: [{ id: "golpe", name: "Golpe do Véu", copias: 1, esquecivel: true, bloqueio: null }],
      esquecer: { descanso: false, templo: false, ouro: 30, motivos: { descanso: "Só dá para esquecer uma Carta depois de um descanso longo.", templo: "Só um templo ou curandeiro ajuda a esquecer uma Carta." } },
      afiar: { material: null, afiaveis: [], afiadas: [] },
      purgar: { medico: false, templo: false, ouro: 20 }, cicatrizes: [],
    } as never;
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await page.getByRole("tab", { name: /Combate/ }).click();
    await page.locator("article.combat-card.espolio__card").nth(1).locator(".kw").first().hover();
    await expect(page.locator("[role=tooltip]")).toBeVisible();
    await page.screenshot({ path: `${OUT}/1440-tooltip-espolio.png` });
    await page.mouse.move(0, 0);
    await page.locator("[data-forja-row='golpe']").click();
    await page.locator("[data-forja-why]").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${OUT}/1440-forja.png` });
  });
});

test.describe("390 pos-combate", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("390-pos-combate", async ({ page, backend }) => {
    backend.unexpectedAllowed.push(/combat\/preview/);
    armDeck(backend, { enemies: [["e1", "Saqueador"]] });
    await openCombat(page);
    await page.locator('.deck-card[data-card="golpe"]').dispatchEvent("click");
    await page.locator("[data-play-confirm]").dispatchEvent("click");
    await page.locator("[data-end-turn]").dispatchEvent("click");
    await expect(page.locator(".combat-outcome__continue")).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/390-pos-combate.png` });
  });
});
