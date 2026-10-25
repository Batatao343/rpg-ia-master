// SPEC-320: espera do turno (linha de status, escalonamento no tempo, retry sem duplicar),
// typewriter pulável e banner persistente. Roda com a fixture determinística (SSE entregue de uma vez).
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

for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  test.describe(`espera do turno @${width}x${height}`, () => {
    test.use({ viewport: { width, height } });

    test("a linha de status vive no compositor, é uma região status única e acumula a fase", async ({ page, backend }) => {
      await openGame(page);
      backend.delayStream();
      await page.locator(".story").evaluate((el) => { el.scrollTop = 0; }); // log rolado para o topo
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await expect(status(page)).toBeInViewport();
      await expect(status(page)).toContainText("O mestre consulta os arcanos");
      await expect(status(page)).toHaveAttribute("role", "status");
      await expect(page.locator(".thinking, .thinking__dot")).toHaveCount(0);
      // a fase não é anunciada por um segundo aria-live dentro do log
      await expect(page.locator(".story .turn-status, .log .turn-status")).toHaveCount(0);
      backend.releaseStream();
      await expect(status(page).locator(".turn-status__ledger")).toHaveCount(0);
    });

    test("tranquilização aos 8 s; aos 25 s 'Tentar de novo' recupera sem novo envio", async ({ page, backend }) => {
      await openGame(page);
      await page.clock.install();
      backend.delayStream();
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await expect(status(page)).toContainText("O mestre consulta os arcanos");
      await page.clock.fastForward(8_000);
      await expect(status(page)).toContainText("A noite é longa");
      await expect(status(page).getByRole("button", { name: "Tentar de novo" })).toHaveCount(0);
      await page.clock.fastForward(17_000);
      await expect(status(page).getByRole("button", { name: "Continuar esperando" })).toBeVisible();
      await status(page).getByRole("button", { name: "Tentar de novo" }).click();
      await expect(page.getByRole("button", { name: "Agir" })).toBeEnabled();
      expect(streams(backend)).toHaveLength(1); // o retry consulta a operação; não cria um 2º envio
      backend.releaseStream();
    });

    test("tocar na narração em revelação mostra o texto inteiro", async ({ page }) => {
      await openGame(page);
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      const last = page.locator(".story article.msg--story").last();
      await expect(last).toBeVisible();
      await last.click();
      await expect(page.locator(".msg__cursor")).toHaveCount(0, { timeout: 1000 });
    });

    test("erro de turno persiste além de 30 s, fica na linha de status e fecha pelo ✕", async ({ page, backend }) => {
      backend.allowFailure(/\/game\/action/);
      backend.allowConsole(/.*/);
      await openGame(page);
      backend.failNextTurn = true;
      await composer(page).fill("examino a porta");
      await composer(page).press("Enter");
      const banner = page.locator(".banner[role=alert]");
      await expect(banner).toBeVisible();
      await expect(status(page)).toContainText("Ação não confirmada");
      await page.clock.install();
      await page.clock.fastForward(30_000);
      await expect(banner).toBeVisible();
      const topbar = await page.locator(".topbar").boundingBox();
      const box = await banner.boundingBox();
      expect(box!.y).toBeGreaterThanOrEqual(topbar!.y + topbar!.height - 1); // no fluxo, abaixo da topbar
      const close = banner.getByRole("button", { name: "Fechar aviso" });
      const closeBox = await close.boundingBox();
      expect(closeBox!.width).toBeGreaterThanOrEqual(44);
      expect(closeBox!.height).toBeGreaterThanOrEqual(44);
      await close.click();
      await expect(banner).toHaveCount(0);
    });
  });
}
