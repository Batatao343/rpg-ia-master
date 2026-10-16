import AxeBuilder from "@axe-core/playwright";
import { test, expect, MAP_UNREACHED } from "./fixtures";
import type { Page } from "@playwright/test";
import type { CardView } from "../src/types";

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
  await page.getByLabel("Declaro ter 18 anos ou mais.").check(); // SPEC-222 R9
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

test("F06 map_travel", async ({ page, backend }) => {
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await page.getByRole("tab", { name: "Mapa" }).click();
  const destination = page.getByRole("button", { name: "Brumalta" });
  await expect(destination).toBeEnabled();
  // SPEC-210: clicar o nó SELECIONA (detalhe); a viagem exige o botão "Viajar" separado.
  await destination.click();
  const travel = page.getByRole("button", { name: /^Viajar · \d+ períodos?/ });
  await expect(travel).toBeEnabled();
  expect(backend.requests.filter((r) => r.path.startsWith("/game/action"))).toHaveLength(0);
  await travel.click();
  const sent = backend.requests.filter((r) => r.path.startsWith("/game/action")).at(-1)!;
  expect(JSON.stringify(sent.body ?? "")).toContain("Viajo para Brumalta");
  await expect(page.getByText("A trilha termina nos portões de Brumalta.")).toBeVisible();
  await expect(page.getByText("Brumalta", { exact: true }).first()).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Brumalta", { exact: true }).first()).toBeVisible();
  await assertA11y(page);
});

async function openPeople(page: Page) {
  // SPEC-204 (D1/P1): "Pessoas" deixou de ser aba de topo e virou seção do Codex.
  await page.getByRole("tablist", { name: "Abas do painel" }).getByRole("tab", { name: "Codex" }).click();
  const section = page.getByRole("tablist", { name: "Seções do Codex" }).getByRole("tab", { name: "Pessoas" });
  await section.click();
  await expect(section).toHaveAttribute("aria-selected", "true");
}

test("F07 npc_interaction", async ({ page }) => {
  await openGame(page);
  await openPeople(page);
  await expect(page.getByText("Borin", { exact: true })).toBeVisible();
  await submitAction(page, "Converso com Borin");
  await expect(page.getByText("Borin, o barqueiro, responde sem desviar o olhar.")).toBeVisible();
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await openPeople(page);
  await expect(page.getByText("Prometeu mostrar a rota.")).toBeVisible();
  await assertA11y(page);
});

