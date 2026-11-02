// SPEC-364 R22: inimigo escondido nunca vira alvo na tela (com e sem `valid_targets` do servidor), em 1440 e 390.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";
import type { HandCard } from "../src/types";

const BASIC: HandCard[] = [
  { id: "bas_golpe", name: "Golpe Básico", custo_folego: 1, custo_entropia: 0, jogavel: true, alvo: "inimigo", texto: "Causa 3 de dano." },
];

function hiddenSetup(backend: Parameters<typeof armDeck>[0], serverTargets: boolean) {
  const state = armDeck(backend, { hand: BASIC });
  // espelha o contrato do servidor: `combat.scene.positions[*].concealment` e `pilhas.mao[*].valid_targets`
  const pos = state.combat.scene.positions.find((p) => p.participant_id === "e2")!;
  pos.concealment = "escondido";
  state.combat.cards = []; // carta básica da mão: não é uma Carta preparada (sem `valid_targets` de apoio)
  const card = state.combat.pilhas!.mao[0] as unknown as Record<string, unknown>;
  if (serverTargets) { card.valid_targets = ["e1"]; card.invalid_reason = null; }
  else { delete card.valid_targets; delete card.invalid_reason; }
  return state;
}

for (const [label, viewport] of [["1440", { width: 1440, height: 900 }], ["390", { width: 390, height: 844 }]] as const) {
  test.describe(`spec364 escondido ${label}`, () => {
    test.use({ viewport, hasTouch: label === "390", isMobile: label === "390" });

    for (const serverTargets of [true, false]) {
      test(`o escondido não arma a jogada, o visível arma (${serverTargets ? "valid_targets do servidor" : "fallback do cliente"})`, async ({ page, backend }) => {
        hiddenSetup(backend, serverTargets);
        await openCombat(page);
        await page.locator('.deck-card[data-card="bas_golpe"]').click();
        const visible = page.locator('button[data-target="e1"]');
        const hidden = page.locator('button[data-target="e2"]');
        await expect(visible).toBeVisible();
        await expect(hidden).toBeVisible();
        await expect(hidden).toHaveAttribute("aria-disabled", "true");
        await expect(hidden).toHaveAttribute("title", "escondido — fora de alcance");
        await hidden.click({ force: true });
        await expect(page.locator(".play-queue__item")).toHaveCount(0);
        await expect(visible).not.toHaveAttribute("aria-disabled", "true");
        await visible.click();
        await page.locator("[data-play-confirm]").click();
        await expect(page.locator(".play-queue__item")).toHaveCount(1);
      });
    }
  });
}
