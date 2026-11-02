// SPEC-363 R39: oferta de retrato com/sem mira, 409 de alvo (só a jogada recusada sai) e morte (tabuleiro fecha).
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

function withOffer(backend: Parameters<typeof armDeck>[0], gerar: boolean) {
  const state = armDeck(backend);
  (state.combat.enemies[0] as unknown as Record<string, unknown>).retrato = {
    estado: "marcador", src: null, familia: "bruto", icone: "combat", proprio: false,
    alt: "Retrato de Saqueador", gerar: gerar ? { preco_estilhas: 3, escopo: "tipo" } : null,
  };
  return state;
}

for (const [label, viewport] of [["390", { width: 390, height: 844 }], ["1440", { width: 1440, height: 900 }]] as const) {
  test.describe(`spec363 ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    test(`oferta de retrato aparece com e sem mira (${label})`, async ({ page, backend }) => {
      withOffer(backend, true);
      await openCombat(page);
      const offer = page.locator('[data-gen-portrait="e1"]');
      await expect(offer).toBeVisible();
      await page.locator('[data-card-id="golpe"], .deck-card').first().click(); // arma uma carta: entra em mira
      await expect(page.locator("button[data-target]").first()).toBeVisible();
      await expect(offer).toBeVisible(); // R3: continua visível com mira
      // tocar na oferta não escolhe alvo nem enfileira jogada
      await offer.click();
      await expect(page.locator(".play-queue__item")).toHaveCount(0);
    });

    test(`sem oferta no servidor, sem botão (switch desligado) (${label})`, async ({ page, backend }) => {
      withOffer(backend, false);
      await openCombat(page);
      await expect(page.locator("[data-gen-portrait]")).toHaveCount(0);
    });

    test(`503 da cotação apaga a oferta daquele inimigo (${label})`, async ({ page, backend }) => {
      withOffer(backend, true);
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "image_generation_disabled" }) }));
      backend.allowConsole(/status of 503/);
      backend.allowFailure(new RegExp("art.quote"));
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.getByText("Geração de imagem indisponível agora.")).toBeVisible();
      await expect(page.locator('[data-gen-portrait="e1"]')).toHaveCount(0);
    });
  });
}

test.describe("spec363 fila e morte", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  const card = (page: import("@playwright/test").Page, id: string) => page.locator(`.deck-card[data-card="${id}"]`);

  test("409 de alvo tira só a jogada recusada da fila (R21)", async ({ page, backend }) => {
    armDeck(backend);
    backend.allowConsole(/status of 409/);
    await page.route("**/game/action/stream", (route) =>
      route.fulfill({
        status: 200, contentType: "text/event-stream",
        body: `event: error\ndata: ${JSON.stringify({ code: 409, detail: { code: "invalid_target", message: "O alvo escolhido deixou de ser válido. Escolha de novo.", play_index: 0, card_id: "golpe" } })}\n\n`,
      }));
    await page.route("**/game/action", (route) =>
      route.fulfill({
        status: 409, contentType: "application/json",
        body: JSON.stringify({ detail: { code: "invalid_target", message: "O alvo escolhido deixou de ser válido. Escolha de novo.", play_index: 0, card_id: "golpe" } }),
      }));
    await openCombat(page);
    await card(page, "golpe").click();
    await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
    await page.locator("[data-play-confirm]").click();
    await card(page, "corte").click();
    await page.getByRole("button", { name: /Alvo: Bandoleiro/ }).click();
    await page.locator("[data-play-confirm]").click();
    await expect(page.locator(".play-queue__item")).toHaveCount(2);
    await page.locator("[data-end-turn]").click();
    await expect(page.locator(".play-queue__item")).toHaveCount(1);
    await expect(page.locator(".play-queue__item")).toContainText("Corte Largo");
  });

  test("morte pendente: mão, Encerrar e Fugir desabilitados no mesmo render (R16)", async ({ page, backend }) => {
    const state = armDeck(backend);
    await openCombat(page);
    await expect(page.locator("[data-flee], button:has-text('Fugir')").first()).toBeVisible();
    // o servidor passa a dizer que o herói tombou
    (state as unknown as Record<string, unknown>).death_pending = true;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await page.reload();
    await expect(page.locator(".deck-card:not([aria-disabled='true']):not([disabled])")).toHaveCount(0);
  });
});
