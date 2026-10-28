// SPEC-347 Etapa 5 (R13.8): retrato no chip do inimigo — marcador, imagem, tamanho fixo e o resto do tabuleiro intacto.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, panel } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

// 1x1 transparente (data URI: sem rede)
const PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

for (const [label, viewport, size] of [["390", { width: 390, height: 844 }, 56], ["1440", { width: 1440, height: 900 }, 72]] as const) {
  test.describe(`retrato ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    test(`retrato_marcador_e_imagem_${label}: tamanho fixo e sem salto`, async ({ page, backend }) => {
      const state = armDeck(backend);
      const common = { familia: "bruto", icone: "combat", proprio: false, gerar: null };
      (state.combat.enemies[0] as unknown as Record<string, unknown>).retrato = { ...common, estado: "marcador", src: null, alt: "Retrato de Saqueador" };
      (state.combat.enemies[1] as unknown as Record<string, unknown>).retrato = { ...common, estado: "pronto", src: PIXEL, alt: "Retrato de Bandoleiro" };
      await openCombat(page);
      const marker = page.locator('[data-portrait="marcador"]');
      const img = page.locator('[data-portrait="pronto"] img');
      await expect(marker).toBeVisible();
      await expect(img).toHaveAttribute("alt", "Retrato de Bandoleiro");
      const a = await measure(marker);
      expect(Math.round(a.w)).toBe(size);
      expect(Math.round(a.h)).toBe(size);
      expect(Math.round((await measure(page.locator('[data-portrait="pronto"]'))).w)).toBe(size);
      // o nome continua no texto e a barra de Vitalidade não some
      await expect(page.locator('[data-participant="e1"] strong')).toHaveText("Saqueador");
      if (label === "1440") {
        expect(await panel(page).evaluate((el) => el.scrollTop)).toBe(0);
        expect((await measure(page.locator(".deck-card").first())).inView).toBe(true);
      }
    });
  });
}

test("retrato_ausente_nao_muda_o_chip: sem `retrato` o markup é o de hoje", async ({ page, backend }) => {
  armDeck(backend);
  await openCombat(page);
  await expect(page.locator("[data-portrait]")).toHaveCount(0);
  await expect(page.locator(".tchip--portrait")).toHaveCount(0);
});
