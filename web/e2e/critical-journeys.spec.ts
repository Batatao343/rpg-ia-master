import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

async function assertA11y(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, "A11Y serious/critical: " + blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

async function submitAction(page: Page, text: string) {
  const input = page.getByPlaceholder(/O que você faz/);
  await input.fill(text);
  await page.getByRole("button", { name: "Agir" }).click();
}

test("F01 auth_signup_login", async ({ page, backend }) => {
  backend.authenticated = false;
  backend.saves = [];
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  expect(backend.protectedBeforeAuth).toBe(0);
  await page.getByLabel("E-mail").fill("ayla@example.test");
  await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByRole("heading", { name: "Forje sua lenda" })).toBeVisible();
  await page.getByRole("button", { name: "Encerrar sessão" }).click();
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  expect(backend.protectedBeforeAuth).toBe(0);
  await assertA11y(page);
});

test("F02 character_creation", async ({ page, backend }) => {
  backend.saves = [];
  await page.goto("/");
  await expect(page.getByText("Valoria aguarda")).toBeVisible();
  await page.getByRole("button", { name: /Origem/ }).click();
  await page.getByRole("button", { name: "Humano" }).click();
  await page.getByRole("button", { name: /Vocação/ }).click();
  await page.getByRole("button", { name: "Devoto do Abismo" }).click();
  await page.getByRole("button", { name: /Região/ }).click();
  await page.getByRole("button", { name: /Porto Cinzento/ }).click();
  await page.getByRole("button", { name: /Identidade/ }).click();
  await page.getByLabel("Nome do herói").fill("Mira");
  await page.getByRole("button", { name: "Tecer o prólogo" }).click();
  await expect(page.getByText("O Chamado")).toBeVisible();
  await page.getByRole("button", { name: "Começar a jornada" }).click();
  await expect(page.getByText("Mira", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: /Ficha/ }).click();
  await expect(page.getByText(/Devoto do Abismo/).first()).toBeVisible();
  await assertA11y(page);
});

test("F03 resume_save", async ({ page }) => {
  await openGame(page);
  await expect(page.getByText("Ayla chegou ao porto.")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla chegou ao porto.")).toBeVisible();
  await expect(page.getByText("Porto Cinzento", { exact: true }).first()).toBeVisible();
  await assertA11y(page);
});

test("F04 action_stream", async ({ page }) => {
  await openGame(page);
  await submitAction(page, "Examino o sino quebrado");
  await expect(page.getByText("O mundo responde a: Examino o sino quebrado")).toBeVisible();
  await expect(page.getByText("Examino o sino quebrado", { exact: true })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Agir" })).toBeEnabled();
  const pending = await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("valoria:pending")));
  expect(pending).toEqual([]);
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Examino o sino quebrado", { exact: true })).toHaveCount(1);
  await assertA11y(page);
});

