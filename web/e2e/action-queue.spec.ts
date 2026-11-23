// SPEC-427: fila de uma ação (RPG_ACTION_QUEUE=on). O Enter em "registrando…" guarda a ação e o envio só acontece
// DEPOIS do `state` do turno anterior, pelo mesmo `handleAction`. Cada caso de devolução ao rascunho tem teste próprio.
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";
import { installControlledSse, ev, push, closeSse, sseReqs, waitSseReqs, finalState } from "./sseControl";

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
const live = (page: Page) => page.locator(".ws-composer > .sr-only[aria-live]");
const pendingBtn = (page: Page) => page.locator('[data-effect="chat.pending"]');
const chip = (page: Page) => page.locator(".queued-action");
const hint = (page: Page) => page.locator(".ws-composer .composer-hint");
const posts = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action");
const echoes = (page: Page, text: string) => page.locator(".story article.msg--player", { hasText: text });
const NARRATION = ": ack\n\n" + ev("narrative", { chunk: "A névoa sobe do porto.", done: false }) + ev("narrative", { chunk: "", done: true });

/** Turno 1 em voo com a narração entregue e o `state` ainda segurado ("registrando…"). */
async function toNarrated(page: Page) {
  await composer(page).fill("olho ao redor");
  await composer(page).press("Enter");
  await waitSseReqs(page, 1);
  await push(page, NARRATION);
  await expect(live(page)).toContainText("registrando…");
}

/** `toNarrated` + a ação "olho o céu" na fila. */
async function toQueued(page: Page, text = "olho o céu") {
  await toNarrated(page);
  await composer(page).fill(text);
  await composer(page).press("Enter");
  await expect(chip(page)).toBeVisible();
}

/** `state` do turno (com `patch` opcional sobre o estado final) + fim do stream. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Patch = (s: Record<string, any>) => Record<string, any>;
const closeTurn = async (page: Page, message = "A névoa sobe do porto.", patch: Patch = (s) => s) => {
  await push(page, ev("state", patch(await finalState(page, message))));
  await closeSse(page);
};

const QUEUED = "olho o céu";
const sentQueued = async (page: Page, backend: DeterministicBackend) =>
  (await sseReqs(page)).filter((r) => r.input_text === QUEUED).length
  + posts(backend).filter((r) => r.body?.input_text === QUEUED).length;

/** Devolução ao rascunho (R10): chip fora, texto no campo, nota visível, anúncio, 0 eco e 0 envio da fila. */
async function expectReturned(page: Page, backend: DeterministicBackend, reason: string, sseCount = 1) {
  await expect(chip(page)).toHaveCount(0);
  await expect(page.locator("#composer")).toHaveValue(QUEUED); // no celular o combate esconde o compositor; o texto está lá
  await expect(hint(page)).toContainText(reason);
  await expect(live(page)).toContainText(`A ação na fila não foi enviada: ${reason}`);
  await expect(echoes(page, QUEUED)).toHaveCount(0);
  expect(await sseReqs(page)).toHaveLength(sseCount);
  expect(await sentQueued(page, backend)).toBe(0);
}

