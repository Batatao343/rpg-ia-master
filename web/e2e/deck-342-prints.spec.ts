// SPEC-342 R26: prints de conferência em docs/spec342/ (fora do CI: só com RPG_SPEC342_PRINTS=1).
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";
import type { Page } from "@playwright/test";

test.skip(!process.env.RPG_SPEC342_PRINTS, "prints só sob demanda");
const OUT = "../docs/spec342";
const shot = (page: Page, name: string) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });

async function openIdle(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
  await page.waitForTimeout(800);
  const tab = page.getByRole("tab", { name: /Combate/ });
  if (await tab.count()) await tab.click();
  else await page.getByRole("button", { name: /^Combate/ }).click();
}

for (const [w, h] of [[360, 740], [390, 844], [1440, 900]] as const) {
  test.describe(`prints @${w}`, () => {
    test.use({ viewport: { width: w, height: h }, hasTouch: w < 500, isMobile: w < 500 });

    test("on combate", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await shot(page, `on-${w}-combate`);
      if (w !== 360) {
        await page.locator(".deck-card[data-card='golpe']").click();
        await shot(page, `on-${w}-mira`);
        if (w === 390) {
          await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
          await page.locator("[data-play-confirm]").click();
          await page.evaluate(() => { document.querySelectorAll(".ws-panel").forEach((e) => { (e as HTMLElement).scrollTop = 9999; }); });
          await shot(page, "on-390-fila-sticky");
        }
      }
    });

    test("off combate", async ({ page, backend }) => {
      const state = backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
      void state;
      await openIdle(page);
      await shot(page, `off-${w}-combate`);
    });
  });
}

test("espólio 390", async ({ page, backend }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  backend.states.get("game-a")!.player_stats.espolio_pendente = { id: "e", origem: "vitoria", recusa_ouro: 5, ofertas: [
    { id: "c1", name: "Estocada", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "**Sangria** 1.", descricao: "Um golpe curto.", conhecida: false }] } as never;
  await openIdle(page);
  await shot(page, "on-390-espolio");
});

test("forja 1440", async ({ page, backend }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  backend.states.get("game-a")!.player_stats.forja = {
    permitido: true, motivo: "", baralho_min: 3, baralho: [{ id: "golpe", name: "Golpe do Véu", copias: 1, esquecivel: true }],
    esquecer: { descanso: true, templo: true, ouro: 30 }, afiar: { material: null, afiaveis: [], afiadas: [] },
    purgar: { medico: true, templo: true, ouro: 20 }, cicatrizes: [] } as never;
  await openIdle(page);
  await page.locator("[data-forja-row='golpe']").click();
  await page.locator("[data-forja-forget='golpe:descanso']").click();
  await shot(page, "on-1440-forja");
});
