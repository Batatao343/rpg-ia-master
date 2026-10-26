// SPEC-205: combate por gesto. Testes do executor (não governados); as jornadas F novas
// são autoradas na tarefa de eval (handoffs/SPEC-205-eval-authoring.md).
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";

const enemy = (id: string, name: string) => ({ id, name, hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0,
  integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] });

function setupCombat(backend: DeterministicBackend, enemyCount = 2) {
  const state = backend.states.get("game-a")!;
  const base = state.player_stats.cards;
  const ids = ["e1", "e2"].slice(0, enemyCount);
  state.combat.active = true; state.combat.round = 1;
  state.combat.enemies = [enemy("e1", "Saqueador"), enemy("e2", "Bandoleiro")].slice(0, enemyCount);
  state.combat.cards = [
    { ...base[0], valid_targets: ids, invalid_reason: null },
    { ...base[0], id: "cura", name: "Folego", target_kind: "self", effect_kind: "cura", valid_targets: ["player"], invalid_reason: null },
    { ...base[0], id: "caro", name: "Cataclismo", cost: 9, ready: false, valid_targets: [], invalid_reason: "no_entropy" },
    base[1],
  ] as typeof base;
  state.combat.basic_actions = [
    { kind: "attack", valid_targets: ids, invalid_reason: null, cost: 0 },
    { kind: "maneuver", maneuver: "guardar", valid_targets: [], invalid_reason: null, cost: 0 },
    { kind: "flee", valid_targets: [], invalid_reason: null, cost: 0 },
  ];
  state.combat.scene = { zones: [{ id: "z", name: "Ponte", connections: [] }], positions: [
    { participant_id: "player", participant_name: "Ayla", zone_id: "z", distance: "proximo", posture: "neutro", concealment: "visivel", engaged_with: [], engaged_names: [] },
    ...ids.map((id, i) => ({ participant_id: id, participant_name: i ? "Bandoleiro" : "Saqueador", zone_id: "z", distance: "proximo", posture: "neutro", concealment: "visivel", engaged_with: [], engaged_names: [] })),
  ] };
}

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
  const tab = page.getByRole("tab", { name: "Combate" });
  if (await tab.count()) await tab.click();
}

const actions = (b: DeterministicBackend) => b.requests.filter((r) => r.path.startsWith("/game/action"));
const panel = (page: Page) => page.locator("#ws-panel-combate");
const card = (page: Page, name: string) => panel(page).getByRole("button", { name: new RegExp(`Jogar Carta ${name}`) });

