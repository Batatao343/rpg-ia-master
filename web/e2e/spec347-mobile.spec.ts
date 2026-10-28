// SPEC-347 Etapa 1: sobreposições e quebras a 390 px / 1440 (mira, barra de envio, presságio). Sem rolar antes de medir.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, roundLog } from "./deck-342-helpers";
import { measure, isFreeAndVisible } from "./spec347-helpers";

async function armAndAim(page: import("@playwright/test").Page, touch: boolean, enemies: number) {
  const card = page.locator('.deck-card[data-card="golpe"]');
  if (touch) await card.dispatchEvent("click"); else await page.keyboard.press("1");
  if (enemies > 1) {
    const target = page.locator("button[data-target='e1']");
    await expect(target).toBeVisible();
    await target.dispatchEvent("click");
  }
  await expect(page.locator(".preview-chip[data-preview='ok']")).toBeVisible();
}

for (const [label, viewport, touch] of [["390", { width: 390, height: 844 }, true], ["1440", { width: 1440, height: 900 }, false]] as const) {
  test.describe(`mira ${label}`, () => {
    test.use({ viewport, hasTouch: touch, isMobile: touch });
    for (const enemies of [1, 2]) {
      test(`mira_livre_apos_previa_${label}_${enemies}inimigo`, async ({ page, backend }) => {
        armDeck(backend, { enemies: enemies === 1 ? [["e1", "Saqueador"]] : [["e1", "Saqueador"], ["e2", "Bandoleiro"]] });
        backend.previewDelayMs = 150;
        await openCombat(page);
        await armAndAim(page, touch, enemies);
        await page.waitForTimeout(250); // a rolagem do efeito assenta (sem ação do teste)
        const ok = await measure(page.locator("[data-play-confirm]"));
        const cancel = await measure(page.locator(".aimbar__cancel"));
        expect(isFreeAndVisible(ok), JSON.stringify(ok)).toBe(true);
        expect(isFreeAndVisible(cancel), JSON.stringify(cancel)).toBe(true);
      });
    }
  });
}

test.describe("390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("barra_sem_quebra_fila_cheia: uma linha por rótulo, selo afastado, alvos >= 44", async ({ page, backend }) => {
    armDeck(backend, { nonlethal: true });
    await openCombat(page);
    for (const id of ["golpe", "corte"]) {
      await page.locator(`.deck-card[data-card="${id}"]`).dispatchEvent("click");
      await page.locator("button[data-target='e1']").dispatchEvent("click").catch(() => {});
      await page.locator("[data-play-confirm]").dispatchEvent("click");
    }
    await expect(page.locator(".play-queue__item")).toHaveCount(2);
    const bar = page.locator(".play-queue__end");
    const barBox = await bar.boundingBox();
    for (const sel of ["[data-spare]", "[data-end-turn]"]) {
      const b = await measure(page.locator(sel));
      expect(b.lines, sel).toBe(1);
      expect(b.clipped, `${sel} cortado`).toBe(false);
      expect(b.h, sel).toBeGreaterThanOrEqual(43.5);
      expect(b.x + b.w, sel).toBeLessThanOrEqual(barBox!.x + barBox!.width + 0.5);
    }
    const label = await page.locator("[data-end-turn] span").first().boundingBox();
    const badge = await page.locator(".play-queue__badge").boundingBox();
    expect(badge!.x - (label!.x + label!.width)).toBeGreaterThanOrEqual(6);
    await expect(page.locator("[data-end-turn]")).toHaveAccessibleName("Encerrar a rodada, 2 cartas");
    await expect(page.locator(".play-queue__clear--bar")).toBeHidden();
    const clear = await measure(page.locator(".play-queue__clear--inline"));
    expect(clear.lines).toBe(1);
    expect(clear.h).toBeGreaterThanOrEqual(43.5);
  });

  test("pressagio_faixa_inteira: '3–6' numa linha", async ({ page, backend }) => {
    const state = armDeck(backend, { intent: true });
    state.combat.pressagios_publicos = [{ actor_id: "e1", tipo: "ataque", alvo_id: "player", valor_estimado: null, faixa: [3, 6], carta_nome: "Talho", sinal: "ergue a lâmina" }];
    await openCombat(page);
    const num = page.locator(".tchip__omen-num").first();
    await expect(num).toBeVisible();
    expect((await measure(num)).lines).toBe(1);
  });

  test("alvos_44_mira_e_fila", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await page.locator('.deck-card[data-card="golpe"]').dispatchEvent("click");
    await page.locator("button[data-target='e1']").dispatchEvent("click");
    await expect(page.locator(".preview-chip[data-preview='ok']")).toBeVisible();
    for (const sel of ["[data-play-confirm]", ".aimbar__cancel", "[data-other-target]"]) {
      const b = await measure(page.locator(sel));
      expect(b.h, sel).toBeGreaterThanOrEqual(43.5);
    }
  });
});

test.describe("390 etapa 3", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("has_loot_mobile: o botão Combate da barra avisa o espólio e limpa ao abrir", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.player_stats.espolio_pendente = { id: "esp1", origem: "vitoria", recusa_ouro: 5, ofertas: [
      { id: "c1", name: "Estocada", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "**Sangria** 1.", descricao: "", conhecida: false },
    ] } as never;
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    const btn = page.locator(".mtabbar__btn", { hasText: "Combate" });
    await expect(btn).toHaveClass(/has-loot/);
    await expect(btn).toHaveAccessibleName(/ — espólio à espera$/);
    await btn.click();
    await expect(btn).not.toHaveClass(/has-loot/);
  });

  test("desfecho_abre_no_topo_390: Continuar visível e livre depois de rolar o painel até o fim", async ({ page, backend }) => {
    backend.unexpectedAllowed.push(/combat\/preview/);
    armDeck(backend, { enemies: [["e1", "Saqueador"]] });
    await openCombat(page);
    await page.locator('.deck-card[data-card="golpe"]').dispatchEvent("click");
    await page.locator("[data-play-confirm]").dispatchEvent("click");
    await expect(page.locator(".play-queue__item")).toHaveCount(1);
    await page.locator(".ws-panel, #ws-panel-combate").first().evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.locator("[data-end-turn]").dispatchEvent("click");
    const next = page.locator(".combat-outcome__continue");
    await expect(next).toBeVisible();
    await page.waitForTimeout(300);
    const b = await measure(next);
    expect(isFreeAndVisible(b), JSON.stringify(b)).toBe(true);
  });

  test("registro_acima_da_arena_390: 4 recentes + 'Ver a rodada inteira (6)'", async ({ page, backend }) => {
    armDeck(backend, { roundLog: roundLog(6) });
    await openCombat(page);
    const board = page.locator("[data-roundboard]");
    await expect(board.locator(".roundboard__list").first().locator(".roundboard__row")).toHaveCount(4);
    await expect(board.locator("summary")).toHaveText("Ver a rodada inteira (6)");
    expect((await measure(board.locator("summary"))).h).toBeGreaterThanOrEqual(43.5);
    const above = await page.evaluate(() => !!(document.querySelector("[data-roundboard]")!.compareDocumentPosition(document.querySelector(".arena")!) & Node.DOCUMENT_POSITION_FOLLOWING));
    expect(above).toBe(true);
  });
});