test("F08 combat_core", async ({ page, backend }) => {
  // SPEC-205: contrato atual (`valid_targets`) — carta com alvo exige o 2º gesto (clicar o alvo).
  backend.armCombat("game-a", [["e1", "Saqueador"]]);
  await openGame(page);
  await expect(page.getByText(/Combate/).first()).toBeVisible();
  await page.getByRole("button", { name: /Aparar/ }).click();
  await page.getByRole("button", { name: /^Jogar Carta Golpe do Véu/ }).click();
  await expect(page.locator(".aimbar")).toContainText("Mirando Golpe do Véu: escolha um alvo");
  expect(backend.requests.filter((r) => r.path.startsWith("/game/action"))).toHaveLength(0);
  await page.getByRole("button", { name: /^Alvo: Saqueador/ }).click();
  await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sua mão" })).toHaveCount(0);
  const sent = backend.requests.filter((r) => r.path.startsWith("/game/action"));
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toMatchObject({ card_id: "golpe", target_id: "e1", reaction_card_id: "aparar" });
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
  backend.expireConcurrently("/game/game-a/art/portrait-expiry", "/game/map");
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

// --- SPEC-204: workspace chat + contexto (F17–F19) -------------------------------------------
const DESKTOP = { width: 1440, height: 900 };
const chatRegion = (page: Page) => page.getByRole("region", { name: "Chat da aventura" });
const contextRegion = (page: Page) => page.getByRole("region", { name: "Painel de contexto" });
const composerBox = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const divider = (page: Page) => page.getByRole("separator", { name: "Redimensionar chat e painel" });
const modeButton = (page: Page, name: "Chat" | "Dividido" | "Painel") =>
  page.getByRole("group", { name: "Modo de exibição" }).getByRole("button", { name, exact: true });
const panelTab = (page: Page, name: string) =>
  page.getByRole("tablist", { name: "Abas do painel" }).getByRole("tab", { name, exact: true });

async function expectTab(page: Page, name: string) {
  await expect(panelTab(page, name)).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tablist", { name: "Abas do painel" }).locator('[role="tab"][aria-selected="true"]')).toHaveCount(1);
}

/** R1: no máximo duas superfícies de conteúdo; dock tático/gaveta antigos não existem. */
async function expectAtMostTwoSurfaces(page: Page) {
  const visible = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[aria-label="Chat da aventura"], [aria-label="Painel de contexto"], .tactical-dock, aside.hud'))
      .filter((el) => (el as HTMLElement).offsetParent !== null).length);
  expect(visible).toBeGreaterThanOrEqual(1);
  expect(visible).toBeLessThanOrEqual(2);
  await expect(page.locator(".tactical-dock, aside.hud")).toHaveCount(0);
}

async function expectNoOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function relogInto(page: Page, backend: { authenticated: boolean }, name: string) {
  backend.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  await page.getByLabel("E-mail").fill("ayla@example.test"); await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

test("F17 workspace_modes", async ({ page, backend }) => {
  // Jornada longa (vários modos/viewports/reloads): orçamento de tempo próprio, mesmos asserts.
  test.setTimeout(90_000);
  await page.setViewportSize(DESKTOP);
  await page.emulateMedia({ reducedMotion: "reduce" });
  const state = backend.states.get("game-a")!;
  state.player_stats.pending_choices = [{ id: "level-2", level: 2, kind: "attribute" }];
  state.player_stats.level_up = { pending: state.player_stats.pending_choices };
  await openGame(page);

  // R16: overlay cobre o viewport, prende o foco e não altera o workspace.
  const overlay = page.getByRole("dialog");
  await expect(overlay).toContainText("Nível 2 alcançado");
  const cover = (await overlay.boundingBox())!;
  expect(cover.width).toBeGreaterThanOrEqual(DESKTOP.width - 10);
  for (let i = 0; i < 8; i++) await page.keyboard.press("Tab");
  expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(overlay).toHaveCount(0);

  // R2: primeiro uso do save em ≥1100px abre split 50/50.
  await expect(chatRegion(page)).toBeVisible(); await expect(contextRegion(page)).toBeVisible();
  await expect(modeButton(page, "Dividido")).toHaveAttribute("aria-pressed", "true");
  await expect(divider(page)).toHaveAttribute("aria-orientation", "vertical");
  await expect(divider(page)).toHaveAttribute("aria-valuenow", "50");
  const [c0, x0] = [(await chatRegion(page).boundingBox())!, (await contextRegion(page).boundingBox())!];
  expect(Math.abs(c0.width - x0.width) / (c0.width + x0.width)).toBeLessThan(0.06);
  await expectAtMostTwoSurfaces(page);

  // R3: divisor por teclado — passos, limites mínimos em px e retorno a 50%.
  const sep = divider(page);
  await sep.focus();
  await page.keyboard.press("ArrowRight"); await expect(sep).toHaveAttribute("aria-valuenow", "55");
  await page.keyboard.press("Shift+ArrowLeft"); await expect(sep).toHaveAttribute("aria-valuenow", "45");
  await page.keyboard.press("ArrowLeft"); await expect(sep).toHaveAttribute("aria-valuenow", "40");
  await page.keyboard.press("Home");
  await expect(sep).toHaveAttribute("aria-valuenow", (await sep.getAttribute("aria-valuemin"))!);
  expect((await chatRegion(page).boundingBox())!.width).toBeGreaterThanOrEqual(379);
  await page.keyboard.press("End");
  const max = Number(await sep.getAttribute("aria-valuemax"));
  await expect(sep).toHaveAttribute("aria-valuenow", String(max));
  expect((await contextRegion(page).boundingBox())!.width).toBeGreaterThanOrEqual(359);
  await page.keyboard.press("Enter"); await expect(sep).toHaveAttribute("aria-valuenow", "50");

  // R3: divisor por ponteiro (~35%) e clique nas superfícies não move o divisor.
  const handle = (await sep.boundingBox())!;
  const wsBox = (await page.locator(".ws").boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + 150);
  await page.mouse.down();
  await page.mouse.move(wsBox.x + wsBox.width * 0.35, handle.y + 170, { steps: 6 });
  await page.mouse.up();
  const dragged = Number(await sep.getAttribute("aria-valuenow"));
  expect(dragged).toBeGreaterThanOrEqual(31); expect(dragged).toBeLessThanOrEqual(39);
  await panelTab(page, "Mapa").click();
  await chatRegion(page).click({ position: { x: 30, y: 200 } });
  await expect(sep).toHaveAttribute("aria-valuenow", String(dragged));

  // R1: chat solo e painel solo; composer sempre visível; nunca três regiões.
  await modeButton(page, "Chat").click();
  await expect(modeButton(page, "Chat")).toHaveAttribute("aria-pressed", "true");
  await expect(contextRegion(page)).toBeHidden(); await expect(divider(page)).toHaveCount(0);
  await expect(composerBox(page)).toBeVisible(); await expectAtMostTwoSurfaces(page);
  await modeButton(page, "Painel").click();
  await expect(modeButton(page, "Painel")).toHaveAttribute("aria-pressed", "true");
  await expect(chatRegion(page)).toBeHidden(); await expect(contextRegion(page)).toBeVisible();
  await expect(composerBox(page)).toBeVisible(); await expectAtMostTwoSurfaces(page);
  await modeButton(page, "Dividido").click();
  await expect(divider(page)).toHaveAttribute("aria-valuenow", String(dragged));

  // R9: reload restaura modo, proporção e aba do save.
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(modeButton(page, "Dividido")).toHaveAttribute("aria-pressed", "true");
  await expect(divider(page)).toHaveAttribute("aria-valuenow", String(dragged));
  await expectTab(page, "Mapa");

  // R12: abaixo de 1100px só uma superfície, sem modo Dividido e sem overflow.
  for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    await expect(modeButton(page, "Dividido")).toHaveCount(0);
    await expect(divider(page)).toHaveCount(0);
    expect((await chatRegion(page).isVisible()) !== (await contextRegion(page).isVisible())).toBe(true);
    await expect(composerBox(page)).toBeVisible();
    await expectNoOverflow(page);
  }
  await page.setViewportSize(DESKTOP);
  await expect(divider(page)).toHaveAttribute("aria-valuenow", String(dragged));
  await expectNoOverflow(page);

  // R17: laboratório abre em split com Combate e não consulta o Codex da campanha.
  state.combat_simulation = { enabled: true, finished: false, outcome: null } as typeof state.combat_simulation;
  state.combat.active = true; state.combat.round = 1; state.combat.cards = state.player_stats.cards;
  state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
  state.player_stats.pending_choices = []; state.player_stats.level_up = { pending: [] };
  const codexBefore = backend.requests.filter((r) => r.path === "/game/codex").length;
  await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
  await expectTab(page, "Combate");
  await expect(divider(page)).toBeVisible();
  await expect(page.locator("#ws-panel-combate").getByRole("heading", { name: "Sua mão" })).toBeVisible();
  await panelTab(page, "Codex").click();
  await expect(page.locator("#ws-panel-codex").getByText(/Laboratório de combate: sem campanha/)).toBeVisible();
  await panelTab(page, "Bestiário").click(); await panelTab(page, "Mapa").click();
  await expect(page.locator("#ws-panel-mapa").getByText(/Laboratório de combate: sem campanha/)).toBeVisible();
  expect(backend.requests.filter((r) => r.path === "/game/codex").length).toBe(codexBefore);
  await expectAtMostTwoSurfaces(page);
  await assertA11y(page);
});

test("F18 tabs_history", async ({ page }) => {
  // Jornada longa (vários modos/viewports/reloads): orçamento de tempo próprio, mesmos asserts.
  test.setTimeout(90_000);
  await page.setViewportSize(DESKTOP);
  await openGame(page);
  const tablist = page.getByRole("tablist", { name: "Abas do painel" });
  await expect(tablist.getByRole("tab")).toHaveText(["Codex", "Personagem", "Combate", "Bestiário", "Mapa"]);
  for (const [name, id] of [["Codex", "codex"], ["Personagem", "personagem"], ["Combate", "combate"], ["Bestiário", "bestiario"], ["Mapa", "mapa"]]) {
    await expect(panelTab(page, name)).toHaveAttribute("aria-controls", `ws-panel-${id}`);
    await expect(page.locator(`#ws-panel-${id}`)).toHaveAttribute("role", "tabpanel");
  }
  await expectTab(page, "Personagem");
  const back = page.getByRole("button", { name: "Voltar para a aba anterior" });
  const forward = page.getByRole("button", { name: "Avançar para a próxima aba" });
  await expect(back).toBeDisabled(); await expect(forward).toBeDisabled();

  // R4: foco roving por setas/Home/End.
  await panelTab(page, "Personagem").focus();
  await page.keyboard.press("ArrowRight"); await expectTab(page, "Combate"); await expect(panelTab(page, "Combate")).toBeFocused();
  await page.keyboard.press("ArrowLeft"); await expectTab(page, "Personagem"); await expect(panelTab(page, "Personagem")).toBeFocused();
  await page.keyboard.press("End"); await expectTab(page, "Mapa"); await expect(panelTab(page, "Mapa")).toBeFocused();
  await expect(page.getByRole("button", { name: "Brumalta" })).toBeVisible();
  await page.keyboard.press("Home"); await expectTab(page, "Codex"); await expect(panelTab(page, "Codex")).toBeFocused();

  // R6: histórico tipo navegador — Personagem → Combate → Personagem → Mapa → Codex.
  await back.click(); await expectTab(page, "Mapa");
  await back.click(); await expectTab(page, "Personagem");
  await forward.click(); await expectTab(page, "Mapa");
  await forward.click(); await expectTab(page, "Codex");
  await expect(forward).toBeDisabled();
  // Navegar depois de voltar descarta o "avançar".
  await back.click(); await expectTab(page, "Mapa");
  await panelTab(page, "Bestiário").click(); await expectTab(page, "Bestiário");
  await expect(forward).toBeDisabled();
  await panelTab(page, "Bestiário").focus();
  await page.keyboard.press("Alt+ArrowLeft"); await expectTab(page, "Mapa");
  await page.keyboard.press("Alt+ArrowRight"); await expectTab(page, "Bestiário");

  // Atalhos não disparam dentro do composer (exceto Esc e Ctrl+1) e não sujam o texto.
  await composerBox(page).fill("rascunho");
  await composerBox(page).focus();
  await page.keyboard.press("Alt+ArrowLeft"); await page.keyboard.press("Control+3");
  await expectTab(page, "Bestiário");
  await expect(composerBox(page)).toHaveValue("rascunho");

  // Ctrl+1 → chat solo, inclusive a partir do composer.
  await page.keyboard.press("Control+1");
  await expect(contextRegion(page)).toBeHidden(); await expect(modeButton(page, "Chat")).toHaveAttribute("aria-pressed", "true");
  // Ctrl+2..6 abrem a aba N (e trazem o painel de volta).
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  for (const [key, name] of [["2", "Codex"], ["3", "Personagem"], ["4", "Combate"], ["5", "Bestiário"], ["6", "Mapa"]]) {
    await page.keyboard.press(`Control+${key}`);
    await expectTab(page, name); await expect(contextRegion(page)).toBeVisible();
  }
  // Ctrl+\ alterna split ↔ último modo solo (painel, aqui).
  await modeButton(page, "Painel").click(); await modeButton(page, "Dividido").click();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.keyboard.press("Control+\\");
  await expect(modeButton(page, "Painel")).toHaveAttribute("aria-pressed", "true"); await expect(chatRegion(page)).toBeHidden();
  await page.keyboard.press("Control+\\");
  await expect(modeButton(page, "Dividido")).toHaveAttribute("aria-pressed", "true"); await expect(divider(page)).toBeVisible();

  // Esc no painel devolve foco ao composer sem mudar modo nem aba.
  await panelTab(page, "Mapa").focus();
  await page.keyboard.press("Escape");
  await expect(composerBox(page)).toBeFocused();
  await expect(modeButton(page, "Dividido")).toHaveAttribute("aria-pressed", "true");
  await expectTab(page, "Mapa");
  await expect(composerBox(page)).toHaveValue("rascunho");
  await assertA11y(page);
});

test("F19 workspace_preservation", async ({ page, backend }) => {
  // Jornada longa (vários modos/viewports/reloads): orçamento de tempo próprio, mesmos asserts.
  test.setTimeout(90_000);
  await page.setViewportSize(DESKTOP);
  await page.emulateMedia({ reducedMotion: "reduce" });
  const history = backend.histories.get("game-a")!;
  for (let i = 1; i <= 30; i++) {
    history.push({ id: `f19-p${i}`, turn: i, epoch: 1, role: "player", text: `Passo antigo ${i}`, type: "STORY" });
    history.push({ id: `f19-n${i}`, turn: i, epoch: 1, role: "narrator", text: `Registro extenso ${i}. `.repeat(12), type: "STORY" });
  }
  backend.delayStream();
  await openGame(page);
  await panelTab(page, "Mapa").click();

  // Ação em voo (SSE pendente) + rascunho novo + scroll fora do fim.
  await submitAction(page, "Ação lenta de Ayla");
  await expect.poll(() => backend.requests.filter((r) => r.path === "/game/action/stream").length).toBe(1);
  const pendingKeys = () => page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("valoria:pending")).sort());
  const pendingBefore = await pendingKeys();
  expect(pendingBefore).toHaveLength(1);
  const draft = "Rascunho de Ayla ainda não enviado";
  await composerBox(page).fill(draft);
  const story = page.getByRole("region", { name: "Narrativa" });
  await story.evaluate((el) => { el.scrollTop = 240; el.dispatchEvent(new Event("scroll")); });
  expect(await story.evaluate((el) => el.scrollHeight - el.clientHeight - el.scrollTop)).toBeGreaterThan(200);

  // R7: 10 trocas de aba/modo não tocam rascunho, scroll nem a operação pendente.
  const steps: Array<["tab" | "mode", string]> = [["tab", "Codex"], ["mode", "Painel"], ["tab", "Combate"], ["mode", "Chat"],
    ["mode", "Dividido"], ["tab", "Bestiário"], ["tab", "Personagem"], ["mode", "Painel"], ["tab", "Mapa"], ["mode", "Dividido"]];
  for (const [kind, name] of steps) {
    if (kind === "tab") await panelTab(page, name).click();
    else await modeButton(page, name as "Chat" | "Dividido" | "Painel").click();
  }
  await expect(composerBox(page)).toHaveValue(draft);
  expect(await story.evaluate((el) => el.scrollTop)).toBe(240);
  expect(await pendingKeys()).toEqual(pendingBefore);
  await expect(page.getByRole("button", { name: "Agir" })).toHaveAttribute("aria-busy", "true");
  // Foco: Esc no painel volta ao composer com o rascunho intacto.
  await panelTab(page, "Mapa").focus(); await page.keyboard.press("Escape");
  await expect(composerBox(page)).toBeFocused(); await expect(composerBox(page)).toHaveValue(draft);

  // R8: trocar de jogo com SSE pendente não vaza rascunho, aba nem scroll.
  await relogInto(page, backend, "Breno");
  await expect(composerBox(page)).toHaveValue("");
  await expectTab(page, "Personagem");
  await expect(page.getByText("Breno observa Brumalta.")).toBeVisible();
  expect(await page.getByRole("region", { name: "Narrativa" }).evaluate((el) => el.scrollTop)).toBeLessThan(240);
  backend.releaseStream();
  await expect.poll(() => backend.histories.get("game-a")!.some((e) => e.text === "Ação lenta de Ayla")).toBe(true);
  await expect(page.getByText("O mundo responde a: Ação lenta de Ayla")).toHaveCount(0);
  await expect(page.getByText("Ação lenta de Ayla", { exact: true })).toHaveCount(0);

  // Voltar ao jogo anterior na mesma página restaura o rascunho e a aba dele.
  await relogInto(page, backend, "Ayla");
  await expect(composerBox(page)).toHaveValue(draft);
  await expectTab(page, "Mapa");
  await expect(page.getByText("Ação lenta de Ayla", { exact: true })).toHaveCount(1);
  // §8 P3: rascunho nunca em disco; layout sim, por owner+game.
  const stored = await page.evaluate(() => Object.entries(localStorage).map(([k, v]) => `${k}=${v}`).join("|"));
  expect(stored).not.toContain(draft);
  expect(stored).toContain("valoria:workspace:v1:fixture-user:game-a");
  await expectNoOverflow(page);
  await assertA11y(page);
});

