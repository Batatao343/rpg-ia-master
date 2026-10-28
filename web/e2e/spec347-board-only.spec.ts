// SPEC-347 Etapa 4b: sem texto livre com o tabuleiro aberto (R18) e "Fugir" como botão do tabuleiro (R19).
import { test, expect } from "./fixtures";
import { actions, armDeck, openCombat } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

for (const [label, viewport, touch] of [["1440", { width: 1440, height: 900 }, false], ["390", { width: 390, height: 844 }, true]] as const) {
  test.describe(`tabuleiro ${label}`, () => {
    test.use({ viewport, hasTouch: touch, isMobile: touch });

    test(`sem_texto_livre_${label}: sem #composer nem "Lutar", com a nota; sem pilhas o composer fica como hoje`, async ({ page, backend }) => {
      const state = armDeck(backend);
      await openCombat(page);
      if (!touch) {
        await expect(page.locator("#composer")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Lutar", exact: true })).toHaveCount(0);
        await expect(page.getByRole("note").filter({ hasText: "Na luta, você age pelas cartas do tabuleiro." })).toBeVisible();
      } else {
        await expect(page.locator("#composer")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Lutar", exact: true })).toHaveCount(0);
      }
      // mesmo combate sem pilhas: composer como hoje
      delete (state.combat as { pilhas?: unknown }).pilhas;
      await page.reload();
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).click();
      if (!touch) {
        await expect(page.locator("#composer")).toHaveAttribute("placeholder", "O inimigo avança. O que você faz?");
        await expect(page.getByRole("button", { name: "Lutar", exact: true })).toBeVisible();
      }
    });
  });
}

test.describe("fuga 390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("fugir_alvo_44_390 e barra_sem_quebra_com_fugir_390", async ({ page, backend }) => {
    armDeck(backend, { nonlethal: true });
    await openCombat(page);
    for (const id of ["golpe", "corte"]) {
      await page.locator(`.deck-card[data-card="${id}"]`).dispatchEvent("click");
      await page.locator("button[data-target='e1']").dispatchEvent("click").catch(() => {});
      await page.locator("[data-play-confirm]").dispatchEvent("click");
    }
    const barBox = await page.locator(".play-queue__end").boundingBox();
    for (const sel of ["[data-spare]", "[data-flee]", "[data-end-turn]"]) {
      const b = await measure(page.locator(sel));
      expect(b.lines, sel).toBe(1);
      expect(b.clipped, `${sel} cortado`).toBe(false);
      expect(b.h, sel).toBeGreaterThanOrEqual(43.5);
      expect(b.x + b.w, sel).toBeLessThanOrEqual(barBox!.x + barBox!.width + 0.5);
    }
    expect((await measure(page.locator("[data-flee]"))).w).toBeGreaterThanOrEqual(43.5);
  });
});

test.describe("fuga 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("fugir_confirma_com_fila: 1ª ativação confirma sem request; Ficar e Esc devolvem o foco", async ({ page, backend }) => {
    backend.unexpectedAllowed.push(/combat\/preview/);
    armDeck(backend, { enemies: [["e1", "Saqueador"]] });
    await openCombat(page);
    await page.keyboard.press("1");
    await page.locator("[data-play-confirm]").press("Enter");
    await expect(page.locator(".play-queue__item")).toHaveCount(1);
    await page.locator("[data-flee]").click();
    await expect(page.getByText("Fugir agora? A fila desta rodada é descartada.")).toBeVisible();
    expect(actions(backend)).toHaveLength(0);
    await page.locator("[data-flee-stay]").click();
    await expect(page.locator("[data-flee]")).toBeFocused();
    await page.locator("[data-flee]").click();
    await page.keyboard.press("Escape");
    await expect(page.locator("[data-flee-confirm]")).toHaveCount(0);
    await expect(page.locator("[data-flee]")).toBeFocused();
    expect(actions(backend)).toHaveLength(0);
  });

  test("fugir_envia_acao_estruturada: fila vazia envia direto, sem jogadas", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await expect(page.locator("[data-basic='flee']")).toHaveCount(0); // a manobra saiu do details no Baralho (R19.1)
    await page.locator("[data-flee]").click();
    await expect.poll(() => actions(backend).length).toBe(1);
    const body = actions(backend)[0].body!;
    expect(body.action_kind).toBe("flee");
    expect(body.input_text).toBe("Tento fugir.");
    expect(body.jogadas).toBeUndefined();
  });

  test("fugir_resultado_escapou: a faixa mostra o texto literal", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await page.locator("[data-flee]").click();
    await expect(page.locator("[data-flee-result]")).toHaveText("Você escapou.");
  });

  test("fugir_resultado_falhou: o combate segue e a faixa diz que não escapou", async ({ page, backend }) => {
    backend.combatHits = true;
    armDeck(backend);
    await openCombat(page);
    await page.locator("[data-flee]").click();
    await expect(page.locator("[data-flee-result]")).toHaveText("Não escapou: o inimigo ainda está no seu encalço.");
  });
});
