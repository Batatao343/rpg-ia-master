// SPEC-387 R8/R9: o chip vira "Gerando retrato…" no clique (cotação atrasada 1 s), o botão tem `disabled`
// de verdade e erro/cancelamento devolvem a oferta.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

const QUOTE_ID = "123e4567-e89b-42d3-a456-426614174097";
const quoteBody = (milli: string) => ({
  quote_id: QUOTE_ID, type: "monster", credits_milli: milli, pricing_version: "test-v1",
  expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
});

function offer(backend: Parameters<typeof armDeck>[0]) {
  const state = armDeck(backend);
  (state.combat.enemies[0] as unknown as Record<string, unknown>).retrato = {
    estado: "marcador", src: null, familia: "bruto", icone: "combat", proprio: false,
    alt: "Retrato de Saqueador", gerar: { preco_estilhas: 3, escopo: "tipo" },
  };
  return state;
}

for (const [label, viewport] of [["390", { width: 390, height: 844 }], ["1440", { width: 1440, height: 900 }]] as const) {
  test.describe(`retrato otimista ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    test(`chip "Gerando retrato…" no clique, sem botão de gerar durante a cotação (${label})`, async ({ page, backend }) => {
      offer(backend);
      await page.route("**/game/game-a/art/quote", async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody("3000")) });
      });
      await page.route("**/game/game-a/art/confirm", (route) => route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ status: "pending", generation_id: "123e4567-e89b-42d3-a456-426614174096", type: "monster", placeholder: true }) }));
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.getByText("Gerando retrato…").first()).toBeVisible({ timeout: 300 });
      await expect(page.locator("[data-gen-portrait]")).toHaveCount(0);
    });

    test(`503 na cotação devolve a oferta (${label})`, async ({ page, backend }) => {
      offer(backend);
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporarily_unavailable" }) }));
      backend.allowConsole(/status of 503/);
      backend.allowFailure(/art.quote/);
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.locator('[data-gen-portrait="e1"]')).toBeVisible();
      await expect(page.getByText("Gerando retrato…")).toHaveCount(0);
    });

    test(`cotação maior e "Agora não" devolve a oferta (${label})`, async ({ page, backend }) => {
      offer(backend);
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody("9000")) }));
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.getByRole("button", { name: /cancelar|agora não|fechar/i }).first().click();
      await expect(page.locator('[data-gen-portrait="e1"]')).toBeVisible();
    });
  });
}