// --- SPEC-205: combate por gesto (F20–F24) ---------------------------------------------------
const combatPanel = (page: Page) => page.locator("#ws-panel-combate");
const handCard = (page: Page, name: string) => combatPanel(page).getByRole("button", { name: new RegExp(`^Jogar Carta ${name}`) });
const targetChip = (page: Page, name: string) => combatPanel(page).getByRole("button", { name: new RegExp(`^Alvo: ${name}`) });
const participant = (page: Page, id: string) => combatPanel(page).locator(`[data-participant="${id}"], [data-target="${id}"]`);
const aimbar = (page: Page) => combatPanel(page).locator(".aimbar");
const combatActions = (backend: { requests: Array<{ path: string; body: Record<string, unknown> | null }> }) =>
  backend.requests.filter((r) => r.path === "/game/action/stream" || r.path === "/game/action");

async function openCombat(page: Page) {
  await openGame(page);
  await panelTab(page, "Combate").click();
  await expect(combatPanel(page).getByRole("heading", { name: "Sua mão" })).toBeVisible();
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
}

test("F20 combat_gesture_target", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  backend.combatHits = true;
  await openCombat(page);
  await expect(combatPanel(page).locator("select")).toHaveCount(0);
  await expect(combatPanel(page).getByRole("button", { name: "Jogar Carta", exact: true })).toHaveCount(0);

  // Gesto 1: a carta entra em mira (aria-pressed, aimbar, alvos válidos como botões) e nada é enviado.
  const started = Date.now();
  await handCard(page, "Golpe do Véu").click();
  await expect(handCard(page, "Golpe do Véu")).toHaveAttribute("aria-pressed", "true");
  await expect(aimbar(page)).toContainText("Mirando Golpe do Véu: escolha um alvo");
  await expect(combatPanel(page).locator('[aria-live="polite"]').first()).toHaveText("Mirando Golpe do Véu: escolha um alvo.");
  await expect(targetChip(page, "Saqueador")).toBeVisible(); await expect(targetChip(page, "Bandoleiro")).toBeVisible();
  await expect(combatPanel(page).getByRole("button", { name: /^Ayla: alvo inválido/ })).toHaveAttribute("aria-disabled", "true");
  expect(combatActions(backend)).toHaveLength(0);

  // Gesto 2 com duplo clique e resposta atrasada: 1 request; HP só muda depois da resposta.
  backend.delayStream();
  await targetChip(page, "Bandoleiro").dblclick();
  await expect.poll(() => combatActions(backend).length).toBe(1);
  test.info().annotations.push({ type: "gesture", description: `clicks_to_action=2 failed_clicks=0 ms=${Date.now() - started}` });
  const body = combatActions(backend)[0].body!;
  expect(body).toMatchObject({ card_id: "golpe", target_id: "e2", input_text: "Uso Golpe do Véu em Bandoleiro." });
  expect(String(body.action_id)).toMatch(/^[0-9a-f-]{36}$/);
  expect(backend.states.get("game-a")!.combat.enemies.find((e) => e.id === "e2")!.vitalidade).toBe(2);
  await expect(aimbar(page)).toContainText("Enviando");
  await expect(participant(page, "e2")).toContainText("6/6");
  await expect(participant(page, "e1")).toContainText("6/6");
  await handCard(page, "Golpe do Véu").click({ force: true });
  expect(combatActions(backend)).toHaveLength(1);
  backend.releaseStream();
  await expect(participant(page, "e2")).toContainText("2/6");
  await expect(participant(page, "e1")).toContainText("6/6");
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  await expect(handCard(page, "Golpe do Véu")).toHaveAttribute("aria-pressed", "false");
  expect(combatActions(backend)).toHaveLength(1);
  expect(backend.histories.get("game-a")!.filter((e) => e.role === "player" && e.text === "Uso Golpe do Véu em Bandoleiro.")).toHaveLength(1);
  // R19: mão, ações e alvos nunca se sobrepõem no split 1440×900.
  const boxes = await combatPanel(page).locator(".combat-card, .actionchip, .tchip").evaluateAll((els) =>
    els.map((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; }));
  expect(boxes.length).toBeGreaterThan(5);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, b] = [boxes[i], boxes[j]];
    expect(a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t, `sobreposição ${i}×${j}`).toBe(false);
  }
  await expectNoOverflow(page);
  await assertA11y(page);
});

