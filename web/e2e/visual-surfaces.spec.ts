import { test, expect } from "./fixtures";

// Snapshots têm uma única autoridade: Chromium pinado em Linux e opt-in explícito.
// Isso evita atualizar baselines por diferenças de fonte/GPU do ambiente local.
test("visual surfaces in pinned environment", async ({ page }) => {
  test.skip(process.platform !== "linux" || process.env.RPG_VISUAL_SNAPSHOTS !== "1", "visual baseline requires pinned Linux CI");
  await page.goto("/");
  await expect(page).toHaveScreenshot("saves.png", { animations: "disabled", fullPage: true });
});
