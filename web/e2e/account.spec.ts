import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";

for (const width of [390, 1440]) {
  test(`SPEC-185 account and turn cost at ${width}px`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: 850 });
    await page.route("https://fonts.googleapis.com/**", route =>
      route.fulfill({ status: 200, contentType: "text/css", body: "" }));
    await page.route("**/account/**", route => {
      const path = new URL(route.request().url()).pathname;
      const points = Array.from({ length: path.endsWith("/series") ? 30 : 0 }, (_, i) => ({
        start: new Date(Date.UTC(2026, 9, i + 1)).toISOString(),
        game: i === 6 ? "1500" : "0", image: "0", voice: "0", total: i === 6 ? "1500" : "0",
      }));
      const body = path.endsWith("/balance") ? { available_milli: "3250", reserved_milli: "0" }
        : path.endsWith("/series") ? { period: "7d", unit: "milli_shard", totals: { game: "1500", image: "0", voice: "0" }, points }
          : { items: [], next_cursor: null };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.route("**/game/*/operations/*/cost", route => route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ history_id: "turn-cost", cost_milli: null,
        technical_cost_usd: "0.000041550", technical_cost_basis: "usage_ledger",
        technical_cost_exact: false }),
    }));
    const history = backend.histories.get("game-a")!;
    Object.assign(history[0], { cost_milli: "1250", technical_cost_usd: "0.000041550",
      technical_cost_basis: "usage_ledger", technical_cost_exact: false });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Continuar jornada" })).toBeVisible();
    await page.getByRole("button", { name: /Conta · 3,25 Estilhas/ }).click();
    await expect(page.getByRole("heading", { name: "Minha conta" })).toBeVisible();
    await expect(page.getByText("3,25", { exact: false }).first()).toBeVisible();
    await expect(page.getByRole("img", { name: /Consumo liquidado em 7 dias/ })).toBeVisible();
    await page.getByText("Ver valores por período").click();
    await expect(page.getByRole("table", { name: /Consumo liquidado por período/ })).toBeVisible();
    await page.getByRole("button", { name: "24h" }).click();
    await expect(page.getByRole("img", { name: /24 horas/ })).toBeVisible();
    const accountA11y = await new AxeBuilder({ page }).analyze();
    expect(accountA11y.violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
    await page.getByRole("button", { name: /Voltar/ }).click();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    const cost = page.getByRole("button", { name: /Custo deste turno.*Débito liquidado: 1,25 Estilhas/ });
    await expect(cost).toBeVisible();
    await cost.focus();
    await expect(page.getByText(/Débito liquidado: 1,25 Estilhas/).first()).toBeVisible();
    await cost.press("Enter");
    await expect(cost).toHaveAttribute("aria-expanded", "true");
    await cost.click();
    await expect(cost).toHaveAttribute("aria-expanded", "false");
    await page.getByPlaceholder(/O que você faz/).fill("Examino o sino");
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(page.getByRole("button", { name: /Estimativa de custo técnico: US\$ 0,000041550/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("SPEC-185 fallback updates technical cost after classic action", async ({ page, backend }) => {
  backend.allowFailure(/\/game\/action\/stream$/);
  backend.allowConsole(/ERR_FAILED/);
  await page.route("https://fonts.googleapis.com/**", route =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("**/account/**", route => route.fulfill({ status: 200,
    contentType: "application/json", body: JSON.stringify({ available_milli: "0", reserved_milli: "0" }) }));
  await page.route("**/game/*/operations/*/cost", route => route.fulfill({ status: 200,
    contentType: "application/json", body: JSON.stringify({ history_id: "fallback-entry",
      cost_milli: null, technical_cost_usd: "0.000000042",
      technical_cost_basis: "usage_ledger", technical_cost_exact: false }) }));
  await page.route("**/game/action/stream", route => route.abort("failed"));
  await page.goto("/");
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByPlaceholder(/O que você faz/).fill("Abro a porta");
  await page.getByRole("button", { name: "Agir" }).click();
  await expect(page.getByText("O mundo responde a: Abro a porta")).toBeVisible();
  await expect(page.getByRole("button", { name: /Estimativa de custo técnico: US\$ 0,000000042/ })).toBeVisible();
});

test("SPEC-185 large balance stays exact and owner switch drops delayed cost", async ({ page, backend }) => {
  backend.userId = "owner-a";
  await page.route("https://fonts.googleapis.com/**", route =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route("**/account/**", route => route.fulfill({ status: 200,
    contentType: "application/json", body: JSON.stringify({
      available_milli: backend.userId === "owner-a" ? "9007199254740993" : "1500",
      reserved_milli: "0", points: [], totals: { game: "0", image: "0", voice: "0" },
      items: [], next_cursor: null,
    }) }));
  let releaseCost!: () => void;
  const costGate = new Promise<void>(resolve => { releaseCost = resolve; });
  await page.route("**/game/*/operations/*/cost", async route => {
    await costGate;
    return route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ history_id: "owner-a-entry", cost_milli: "1000",
        technical_cost_usd: "0.000000100", technical_cost_exact: true }) });
  });
  await page.goto("/");
  await expect(page.getByRole("button", { name: /9\.007\.199\.254\.740,993 Estilhas/ })).toBeVisible();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByPlaceholder(/O que você faz/).fill("Escuto a praça");
  await page.getByRole("button", { name: "Agir" }).click();
  await expect(page.getByText("O mundo responde a: Escuto a praça")).toBeVisible();
  await page.getByRole("button", { name: "Encerrar sessão" }).click();
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  backend.userId = "owner-b";
  await page.getByLabel("E-mail").fill("b@example.test");
  await page.getByLabel("Senha").fill("segredo-123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("button", { name: /Conta · 1,5 Estilhas/ })).toBeVisible();
  releaseCost();
  await page.getByRole("button", { name: /^Breno/ }).click();
  await expect(page.getByText("Breno observa Brumalta.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Custo deste turno/ })).toHaveCount(0);
});