async function a11y(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, `${label}: ` + blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

async function relogin(page: Page, backend: DeterministicBackend, name = "Ayla") {
  backend.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  await page.getByLabel("E-mail").fill("ayla@example.test");
  await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

for (const [width, height] of [[1440, 900], [390, 844]] as const) {
  test.describe(`fila de uma ação @${width}x${height}`, () => {
    test.use({ viewport: { width, height } });

    test("fila: nada sai antes do state; 1 envio depois", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toNarrated(page);
      await expect(pendingBtn(page)).toBeEnabled();
      await expect(pendingBtn(page)).toHaveText("Pôr na fila");
      await composer(page).fill("olho o céu");
      await composer(page).press("Enter");
      await expect(chip(page)).toContainText("Na fila: olho o céu");
      await expect(composer(page)).toHaveValue("");
      expect(await sseReqs(page)).toHaveLength(1);
      expect(posts(backend)).toHaveLength(0);
      await expect(echoes(page, "olho o céu")).toHaveCount(0);
      await closeTurn(page);
      await waitSseReqs(page, 2);
      expect((await sseReqs(page))[1].input_text).toBe("olho o céu");
      await expect(chip(page)).toHaveCount(0);
      await expect(echoes(page, "olho o céu")).toHaveCount(1);
      await push(page, NARRATION);
      await closeTurn(page);
      await expect(pendingBtn(page)).toBeEnabled();
      await expect(pendingBtn(page)).toHaveText("Agir");
      expect(await sseReqs(page)).toHaveLength(2);
      expect(posts(backend)).toHaveLength(0);
      await expect(composer(page)).toHaveValue("");
      await expect(chip(page)).toHaveCount(0);
      await expect(echoes(page, "olho o céu")).toHaveCount(1);
    });

    test("fila desligada: Enter ignorado como hoje", async ({ page, backend }) => {
      backend.actionQueue = false;
      await installControlledSse(page);
      await openGame(page);
      await toNarrated(page);
      await expect(pendingBtn(page)).toBeDisabled();
      await expect(pendingBtn(page)).toHaveText("Aguardando o narrador");
      await composer(page).fill("olho o céu");
      await composer(page).press("Enter");
      await expect(chip(page)).toHaveCount(0);
      await expect(composer(page)).toHaveValue("olho o céu");
      await expect(live(page)).toHaveText("registrando…");
      await closeTurn(page);
      await expect(pendingBtn(page)).toBeEnabled();
      expect(await sseReqs(page)).toHaveLength(1);
    });
    test("fila: action_id novo e 0 consultas", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await closeTurn(page);
      await waitSseReqs(page, 2);
      const [first, second] = await sseReqs(page);
      expect(second.action_id).toBeTruthy();
      expect(second.action_id).not.toBe(first.action_id);
      const pendingId = await page.evaluate(() => {
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i)!;
          if (k.startsWith("valoria:pending:v1:")) return JSON.parse(localStorage.getItem(k)!).operation_id as string;
        }
        return null;
      });
      expect(pendingId).toBe(second.action_id);
      await push(page, NARRATION);
      await closeTurn(page);
      await expect(pendingBtn(page)).toHaveText("Agir");
      expect(backend.requests.filter((r) => /^\/game\/[^/]+\/operations\/[^/]+$/.test(r.path))).toHaveLength(0);
      expect(await sseReqs(page)).toHaveLength(2);
    });

    test("fila: segundo Enter substitui", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page, "primeira");
      await composer(page).fill("segunda");
      await composer(page).press("Enter");
      await expect(chip(page)).toContainText("Na fila: segunda");
      await expect(chip(page)).not.toContainText("primeira");
      await expect(live(page)).toContainText("Ação na fila substituída.");
      await composer(page).press("Enter"); // campo vazio: não faz nada
      await expect(chip(page)).toContainText("segunda");
      await closeTurn(page);
      await waitSseReqs(page, 2);
      expect((await sseReqs(page))[1].input_text).toBe("segunda");
      await push(page, NARRATION);
      await closeTurn(page);
      await expect(pendingBtn(page)).toHaveText("Agir");
      expect(await sseReqs(page)).toHaveLength(2);
    });

    for (const how of ["clique", "teclado"] as const) {
      test(`fila: tirar da fila devolve sem enviar (${how})`, async ({ page, backend }) => {
        backend.actionQueue = true;
        await installControlledSse(page);
        await openGame(page);
        await toQueued(page);
        const remove = page.getByRole("button", { name: "Tirar da fila" });
        if (how === "clique") await remove.click();
        else { await page.keyboard.press("Shift+Tab"); await expect(remove).toBeFocused(); await page.keyboard.press("Enter"); }
        await expect(chip(page)).toHaveCount(0);
        await expect(composer(page)).toHaveValue(QUEUED);
        await expect(composer(page)).toBeFocused();
        await expect(live(page)).toContainText("Ação tirada da fila; o texto voltou ao campo.");
        await closeTurn(page);
        await expect(pendingBtn(page)).toHaveText("Agir");
        expect(await sseReqs(page)).toHaveLength(1);
        expect(posts(backend)).toHaveLength(0);
        await expect(echoes(page, QUEUED)).toHaveCount(0);
      });
    }

    for (const value of ["true", 1, "on", "1"] as const) {
      test(`fila: action_queue=${JSON.stringify(value)} no /auth/config não liga (só o booleano true)`, async ({ page, backend }) => {
        backend.actionQueue = value;
        await installControlledSse(page);
        await openGame(page);
        await toNarrated(page);
        await expect(pendingBtn(page)).toBeDisabled();
        await expect(pendingBtn(page)).toHaveText("Aguardando o narrador");
        await composer(page).fill(QUEUED);
        await composer(page).press("Enter");
        await expect(chip(page)).toHaveCount(0);
        await expect(composer(page)).toHaveValue(QUEUED);
        await closeTurn(page);
        await expect(pendingBtn(page)).toBeEnabled();
        expect(await sseReqs(page)).toHaveLength(1);
      });
    }

    test("fila: Enter em waiting é ignorado como hoje", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      await waitSseReqs(page, 1);
      await push(page, ": ack\n\n");
      await expect(pendingBtn(page)).toHaveText("Aguardando o narrador");
      await composer(page).fill(QUEUED);
      await composer(page).press("Enter");
      await expect(chip(page)).toHaveCount(0);
      await expect(composer(page)).toHaveValue(QUEUED);
    });

    test("fila: acessibilidade (axe, região viva única, alvo de toque, anúncio)", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await expect(live(page)).toHaveCount(1);
      await expect(live(page)).toContainText("Ação na fila: será enviada quando o turno for registrado.");
      await expect(chip(page)).toHaveAttribute("aria-label", `Ação na fila: ${QUEUED}`);
      const box = await page.getByRole("button", { name: "Tirar da fila" }).boundingBox();
      expect(box!.width).toBeGreaterThanOrEqual(44);
      expect(box!.height).toBeGreaterThanOrEqual(44);
      await a11y(page, "fila visível");
    });

    // ---------------- R10: devolução ao rascunho, um teste por caso ----------------
    test("devolve a: começou um combate", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      backend.armCombat("game-a");
      await closeTurn(page);
      await expectReturned(page, backend, "começou um combate");
    });

    test("devolve b: desfecho de combate no turno", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await closeTurn(page, undefined, (st) => ({ ...st, combat_result: { encounter_id: "game-a:0:1", outcome: "victory", participants: [],
        xp_event_ref: null, loot_ref: null, ended_round: 1, result_event_id: "res-novo" } }));
      await expectReturned(page, backend, "o combate mudou a cena");
    });

    for (const key of ["death_pending", "game_over"] as const) {
      test(`devolve c: ${key}`, async ({ page, backend }) => {
        backend.actionQueue = true;
        await installControlledSse(page);
        await openGame(page);
        await toQueued(page);
        await closeTurn(page, undefined, (st) => ({ ...st, [key]: true }));
        await expectReturned(page, backend, "a Roda do Abismo aguarda sua escolha");
      });
    }

    test("devolve d: escolha de nível nova", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await closeTurn(page, undefined, (st) => {
        const choices = [{ id: "level-2", level: 2, kind: "attribute" }];
        return { ...st, player_stats: { ...st.player_stats, pending_choices: choices, level_up: { pending: choices } } };
      });
      await expectReturned(page, backend, "há uma escolha de nível");
    });

    test("devolve e: erro do turno sem narração mostrada", async ({ page, backend }) => {
      backend.allowFailure(/\/game\/action/); backend.allowConsole(/.*/);
      backend.actionQueue = true; backend.failNextTurn = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await push(page, ev("error", { detail: "falhou", code: 500, error_code: "internal_error", request_id: "e2e-req-0002" }));
      await closeSse(page);
      await expectReturned(page, backend, "o turno falhou");
      expect(posts(backend)).toHaveLength(1); // só o fallback do turno 1
    });

    test("devolve f: não salvo; o retry reenvia o MESMO action_id e a fila não dispara", async ({ page, backend }) => {
      backend.allowFailure(/\/game\/action/); backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await push(page, ev("error", { detail: "commit falhou", code: 500, error_code: "commit_failed", request_id: "e2e-req-0003", narrative_shown: true }));
      await closeSse(page);
      await expectReturned(page, backend, "o turno não foi registrado");
      await page.locator(".ws-composer .turn-status").getByRole("button", { name: "Tentar de novo" }).click();
      await waitSseReqs(page, 2);
      const [first, second] = await sseReqs(page);
      expect(second.action_id).toBe(first.action_id);
      expect(second.input_text).toBe("olho ao redor");
      await push(page, NARRATION);
      await closeTurn(page);
      await expect(pendingBtn(page)).toHaveText("Agir");
      expect(await sseReqs(page)).toHaveLength(2);
      expect(await sentQueued(page, backend)).toBe(0);
      await expect(composer(page)).toHaveValue(QUEUED);
    });

    for (const [name, event] of [["replace", { chunk: "Outro texto final.", done: true, replace: true }], ["reset", { reset: true }]] as const) {
      test(`devolve g: ${name} da narração`, async ({ page, backend }) => {
        backend.actionQueue = true;
        await installControlledSse(page);
        await openGame(page);
        await toQueued(page);
        await push(page, ev("narrative", event));
        await closeTurn(page);
        await expectReturned(page, backend, "a narração mudou");
      });
    }

    test("devolve h: stream caiu sem state e o fallback POST concluiu", async ({ page, backend }) => {
      backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await closeSse(page);
      await expectReturned(page, backend, "a narração mudou");
      expect(posts(backend)).toHaveLength(1); // o fallback do turno 1
    });

    test("devolve i: outra aba gravou uma ação pendente", async ({ page, backend }) => {
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await page.evaluate(() => { // "outra aba": mesma chave, outra operação (o clearPendingIfOwn do turno 1 não a apaga)
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i)!; if (!k.startsWith("valoria:pending:v1:")) continue;
          const row = JSON.parse(localStorage.getItem(k)!);
          row.operation_id = "00000000-0000-4000-8000-000000000001";
          localStorage.setItem(k, JSON.stringify(row));
          return;
        }
        throw new Error("sem pending do turno 1");
      });
      await closeTurn(page);
      await expectReturned(page, backend, "há uma ação pendente");
    });

    test("devolve k: sem conexão no momento do envio", async ({ page, backend }) => {
      backend.allowFailure(/.*/); backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      const state = ev("state", await finalState(page, "A névoa sobe do porto."));
      await page.context().setOffline(true);
      await push(page, state);
      await closeSse(page);
      await expectReturned(page, backend, "sem conexão");
      await page.context().setOffline(false);
    });

    test("devolve l: sessão expira, volta à partida e o texto está no rascunho (montar nunca envia)", async ({ page, backend }) => {
      backend.allowFailure(/.*/); backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await relogin(page, backend);
      await expect(composer(page)).toHaveValue(QUEUED);
      await expect(hint(page)).toContainText("você saiu da partida");
      await expect(chip(page)).toHaveCount(0);
      await expect(echoes(page, QUEUED)).toHaveCount(0);
      expect(await sentQueued(page, backend)).toBe(0);
    });

    test("I7: troca de dono depois da sessão expirada não envia nem guarda o texto", async ({ page, backend }) => {
      backend.allowFailure(/.*/); backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      backend.userId = "outro-dono";
      await relogin(page, backend);
      await expect(composer(page)).toHaveValue("");
      await expect(hint(page)).toHaveCount(0);
      expect(await sentQueued(page, backend)).toBe(0);
    });

    test("reload com a fila: 0 envios e o texto não volta", async ({ page, backend }) => {
      backend.allowFailure(/.*/); backend.allowConsole(/.*/);
      backend.actionQueue = true;
      await installControlledSse(page);
      await openGame(page);
      await toQueued(page);
      await page.reload();
      await openGame(page);
      await expect(composer(page)).toHaveValue("");
      await expect(chip(page)).toHaveCount(0);
      expect(await sentQueued(page, backend)).toBe(0);
      await expect(echoes(page, QUEUED)).toHaveCount(0);
    });
  });
}
