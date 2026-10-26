// SPEC-210: aba Mapa com fog server-side. Testes do executor (nao entram no registry de jornadas
// criticas; a adaptacao de F06/F13 e tarefa de eval separada - ver handoffs/SPEC-210-eval-authoring.md).
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const SHOTS = "test-results/spec210";
const SENTINEL = "NOME-NAO-DESCOBERTO";

const view = (over: Record<string, unknown> = {}) => ({
  game_id: "game-a", turn_count: 1, map_version: "v1", current_id: "porto", anchor_id: "porto",
  nodes: [
    { id: "porto", state: "atual", name: "Porto Cinzento", coords: { x: 30, y: 55 }, region_id: "costa", danger: 1,
      lore_seed: "Cais sob névoa", art: { location_id: "porto", scope: "placeholder", asset: null } },
    { id: "brumalta", state: "adjacente", name: "Brumalta", coords: { x: 70, y: 35 }, reachable: true },
  ],
  edges: [{ a: "brumalta", b: "porto", blocked: false }],
  interiors: { here: [{ id: "taverna", name: "Taverna do Cais", danger: 0, tags: [] }], exit_to: null },
  travel_options: [{ location_id: "brumalta", name: "Brumalta", periods: 2, reachable: true, blocked: false, reason: "" }],
  travel_gate: { blocked: false, reason: "" }, looming_threat: "", ...over,
});

async function openMap(page: Page, payload: unknown, status = 200) {
  await page.route("**/game/map?*", (r) => r.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) }));
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("region", { name: "Painel de contexto" }).getByRole("tab", { name: "Mapa" }).click();
}

test.beforeEach(async ({ backend }) => {
  backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
  backend.allowConsole(/ERR_CONNECTION_CLOSED|Failed to load resource/);
});

for (const [name, viewport] of [["full", { width: 1440, height: 900 }], ["half", { width: 1440, height: 900 }]] as const) {
  test(`mapa ${name}: adjacente, custo, Viajar como turno de chat e a11y`, async ({ page, backend }) => {
    await page.setViewportSize(viewport);
    await openMap(page, view());
    // "half" = split 50/50 (padrao); "full" = so o painel.
    if (name === "full") await page.getByRole("group", { name: "Modo de exibição" }).getByRole("button", { name: "Painel" }).click();
    const panel = page.locator("#ws-panel-mapa");
    const node = panel.getByRole("button", { name: /^Brumalta, ainda não visitado, 2 períodos/ });
    await expect(node).toBeVisible();
    await node.click();
    await expect(panel.getByRole("region", { name: "Detalhe de Brumalta" })).toBeVisible();
    // adjacente: sem lore/perigo
    await expect(panel.getByText(/Região inexplorada/)).toBeVisible();
    await expect(panel.getByText(/perigo/)).toHaveCount(0);
    const travel = panel.getByRole("button", { name: /^Viajar · 2 períodos/ });
    await expect(travel).toBeEnabled();
    mkdirSync(SHOTS, { recursive: true });
    await page.screenshot({ path: `${SHOTS}/${name}.png` });
    const blocking = (await new AxeBuilder({ page }).analyze()).violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking.map((v) => v.id + v.help)).toEqual([]);
    await travel.click();
    await expect.poll(() => backend.requests.filter((r) => r.path === "/game/action" || r.path === "/game/action/stream").length).toBeGreaterThan(0);
    const sent = backend.requests.filter((r) => r.path.startsWith("/game/action")).slice(-1)[0]!;
    expect(JSON.stringify(sent.body ?? "")).toContain("Viajo para Brumalta");
  });
}

test("mapa: combate desabilita Viajar com razao e a rede nao traz nomes nao descobertos", async ({ page }) => {
  const bodies: string[] = [];
  page.on("response", async (r) => { if (r.url().includes("/game/map")) bodies.push(await r.text()); });
  await openMap(page, view({ travel_gate: { blocked: true, reason: "Em combate: fuga é uma ação do encontro." } }));
  const panel = page.locator("#ws-panel-mapa");
  await panel.getByRole("button", { name: /^Brumalta/ }).click();
  await expect(panel.getByRole("button", { name: /^Viajar/ })).toBeDisabled();
  await expect(panel.getByText("Em combate: fuga é uma ação do encontro.")).toBeVisible();
  // razao de bloqueio legivel (revisao Sol: vermelho puro reprovava contraste no axe)
  const blocking = (await new AxeBuilder({ page }).analyze()).violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking.map((v) => v.id + v.help)).toEqual([]);
  expect(bodies.join("")).not.toContain(SENTINEL);
});

test("mapa: sem rota direta (visitado nao conectado) nao tem botao Viajar habilitado", async ({ page }) => {
  const payload = view();
  (payload.nodes as unknown[]).push({ id: "far", state: "visitado", name: "Longe", coords: { x: 10, y: 10 }, reachable: false,
    reason: "Sem rota direta daqui.", region_id: "x", danger: 2, lore_seed: "Distante", art: { location_id: "far", scope: "placeholder", asset: null } });
  await openMap(page, payload);
  const panel = page.locator("#ws-panel-mapa");
  await panel.getByRole("button", { name: /^Longe, visitado/ }).click();
  await expect(panel.getByRole("button", { name: /^Viajar/ })).toBeDisabled();
  await expect(panel.getByText("Sem rota direta daqui.")).toBeVisible();
});

test("mapa: falha da view cai no legado filtrado por jogo (R12)", async ({ page }) => {
  await openMap(page, { detail: "nope" }, 404);
  await expect(page.locator("#ws-panel-mapa .worldmap")).toBeVisible();
});

// Follow-up SPEC-321: rótulos de nós próximos não se sobrepõem (anti-colisão).
test("mapa: rótulos visíveis de nós vizinhos não se intersectam", async ({ page }) => {
  const payload = view();
  const names = ["Anel de Ferro", "Nova Arcádia", "Pântano da Melancolia", "Anel de Lama", "Pradaria das Ruínas"];
  names.forEach((name, i) => (payload.nodes as unknown[]).push({ id: `n${i}`, state: i % 2 ? "visitado" : "adjacente", name,
    coords: { x: 50 + i * 3, y: 50 + (i % 2) * 2 }, reachable: true, region_id: "x", danger: 1, lore_seed: "x",
    art: { location_id: `n${i}`, scope: "placeholder", asset: null } }));
  await openMap(page, payload);
  const labels = page.locator("#ws-panel-mapa .maptab__node:not(.label-hidden) .worldmap__label");
  await expect(labels.first()).toBeVisible();
  const boxes = [];
  for (const l of await labels.all()) boxes.push((await l.boundingBox())!);
  expect(boxes.length).toBeGreaterThan(1);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j];
    expect(a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height, `rótulos ${i} e ${j} se sobrepõem`).toBe(false);
  }
});
