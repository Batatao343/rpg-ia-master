// SPEC-324: estrutura de headings (h1 local · h2 painel · h3 seção), skip link, atalhos Alt+dígito e folha "?".
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Sua ação" })).toBeVisible();
}

/** Headings expostos à árvore de acessibilidade (fora de [hidden] e de display:none), em ordem de documento. */
async function headingLevels(page: Page): Promise<{ level: number; text: string; cls: string }[]> {
  return page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6"))
    .filter((el) => !el.closest("[hidden]") && el.checkVisibility())
    .map((el) => ({ level: Number(el.tagName[1]), text: (el.textContent ?? "").trim(), cls: el.className })));
}

function assertNoSkips(list: { level: number; text: string }[]) {
  let prev = 0;
  for (const h of list) {
    expect(h.level, `"${h.text}" pula nível (veio depois de h${prev})`).toBeLessThanOrEqual(prev + 1);
    prev = h.level;
  }
}

test("um h1 (local), h2 por painel e h3 por seção, sem pular nível", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  const tabs = ["Codex", "Personagem", "Combate", "Bestiário", "Mapa"];
  for (const name of tabs) {
    await page.getByRole("tab", { name }).click();
    const list = await headingLevels(page);
    expect(list.filter((h) => h.level === 1), "exatamente um h1").toHaveLength(1);
    expect(list.filter((h) => h.level === 2).map((h) => h.text)).toContain(name);
    for (const h of list.filter((x) => x.cls.includes("hud__label"))) expect(h.level).toBe(3);
    assertNoSkips(list);
  }
  const place = await page.locator("h1.topbar__place").innerText();
  expect(place.trim().length).toBeGreaterThan(0);
  const axe = await new AxeBuilder({ page }).withRules(["heading-order", "page-has-heading-one", "empty-heading"]).analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);
});

test("h3 de seção mantém o visual do rótulo (sem negrito, sem margem de heading)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  await page.getByRole("tab", { name: "Personagem" }).click();
  const label = page.locator("h3.hud__label:visible").first();
  await expect(label).toBeVisible();
  const css = await label.evaluate((el) => {
    const s = getComputedStyle(el);
    return { weight: s.fontWeight, top: s.marginTop, size: s.fontSize };
  });
  expect(css.weight).toBe("400");
  expect(css.top).toBe("0px");
  const root = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  expect(parseFloat(css.size)).toBeCloseTo(0.8 * root, 1);
});

test("no celular o local é o h1 e a cabeça mantém o h2 da superfície", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openGame(page);
  const list = await headingLevels(page);
  expect(list.filter((h) => h.level === 1)).toHaveLength(1);
  expect(list[0].level).toBe(1);
  await expect(page.getByTestId("surface-title")).toBeVisible();
  assertNoSkips(list);
});

test("skip link é o primeiro foco e leva ao compositor", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  // Primeiro elemento focável do documento (ordem de Tab) é o skip link.
  const first = await page.evaluate(() => document.querySelector<HTMLElement>(
    "a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex=\"-1\"])")?.textContent);
  expect(first).toBe("Pular para a ação");
  const skip = page.getByRole("link", { name: "Pular para a ação" });
  await skip.focus();
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("textbox", { name: "Sua ação" })).toBeFocused();
});

test("Alt+dígito abre painéis (Ctrl+dígito não); abas anunciam aria-keyshortcuts", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  await page.getByRole("tab", { name: "Codex" }).focus();
  await page.keyboard.press("Alt+3");
  await expect(page.getByRole("tab", { name: "Personagem" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Control+4");
  await expect(page.getByRole("tab", { name: "Personagem" })).toHaveAttribute("aria-selected", "true");
  const tab = page.getByRole("tab", { name: "Mapa" });
  await expect(tab).toHaveAttribute("aria-keyshortcuts", /Alt\+6$/);
  await expect(tab).toHaveAttribute("title", /\(.*Alt\+6\)$/);
});

test("? abre a folha de atalhos com foco preso e Esc devolve o foco", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  const tab = page.getByRole("tab", { name: "Personagem" });
  await tab.focus();
  await page.keyboard.press("?");
  const sheet = page.getByRole("dialog", { name: "Atalhos" });
  await expect(sheet).toBeVisible();
  await expect(sheet.locator("li")).toHaveCount(10);
  for (let i = 0; i < 4; i += 1) await page.keyboard.press("Tab");
  expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(tab).toBeFocused();
  // Dentro do compositor "?" é só texto.
  const box = page.getByRole("textbox", { name: "Sua ação" });
  await box.focus();
  await page.keyboard.type("?");
  await expect(sheet).toBeHidden();
  await expect(box).toHaveValue("?");
});
