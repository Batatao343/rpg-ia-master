// SPEC-320: espera do turno (linha de status, escalonamento no tempo, retry sem duplicar),
// typewriter pulável, banner persistente e a fiação do contrato SSE da SPEC-316 (§3.1).
// A fixture padrão entrega o SSE inteiro de uma vez; os casos "316" trocam o `fetch` do stream por um
// ReadableStream controlado pelo teste (ack, fases, chunks, done, replace, state, erro com narrative_shown).
import AxeBuilder from "@axe-core/playwright";
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
const live = (page: Page) => page.locator(".ws-composer > .sr-only[role=status]");
const pendingBtn = (page: Page) => page.locator('[data-effect="chat.pending"]');
const streams = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action/stream");
const posts = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action");

async function a11y(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, `${label}: ` + blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

// ---- SSE controlado (SPEC-316 §3.1) ---------------------------------------------------------------
type SseWindow = Window & { __sseReqs: Array<Record<string, unknown>>; __sse: { push(t: string): void; close(): void } };

/** Chamar ANTES do `goto`: troca o fetch de `/game/action/stream` por um stream que o teste empurra. */
async function installControlledSse(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as SseWindow;
    w.__sseReqs = [];
    const orig = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
      if (!url.includes("/game/action/stream")) return orig(input, init);
      w.__sseReqs.push(JSON.parse(String(init?.body ?? "{}")));
      const enc = new TextEncoder();
      let ctrl!: ReadableStreamDefaultController<Uint8Array>;
      const body = new ReadableStream<Uint8Array>({ start(c) { ctrl = c; } });
      w.__sse = { push: (t: string) => ctrl.enqueue(enc.encode(t)), close: () => ctrl.close() };
      return Promise.resolve(new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    };
  });
}
const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
const push = (page: Page, text: string) => page.evaluate((t) => (window as unknown as SseWindow).__sse.push(t), text);
const closeSse = (page: Page) => page.evaluate(() => (window as unknown as SseWindow).__sse.close());
const sseReqs = (page: Page) => page.evaluate(() => (window as unknown as SseWindow).__sseReqs);
async function waitSseReqs(page: Page, n: number) {
  await expect.poll(async () => (await sseReqs(page)).length).toBe(n);
}
/** `state` final: o estado atual do jogo com a narração final (como o api.py). */
async function finalState(page: Page, message: string) {
  const state = await page.evaluate(async () => (await fetch("/game/state?game_id=game-a")).json());
  return { ...state, message, message_type: "STORY" };
}

