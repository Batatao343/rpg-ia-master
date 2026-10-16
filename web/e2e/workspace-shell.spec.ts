// SPEC-204: shell chat + contexto (split / abas). Testes do executor — não substituem
// as jornadas F17–F19, cuja autoria é da tarefa de eval (handoffs/SPEC-204-eval-authoring.md).
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// Capturas vão para test-results (gitignored); as versões WebP versionadas ficam em docs/spec204/capturas.
const SHOTS = "test-results/spec204-capturas";

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

async function switchGame(page: Page, backend: { authenticated: boolean }, name: string) {
  backend.authenticated = false;
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await page.getByLabel("E-mail").fill("ayla@example.test");
  await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

const chat = (page: Page) => page.getByRole("region", { name: "Chat da aventura" });
const context = (page: Page) => page.getByRole("region", { name: "Painel de contexto" });
const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const separator = (page: Page) => page.getByRole("separator", { name: "Redimensionar chat e painel" });
const modes = (page: Page) => page.getByRole("group", { name: "Modo de exibição" });

/** R1: nunca chat + painel + uma terceira região de conteúdo de jogo. */
async function assertAtMostTwoSurfaces(page: Page) {
  const visible = await page.evaluate(() => {
    const regions = Array.from(document.querySelectorAll(".ws-chat, .ws-ctx, .tactical-dock, aside.hud"));
    return regions.filter((el) => (el as HTMLElement).offsetParent !== null).length;
  });
  expect(visible).toBeLessThanOrEqual(2);
  await expect(page.locator(".tactical-dock, aside.hud")).toHaveCount(0);
}

test.describe("desktop 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("modos, cinco abas e histórico", async ({ page }) => {
    await openGame(page);
    // R2: primeiro uso → split 50/50 com a ficha do personagem.
    await expect(chat(page)).toBeVisible();
    await expect(context(page)).toBeVisible();
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "50");
    const tabs = context(page).getByRole("tablist", { name: "Abas do painel" }).getByRole("tab");
    await expect(tabs).toHaveText(["Codex", "Personagem", "Combate", "Bestiário", "Mapa"]);
    await expect(page.getByRole("tab", { name: "Personagem" })).toHaveAttribute("aria-selected", "true");
    await assertAtMostTwoSurfaces(page);
    await page.screenshot({ path: `${SHOTS}/1440-split.png` });

    // Foco roving: setas trocam a aba selecionada.
    await page.getByRole("tab", { name: "Personagem" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Combate" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tab", { name: "Combate" })).toBeFocused();
    await page.keyboard.press("End");
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("button", { name: "Brumalta" })).toBeVisible();
    await page.keyboard.press("Home");
    await expect(page.getByRole("tab", { name: "Codex" })).toHaveAttribute("aria-selected", "true");

    // Voltar/Avançar como navegador.
    const back = page.getByRole("button", { name: "Voltar para a aba anterior" });
    const forward = page.getByRole("button", { name: "Avançar para a próxima aba" });
    await expect(forward).toBeDisabled();
    await back.click();
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
    await forward.click();
    await expect(page.getByRole("tab", { name: "Codex" })).toHaveAttribute("aria-selected", "true");
    // Atalhos Alt+←/→ (foco dentro do app, fora de campos de texto).
    await page.getByRole("tab", { name: "Codex" }).focus();
    await page.keyboard.press("Alt+ArrowLeft");
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("Alt+ArrowRight");
    await expect(page.getByRole("tab", { name: "Codex" })).toHaveAttribute("aria-selected", "true");

    // D1: Pessoas/Fações/Crônica viram seções do Codex.
    const sections = page.getByRole("tablist", { name: "Seções do Codex" }).getByRole("tab");
    await expect(sections).toHaveText(["Locais (0)", "Pessoas", "Personagens (0)", "Fações", "Segredos (0)", "Crônica"]);
    await page.getByRole("tab", { name: "Pessoas" }).click();
    await expect(page.getByText("Prometeu mostrar a rota.")).toBeVisible();
    await page.getByRole("tab", { name: "Crônica" }).click();
    await expect(page.getByRole("searchbox", { name: "Buscar na crônica" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/1440-split-codex.png` });

    // Missões → Personagem › Jornada; Bestiário é aba própria.
    await page.getByRole("tab", { name: "Personagem" }).click();
    await page.getByRole("tab", { name: /Jornada/ }).click();
    await expect(page.getByText("Ativa")).toBeVisible();
    await page.getByRole("tab", { name: "Bestiário" }).click();
    await expect(page.getByText("Nenhuma criatura registrada ainda.")).toBeVisible();

    // Modos: só chat (painel some, composer fica), só painel (chat some, composer fica).
    await modes(page).getByRole("button", { name: "Chat" }).click();
    await expect(context(page)).toBeHidden();
    await expect(separator(page)).toHaveCount(0);
    await expect(composer(page)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/1440-chat.png` });
    await modes(page).getByRole("button", { name: "Painel" }).click();
    await expect(chat(page)).toBeHidden();
    await expect(context(page)).toBeVisible();
    await expect(composer(page)).toBeVisible();
    await assertAtMostTwoSurfaces(page);
    await page.screenshot({ path: `${SHOTS}/1440-contexto.png` });
    // Esc no painel devolve o foco ao composer sem mudar de modo.
    await page.getByRole("tab", { name: "Bestiário" }).focus();
    await page.keyboard.press("Escape");
    await expect(composer(page)).toBeFocused();
    await expect(chat(page)).toBeHidden();
    // Ctrl+1 → chat solo mesmo com foco no composer; Ctrl+5 abre a aba 4 (Bestiário).
    await page.keyboard.press("Control+1");
    await expect(context(page)).toBeHidden();
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.keyboard.press("Control+6");
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
    await expect(separator(page)).toBeVisible();
    // Ctrl+\ alterna split ↔ último modo solo (chat, após o Ctrl+1).
    await page.keyboard.press("Control+\\");
    await expect(context(page)).toBeHidden();
    await page.keyboard.press("Control+\\");
    await expect(separator(page)).toBeVisible();
    await assertA11y(page);
  });

  test("divisor por teclado e ponteiro, limites e reload", async ({ page }) => {
    // Sem transição de largura: as medições do divisor não pegam a coluna no meio da animação.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openGame(page);
    const sep = separator(page);
    await sep.focus();
    await page.keyboard.press("ArrowRight");
    await expect(sep).toHaveAttribute("aria-valuenow", "55");
    await page.keyboard.press("Shift+ArrowLeft");
    await expect(sep).toHaveAttribute("aria-valuenow", "45");
    await page.keyboard.press("Home");
    const min = Number(await sep.getAttribute("aria-valuemin"));
    await expect(sep).toHaveAttribute("aria-valuenow", String(min));
    const chatBox = await chat(page).boundingBox();
    expect(chatBox!.width).toBeGreaterThanOrEqual(379);
    await page.keyboard.press("End");
    const max = Number(await sep.getAttribute("aria-valuemax"));
    await expect(sep).toHaveAttribute("aria-valuenow", String(max));
    const ctxBox = await context(page).boundingBox();
    expect(ctxBox!.width).toBeGreaterThanOrEqual(359);
    await page.keyboard.press("Enter");
    await expect(sep).toHaveAttribute("aria-valuenow", "50");

    // Ponteiro: arrastar para ~70%.
    const box = (await sep.boundingBox())!;
    const grid = (await page.locator(".ws").boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + 200);
    await page.mouse.down();
    await page.mouse.move(grid.x + grid.width * 0.7, box.y + 220, { steps: 6 });
    await page.mouse.up();
    const dragged = Number(await sep.getAttribute("aria-valuenow"));
    expect(dragged).toBeGreaterThanOrEqual(66);
    expect(dragged).toBeLessThanOrEqual(maxOf(max));
    // Clique dentro das superfícies não mexe no divisor.
    await page.getByRole("tab", { name: "Mapa" }).click();
    await chat(page).click({ position: { x: 40, y: 260 } });
    await expect(sep).toHaveAttribute("aria-valuenow", String(dragged));

    // Reload restaura modo/ratio/aba do save.
    await page.reload();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await expect(separator(page)).toHaveAttribute("aria-valuenow", String(dragged));
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
    // Duplo clique restaura 50%.
    await separator(page).dblclick();
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "50");
  });

  test("rascunho, scroll e foco sobrevivem a trocas; isolamento por jogo", async ({ page, backend }) => {
    const history = backend.histories.get("game-a")!;
    for (let i = 1; i <= 30; i++) {
      history.push({ id: `a-p${i}`, turn: i, epoch: 1, role: "player", text: `Ação antiga ${i}`, type: "STORY" });
      history.push({ id: `a-n${i}`, turn: i, epoch: 1, role: "narrator", text: `Narração longa ${i}. `.repeat(12), type: "STORY" });
    }
    await openGame(page);
    const story = page.getByRole("region", { name: "Narrativa" });
    await story.evaluate((el) => { el.scrollTop = 300; el.dispatchEvent(new Event("scroll")); });
    await composer(page).fill("Rascunho que não foi enviado");
    // 10 trocas de aba/modo.
    const steps: Array<["tab" | "mode", string]> = [["tab", "Codex"], ["tab", "Mapa"], ["mode", "Painel"],
      ["tab", "Personagem"], ["mode", "Chat"], ["mode", "Dividido"], ["tab", "Bestiário"], ["tab", "Combate"],
      ["mode", "Painel"], ["mode", "Dividido"]];
    for (const [kind, name] of steps) {
      if (kind === "tab") await page.getByRole("tab", { name, exact: true }).click();
      else await modes(page).getByRole("button", { name }).click();
    }
    await expect(composer(page)).toHaveValue("Rascunho que não foi enviado");
    expect(await story.evaluate((el) => el.scrollTop)).toBe(300);
    await composer(page).focus();
    await page.getByRole("tab", { name: "Mapa" }).click();
    await page.keyboard.press("Escape");
    await expect(composer(page)).toBeFocused();

    // Trocar de jogo: outro rascunho/aba; voltar restaura o rascunho de Ayla (memória da página).
    await switchGame(page, backend, "Breno");
    await expect(composer(page)).toHaveValue("");
    await expect(page.getByRole("tab", { name: "Personagem" })).toHaveAttribute("aria-selected", "true");
    await switchGame(page, backend, "Ayla");
    await expect(composer(page)).toHaveValue("Rascunho que não foi enviado");
    // Rascunho nunca vai para o disco (§8 P3).
    const stored = await page.evaluate(() => Object.entries(localStorage).map(([k, v]) => k + v).join("|"));
    expect(stored).not.toContain("Rascunho que não foi enviado");
    expect(stored).toContain("valoria:workspace:v1:fixture-user:game-a");
  });

  test("ação pendente sobrevive a 10 trocas de aba/modo", async ({ page, backend }) => {
    backend.failNextTurn = true;
    backend.allowFailure(/\/game\/action(?:\/stream)?$/);
    backend.allowConsole(/Failed to load resource: net::ERR_FAILED/);
    await openGame(page);
    await composer(page).fill("Investigo a ponte partida");
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(page.getByText(/Ação não confirmada/)).toBeVisible();
    const pendingKeys = () => page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("valoria:pending")));
    const before = await pendingKeys();
    expect(before).toHaveLength(1);
    await composer(page).fill("Outro rascunho");
    for (const name of ["Codex", "Mapa", "Combate", "Bestiário", "Personagem"]) {
      await page.getByRole("tab", { name, exact: true }).click();
      await modes(page).getByRole("button", { name: name === "Mapa" ? "Painel" : "Dividido" }).click();
    }
    expect(await pendingKeys()).toEqual(before);
    await expect(page.getByRole("button", { name: "Consultar / retomar ação pendente" })).toBeVisible();
    await expect(composer(page)).toHaveValue("Outro rascunho");
  });

  test("combate abre split com Combate e controles só na aba", async ({ page, backend }) => {
    await page.addInitScript(() => localStorage.setItem("valoria:workspace:v1:fixture-user:game-a",
      JSON.stringify({ version: 1, mode: "chat", ratio: 0.7, tab: "mapa", lastSolo: "chat" })));
    const state = backend.states.get("game-a")!;
    state.combat.active = true; state.combat.round = 1;
    state.combat.cards = state.player_stats.cards;
    state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
    await openGame(page);
    await expect(page.getByRole("tab", { name: "Combate" })).toHaveAttribute("aria-selected", "true");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "50");
    const panel = page.locator("#ws-panel-combate");
    await expect(page.getByRole("heading", { name: "Sua mão" })).toHaveCount(1);
    await expect(panel.getByRole("heading", { name: "Sua mão" })).toBeVisible();
    await expect(panel.getByRole("group", { name: "Manobras táticas" })).toBeVisible();
    await expect(chat(page).getByRole("button", { name: /Aparar|Jogar Carta|Engajar/ })).toHaveCount(0);
    await assertAtMostTwoSurfaces(page);
    await page.screenshot({ path: `${SHOTS}/1440-combate.png` });
    await assertA11y(page);
    await panel.getByRole("button", { name: /Aparar/ }).click();
    await panel.getByRole("button", { name: "Jogar Carta" }).click();
    await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
    // D2: encerrado, a aba Combate continua aberta com o pós-combate.
    await expect(page.getByRole("tab", { name: "Combate" })).toHaveAttribute("aria-selected", "true");
    await expect(panel.getByRole("note")).toContainText("Combate encerrado");
    await expect(page.getByRole("heading", { name: "Sua mão" })).toHaveCount(0);
    await page.screenshot({ path: `${SHOTS}/1440-pos-combate.png` });
  });

  test("level-up cobre a tela, prende e devolve foco sem mudar o workspace", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.player_stats.pending_choices = [{ id: "level-2", level: 2, kind: "attribute" }];
    state.player_stats.level_up = { pending: state.player_stats.pending_choices };
    await openGame(page);
    const dialog = page.getByRole("dialog", { name: /Virtude/ });
    await expect(dialog).toBeVisible();
    const rect = await dialog.boundingBox();
    expect(rect!.width).toBeGreaterThanOrEqual(1430);
    const focusedInside = await page.evaluate(() => !!document.activeElement?.closest("[role='dialog']"));
    expect(focusedInside).toBe(true);
    for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
    expect(await page.evaluate(() => !!document.activeElement?.closest("[role='dialog']"))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Personagem" })).toHaveAttribute("aria-selected", "true");
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "50");
    await page.getByRole("button", { name: "⬆ Nível!" }).focus();
    await page.getByRole("button", { name: "⬆ Nível!" }).click();
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "⬆ Nível!" })).toBeFocused();
  });

  test("laboratório abre em Combate e não consulta campanha", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.combat_simulation = { enabled: true, finished: false, outcome: null } as typeof state.combat_simulation;
    state.combat.active = true; state.combat.round = 1; state.combat.cards = state.player_stats.cards;
    state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
    await openGame(page);
    await expect(page.getByRole("tab", { name: "Combate" })).toHaveAttribute("aria-selected", "true");
    await expect(separator(page)).toBeVisible();
    await page.getByRole("tab", { name: "Codex" }).click();
    await expect(page.getByText(/Laboratório de combate: sem campanha/)).toBeVisible();
    await page.getByRole("tab", { name: "Mapa" }).click();
    await page.getByRole("tab", { name: "Bestiário" }).click();
    expect(backend.requests.filter((r) => r.path === "/game/codex")).toHaveLength(0);
  });

  test("storage bloqueado não gera erro de console", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new DOMException("blocked", "SecurityError"); } });
    });
    await openGame(page);
    await expect(separator(page)).toHaveAttribute("aria-valuenow", "50");
    await page.getByRole("tab", { name: "Mapa" }).click();
    await expect(page.getByRole("button", { name: "Brumalta" })).toBeVisible();
    // a fixture falha o teste se houver pageerror/console.error
  });
});

