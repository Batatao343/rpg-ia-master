// SPEC-367 R4/R5/R6: depois de "Gerar" o chip troca na hora para "Gerando retrato…"; duplo clique = 1 cotação e 1 confirmação.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

const QUOTE_ID = "123e4567-e89b-42d3-a456-426614174099";
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
  test.describe(`retrato pendente ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    test(`confirmar tira a oferta e mostra "Gerando retrato…"; duplo clique = 1 quote e 1 confirm (${label})`, async ({ page, backend }) => {
      offer(backend);
      let quotes = 0;
      let confirms = 0;
      await page.route("**/game/game-a/art/quote", async (route) => {
        quotes += 1;
        await new Promise((resolve) => setTimeout(resolve, 150));
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody("3000")) });
      });
      await page.route("**/game/game-a/art/confirm", (route) => {
        confirms += 1;
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          status: "pending", generation_id: "123e4567-e89b-42d3-a456-426614174098", type: "monster", placeholder: true }) });
      });
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").dblclick();
      await expect(page.getByText("Retrato encomendado. O saldo foi reservado.")).toBeVisible();
      await expect(page.locator('[data-gen-portrait="e1"]')).toHaveCount(0);
      await expect(page.getByText("Gerando retrato…").first()).toBeVisible();
      expect(quotes).toBe(1);
      expect(confirms).toBe(1);
    });

    test(`503 na cotação mantém o comportamento de hoje, sem confirm (${label})`, async ({ page, backend }) => {
      offer(backend);
      let confirms = 0;
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "image_generation_disabled" }) }));
      await page.route("**/game/game-a/art/confirm", (route) => { confirms += 1; return route.abort(); });
      backend.allowConsole(/status of 503/);
      backend.allowFailure(/art.quote/);
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.getByText("Geração de imagem indisponível agora.")).toBeVisible();
      expect(confirms).toBe(0);
      await expect(page.getByText("Gerando retrato…")).toHaveCount(0);
    });
  });
}
