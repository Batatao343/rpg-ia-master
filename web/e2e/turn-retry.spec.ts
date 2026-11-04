// SPEC-383 Etapa 1: caracterização do turno (guarda de corrida de handleAction / retryTurnInner).
// Estes casos fixam o comportamento ATUAL antes de mover o código para hooks; nenhum deles muda asserção
// de outro spec. O "em voo" é feito com `backend.delayStream()` (o SSE do fake responde inteiro de uma vez).
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";

test.beforeEach(async ({ backend }) => {
  backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
  backend.allowConsole(/ERR_CONNECTION_CLOSED|Failed to load resource/);
});

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const status = (page: Page) => page.locator(".ws-composer .turn-status");
const streams = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action/stream");
const posts = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action");
const hasPending = (page: Page) =>
  page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith("valoria:pending")));

async function send(page: Page, text: string) {
  await composer(page).fill(text);
  await composer(page).press("Enter");
}

test.describe("turno em voo: guarda de corrida e retry", () => {
  test("401 no meio do turno: vai para a tela de login e a resposta tardia é ignorada", async ({ page, backend }) => {
    backend.delayStream();
    await openGame(page);
    await send(page, "Ação lenta de Ayla");
    await expect.poll(() => streams(backend).length).toBe(1);
    backend.authenticated = false;
    await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
    await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
    backend.releaseStream();
    await page.waitForTimeout(300);
    await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
    await expect(page.getByText("O mundo responde a: Ação lenta de Ayla")).toHaveCount(0);
    expect(streams(backend)).toHaveLength(1);
    expect(posts(backend)).toHaveLength(0);
  });

  test("Nova jornada e Sair ficam travados enquanto o turno voa; a resposta chega uma vez", async ({ page, backend }) => {
    backend.delayStream();
    await openGame(page);
    await send(page, "Ação lenta de Ayla");
    await expect.poll(() => streams(backend).length).toBe(1);
    await expect(page.getByRole("button", { name: "Nova jornada" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Encerrar sessão" })).toBeDisabled();
    backend.releaseStream();
    await expect(page.getByText("O mundo responde a: Ação lenta de Ayla").first()).toBeVisible();
    await expect(page.getByText("O mundo responde a: Ação lenta de Ayla")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Nova jornada" })).toBeEnabled();
    expect(streams(backend)).toHaveLength(1);
    expect(posts(backend)).toHaveLength(0);
  });

  test("Tentar de novo com a operação 'running': só avisa, não reenvia e mantém o pending", async ({ page, backend }) => {
    await openGame(page);
    await page.clock.install();
    backend.delayStream();
    await send(page, "olho ao redor");
    await expect(status(page)).toContainText("O mestre consulta os arcanos");
    const opRoute = /\/game\/[^/]+\/operations\/[^/]+$/;
    await page.route(opRoute, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "running", response: null }) }));
    await page.clock.fastForward(25_000);
    await status(page).getByRole("button", { name: "Tentar de novo" }).click();
    await expect(page.locator(".banner")).toContainText("O turno ainda está em andamento no servidor");
    expect(streams(backend)).toHaveLength(1);
    expect(posts(backend)).toHaveLength(0);
    expect(await hasPending(page)).toBe(true);
    await page.unroute(opRoute);
    backend.releaseStream();
    await expect(page.getByText("O mundo responde a: olho ao redor").first()).toBeVisible();
    expect(await hasPending(page)).toBe(false);
  });

  test("Tentar de novo com a operação 'unknown': abandona o SSE velho e reenvia o MESMO action_id", async ({ page, backend }) => {
    await openGame(page);
    await page.clock.install();
    backend.delayStream();
    await send(page, "olho ao redor");
    await expect(status(page)).toContainText("O mestre consulta os arcanos");
    const opRoute = /\/game\/[^/]+\/operations\/[^/]+$/;
    await page.route(opRoute, (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "unknown", response: null }) }));
    await page.clock.fastForward(25_000);
    await status(page).getByRole("button", { name: "Tentar de novo" }).click();
    await expect.poll(() => streams(backend).length).toBe(2);
    await page.unroute(opRoute);
    const [first, second] = streams(backend);
    expect(second.body?.action_id).toBeTruthy();
    expect(second.body?.action_id).toBe(first.body?.action_id);
    await expect(page.locator(".banner")).toContainText("reenviando a mesma ação");
    backend.releaseStream();
    await expect(page.getByText("O mundo responde a: olho ao redor").first()).toBeVisible();
    await expect(page.getByText("O mundo responde a: olho ao redor")).toHaveCount(1);
    expect(posts(backend)).toHaveLength(0);
    expect(await hasPending(page)).toBe(false);
  });

  test("duplo clique em 'Consultar / retomar ação pendente' envia uma única vez", async ({ page, backend }) => {
    backend.allowFailure(/\/game\/action(?:\/stream)?$/);
    backend.allowConsole(/.*/);
    await openGame(page);
    backend.failNextTurn = true;
    await send(page, "Investigo a ponte partida");
    await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
    expect(await hasPending(page)).toBe(true);
    const streamsBefore = streams(backend).length;
    const postsBefore = posts(backend).length;
    backend.delayStream();
    const opRoute = /\/game\/[^/]+\/operations\/[^/]+$/;
    await page.route(opRoute, async (route) => { // consulta lenta: o 2º clique cai com `busy` ligado
      await new Promise((resolve) => setTimeout(resolve, 400));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "missing", response: null }) });
    });
    const resume = page.getByRole("button", { name: "Consultar / retomar ação pendente" });
    await resume.dblclick();
    await expect.poll(() => streams(backend).length).toBe(streamsBefore + 1);
    await page.waitForTimeout(300);
    expect(streams(backend)).toHaveLength(streamsBefore + 1);
    backend.releaseStream();
    await expect(page.getByText("O mundo responde a: Investigo a ponte partida").first()).toBeVisible();
    await expect(page.getByText("O mundo responde a: Investigo a ponte partida")).toHaveCount(1);
    expect(posts(backend)).toHaveLength(postsBefore);
    expect(await hasPending(page)).toBe(false);
  });

  test("stream que cai antes da narração: o POST de fallback entrega a resposta uma vez", async ({ page, backend }) => {
    backend.allowFailure(/\/game\/action(?:\/stream)?$/);
    backend.allowConsole(/.*/);
    await openGame(page);
    await page.route("**/game/action/stream", (route) => route.abort("failed"));
    await send(page, "Sigo para o cais");
    await expect(page.getByText("O mundo responde a: Sigo para o cais").first()).toBeVisible();
    await expect(page.getByText("O mundo responde a: Sigo para o cais")).toHaveCount(1);
    expect(posts(backend)).toHaveLength(1);
    expect(await hasPending(page)).toBe(false);
    await page.unroute("**/game/action/stream");
  });

  test("recusa 4xx definitiva (invalid_target) descarta o pending e libera o compositor", async ({ page, backend }) => {
    backend.allowFailure(/\/game\/action(?:\/stream)?$/);
    backend.allowConsole(/.*/);
    await openGame(page);
    await page.route(/\/game\/action\/stream$/, (route) =>
      route.fulfill({ status: 200, contentType: "text/event-stream",
        body: `event: error\ndata: ${JSON.stringify({ detail: "alvo inválido", code: 409, error_code: "invalid_target" })}\n\n` }));
    await send(page, "Ataco o alvo velho");
    await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
    await expect(page.getByText(/A ação pendente foi descartada/)).toBeVisible();
    expect(await hasPending(page)).toBe(false);
    await expect(page.getByRole("button", { name: "Descartar ação pendente" })).toHaveCount(0);
    await expect(composer(page)).toBeEnabled();
    expect(posts(backend)).toHaveLength(0);
  });
});