test("F21 combat_gesture_direct", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.armCombat("game-a", [["e1", "Saqueador"]]);
  backend.combatHits = true;
  await openCombat(page);
  // Carta sem alvo: 1 clique, sem `target_id`, sem passar pela mira.
  await handCard(page, "Fôlego").click();
  await expect.poll(() => combatActions(backend).length).toBe(1);
  const support = combatActions(backend)[0].body!;
  expect(support.card_id).toBe("folego");
  expect(support.target_id ?? null).toBeNull();
  await expect.poll(() => backend.states.get("game-a")!.combat.round).toBe(2);
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  // Ataque básico no jogo real (não simulação): 1 alvo válido = 1 clique, `action_kind` estruturado.
  expect(backend.states.get("game-a")!.combat_simulation?.enabled).toBe(false);
  const attack = combatPanel(page).getByRole("group", { name: "Manobras táticas" }).getByRole("button", { name: "Ataque básico" });
  await attack.click();
  await expect.poll(() => combatActions(backend).length).toBe(2);
  expect(combatActions(backend)[1].body).toMatchObject({ action_kind: "attack", target_id: "e1" });
  expect(combatActions(backend)[1].body!.card_id ?? null).toBeNull();
  await expect(participant(page, "e1")).toContainText("2/6");
  // Viewports do registry: a aba Combate não gera overflow horizontal.
  for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, DESKTOP]) {
    await page.setViewportSize(viewport);
    if (!(await contextRegion(page).isVisible())) await modeButton(page, "Painel").click();
    await expect(handCard(page, "Golpe do Véu")).toBeVisible();
    await expectNoOverflow(page);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await assertA11y(page);
});

