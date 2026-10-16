import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-235 R2: a pending action is always resolvable (definitive 409 clears it;
// the composer always offers "Descartar ação pendente").

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

async function submitAction(page: Page, text: string) {
  await page.getByPlaceholder(/O que você faz/).fill(text);
  await page.getByRole("button", { name: "Agir" }).click();
}

const hasPending = (page: Page) =>
  page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith("valoria:pending")));

async function failOneTurn(page: Page, backend: { failNextTurn: boolean; allowFailure(p: RegExp): void; allowConsole(p: RegExp): void }) {
  backend.failNextTurn = true;
  backend.allowFailure(/\/game\/action(?:\/stream)?$/);
  backend.allowConsole(/Failed to load resource/);
  await submitAction(page, "Investigo a ponte partida");
  await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
  expect(await hasPending(page)).toBe(true);
}

for (const width of [390, 1440]) {
  test(`SPEC-235 discard pending button @${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await openGame(page);
    await failOneTurn(page, backend);
    const discard = page.getByRole("button", { name: "Descartar ação pendente" });
    await expect(discard).toBeVisible();
    await expect(page.getByRole("button", { name: "Consultar / retomar ação pendente" })).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.filter((v) => v.impact === "critical" || v.impact === "serious")
      .map((v) => v.id)).toEqual([]);
    // Evidence capture is opt-in so CI runs never write into docs/.
    if (process.env.RPG_SPEC235_SHOTS) await page.screenshot({ path: `../docs/spec235/discard-pending-${width}.png` });
    await discard.click();
    await expect(discard).toHaveCount(0);
    expect(await hasPending(page)).toBe(false);
    await submitAction(page, "Sigo para o cais");
    await expect(page.getByText("O mundo responde a: Sigo para o cais").first()).toBeVisible();
  });
}

test("SPEC-235 definitive 409 releases the pending action", async ({ page, backend }) => {
  await openGame(page);
  await failOneTurn(page, backend);
  backend.allowConsole(/409/);
  const conflict = async (route: import("@playwright/test").Route) =>
    route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "operation_conflict" }) });
  await page.route(/\/game\/[^/]+\/operations\/[^/]+$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "missing", response: null }) }));
  await page.route(/\/game\/action(\/stream)?$/, conflict);
  await page.getByRole("button", { name: "Consultar / retomar ação pendente" }).click();
  await expect(page.getByText(/A ação pendente foi descartada/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Descartar ação pendente" })).toHaveCount(0);
  expect(await hasPending(page)).toBe(false);
  await page.unroute(/\/game\/action(\/stream)?$/, conflict);
  await page.unrouteAll({ behavior: "ignoreErrors" }).catch(() => undefined);
  await backend.install(page);
  const input = page.getByPlaceholder(/O que você faz/);
  await expect(input).toBeEnabled();
  await submitAction(page, "Sigo para o cais");
  await expect(page.getByText("O mundo responde a: Sigo para o cais").first()).toBeVisible();
});
