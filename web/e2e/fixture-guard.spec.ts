import { test, expect } from "./fixtures";

// Regressão do guard global de `fixtures.ts`. No Chromium do Playwright (o do
// CI), o reload/goto do próprio teste aborta com net::ERR_ABORTED as requisições
// em voo do documento anterior (boot da API, fontes) — isso não é falha da
// aplicação. Um aborto feito pela app continua reprovando.

test("guard ignora requisições em voo abortadas pela navegação do teste", async ({ page, backend }) => {
  await page.route("**/guard-probe/slow*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 50));
    await route.fulfill({ status: 200, body: "ok" }).catch(() => undefined);
  });
  for (let round = 0; round < 3; round += 1) {
    await page.goto("/");
    await page.evaluate(() => { for (let k = 0; k < 5; k += 1) void fetch(`/guard-probe/slow?${k}`).catch(() => undefined); });
    // Mesmo padrão dos testes de reload: reload seguido de goto imediato.
    await page.reload();
    await page.evaluate(() => { for (let k = 5; k < 10; k += 1) void fetch(`/guard-probe/slow?${k}`).catch(() => undefined); });
    await page.goto("/");
  }
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  expect(backend.guardFailures).toEqual([]);
});

test("guard segue reprovando aborto feito pela própria aplicação", async ({ page, backend }) => {
  await page.route("**/guard-probe/app-abort", () => { /* nunca responde: fica em voo */ });
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  const aborted = page.waitForEvent("requestfailed", (r) => r.url().endsWith("/guard-probe/app-abort"));
  await page.evaluate(() => {
    const controller = new AbortController();
    void fetch("/guard-probe/app-abort", { signal: controller.signal }).catch(() => undefined);
    setTimeout(() => controller.abort(), 50);
  });
  await aborted;
  await expect.poll(() => backend.guardFailures.join("\n")).toContain("guard-probe/app-abort (net::ERR_ABORTED)");
  // Esperado por este teste: limpa para o teardown não reprovar.
  backend.guardFailures.splice(0);
});