test("F22 combat_gesture_cancel", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  await openCombat(page);
  const golpe = handCard(page, "Golpe do Véu");
  // Esc cancela, devolve o foco à carta e não envia nada.
  await golpe.click();
  await expect(aimbar(page)).toContainText("Mirando Golpe do Véu");
  await page.keyboard.press("Escape");
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  await expect(golpe).toHaveAttribute("aria-pressed", "false");
  await expect(golpe).toBeFocused();
  await expect(combatPanel(page).getByRole("button", { name: /^Alvo:/ })).toHaveCount(0);
  // Clique fora da arena cancela.
  await golpe.click();
  await expect(aimbar(page)).toContainText("Mirando Golpe do Véu");
  await page.locator("header.topbar").click({ position: { x: 5, y: 5 } });
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  // Clicar de novo na carta selecionada cancela; trocar de origem substitui a mira.
  await golpe.click();
  await expect(aimbar(page)).toContainText("Mirando Golpe do Véu");
  await golpe.click();
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  await golpe.click();
  await combatPanel(page).getByRole("button", { name: "Ataque básico" }).click();
  await expect(aimbar(page)).toContainText("Mirando Ataque básico: escolha um alvo");
  await expect(golpe).toHaveAttribute("aria-pressed", "false");
  await combatPanel(page).getByRole("button", { name: "Cancelar (Esc)" }).click();
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  // Carta indisponível: aria-disabled + motivo visível; clique não envia nem mira.
  const caro = handCard(page, "Cataclismo");
  await expect(caro).toHaveAttribute("aria-disabled", "true");
  await expect(caro).toContainText("Entropia insuficiente");
  await caro.click({ force: true });
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  expect(combatActions(backend)).toHaveLength(0);
  await assertA11y(page);
});

test("F23 combat_gesture_keyboard", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  backend.combatHits = true;
  await openCombat(page);
  const golpe = handCard(page, "Golpe do Véu");
  await golpe.focus();
  await expect(combatPanel(page).locator(".card-detail")).toContainText("Custo: 1E");
  // Enter entra em mira e leva o foco ao 1º alvo válido; setas circulam; Esc volta à carta.
  await page.keyboard.press("Enter");
  await expect(targetChip(page, "Saqueador")).toBeFocused();
  await page.keyboard.press("ArrowRight"); await expect(targetChip(page, "Bandoleiro")).toBeFocused();
  await page.keyboard.press("ArrowRight"); await expect(targetChip(page, "Saqueador")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(golpe).toBeFocused();
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  expect(combatActions(backend)).toHaveLength(0);
  // Atalho numérico (P2) abre a mira; setas + Enter no alvo executam.
  await page.keyboard.press("1");
  await expect(aimbar(page)).toContainText("Mirando Golpe do Véu");
  await expect(targetChip(page, "Saqueador")).toBeFocused();
  await page.keyboard.press("ArrowLeft"); await expect(targetChip(page, "Bandoleiro")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect.poll(() => combatActions(backend).length).toBe(1);
  expect(combatActions(backend)[0].body).toMatchObject({ card_id: "golpe", target_id: "e2" });
  await expect(participant(page, "e2")).toContainText("2/6");
  // Atalhos não disparam enquanto se digita no composer.
  await composerBox(page).fill("rascunho");
  await composerBox(page).focus();
  await page.keyboard.press("1");
  await expect(composerBox(page)).toHaveValue("rascunho1");
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  expect(combatActions(backend)).toHaveLength(1);
  await assertA11y(page);
});

test("F24 combat_invalid_target_reaim", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  backend.combatHits = true;
  backend.staleTargets.add("e2");
  await openCombat(page);
  const statesBefore = backend.requests.filter((r) => r.path === "/game/state").length;
  await handCard(page, "Golpe do Véu").click();
  await targetChip(page, "Bandoleiro").click();
  // 409 `invalid_target`: motivo visível, estado novo buscado, nenhum turno/Entropia/histórico.
  await expect(page.getByText(/O alvo escolhido deixou de ser válido/)).toBeVisible();
  await expect.poll(() => backend.requests.filter((r) => r.path === "/game/state").length).toBeGreaterThan(statesBefore);
  await expect(participant(page, "e2")).toHaveCount(0);
  await expect(participant(page, "e1")).toContainText("6/6");
  expect(backend.states.get("game-a")!.combat.round).toBe(1);
  expect(backend.states.get("game-a")!.player_stats.entropy).toBe(8);
  expect(backend.histories.get("game-a")!.some((e) => e.role === "player" && /Golpe/.test(e.text))).toBe(false);
  const pending = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("valoria:pending")));
  expect(pending).toEqual([]);
  // Refaz a mira com o estado novo: só o alvo vivo é oferecido; a nova ação usa outro action_id.
  await expect(aimbar(page)).toContainText("Escolha uma carta ou ação");
  await handCard(page, "Golpe do Véu").click();
  await expect(combatPanel(page).getByRole("button", { name: /^Alvo:/ })).toHaveCount(1);
  await targetChip(page, "Saqueador").click();
  await expect.poll(() => combatActions(backend).length).toBe(2);
  const [rejected, accepted] = combatActions(backend);
  expect(rejected.body).toMatchObject({ card_id: "golpe", target_id: "e2" });
  expect(accepted.body).toMatchObject({ card_id: "golpe", target_id: "e1" });
  expect(accepted.body!.action_id).not.toBe(rejected.body!.action_id);
  await expect(participant(page, "e1")).toContainText("2/6");
  expect(backend.states.get("game-a")!.combat.round).toBe(2);
  await assertA11y(page);
});

// --- SPEC-209: deck fora de combate e ficha do personagem (F25-F29) ---
const deckCard = (over: Partial<CardView> & { id: string; name: string }): CardView => ({
  type: "ativa", description: `${over.name} de teste`, effect_kind: "damage", target_kind: "enemy", subclass: "",
  prepared: false, cost: 2, base_cost: 2, frequency: "turno", spent: false, ready: false, has_rupture: false,
  rupture_ready: false, trigger: "", evolved: null, ...over,
});

