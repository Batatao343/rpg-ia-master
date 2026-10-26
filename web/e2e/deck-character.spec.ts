// SPEC-209: aba Combate fora de encontro (deck) e aba Personagem (ficha/Jornada). Testes do executor —
// a autoria das jornadas F de eval é separada (handoffs/SPEC-209-eval-authoring.md).
import AxeBuilder from "@axe-core/playwright";
import { test, expect, openFicha } from "./fixtures";
import type { DeterministicBackend } from "./fixtures";
import type { Page } from "@playwright/test";
import type { CardView } from "../src/types";

const mk = (id: string, name: string, over: Partial<CardView> = {}): CardView => ({
  id, name, type: "ativa", description: `${name} de teste`, effect_kind: "damage", target_kind: "enemy",
  subclass: "", prepared: false, cost: 2, base_cost: 2, frequency: "turno", spent: false, ready: false,
  has_rupture: false, rupture_ready: false, trigger: "", evolved: null, ...over,
});

function seed(backend: DeterministicBackend, over: { allowed?: boolean; reason?: string } = {}) {
  const ps = backend.states.get("game-a")!.player_stats;
  ps.cards = [
    mk("golpe", "Golpe do Véu", { prepared: true, has_rupture: true }),
    mk("fenda", "Fenda", { cost: 3, base_cost: 2 }),
    mk("aparar", "Aparar", { type: "reacao", trigger: "ao_ser_alvo" }),
    mk("ecos", "Ecos", { type: "passiva", frequency: "livre", cost: 0 }),
  ];
  ps.prepared_slots = 2;
  ps.can_reorganize = { allowed: over.allowed ?? true, reason: over.reason ?? "" };
  ps.scars = [{ id: "s1", origem: "Queda em Vorr", consequencia_negativa: "Tremor na mão", habilidade_positiva_relacionada: "Olhar frio" }];
  backend.states.get("game-a")!.chronicle = [{ chapter_id: "c1", title: "Cap", started_turn: 0, location: "Porto",
    entries: [{ text: "O herói alcançou o nível 2.", turn: 1, kind: "milestone" }, { text: "Ayla chegou.", turn: 0, kind: "milestone" }] }];
}

async function open(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: "Combate" }).click();
}

// SPEC-216: < 900px é uma superfície por vez (barra "Superfícies"); >= 900px seguem as abas do painel.
async function goSurface(page: Page, name: "Combate" | "Personagem") {
  if ((page.viewportSize()?.width ?? 1440) < 900) {
    await page.getByRole("navigation", { name: "Superfícies" }).getByRole("button", { name, exact: true }).click();
  } else {
    await page.getByRole("tab", { name }).click();
  }
}

const card = (page: Page, name: string) => page.getByRole("button", { name: new RegExp(`^${name},`) });

async function a11y(page: Page) {
  const r = await new AxeBuilder({ page }).analyze();
  const bad = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(bad, bad.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

test.describe("deck fora de encontro", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("prepara, respeita o limite e sobrevive a reload", async ({ page, backend }) => {
    seed(backend);
    await open(page);
    await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("1/2");
    await expect(card(page, "Golpe do Véu").first()).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("(base 2)").first()).toBeVisible(); // custo real != base, vindo do servidor
    await card(page, "Fenda").last().click();
    await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("2/2");
    // limite: a terceira fica indisponível com razão textual e NÃO chama o servidor
    const before = backend.requests.filter((r) => r.path === "/game/cards/prepare").length;
    const aparar = card(page, "Aparar").last();
    await expect(aparar).toHaveAttribute("aria-disabled", "true");
    await expect(aparar).toContainText("limite de 2");
    await aparar.click({ force: true });
    expect(backend.requests.filter((r) => r.path === "/game/cards/prepare").length).toBe(before);
    await page.reload();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await page.getByRole("tab", { name: "Combate" }).click();
    await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("2/2");
  });

  test("servidor recusa: rollback e erro anunciado em aria-live", async ({ page, backend }) => {
    seed(backend);
    backend.allowConsole(/status of 409/);
    await page.route("**/game/cards/prepare", (route) =>
      route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Local perigoso demais." }) }));
    await open(page);
    await card(page, "Fenda").last().click();
    await expect(page.locator(".deck__msg")).toContainText("Local perigoso demais.");
    await expect(card(page, "Fenda").last()).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("1/2");
  });

  test("não autorizado: controles desabilitados com a razão do servidor", async ({ page, backend }) => {
    seed(backend, { allowed: false, reason: "Local perigoso demais (apex) para reorganizar as Cartas." });
    await open(page);
    await expect(page.locator(".deck__note")).toContainText("apex");
    const fenda = card(page, "Fenda").last();
    await expect(fenda).toHaveAttribute("aria-disabled", "true");
    const before = backend.requests.filter((r) => r.path === "/game/cards/prepare").length;
    await fenda.click({ force: true });
    expect(backend.requests.filter((r) => r.path === "/game/cards/prepare").length).toBe(before);
  });

  test("teclado: setas movem o foco e Enter prepara", async ({ page, backend }) => {
    seed(backend);
    await open(page);
    await card(page, "Golpe do Véu").first().focus();
    await page.keyboard.press("ArrowRight");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("data-deck-card"));
    expect(focused).not.toBeNull();
    await card(page, "Fenda").last().focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("2/2");
    await a11y(page);
  });

  test("em combate o deck some e a mão tática assume", async ({ page, backend }) => {
    seed(backend);
    backend.armCombat("game-a");
    await open(page);
    await expect(page.locator(".deck")).toHaveCount(0);
  });
});

