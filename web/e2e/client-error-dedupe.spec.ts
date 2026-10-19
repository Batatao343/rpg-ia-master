import { test, expect } from "./fixtures";

// SPEC-284 (follow-up da SPEC-244): o mesmo erro forçado no cliente gera exatamente UM
// POST /telemetry/client-error (dedupe por assinatura, 1x/min), mesmo se repetido.
test("SPEC-284 forced client error produces exactly one client-error beacon", async ({ page, backend }) => {
  await page.goto("/");
  await expect(page.locator("#root")).not.toBeEmpty();
  const before = backend.clientErrorBeacons;

  const fire = () => page.evaluate(() => {
    const error = new TypeError("erro forçado pelo teste");
    window.dispatchEvent(new ErrorEvent("error", { error, message: error.message }));
  });
  await fire();
  await expect.poll(() => backend.clientErrorBeacons - before).toBe(1);

  // Repetições da mesma assinatura dentro da janela de dedupe não geram novo POST.
  await fire();
  await fire();
  await page.waitForTimeout(500);
  expect(backend.clientErrorBeacons - before).toBe(1);
});
