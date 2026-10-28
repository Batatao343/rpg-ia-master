// SPEC-347 Etapa 2/3 (1440): Arena compacta, tooltip fora dos controles, desfecho no topo. Sem rolar antes de medir.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, panel } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

test.use({ viewport: { width: 1440, height: 900 } });

test("arena_tres_zonas_1440: chips legíveis e a 1ª carta inteira no painel sem rolar", async ({ page, backend }) => {
  const state = armDeck(backend, { zones: ["Veio de Calcário", "Boca do Abismo"], intent: true, scene: true });
  state.combat.enemies[0].conditions = [{ name: "Sangramento", duration: 2 }, { name: "Rachadura", duration: 1 }] as never;
  state.combat.enemies[1].conditions = [{ name: "Medo", duration: 1 }, { name: "Atordoado", duration: 1 }] as never;
  await openCombat(page);
  const chips = page.locator(".arena--compact .tchip");
  await expect(chips.first()).toBeVisible();
  for (const box of await chips.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().width))) expect(box).toBeGreaterThanOrEqual(224);
  for (const lines of await page.locator(".tchip__vit").evaluateAll((els) => els.map((e) => e.getClientRects().length))) expect(lines).toBe(1);
  await expect(page.locator(".arena__empty-zones")).toContainText("Também na cena: Veio de Calcário · Boca do Abismo");
  expect(await panel(page).evaluate((el) => el.scrollTop)).toBe(0);
  const first = await measure(page.locator(".deck-card").first());
  expect(first.inView, JSON.stringify(first)).toBe(true);
});

test("rodada_uma_vez_e_sem_zero: iniciativa honesta no Baralho", async ({ page, backend }) => {
  const state = armDeck(backend, {});
  state.combat.order = [{ name: "Heróis", side: "hero", init: 0 }, { name: "Inimigos", side: "enemy", init: 0 }];
  await openCombat(page);
  await expect(page.locator(".arena__turn")).toHaveText(/^Na última rodada, (Heróis|Inimigos) agiram primeiro\.$/);
  const text = await page.locator(".ws-combat").first().textContent() ?? "";
  expect((text.match(/Rodada/g) ?? []).length).toBe(1);
  expect(text).not.toMatch(/\b0 · (Heróis|Inimigos)/);
});

test("off_iniciativa_honesta: sem 'Rodada N · iniciativa' nem '0 ·' com o Baralho desligado", async ({ page, backend }) => {
  const state = backend.armCombat("game-a", [["e1", "Saqueador"]]);
  state.combat.order = [{ name: "Heróis", side: "hero", init: 0 }, { name: "Inimigos", side: "enemy", init: 0 }];
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
  const tab = page.getByRole("tab", { name: "Combate" });
  if (await tab.count()) await tab.click();
  await expect(page.locator(".arena__turn")).toHaveText("Na última rodada, Heróis agiram primeiro.");
  const body = (await page.locator("body").textContent()) ?? "";
  expect(body).not.toMatch(/iniciativa:/);
  expect(body).not.toMatch(/\b0 · (Heróis|Inimigos)/);
  await expect(page.locator(".initiative")).toHaveCount(0);
});
