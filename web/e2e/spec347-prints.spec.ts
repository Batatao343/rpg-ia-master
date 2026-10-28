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
});
