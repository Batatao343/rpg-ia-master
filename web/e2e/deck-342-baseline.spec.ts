// SPEC-342 Etapa 0 / R24: linha de base do caminho `off` (sem pilhas/cena/pressagios/espolio).
// Os snapshots foram gerados ANTES de qualquer mudanca de front desta spec.
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";

const enemy = (id: string, name: string) => ({ id, name, hp: 6, max_hp: 6, vitalidade: 6, max_vitalidade: 6, esquiva: 9, protecao: 0,
  integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [] });

function setupCombat(backend: DeterministicBackend) {
  const state = backend.states.get("game-a")!;
  const base = state.player_stats.cards;
  const ids = ["e1", "e2"];
  state.combat.active = true; state.combat.round = 1;
  state.combat.enemies = [enemy("e1", "Saqueador"), enemy("e2", "Bandoleiro")];
  state.combat.cards = [
    { ...base[0], valid_targets: ids, invalid_reason: null },
    { ...base[0], id: "cura", name: "Folego", target_kind: "self", effect_kind: "cura", valid_targets: ["player"], invalid_reason: null },
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

for (const [width, height] of [[360, 740], [390, 844], [1440, 900]] as const) {
  test.describe(`baseline off @${width}`, () => {
    test.use({ viewport: { width, height } });
    const shot = { maxDiffPixelRatio: 0.01, animations: "disabled" as const };

    test("fora de combate", async ({ page, backend }) => {
      await openGame(page);
      await expect(page).toHaveScreenshot(`off-idle-${width}.png`, shot);
    });

    test("em combate", async ({ page, backend }) => {
      setupCombat(backend);
      await openGame(page);
      await expect(page.locator("#ws-panel-combate .arena")).toBeVisible();
      await expect(page.locator("#ws-panel-combate")).toHaveScreenshot(`off-combat-${width}.png`, shot);
    });
  });
}