function seedDeck(backend: { states: Map<string, any> }, allowed = true, reason = "") {
  const state = backend.states.get("game-a")!;
  const ps = state.player_stats;
  ps.cards = [
    deckCard({ id: "golpe", name: "Golpe do Véu", prepared: true, has_rupture: true }),
    deckCard({ id: "fenda", name: "Fenda", cost: 3, base_cost: 2 }),
    deckCard({ id: "aparar", name: "Aparar", type: "reacao", trigger: "ao_ser_alvo" }),
    deckCard({ id: "ecos", name: "Ecos", type: "passiva", frequency: "livre", cost: 0 }),
  ];
  ps.prepared_slots = 2;
  ps.subclass = "Pacto do Cinzel";
  ps.can_reorganize = { allowed, reason };
  ps.scars = [{ id: "s1", origem: "Queda em Vorr", consequencia_negativa: "Tremor na mão", habilidade_positiva_relacionada: "Olhar frio" }];
  state.chronicle = [{ chapter_id: "c1", title: "Cap", started_turn: 0, location: "Porto", entries: [
    { text: "O herói alcançou o nível 2.", turn: 1, kind: "milestone" }, { text: "Ayla chegou.", turn: 0, kind: "milestone" }] }];
}

async function openDeck(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Combate" }).click();
  await expect(page.getByRole("heading", { name: /Preparação/ })).toBeVisible();
}

