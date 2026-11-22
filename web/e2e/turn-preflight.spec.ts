// SPEC-420: envio novo não consulta /operations/{op}; pending existente consulta uma vez; eco único.
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";

test.beforeEach(async ({ backend }) => {
  backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
  backend.allowFailure(/\/game\/action(?:\/stream)?$/);
  backend.allowConsole(/.*/);
});

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const streams = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action/stream");
const opQueries = (b: DeterministicBackend) => b.requests.filter((r) => /^\/game\/[^/]+\/operations\/[^/]+$/.test(r.path));
const echoes = (page: Page, text: string) => page.locator("article.msg--player", { hasText: text });
const pendingId = (page: Page) => page.evaluate(() => {
  const k = Object.keys(localStorage).find((key) => key.startsWith("valoria:pending"));
  return k ? (JSON.parse(localStorage.getItem(k)!) as { operation_id: string }).operation_id : null;
});
const OP_ROUTE = /\/game\/[^/]+\/operations\/[^/]+$/;
// A rota roteada pelo teste não chega ao fake: conta aqui as consultas que ela atendeu.
async function missing(page: Page) {
  const seen = { count: 0 };
  await page.route(OP_ROUTE, (route) => {
    seen.count += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "missing", response: null }) });
  });
  return seen;
}

async function send(page: Page, text: string) {
  await composer(page).fill(text);
  await composer(page).press("Enter");
}

test("envio novo: 0 consultas e mesmo operation_id", async ({ page, backend }) => {
  await openGame(page);
  backend.delayStream();
  await send(page, "Examino o portão");
  await expect.poll(() => streams(backend).length).toBe(1);
  const id = await pendingId(page);
  expect(id).toBeTruthy();
  expect(streams(backend)[0].body?.action_id).toBe(id);
  backend.releaseStream();
  await expect(page.getByText("O mundo responde a: Examino o portão").first()).toBeVisible();
  expect(opQueries(backend)).toHaveLength(0);
  expect(streams(backend)).toHaveLength(1);
});

test("eco antes de qualquer rede: aparece com a consulta pendurada", async ({ page, backend }) => {
  await openGame(page);
  await page.route(OP_ROUTE, () => { /* nunca responde */ });
  backend.delayStream();
  await send(page, "Observo a praça");
  await expect(echoes(page, "Observo a praça")).toHaveCount(1);
  await expect.poll(() => streams(backend).length).toBe(1);
  backend.releaseStream();
  await expect(page.getByText("O mundo responde a: Observo a praça")).toHaveCount(1);
});

test("pending existente consulta uma vez", async ({ page, backend }) => {
  await openGame(page);
  backend.failNextTurn = true;
  await send(page, "Investigo a ponte");
  await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
  const failedId = streams(backend)[0].body?.action_id;
  const streamsBefore = streams(backend).length;
  const routed = await missing(page);
  await page.getByRole("button", { name: "Consultar / retomar ação pendente" }).click();
  await expect.poll(() => streams(backend).length).toBe(streamsBefore + 1);
  expect(routed.count).toBe(1);
  expect(streams(backend)[streamsBefore].body?.action_id).toBe(failedId);
});

test("eco único após falha e retomada", async ({ page, backend }) => {
  await openGame(page);
  backend.failNextTurn = true;
  await send(page, "Investigo a ponte");
  await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
  await expect(echoes(page, "Investigo a ponte")).toHaveCount(0);
  expect(await pendingId(page)).toBeTruthy();
  await missing(page);
  await page.getByRole("button", { name: "Consultar / retomar ação pendente" }).click();
  await expect(page.getByText("O mundo responde a: Investigo a ponte").first()).toBeVisible();
  await expect(echoes(page, "Investigo a ponte")).toHaveCount(1);
  await expect(page.getByText("O mundo responde a: Investigo a ponte")).toHaveCount(1);
});