for (const width of [1440, 390]) {
  test.describe(`gesto @${width}`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } });

    test("carta com alvo: 2 cliques, sem botao extra", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      await expect(panel(page).locator("select")).toHaveCount(0);
      await card(page, "Golpe do Véu").click();
      await expect(panel(page).getByText("Mirando Golpe do Véu: escolha um alvo").first()).toBeVisible();
      expect(actions(backend)).toHaveLength(0);
      await panel(page).getByRole("button", { name: /Alvo: Bandoleiro/ }).click();
      await expect.poll(() => actions(backend).length).toBe(1);
      const body = actions(backend)[0].body!;
      expect(body.card_id).toBe("golpe"); expect(body.target_id).toBe("e2");
      expect(String(body.input_text)).toBe("Uso Golpe do Véu em Bandoleiro.");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("carta sem alvo: 1 clique", async ({ page, backend }) => {
      setupCombat(backend, 1);
      await openGame(page);
      await card(page, "Folego").click();
      await expect.poll(() => actions(backend).length).toBe(1);
      expect(actions(backend)[0].body!.card_id).toBe("cura");
      expect(actions(backend)[0].body!.target_id ?? null).toBeNull();
    });

    test("ataque basico no jogo real; varios alvos entram em mira; um alvo executa direto", async ({ page, backend }) => {
      setupCombat(backend, 2);
      await openGame(page);
      await panel(page).getByRole("button", { name: "Ataque básico" }).click();
      await expect(panel(page).getByText("Mirando Ataque básico: escolha um alvo").first()).toBeVisible();
      await panel(page).getByRole("button", { name: /Alvo: Saqueador/ }).click();
      await expect.poll(() => actions(backend).length).toBe(1);
      expect(actions(backend)[0].body).toMatchObject({ action_kind: "attack", target_id: "e1" });
    });

    test("ataque basico com 1 alvo: 1 clique", async ({ page, backend }) => {
      setupCombat(backend, 1);
      await openGame(page);
      await panel(page).getByRole("button", { name: "Ataque básico" }).click();
      await expect.poll(() => actions(backend).length).toBe(1);
      expect(actions(backend)[0].body).toMatchObject({ action_kind: "attack", target_id: "e1" });
    });

    test("Esc e clique fora cancelam sem request; carta indisponivel mostra motivo", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      await card(page, "Golpe do Véu").click();
      await page.keyboard.press("Escape");
      await expect(panel(page).getByText("Escolha uma carta ou ação")).toBeVisible();
      await expect(card(page, "Golpe do Véu")).toBeFocused();
      await card(page, "Golpe do Véu").click();
      await page.locator("header.topbar, .ws-mhead").first().click({ position: { x: 5, y: 5 } });
      await expect(panel(page).getByText("Escolha uma carta ou ação")).toBeVisible();
      await card(page, "Cataclismo").click({ force: true });
      await expect(card(page, "Cataclismo")).toHaveAttribute("aria-disabled", "true");
      await expect(card(page, "Cataclismo")).toContainText("Entropia insuficiente");
      expect(actions(backend)).toHaveLength(0);
    });

    test("teclado puro: Enter na carta, setas, Enter no alvo", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      await card(page, "Golpe do Véu").focus();
      await page.keyboard.press("Enter");
      await expect(panel(page).getByRole("button", { name: /Alvo: Saqueador/ })).toBeFocused();
      await page.keyboard.press("ArrowRight");
      await expect(panel(page).getByRole("button", { name: /Alvo: Bandoleiro/ })).toBeFocused();
      await page.keyboard.press("Enter");
      await expect.poll(() => actions(backend).length).toBe(1);
      expect(actions(backend)[0].body!.target_id).toBe("e2");
    });

    test("HP so muda apos a resposta; duplo clique envia uma acao; axe", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      backend.delayStream();
      await card(page, "Golpe do Véu").click();
      await panel(page).getByRole("button", { name: /Alvo: Saqueador/ }).dblclick();
      await expect.poll(() => actions(backend).length).toBe(1);
      await expect(panel(page).getByText("6/6").first()).toBeVisible();
      await expect(page.getByText("O último saqueador cai; o combate termina.")).toHaveCount(0);
      const result = await new AxeBuilder({ page }).analyze();
      expect(result.violations.filter((v) => v.impact === "critical" || v.impact === "serious")).toEqual([]);
      backend.releaseStream();
      if (width < 900) await page.getByRole("navigation", { name: "Superfícies" }).getByRole("button", { name: "Crônica", exact: true }).click();
      await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
      expect(actions(backend)).toHaveLength(1);
    });

    test("tooltip no foco sem cobrir cartas", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      if (width < 900) {
        // SPEC-216: sem hover/foco em toque; o detalhe abre por "Detalhes de <Carta>".
        await panel(page).getByRole("button", { name: "Detalhes de Golpe do Véu" }).click();
      } else {
        await card(page, "Golpe do Véu").focus();
      }
      await expect(panel(page).locator(".card-detail")).toContainText("Custo: 1E");
      await expect(panel(page).locator(".card-detail")).toContainText("1× por turno");
      const boxes = await panel(page).locator(".combat-card").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON()));
      const tip = await panel(page).locator(".card-detail").evaluate((e) => e.getBoundingClientRect().toJSON());
      for (const b of boxes) {
        const overlap = b.left < tip.right && b.right > tip.left && b.top < tip.bottom && b.bottom > tip.top;
        expect(overlap).toBe(false);
      }
    });
  });
}