test.describe("personagem", () => {
  for (const [w, h] of [[1440, 900], [390, 844]] as const) {
    test(`ficha com cicatrizes e Jornada (${w}px)`, async ({ page, backend }) => {
      await page.setViewportSize({ width: w, height: h });
      seed(backend);
      await page.goto("/");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).click();
      if (w < 700) await openFicha(page);
      await goSurface(page, "Personagem");
      await expect(page.getByText("Cicatrizes")).toBeVisible();
      await expect(page.getByText("Tremor na mão")).toBeVisible();
      await expect(page.locator(".char-portrait")).toBeVisible(); // fallback honesto (sem retrato gerado)
      await a11y(page);
      await page.getByRole("tab", { name: /Jornada/ }).click();
      await expect(page.getByText("O herói alcançou o nível 2.")).toBeVisible();
      await expect(page.getByText("Ayla chegou.")).toHaveCount(0); // só marcos de evolução
      await a11y(page);
    });
  }
});

// --- Revisão Sol: critérios restantes (axe 320/768, split 50% sem scroll aninhado, R13, evidência) ---
const EVIDENCE = "../docs/spec209/evidence";

/** R13: dentro do painel de contexto, no máximo UMA região rolável com conteúdo excedente. */
async function scrollRegions(page: Page) {
  return page.evaluate(() => {
    const root = document.querySelector(".ws-ctx") ?? document.body;
    return Array.from(root.querySelectorAll<HTMLElement>("*")).filter((el) => {
      const oy = getComputedStyle(el).overflowY;
      return (oy === "auto" || oy === "scroll") && el.scrollHeight > el.clientHeight + 1;
    }).map((el) => el.className || el.tagName);
  });
}

async function openTab(page: Page, w: number, tab: "Combate" | "Personagem") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  if (w >= 900 && w < 1000) await openFicha(page); // < split: painel único
  await goSurface(page, tab);
}

for (const [w, h] of [[320, 720], [768, 1024]] as const) {
  test(`axe sem serious/critical nas duas abas (${w}px)`, async ({ page, backend }) => {
    await page.setViewportSize({ width: w, height: h });
    seed(backend);
    await openTab(page, w, "Combate");
    await expect(page.getByRole("heading", { name: /Preparação/ })).toBeVisible();
    await a11y(page);
    await goSurface(page, "Personagem");
    await expect(page.getByText("Cicatrizes")).toBeVisible();
    await a11y(page);
    await page.getByRole("tab", { name: /Jornada/ }).click();
    await a11y(page);
  });
}

test("split 50%: uma única região rolável por aba + evidência 1440", async ({ page, backend }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  seed(backend);
  const ps = backend.states.get("game-a")!.player_stats;
  ps.cards = [...ps.cards, ...Array.from({ length: 14 }, (_, i) => mk(`extra${i}`, `Extra ${i}`))]; // força overflow
  await openTab(page, 1440, "Combate");
  await expect(page.getByRole("separator", { name: "Redimensionar chat e painel" })).toHaveAttribute("aria-valuenow", "50");
  const deck = await scrollRegions(page);
  expect(deck.length, deck.join(" | ")).toBeLessThanOrEqual(1);
  if (process.env.RPG_SPEC209_SHOTS) await page.screenshot({ path: `${EVIDENCE}/1440-split50-combate.png`, scale: "css" });
  await page.getByRole("tab", { name: "Personagem" }).click();
  await expect(page.getByText("Cicatrizes")).toBeVisible();
  const sheet = await scrollRegions(page);
  expect(sheet.length, sheet.join(" | ")).toBeLessThanOrEqual(1);
  if (process.env.RPG_SPEC209_SHOTS) await page.screenshot({ path: `${EVIDENCE}/1440-split50-personagem.png`, scale: "css" });
});

test("evidência 390: deck e ficha", async ({ page, backend }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  seed(backend);
  await openTab(page, 390, "Combate");
  await expect(page.getByRole("heading", { name: /Preparação/ })).toBeVisible();
  if (process.env.RPG_SPEC209_SHOTS) await page.screenshot({ path: `${EVIDENCE}/390-combate.png`, scale: "css" });
  await goSurface(page, "Personagem");
  await expect(page.getByText("Cicatrizes")).toBeVisible();
  if (process.env.RPG_SPEC209_SHOTS) await page.screenshot({ path: `${EVIDENCE}/390-personagem.png`, scale: "css" });
});

test("R13: 'atualizando…' enquanto o servidor não confirma, some depois", async ({ page, backend }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  seed(backend);
  let release!: () => void;
  const gate = new Promise<void>((r) => { release = r; });
  await page.route("**/game/cards/prepare", async (route) => { await gate; await route.fallback(); });
  await openTab(page, 1440, "Combate");
  await card(page, "Fenda").last().click();
  await expect(page.locator(".deck__sync")).toContainText("atualizando…");
  await expect(card(page, "Aparar").last()).toHaveAttribute("aria-disabled", "true"); // sem 2º envio concorrente
  release();
  await expect(page.locator(".deck__sync")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Preparação/ })).toContainText("2/2");
});
