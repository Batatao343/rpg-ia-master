import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-202 R13: o StoryLog mostra QUEM respondeu (nome canônico do NPC) como
// rótulo passivo — sem seletor/botão Narrador×NPC e sem mudar o composer.

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

for (const width of [390, 1440]) {
  test(`SPEC-202 speaker label is passive @${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await openGame(page);
    await page.getByPlaceholder(/O que você faz/).fill("Converso com Borin");
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(page.getByText("Borin, o barqueiro, responde sem desviar o olhar.")).toBeVisible();
    const label = page.locator(".msg__role", { hasText: /^Borin$/ });
    await expect(label).toBeVisible();
    await expect(page.locator(".msg__role", { hasText: /^Diálogo$/ })).toHaveCount(0);
    // Nenhum seletor de interlocutor no DOM.
    await expect(page.getByRole("radio", { name: /narrador/i })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: /narrador/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^narrador$/i })).toHaveCount(0);
    if (process.env.RPG_SPEC202_SHOTS) await page.screenshot({ path: `../docs/spec202/speaker-${width}.png` });
  });
}