test("F05 idempotent_replay", async ({ page, backend }) => {
  // O 409 é o oráculo esperado desta jornada; o Chromium registra respostas
  // não-2xx de fetch no console mesmo quando o chamador inspeciona o status.
  backend.allowConsole(/409 \(Conflict\)/);
  await openGame(page);
  await submitAction(page, "Observo as docas");
  await expect(page.getByText("O mundo responde a: Observo as docas")).toBeVisible();
  const stream = backend.requests.find((r) => r.path === "/game/action/stream")!;
  const sameStatus = await page.evaluate(async (payload) => (await fetch("/game/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).status, stream.body);
  const divergent = { ...stream.body, input_text: "Tento duplicar o turno" };
  const conflictStatus = await page.evaluate(async (payload) => (await fetch("/game/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).status, divergent);
  expect(sameStatus).toBe(200);
  expect(conflictStatus).toBe(409);
  expect(backend.histories.get("game-a")?.filter((entry) => entry.role === "player" && entry.text === "Observo as docas")).toHaveLength(1);
  await assertA11y(page);
});

test("F06 map_travel", async ({ page }) => {
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await page.getByRole("tab", { name: "Mapa" }).click();
  const destination = page.getByRole("button", { name: "Brumalta" });
  await expect(destination).toBeEnabled();
  await destination.click();
  await expect(page.getByText("A trilha termina nos portões de Brumalta.")).toBeVisible();
  await expect(page.getByText("Brumalta", { exact: true }).first()).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Brumalta", { exact: true }).first()).toBeVisible();
  await assertA11y(page);
});

test("F07 npc_interaction", async ({ page }) => {
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await page.getByRole("tab", { name: "Pessoas" }).click();
  await expect(page.getByText("Borin", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Ficha/ }).click();
  await submitAction(page, "Converso com Borin");
  await expect(page.getByText("Borin, o barqueiro, responde sem desviar o olhar.")).toBeVisible();
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("button", { name: /Ficha/ }).click(); await page.getByRole("tab", { name: "Pessoas" }).click();
  await expect(page.getByText("Prometeu mostrar a rota.")).toBeVisible();
  await assertA11y(page);
});

test("F08 combat_core", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.combat.active = true; state.combat.round = 1;
  state.combat.cards = state.player_stats.cards;
  state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
  await openGame(page);
  await expect(page.getByText(/Combate/).first()).toBeVisible();
  await page.getByRole("button", { name: /Aparar/ }).click();
  await page.getByRole("button", { name: "Jogar Carta" }).click();
  await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sua mão" })).toHaveCount(0);
  expect(backend.states.get("game-a")?.combat.round).toBe(2);
  await assertA11y(page);
});

test("F09 quest_progress", async ({ page }) => {
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click(); await page.getByRole("tab", { name: /Missões/ }).click();
  await expect(page.getByText("Ativa")).toBeVisible();
  await page.getByRole("button", { name: /Ficha/ }).click();
  await submitAction(page, "Sigo o rastro e as pegadas");
  await page.getByRole("button", { name: /Ficha/ }).click(); await page.getByRole("tab", { name: /Missões/ }).click();
  await expect(page.getByText("Concluída")).toBeVisible();
  await expect(page.getByText("Ativa")).toHaveCount(0);
  await assertA11y(page);
});

test("F10 death_recovery", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.death_pending = true; state.player_stats.hp = 0; state.player_stats.vitalidade = 0;
  state.death = { pending: true, last_action: null, last_action_label: "", entered_terminal: true, stabilization: "falhou", stabilization_attempts: 1, killer: "Saqueador", will_restore_turn: 1, will_lose_turns: 1, retained: ["crônica"], reverted: ["último turno"] };
  await openGame(page);
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Agir" })).toBeDisabled();
  await page.getByRole("button", { name: "Continuar do checkpoint" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Agir" })).toBeEnabled();
  await assertA11y(page);
});

test("F11 level_up", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.player_stats.pending_choices = [{ id: "level-2", level: 2, kind: "attribute" }];
  state.player_stats.level_up = { pending: state.player_stats.pending_choices };
  await openGame(page);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Nível 2 alcançado");
  await dialog.getByRole("button", { name: /Força/ }).click();
  await dialog.getByRole("button", { name: "Confirmar" }).click();
  await expect(dialog).toHaveCount(0);
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await assertA11y(page);
});

test("F12 art_portrait", async ({ page, backend }) => {
  backend.allowFailure(/\/game\/game-a\/art\/portrait-1$/);
  backend.states.get("game-a")!.portrait_generation_id = "portrait-1";
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await expect(page.getByRole("status", { name: undefined })).toContainText("Retrato na fila");
  const expand = page.getByRole("button", { name: "Ampliar retrato do personagem" });
  await expect(expand).toBeVisible({ timeout: 8_000 });
  await expand.focus(); await expand.click();
  const dialog = page.getByRole("dialog", { name: "Retrato do personagem" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(expand).toBeFocused();
  await assertA11y(page);
});

test("F13 session_expiry", async ({ page, backend }) => {
  backend.allowFailure(/\/game\/game-a\/art\/portrait-expiry$/);
  backend.allowConsole(/401 \(Unauthorized\)/);
  backend.states.get("game-a")!.portrait_generation_id = "portrait-expiry";
  backend.expireConcurrently("/game/game-a/art/portrait-expiry", "/data/map");
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await page.getByRole("tab", { name: "Mapa" }).click();
  await expect(page.getByRole("button", { name: "Brumalta" })).toBeVisible();
  await expect.poll(() => backend.refreshCount).toBe(1);
  await assertA11y(page);
});

test("F14 network_failure_recovery", async ({ page, backend }) => {
  backend.failNextTurn = true;
  backend.allowFailure(/\/game\/action(?:\/stream)?$/);
  backend.allowConsole(/Failed to load resource: net::ERR_FAILED/);
  await openGame(page);
  await submitAction(page, "Investigo a ponte partida");
  await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
  const pendingBefore = await page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith("valoria:pending")));
  expect(pendingBefore).toBe(true);
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Investigo a ponte partida", { exact: true })).toHaveCount(1);
  const pendingAfter = await page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith("valoria:pending")));
  expect(pendingAfter).toBe(false);
  await assertA11y(page);
});

test("F15 game_switch_inflight", async ({ page, backend }) => {
  backend.delayStream();
  await openGame(page, "Ayla");
  await submitAction(page, "Ação lenta de Ayla");
  await expect.poll(() => backend.requests.filter((r) => r.path === "/game/action/stream").length).toBe(1);
  backend.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  await page.getByLabel("E-mail").fill("breno@example.test"); await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.getByRole("button", { name: /^Breno/ }).click();
  backend.releaseStream();
  await expect(page.getByText("Brumalta", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("O mundo responde a: Ação lenta de Ayla")).toHaveCount(0);
  await assertA11y(page);
});

test("F16 responsive_navigation", async ({ page }) => {
  await openGame(page);
  for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    const logout = page.getByRole("button", { name: "Encerrar sessão" });
    const ficha = page.getByRole("button", { name: /Ficha/ });
    await expect(logout).toBeVisible(); await expect(ficha).toBeVisible();
    const [a, b] = await Promise.all([logout.boundingBox(), ficha.boundingBox()]);
    expect(a && b && (a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y)).toBeTruthy();
    await ficha.click();
    await expect(page.getByRole("tab", { name: "Mapa" })).toBeVisible();
    await expect(page.getByPlaceholder(/O que você faz/)).toBeVisible();
    if (viewport.width <= 480) await page.getByRole("button", { name: "Fechar ficha" }).click();
    else await ficha.click();
  }
  await assertA11y(page);
});