const deckBtn = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name},`) }).last();
const prepareCalls = (backend: { requests: Array<{ path: string; body: Record<string, unknown> | null }> }) =>
  backend.requests.filter((r) => r.path === "/game/cards/prepare");
const preparedHeading = (page: Page) => page.getByRole("heading", { name: /Preparação/ });

test("F25 deck_prepare_persist", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  seedDeck(backend);
  await openDeck(page);
  await expect(preparedHeading(page)).toContainText("1/2");
  await expect(page.getByRole("button", { name: /^Golpe do Véu,/ }).first()).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("(base 2)").first()).toBeVisible();
  await deckBtn(page, "Fenda").click();
  await expect(preparedHeading(page)).toContainText("2/2");
  await expect(deckBtn(page, "Fenda")).toHaveAttribute("aria-pressed", "true");
  // Exatamente 1 request com a lista completa (confirmação do servidor, sem escrita paralela).
  expect(prepareCalls(backend)).toHaveLength(1);
  expect((prepareCalls(backend)[0].body!.prepared as string[]).slice().sort()).toEqual(["fenda", "golpe"]);
  expect(backend.states.get("game-a")!.player_stats.cards.filter((c: CardView) => c.prepared).map((c: CardView) => c.id).sort())
    .toEqual(["fenda", "golpe"]);
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Combate" }).click();
  await expect(preparedHeading(page)).toContainText("2/2");
  await expect(deckBtn(page, "Fenda")).toHaveAttribute("aria-pressed", "true");
  await assertA11y(page);
});

test("F26 deck_rejection_limit", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  seedDeck(backend);
  backend.allowConsole(/status of 409/);
  let reject = true;
  await page.route("**/game/cards/prepare", (route) => reject
    ? route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Local perigoso demais." }) })
    : route.fallback());
  await openDeck(page);
  const before = JSON.stringify(backend.states.get("game-a")!.player_stats.cards);
  await deckBtn(page, "Fenda").click();
  // Rollback visual + mensagem anunciada em aria-live; save do servidor intocado.
  await expect(page.locator(".deck__msg")).toContainText("Local perigoso demais.");
  await expect(deckBtn(page, "Fenda")).toHaveAttribute("aria-pressed", "false");
  await expect(preparedHeading(page)).toContainText("1/2");
  expect(JSON.stringify(backend.states.get("game-a")!.player_stats.cards)).toBe(before);
  // Limite: com 2/2 a terceira fica indisponível, com razão, sem request.
  reject = false;
  await deckBtn(page, "Fenda").click();
  await expect(preparedHeading(page)).toContainText("2/2");
  const calls = prepareCalls(backend).length;
  const aparar = deckBtn(page, "Aparar");
  await expect(aparar).toHaveAttribute("aria-disabled", "true");
  await expect(aparar).toContainText("limite de 2");
  await aparar.click({ force: true });
  expect(prepareCalls(backend)).toHaveLength(calls);
  await expect(preparedHeading(page)).toContainText("2/2");
  await assertA11y(page);
});

test("F27 deck_blocked_context", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  seedDeck(backend, false, "Local perigoso demais (apex) para reorganizar as Cartas.");
  await openDeck(page);
  await expect(page.locator(".deck__note")).toContainText("apex");
  const fenda = deckBtn(page, "Fenda");
  await expect(fenda).toHaveAttribute("aria-disabled", "true");
  await fenda.click({ force: true });
  expect(prepareCalls(backend)).toHaveLength(0);
  await expect(preparedHeading(page)).toContainText("1/2");
  await assertA11y(page);
  // Em combate ativo o deck dá lugar à mão tática.
  backend.armCombat("game-a");
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Combate" }).click();
  await expect(page.locator(".deck")).toHaveCount(0);
  expect(prepareCalls(backend)).toHaveLength(0);
});

test("F28 deck_keyboard", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  seedDeck(backend);
  await openDeck(page);
  await page.getByRole("button", { name: /^Golpe do Véu,/ }).first().focus();
  await page.keyboard.press("ArrowRight");
  expect(await page.evaluate(() => document.activeElement?.getAttribute("data-deck-card"))).not.toBeNull();
  await deckBtn(page, "Fenda").focus();
  await page.keyboard.press("Enter");
  await expect(preparedHeading(page)).toContainText("2/2");
  expect(prepareCalls(backend)).toHaveLength(1);
  for (const [w, h] of [[320, 720], [390, 844], [768, 1024]] as const) {
    await page.setViewportSize({ width: w, height: h });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `overflow ${w}px`).toBe(true);
  }
  await assertA11y(page);
});

test("F29 character_sheet_journey", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  seedDeck(backend);
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Personagem" }).click();
  await expect(page.getByText(/Pacto do Cinzel/).first()).toBeVisible();
  await expect(page.getByText("Cicatrizes")).toBeVisible();
  await expect(page.getByText("Tremor na mão")).toBeVisible();
  await expect(page.getByText("Olhar frio")).toBeVisible();
  await expect(page.locator(".char-portrait")).toBeVisible();
  await assertA11y(page);
  await page.getByRole("tab", { name: /Jornada/ }).click();
  await expect(page.getByText("Evolução do herói")).toBeVisible();
  await expect(page.getByText("O herói alcançou o nível 2.")).toBeVisible();
  await expect(page.getByText("Ayla chegou.")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Personagem" }).click();
  await expect(page.getByText("Tremor na mão")).toBeVisible();
  // Sem Cicatrizes a seção não aparece (nenhum dado antigo permanece).
  backend.states.get("game-a")!.player_stats.scars = [];
  await page.reload();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Personagem" }).click();
  await expect(page.getByText("Cicatrizes")).toHaveCount(0);
  await expect(page.getByText("Tremor na mão")).toHaveCount(0);
  await assertA11y(page);
});

// --- SPEC-210: mapa com fog server-side (F30) --------------------------------------------------
test("F30 map_fog_privacy", async ({ page, backend }) => {
  const bodies: string[] = [];
  page.on("response", async (r) => { if (new URL(r.url()).pathname.startsWith("/game/map") || new URL(r.url()).pathname === "/data/map") bodies.push(await r.text()); });
  await openGame(page);
  await page.getByRole("button", { name: /Ficha/ }).click();
  await page.getByRole("tab", { name: "Mapa" }).click();
  // Alcançados/adjacentes aparecem; "Docas Velhas" é adjacente ao porto (só placa: nome).
  await expect(page.getByRole("button", { name: /Brumalta/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Docas Velhas/ })).toBeVisible();
  // A view (e só ela) foi pedida; o legado /data/map global nunca é usado pelo cliente.
  expect(backend.requests.some((r) => r.path === "/game/map")).toBe(true);
  expect(backend.requests.some((r) => r.path === "/data/map")).toBe(false);
  await expect.poll(() => bodies.length).toBeGreaterThan(0);
  const net = bodies.join(" ");
  // Nó adjacente: id/coords/nome apenas - nada de lore/perigo.
  expect(net).toContain("Docas Velhas");
  expect(net).not.toContain("DOCAS-LORE-OCULTA");
  // Nó não alcançado (2 saltos): nenhuma pista na rede - nome, lore, id, tesouro, travel_times.
  for (const leak of [MAP_UNREACHED.name, MAP_UNREACHED.lore, "torre_proibida", MAP_UNREACHED.treasure, MAP_UNREACHED.travelTimeId, "travel_times", "treasure"]) {
    expect(net, `rede vazou: ${leak}`).not.toContain(leak);
  }
  const dom = await page.content();
  for (const leak of [MAP_UNREACHED.name, MAP_UNREACHED.lore, "torre_proibida", MAP_UNREACHED.treasure, "DOCAS-LORE-OCULTA"]) {
    expect(dom, `DOM vazou: ${leak}`).not.toContain(leak);
  }
  await assertA11y(page);
});

// --- SPEC-211: dossiês do Codex e do Bestiário (F35-F40) ---
const dosStamp = (kind: string, label: string, certainty = "reported", turn = 4) => ({
  knowledge_kind: kind, certainty, source_kind: "npc_claim", source_ref: "npc:npc_grum",
  label, first_seen_turn: 1, last_updated_turn: turn, stale: false,
});
const dosBase = (id: string, kind: string, title: string, version: number, stamp = dosStamp("fact", "Fato confirmado", "confirmed")) => ({
  id, kind, title, last_updated_turn: version, version, art: null, knowledge: stamp, notes: [],
});
const dosGrum = (version = 4, appears = true) => ({
  ...dosBase("npc_grum", "npc", "Grum", version),
  role: "Ferreiro", location: "Nova Arcádia", status: "", relationship: 8, disposition_label: "Amistoso",
  knowledge_source: "met", revealed_traits: [],
  claims: [
    { text: "Forja lâminas para a guarda.", knowledge: dosStamp("rumor", "Rumor", "rumor") },
    { text: "Deve dinheiro à Legião.", knowledge: dosStamp("suspicion", "Suspeita", "suspected") },
  ],
  appears_to_know: appears
    ? [{ text: "Viu você entrar na ferraria.", knowledge: dosStamp("perception", "Percepção", "perceived") }]
    : [],
  encounters: [{ turn: 2, location_id: "", outcome: "primeiro contato" }],
  last_seen_turn: 4,
  body: "Ferreiro <img src=x onerror=window.__xss=1> **honesto**.",
});
const dosFaction = () => ({
  ...dosBase("legiao_ferro", "faction", "Legião de Ferro", 6, dosStamp("report", "Relato")),
  body: "", goal: "", knows_goal: false, region: "norte", disposition: "neutro", reputation: 3,
  progress: null, intel_stale: true, stale_label: "informação defasada",
});
const dosCreature = (tier: number, extra: Record<string, unknown> = {}) => ({
  ...dosBase(`enemy_t${tier}`, "creature", `Criatura ${"I".repeat(tier)}`, 3),
  tier, tier_name: ["", "Avistada", "Encontrada", "Estudada", "Dominada"][tier], regions: ["nova_arcadia"],
  first_seen_turn: 1, ...extra,
});
const dosPayload = (over: Record<string, unknown> = {}, sections: Record<string, unknown> = {}) => ({
  version: 4, generated_at_turn: 5,
  sections: { npcs: [dosGrum()], locations: [], factions: [], secrets: [], chronicle_index: [], ...sections },
  bestiary: [], meta: { taxonomy_version: 1 }, ...over,
});

test("F35 dossier_people_browse", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.dossiers = dosPayload();
  await openGame(page);
  await openPeople(page);
  const row = page.getByRole("button", { name: /Grum/ });
  await expect(row.getByText("Novo")).toBeVisible();
  await row.click();
  const dossier = page.getByRole("article", { name: "Dossiê: Grum" });
  await expect(dossier).toBeVisible();
  await expect(dossier.getByText("Relação:")).toContainText("Amistoso");
  await expect(dossier.getByText("O que você sabe")).toBeVisible();
  await expect(dossier.getByText("O que ele parece saber")).toBeVisible();
  await expect(dossier.getByText("Viu você entrar na ferraria.")).toBeVisible();
  await expect(dossier.getByTestId("dossier-no-art")).toBeVisible();
  // R13: corpo é texto, nunca HTML executável.
  expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
  await expect(dossier.locator("img")).toHaveCount(0);
  await assertA11y(page);
  // Esc volta à lista sem fechar o painel de contexto.
  await page.keyboard.press("Escape");
  await expect(dossier).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Painel de contexto" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Grum/ })).toBeFocused();
  // Reload mantém o dossiê aberto.
  await page.getByRole("button", { name: /Grum/ }).click();
  await page.reload();
  await openGame(page);
  await openPeople(page);
  await expect(page.getByRole("article", { name: "Dossiê: Grum" })).toBeVisible();
});

test("F36 dossier_markers_no_blocked_counts", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.dossiers = dosPayload();
  await openGame(page);
  await openPeople(page);
  const row = page.getByRole("button", { name: /Grum/ });
  await expect(row.getByText("Novo")).toBeVisible();
  await row.click();
  await page.getByRole("button", { name: /Voltar à lista/ }).click();
  await expect(page.getByRole("button", { name: /Grum/ }).getByText("Novo")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Grum/ }).getByText("Atualizado")).toHaveCount(0);
  // Mesma versão após reload: nenhum selo reaparece.
  await page.reload();
  await openGame(page);
  await openPeople(page);
  await expect(page.getByRole("button", { name: /Grum/ }).getByText(/Novo|Atualizado/)).toHaveCount(0);
  // Versão maior => Atualizado.
  backend.dossiers = dosPayload({}, { npcs: [dosGrum(9)] });
  await page.reload();
  await openGame(page);
  await openPeople(page);
  await expect(page.getByRole("button", { name: /Grum/ }).getByText("Atualizado")).toBeVisible();
  // Contadores só refletem dossiês visíveis; nenhuma menção a categorias bloqueadas.
  const panel = page.getByRole("region", { name: "Painel de contexto" });
  await expect(page.getByRole("tablist", { name: "Seções do Codex" })).not.toContainText(/oculto|bloquead|secret/i);
  await expect(panel).not.toContainText(/oculto|bloquead|ocultas/i);
  await assertA11y(page);
});

test("F37 dossier_certainty_labels", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.dossiers = dosPayload({}, { npcs: [dosGrum(4, false)], factions: [dosFaction()] });
  await openGame(page);
  await openPeople(page);
  await page.getByRole("button", { name: /Grum/ }).click();
  const dossier = page.getByRole("article", { name: "Dossiê: Grum" });
  // Rótulos de certeza vêm do servidor; nada percebido => estado vazio honesto.
  await expect(dossier.getByText("Rumor", { exact: true })).toBeVisible();
  await expect(dossier.getByText("Suspeita", { exact: true })).toBeVisible();
  await expect(dossier.getByText("Fato confirmado").first()).toBeVisible();
  await expect(dossier.getByText("Nada percebido ainda.")).toBeVisible();
  await expect(dossier.getByText("Percepção")).toHaveCount(0);
  await page.keyboard.press("Escape");
  // Facção com informação defasada: sem objetivo, sem progresso, com rótulo.
  await page.getByRole("tablist", { name: "Seções do Codex" }).getByRole("tab", { name: "Fações" }).click();
  await page.getByRole("button", { name: /Legião de Ferro/ }).last().click();
  const faction = page.getByRole("article", { name: "Dossiê: Legião de Ferro" });
  await expect(faction.getByText("informação defasada")).toBeVisible();
  await expect(faction.getByText("Plano desconhecido")).toBeVisible();
  await expect(faction.getByText(/Progresso conhecido/)).toHaveCount(0);
  await assertA11y(page);
});

test("F38 dossier_bestiary_tiers", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.dossiers = dosPayload({
    bestiary: [
      dosCreature(1),
      dosCreature(2, { description: "Roedor inchado.", type: "Minion" }),
      dosCreature(3, { description: "Roedor inchado.", type: "Minion", max_hp: 12, defense: 9, attacks: ["Mordida"] }),
      dosCreature(4, {
        description: "Roedor inchado.", type: "Minion", max_hp: 12, defense: 9, attacks: ["Mordida"], loot: ["Dente"],
        revealed_cards: [{ id: "bst_fuga_suja", name: "Fuga Suja" }], revealed_resistances: ["fogo"],
      }),
    ],
  });
  await openGame(page);
  await page.getByRole("tab", { name: "Bestiário" }).click();
  const open = async (title: string) => {
    await page.getByRole("button", { name: new RegExp(title) }).first().click();
    return page.getByRole("article", { name: `Dossiê: ${title}` });
  };
  const back = () => page.getByRole("button", { name: /Voltar à lista/ }).click();
  let d = await open("Criatura I");
  await expect(d.getByText(/HP |Ataques:|Loot:|Cartas reveladas|Resistências reveladas/)).toHaveCount(0);
  await expect(d.getByText("Roedor inchado.")).toHaveCount(0);
  await back();
  d = await open("Criatura II");
  await expect(d.getByText("Roedor inchado.")).toBeVisible();
  await expect(d.getByText(/HP |Ataques:|Loot:/)).toHaveCount(0);
  await back();
  d = await open("Criatura III");
  await expect(d.getByText("HP 12 · Defesa 9")).toBeVisible();
  await expect(d.getByText(/Ataques: Mordida/)).toBeVisible();
  await expect(d.getByText(/Loot:|Cartas reveladas/)).toHaveCount(0);
  await back();
  d = await open("Criatura IIII");
  await expect(d.getByText("Loot: Dente")).toBeVisible();
  await expect(d.getByText("Cartas reveladas: Fuga Suja")).toBeVisible();
  await expect(d.getByText("Resistências reveladas: fogo")).toBeVisible();
  // Nada de texto de dossiê escondido em title/data-*, nem "null" renderizado.
  await expect(page.locator("[title*='bst_mordida'], [data-hidden], [data-secret]")).toHaveCount(0);
  await expect(d).not.toContainText(/\bnull\b|undefined/);
  await assertA11y(page);
});

test("F39 dossier_endpoint_fallback", async ({ page, backend }) => {
  await page.setViewportSize(DESKTOP);
  backend.dossiers = null;
  await page.route("**/game/codex/dossiers**", (route) => route.fulfill({ status: 500, body: "{}" }));
  backend.allowConsole(/500|Failed to load resource/);
  backend.unexpectedAllowed.push(/\/game\/codex\/dossiers/);
  await openGame(page);
  // Endpoint novo indisponível: Pessoas volta à lista do HUD e o Bestiário ao estado vazio, sem erro bloqueante.
  await openPeople(page);
  await expect(page.getByText("Borin", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: /^Dossiê:/ })).toHaveCount(0);
  await page.getByRole("tab", { name: "Bestiário" }).click();
  await expect(page.getByText("Nenhuma criatura registrada ainda.")).toBeVisible();
  await assertA11y(page);
});

test("F40 dossier_keyboard_reduced_motion", async ({ page, backend }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  backend.dossiers = dosPayload({}, { npcs: [dosGrum(), { ...dosGrum(), id: "npc_ze", title: "Zé" }] });
  await openGame(page);
  await openPeople(page);
  const grum = page.getByRole("button", { name: /Grum/ });
  const box = await grum.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await grum.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("button", { name: /Zé/ })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(grum).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("article", { name: "Dossiê: Grum" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Voltar à lista/ })).toBeFocused();
  await assertA11y(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /Grum/ })).toBeFocused();
  for (const [w, h] of [[320, 720], [390, 844]] as const) {
    await page.setViewportSize({ width: w, height: h });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `overflow ${w}px`).toBe(true);
  }
});
