import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-323: livro, não chat (marginália, sugestões de contexto, arena de treino).
async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByPlaceholder(/O que você faz/)).toBeVisible();
}

test("ação do jogador é marginália: sem caixa, sem flex-end, alinhada à narração", async ({ page }) => {
  await openGame(page);
  await page.getByPlaceholder(/O que você faz/).fill("Examino o sino");
  await page.getByRole("button", { name: "Agir" }).click();
  const player = page.locator("article.msg--player").last();
  await expect(player).toBeVisible();
  const css = await player.evaluate((el) => { const c = getComputedStyle(el); return { self: c.alignSelf, border: c.borderTopWidth, bg: c.backgroundColor }; });
  expect(css.self).not.toBe("flex-end");
  expect(css.border).toBe("0px");
  const narr = page.locator("article.msg--story").last();
  await expect(narr).toBeVisible();
  const [a, b] = await Promise.all([player.boundingBox(), narr.boundingBox()]);
  expect(Math.abs(a!.x - b!.x)).toBeLessThanOrEqual(4);
});

test("sugestão de contexto preenche o campo e não envia turno", async ({ page }) => {
  await openGame(page);
  let posts = 0;
  page.on("request", (r) => { if (/\/game\/action/.test(r.url()) && r.method() === "POST") posts++; });
  await page.getByRole("button", { name: "Descansar", exact: true }).click();
  await expect(page.getByPlaceholder(/O que você faz/)).toHaveValue("Descanso um pouco");
  await page.waitForTimeout(300);
  expect(posts).toBe(0);
});

test("Arena de treino é link secundário depois do botão principal da criação", async ({ page, backend }) => {
  backend.saves = [];
  await page.goto("/");
  const primary = page.getByRole("button", { name: "Continuar", exact: true });
  const arena = page.getByRole("button", { name: /Arena de treino/ });
  await expect(primary).toBeVisible();
  await expect(arena).toBeVisible();
  const order = await page.evaluate(() => {
    const btns = [...document.querySelectorAll("main button")];
    const p = btns.findIndex((b) => b.textContent?.trim() === "Continuar");
    const a = btns.findIndex((b) => /Arena de treino/.test(b.textContent ?? ""));
    return { p, a };
  });
  expect(order.p).toBeGreaterThanOrEqual(0);
  expect(order.a).toBeGreaterThan(order.p);
  await expect(page.getByText(/zero LLM/)).toHaveCount(0);
});
