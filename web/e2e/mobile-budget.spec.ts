// SPEC-321 R4/R12: orçamento vertical no celular — a história ocupa ≥ 55 % da altura da viewport no 2º turno
// de um local (fora de combate e sem onboarding), a arte de cena recolhe (≤ 72 px) e um toque a reabre.
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const VIEWPORTS = [{ width: 360, height: 740 }, { width: 390, height: 844 }];

async function openGame(page: Page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).tap();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const art = (page: Page) => page.locator(".scene-art");

for (const vp of VIEWPORTS) {
  test.describe(`${vp.width}x${vp.height}`, () => {
    test.use({ viewport: vp, hasTouch: true, isMobile: true });

    test("história ≥ 55 % da altura no 2º turno e arte recolhida", async ({ page }) => {
      await openGame(page);
      await composer(page).fill("Observo o porto");
      await page.getByRole("button", { name: "Agir" }).tap();
      await expect(page.getByText("O mundo responde a: Observo o porto").first()).toBeVisible();
      // 1º beat no mesmo local passou: a arte recolhe para a faixa fina.
      await expect.poll(async () => (await art(page).boundingBox())?.height ?? 999).toBeLessThanOrEqual(72);
      const story = (await page.locator(".story").boundingBox())!;
      expect(story.height / vp.height, `história ${Math.round(story.height)}px de ${vp.height}px`).toBeGreaterThanOrEqual(0.55);
    });

    test("rolar a história recolhe a arte e um toque a reabre", async ({ page, backend }) => {
      const history = backend.histories.get("game-a")!;
      for (let i = 1; i <= 20; i++) {
        history.push({ id: `b-n${i}`, turn: i, epoch: 1, role: "narrator", text: `Registro extenso ${i}. `.repeat(12), type: "STORY" });
      }
      await openGame(page);
      expect((await art(page).boundingBox())!.height).toBeGreaterThan(100);
      const story = page.getByRole("region", { name: "Narrativa" });
      const box = (await story.boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.wheel(0, -200); // gesto do jogador subindo no histórico (o auto-scroll não conta)
      await expect.poll(async () => (await art(page).boundingBox())?.height ?? 999).toBeLessThanOrEqual(72);
      await page.getByRole("button", { name: /Mostrar a arte/ }).tap();
      await expect.poll(async () => (await art(page).boundingBox())?.height ?? 0).toBeGreaterThan(100);
    });
  });
}
