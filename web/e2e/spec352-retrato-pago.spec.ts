// SPEC-352 Etapa 6 (R12): retrato de inimigo pago - oferta inline, cotação, confirmação única, 409 sem cobrança.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

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
  test.describe(`retrato pago ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    test(`cotação <= preço mostrado confirma direto: quote e confirm, sem 2º modal (${label})`, async ({ page, backend }) => {
      offer(backend);
      const quoted: Record<string, unknown>[] = [];
      const confirmed: Record<string, unknown>[] = [];
      await page.route("**/game/game-a/art/quote", (route) => {
        quoted.push(route.request().postDataJSON());
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody("3000")) });
      });
      await page.route("**/game/game-a/art/confirm", (route) => {
        confirmed.push(route.request().postDataJSON());
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          status: "pending", generation_id: "123e4567-e89b-42d3-a456-426614174098", type: "monster", placeholder: true }) });
      });
      await openCombat(page);
      const button = page.locator('[data-gen-portrait="e1"]');
      await expect(button).toHaveText("Gerar retrato (3 Estilhas)");
      expect((await measure(button)).h).toBeGreaterThanOrEqual(label === "390" ? 43.5 : 24);
      await button.click();
      await expect(page.locator("[data-gen-risk]")).toHaveText("Se a geração falhar antes de começar, o saldo é liberado.");
      expect(quoted).toHaveLength(0); // confirmar inline ainda não cotou
      await page.locator("[data-gen-go]").click();
      await expect(page.getByText("Retrato encomendado. O saldo foi reservado.")).toBeVisible();
      expect(quoted).toEqual([{ image_type: "monster", reformulation: false, enemy_id: "e1" }]);
      expect(confirmed).toHaveLength(1);
      expect(confirmed[0]).toMatchObject({ quote_id: QUOTE_ID, confirmed: true });
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });

    test(`"Agora não" não cota nem confirma (${label})`, async ({ page, backend }) => {
      offer(backend);
      let calls = 0;
      await page.route("**/game/game-a/art/**", (route) => { calls += 1; return route.abort(); });
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-no]").click();
      await expect(page.locator('[data-gen-portrait="e1"]')).toBeVisible();
      expect(calls).toBe(0);
    });

    test(`cotação maior que o preço mostrado abre o diálogo e não confirma sozinha (${label})`, async ({ page, backend }) => {
      offer(backend);
      let confirms = 0;
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteBody("3500")) }));
      await page.route("**/game/game-a/art/confirm", (route) => { confirms += 1; return route.abort(); });
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      const dialog = page.getByRole("dialog", { name: "Gerar retrato" });
      await expect(dialog).toBeVisible();
      await expect(dialog).toContainText("Custo máximo: 3,5 Estilhas");
      await expect(dialog).toContainText("registro compartilhado");
      expect(confirms).toBe(0);
    });

    test(`409 de outro jogador gerando: aviso sem cobrança e sem confirm (${label})`, async ({ page, backend }) => {
      offer(backend);
      let confirms = 0;
      await page.route("**/game/game-a/art/quote", (route) =>
        route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "creature_portrait_exists" }) }));
      await page.route("**/game/game-a/art/confirm", (route) => { confirms += 1; return route.abort(); });
      backend.allowConsole(/status of 409/);
      await openCombat(page);
      await page.locator('[data-gen-portrait="e1"]').click();
      await page.locator("[data-gen-go]").click();
      await expect(page.getByText("Outro jogador já está gerando este retrato. Ele aparece em breve, sem custo.")).toBeVisible();
      expect(confirms).toBe(0);
    });
  });
}