function maxOf(value: number) { return Number.isFinite(value) ? value : 100; }

test.describe("telefone 390", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("uma superfície por vez, sem overflow e acessível", async ({ page }) => {
    await openGame(page);
    await expect(chat(page)).toBeVisible();
    await expect(context(page)).toBeHidden();
    await expect(separator(page)).toHaveCount(0);
    await expect(modes(page).getByRole("button", { name: "Dividido" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: `${SHOTS}/390-chat.png` });
    await page.getByRole("button", { name: /Ficha/ }).click();
    await expect(context(page)).toBeVisible();
    await expect(chat(page)).toBeHidden();
    await expect(composer(page)).toBeVisible();
    await page.getByRole("tab", { name: "Mapa" }).click();
    await expect(page.getByRole("button", { name: "Brumalta" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: `${SHOTS}/390-contexto.png` });
    await assertA11y(page);
    await page.getByRole("button", { name: "Fechar ficha" }).click();
    await expect(chat(page)).toBeVisible();
    // A preferência split ficou gravada: em 1440 volta a dividir.
    await page.setViewportSize({ width: 1440, height: 900 });
    await expect(separator(page)).toBeVisible();
    await expect(page.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
  });

  test("combate em tela estreita mostra a aba Combate", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.combat.active = true; state.combat.round = 1; state.combat.cards = state.player_stats.cards;
    state.combat.enemies = [{ id: "e1", name: "Saqueador", hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] }];
    await openGame(page);
    await expect(page.getByRole("heading", { name: "Sua mão" })).toBeVisible();
    await expect(composer(page)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await assertA11y(page);
  });
});

test.describe("movimento reduzido", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  test("sem transição de largura no split com reduce; com transição sem reduce", async ({ page }) => {
    // O `reducedMotion` do config não chega a este Chromium local; emula explicitamente.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openGame(page);
    const duration = () => page.locator(".ws").evaluate((el) => getComputedStyle(el).transitionDuration);
    const reduced = await duration();
    expect(reduced.split(",").every((d) => parseFloat(d) <= 0.0001), reduced).toBe(true);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    expect(parseFloat(await duration())).toBeGreaterThan(0.1);
  });
});
