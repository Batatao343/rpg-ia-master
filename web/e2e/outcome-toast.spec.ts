import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-199: chip de XP aparece uma vez por receipt_id e não reanima no reload.
async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

for (const width of [390, 1440]) {
  test(`SPEC-199 chip de XP uma vez @${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await openGame(page);
    const chip = page.locator(".outcome-chip", { hasText: "+50 XP" });
    await expect(chip).toHaveCount(0);
    await page.getByPlaceholder(/O que você faz/).fill("Vitória sobre o saqueador");
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(chip).toBeVisible();
    await expect(page.locator(".outcome-toast")).toHaveAttribute("aria-live", "polite");
    // a prosa do chat não carrega o número
    await expect(page.getByText(/\+50 XP/)).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.reload();
    await openGame(page);
    await page.waitForTimeout(600);
    await expect(chip).toHaveCount(0);
  });
}
