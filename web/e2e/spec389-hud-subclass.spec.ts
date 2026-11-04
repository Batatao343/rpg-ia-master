// SPEC-389 R15: o "Acervo de Cartas" da Ficha mostra o rótulo de subclasse (facção) a 390 e 1440.
import { test, expect, openFicha } from "./fixtures";
import type { CardView } from "../src/types";

const mk = (id: string, name: string, over: Partial<CardView> = {}): CardView => ({
  id, name, type: "ativa", description: `${name} de teste`, effect_kind: "damage", target_kind: "enemy",
  subclass: "", prepared: true, cost: 1, base_cost: 1, frequency: "turno", spent: false, ready: true,
  has_rupture: false, rupture_ready: false, trigger: "", evolved: null, ...over,
});

for (const width of [390, 1440]) {
  test.describe(`acervo ${width}`, () => {
    test.use({ viewport: { width, height: 900 } });

    test(`subclasse_no_acervo_${width}`, async ({ page, backend }) => {
      backend.states.get("game-a")!.player_stats.cards = [
        mk("po", "Pó nos Olhos", { subclass: "Mão Sombria" }),
        mk("golpe", "Golpe do Véu"),
      ];
      await page.goto("/");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).click();
      await openFicha(page);
      const item = page.locator(".abilities li", { hasText: "Pó nos Olhos" });
      await expect(item).toContainText("Pó nos Olhos · Mão Sombria");
      await expect(page.locator(".abilities li", { hasText: "Golpe do Véu" })).not.toContainText("Mão Sombria");
    });
  });
}