for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  test.describe(`espera do turno @${width}x${height}`, () => {
    test.use({ viewport: { width, height } });

    test("a linha de status vive no compositor, tem uma região viva única e acumula a fase", async ({ page, backend }) => {
      await openGame(page);
      backend.delayStream();
      await page.locator(".story").evaluate((el) => { el.scrollTop = 0; }); // log rolado para o topo
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await expect(status(page)).toBeInViewport();
      await expect(status(page)).toContainText("O mestre consulta os arcanos");
      await expect(live(page)).toHaveCount(1);
      await expect(status(page).locator("[aria-live], [role=status]")).toHaveCount(0); // ledger/botões fora da região viva
      await expect(page.locator(".thinking, .thinking__dot")).toHaveCount(0);
      await expect(page.locator(".log .turn-status")).toHaveCount(0);
      await a11y(page, "espera do turno");
      backend.releaseStream();
      await expect(status(page)).toHaveCount(0); // vazio: nada no fluxo, sem gap (P2-10)
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
      await expect(composer(page)).toBeFocused(); // o botão sumiu: o foco volta ao input (P2-5)
      expect(streams(backend)).toHaveLength(1); // o retry consulta a operação; não cria um 2º envio
      expect(posts(backend)).toHaveLength(0);
      backend.releaseStream();
    });

    test("Espaço com o foco na história revela a narração", async ({ page }) => {
      await openGame(page);
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await expect(page.locator(".story article.msg--story").last()).toBeVisible();
      await page.locator(".story").focus();
      await page.keyboard.press("Space");
      await expect(page.locator(".msg__cursor")).toHaveCount(0, { timeout: 1000 });
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

    test("combate: o botão primário se chama 'Lutar' (nome acessível = texto visível)", async ({ page, backend }) => {
      const state = backend.states.get("game-a")!;
      state.combat.active = true; state.combat.round = 1;
      await openGame(page);
      await expect(page.getByRole("button", { name: "Lutar", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Agir", exact: true })).toHaveCount(0);
    });

    // ---------------- SPEC-316 §3.1 (RPG_EARLY_NARRATIVE=on) ----------------
    test("316: ack, fases, 'registrando…' com envio travado até o state, e replace troca o texto inteiro", async ({ page }) => {
      await installControlledSse(page);
      await openGame(page);
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await waitSseReqs(page, 1);
      await push(page, ": ack\n\n");
      await expect(pendingBtn(page)).toHaveText("Aguardando o narrador"); // R4: depois do ack
      await expect(pendingBtn(page)).toHaveAttribute("aria-busy", "true");
      await push(page, ev("accepted", { action_id: "x" }) + ev("phase", { node: "campaign_manager", status: "done" })
        + ev("phase", { node: "dm_router", status: "done" }) + ev("route", { route: "storyteller" }));
      await expect(status(page)).toContainText("O mestre decide o rumo");
      await push(page, ev("narrative", { chunk: "A névoa sobe ", done: false }) + ev("narrative", { chunk: "do porto.", done: false }));
      await expect(page.locator(".story article.msg--story").last()).toContainText("A névoa");
      await push(page, ev("narrative", { chunk: "", done: true }));
      await expect(status(page)).toContainText("registrando…");
      await expect(live(page)).toHaveText("registrando…");
      await expect(pendingBtn(page)).toBeDisabled(); // envio travado até o state
      await a11y(page, "registrando");
      await push(page, ev("phase", { node: "archivist", status: "done" })
        + ev("narrative", { chunk: "O nevoeiro cobre o cais.", done: true, replace: true }));
      // replace: o texto inteiro é trocado (nunca anexado) e revelado direto, sem redigitar do zero
      const last = page.locator(".story article.msg--story").last();
      await expect(last).toHaveText("O nevoeiro cobre o cais.", { timeout: 800 });
      await expect(pendingBtn(page)).toBeDisabled();
      await push(page, ev("state", await finalState(page, "O nevoeiro cobre o cais.")));
      await closeSse(page);
      await expect(pendingBtn(page)).toBeEnabled();
      await expect(pendingBtn(page)).toHaveText("Agir");
      await expect(page.locator(".story article.msg--story", { hasText: "A névoa" })).toHaveCount(0);
    });

    test("316: erro com narrative_shown mantém o texto 'não salvo' e o retry reenvia o MESMO action_id", async ({ page, backend }) => {
      backend.allowFailure(/\/game\/action/);
      backend.allowConsole(/.*/);
      await installControlledSse(page);
      await openGame(page);
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await waitSseReqs(page, 1);
      await push(page, ": ack\n\n" + ev("narrative", { chunk: "A névoa sobe do porto.", done: false })
        + ev("narrative", { chunk: "", done: true })
        + ev("error", { detail: "commit falhou", code: 500, error_code: "commit_failed", request_id: "e2e-req-0001", narrative_shown: true }));
      await closeSse(page);
      const unsaved = page.locator(".story .msg__unsaved");
      await expect(unsaved).toHaveText("não salvo");
      await expect(page.locator(".story article.msg--story").last()).toContainText("A névoa sobe do porto.");
      await expect(live(page)).toContainText("Não salvo");
      expect(posts(backend)).toHaveLength(0); // sem fallback POST automático
      const first = (await sseReqs(page))[0];
      await status(page).getByRole("button", { name: "Tentar de novo" }).click();
      await waitSseReqs(page, 2); // exatamente UM envio a mais
      const second = (await sseReqs(page))[1];
      expect(second.action_id).toBeTruthy();
      expect(second.action_id).toBe(first.action_id);
      await push(page, ": ack\n\n" + ev("narrative", { chunk: "A névoa sobe do porto.", done: false })
        + ev("narrative", { chunk: "", done: true }) + ev("state", await finalState(page, "A névoa sobe do porto.")));
      await closeSse(page);
      await expect(unsaved).toHaveCount(0);
      await expect(pendingBtn(page)).toBeEnabled();
      expect(await sseReqs(page)).toHaveLength(2);
      expect(posts(backend)).toHaveLength(0);
    });

    test("316: stream pendurado aos 25 s — 'Tentar de novo' abandona o SSE e repete o mesmo action_id; aviso some em 9 s", async ({ page }) => {
      await installControlledSse(page);
      await openGame(page);
      await page.clock.install();
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await waitSseReqs(page, 1);
      await push(page, ": ack\n\n" + ev("phase", { node: "campaign_manager", status: "done" }));
      await page.clock.fastForward(25_000);
      await status(page).getByRole("button", { name: "Tentar de novo" }).click();
      await waitSseReqs(page, 2);
      const [a, b] = await sseReqs(page);
      expect(b.action_id).toBe(a.action_id);
      const warn = page.locator(".banner[role=status]");
      await expect(warn).toContainText("reenviando");
      await page.clock.fastForward(9_500);
      await expect(warn).toHaveCount(0);
    });
  });
}
