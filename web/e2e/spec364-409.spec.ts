// SPEC-364 R23b: o 409 com `play_index: 1` tira a jogada de índice 1 (não a primeira) e o aviso cita a Carta 1.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

test.describe("spec364 409 tira só a jogada certa", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  const card = (page: import("@playwright/test").Page, id: string) => page.locator(`.deck-card[data-card="${id}"]`);

  test("play_index 1 sai da fila; as jogadas 0 e 2 ficam", async ({ page, backend }) => {
    armDeck(backend);
    backend.allowConsole(/status of 409/);
    const detail = { code: "invalid_target", message: "O alvo escolhido deixou de ser válido. Escolha de novo.", play_index: 1, card_id: "corte" };
    await page.route("**/game/action/stream", (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream", body: `event: error\ndata: ${JSON.stringify({ code: 409, detail })}\n\n` }));
    await page.route("**/game/action", (route) =>
      route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail }) }));
    await openCombat(page);
    await card(page, "golpe").click();
    await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
    await page.locator("[data-play-confirm]").click();
    await card(page, "corte").click();
    await page.getByRole("button", { name: /Alvo: Bandoleiro/ }).click();
    await page.locator("[data-play-confirm]").click();
    await card(page, "pesada").click();
    await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
    await page.locator("[data-play-confirm]").click();
    await expect(page.locator(".play-queue__item")).toHaveCount(3);
    await page.locator("[data-end-turn]").click();
    const items = page.locator(".play-queue__item");
    await expect(items).toHaveCount(2);
    await expect(items.nth(0)).toContainText("Golpe do Véu");
    await expect(items.nth(1)).toContainText("Golpe Pesado");
    await expect(page.getByText(/Corte Largo perdeu o alvo/)).toBeVisible();
  });
});
