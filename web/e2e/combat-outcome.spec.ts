import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-203 R8: painel de desfecho do combate; "Continuar" fecha só o painel
// (sem consumir turno, draft preservado) e o painel reaparece após reload.
async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

// SPEC-216: < 900px é uma superfície por vez; a barra "Superfícies" substitui o grupo "Modo de exibição".
const phoneSurface = (page: Page, name: "Chat" | "Combate") =>
  page.getByRole("navigation", { name: "Superfícies" }).getByRole("button", { name, exact: true }).click();

for (const width of [390, 1440]) {
  test(`SPEC-203 desfecho do combate @${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    const state = backend.states.get("game-a")!;
    state.combat.active = true; state.combat.round = 1;
    state.combat.cards = state.player_stats.cards;
    state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
    await openGame(page);
    if (width < 900) await phoneSurface(page, "Chat");
    await page.locator("form.actionbar input").first().fill("Golpeio o saqueador");
    await page.getByRole("button", { name: "Lutar" }).click();

    const panel = page.getByRole("region", { name: "Desfecho do combate" });
    if (width < 900) await phoneSurface(page, "Combate");
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("heading", { name: "Vitória" })).toBeVisible();
    await expect(panel.getByText("Saqueador — abatido")).toBeVisible();
    await expect(panel.getByText("+50 XP")).toBeVisible();
    // SPEC-204 R12: < 1100px há uma superfície por vez; o desfecho fica na aba Combate
    // (R10) e a narração no chat — alterna para o chat para conferir a narração.
    if (width < 900) await phoneSurface(page, "Chat");
    // O chat recebe só a narração; nenhum número de XP no balão.
    await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
    await expect(page.locator(".story-log, .storylog, [class*=story]").getByText(/XP/)).toHaveCount(0);

    await page.locator("form.actionbar input").first().fill("rascunho preservado");
    const actions = backend.requests.filter((r) => r.path.startsWith("/game/action")).length;
    if (width < 900) await phoneSurface(page, "Combate");
    await panel.getByRole("button", { name: "Continuar" }).click();
    await expect(panel).toHaveCount(0);
    await expect(page.locator("form.actionbar input").first()).toHaveValue("rascunho preservado");
    expect(backend.requests.filter((r) => r.path.startsWith("/game/action")).length).toBe(actions);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (width === 1440) await page.screenshot({ path: "test-results/spec203-outcome-1440.png" });

    // Reload antes de "Continuar" ser persistido: painel volta igual (derivado do save).
    await page.reload();
    await openGame(page);
    await expect(page.getByRole("region", { name: "Desfecho do combate" })).toBeVisible();
  });
}
