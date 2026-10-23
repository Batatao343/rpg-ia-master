// SPEC-211: dossiês do Codex e do Bestiário. Testes do executor — as jornadas oficiais são
// autoria de eval (handoffs/SPEC-211-eval-authoring.md).
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

async function assertA11y(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

const stamp = (kind: string, label: string, turn = 4) => ({
  knowledge_kind: kind, certainty: "reported", source_kind: "npc_claim", source_ref: "npc:npc_grum",
  label, first_seen_turn: 1, last_updated_turn: turn, stale: false,
});

const payload = (npcVersion = 4) => ({
  version: npcVersion, generated_at_turn: 5,
  sections: {
    npcs: [{
      id: "npc_grum", kind: "npc", title: "Grum", last_updated_turn: npcVersion, version: npcVersion, art: null,
      knowledge: stamp("fact", "Fato confirmado"), notes: [],
      role: "Ferreiro", location: "Nova Arcádia", status: "", attitude_label: "amistoso",
      knowledge_source: "met", revealed_traits: [],
      claims: [{ text: "Forja lâminas para a guarda.", knowledge: stamp("perception", "Percepção") }],
      appears_to_know: [{ text: "Viu você entrar na ferraria.", knowledge: stamp("perception", "Percepção") }],
      encounters: [{ turn: 2, location_id: "", outcome: "primeiro contato" }],
      last_seen_turn: 4,
      body: "Ferreiro <img src=x onerror=window.__xss=1> **honesto**.",
    }],
    locations: [], factions: [], secrets: [], chronicle_index: [],
  },
  bestiary: [
    { id: "enemy_rato", kind: "creature", title: "Rato da Peste", last_updated_turn: 3, version: 3, art: null,
      knowledge: stamp("fact", "Fato confirmado"), notes: [], tier: 2, tier_name: "Encontrada",
      regions: ["nova_arcadia"], first_seen_turn: 1, description: "Roedor inchado.", type: "Minion" },
  ],
  meta: { taxonomy_version: 1 },
});

async function openPeople(page: Page) {
  await page.getByRole("tab", { name: "Codex" }).first().click();
  await page.getByRole("tablist", { name: "Seções do Codex" }).getByRole("tab", { name: /Pessoas/ }).click();
}

test.describe("dossiês 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("Pessoas: lista, dossiê, Esc volta, reload mantém aberto, sem XSS", async ({ page, backend }) => {
    backend.dossiers = payload();
    await openGame(page);
    await openPeople(page);
    const row = page.getByRole("button", { name: /Grum/ });
    await expect(row.getByText("Novo")).toBeVisible();
    await row.click();
    const dossier = page.getByRole("article", { name: "Dossiê: Grum" });
    await expect(dossier).toBeVisible();
    await expect(dossier.getByText("Relação:")).toContainText(/amistoso/i);
    await expect(dossier.getByText("O que ele parece saber")).toBeVisible();
    await expect(dossier.getByText("Viu você entrar na ferraria.")).toBeVisible();
    await expect(dossier.getByTestId("dossier-no-art")).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
    await assertA11y(page);
    // Esc volta para a lista sem fechar o painel de contexto
    await page.keyboard.press("Escape");
    await expect(dossier).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Painel de contexto" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Grum/ }).getByText("Novo")).toHaveCount(0);
    // reload mantém o dossiê aberto
    await page.getByRole("button", { name: /Grum/ }).click();
    await page.reload();
    await openGame(page);
    await openPeople(page);
    await expect(page.getByRole("article", { name: "Dossiê: Grum" })).toBeVisible();
  });

  test("versão maior => Atualizado", async ({ page, backend }) => {
    backend.dossiers = payload(4);
    await openGame(page);
    await openPeople(page);
    await page.getByRole("button", { name: /Grum/ }).click();
    await page.getByRole("button", { name: /Voltar à lista/ }).click();
    backend.dossiers = payload(9);
    await page.reload();
    await openGame(page);
    await openPeople(page);
    await expect(page.getByRole("button", { name: /Grum/ }).getByText("Atualizado")).toBeVisible();
  });

  test("Bestiário em dossiês e nenhum dado fora do tier no DOM", async ({ page, backend }) => {
    backend.dossiers = payload();
    await openGame(page);
    await page.getByRole("tab", { name: "Bestiário" }).click();
    const row = page.getByRole("button", { name: /Rato da Peste/ });
    await expect(row).toBeVisible();
    await row.click();
    const dossier = page.getByRole("article", { name: "Dossiê: Rato da Peste" });
    await expect(dossier.getByText("Roedor inchado.")).toBeVisible();
    await expect(dossier.getByText(/HP /)).toHaveCount(0);
    await expect(page.locator("[title*='Roedor'], [data-hidden]")).toHaveCount(0);
  });

  test("endpoint novo falha => cai para o Codex antigo sem erro", async ({ page, backend }) => {
    backend.dossiers = null;
    await page.route("**/game/codex/dossiers**", (route) => route.fulfill({ status: 500, body: "{}" }));
    backend.allowConsole(/500|Failed to load resource/);
    backend.unexpectedAllowed.push(/\/game\/codex\/dossiers/);
    await openGame(page);
    await page.getByRole("tab", { name: "Bestiário" }).click();
    await expect(page.getByText("Nenhuma criatura registrada ainda.")).toBeVisible();
  });
});

test.describe("dossiês split ~50% / mobile", () => {
  test.use({ viewport: { width: 1100, height: 800 } });

  test("alvo >= 44px e teclado na lista", async ({ page, backend }) => {
    backend.dossiers = payload();
    await openGame(page);
    await openPeople(page);
    const row = page.getByRole("button", { name: /Grum/ });
    const box = await row.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    await row.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("article", { name: "Dossiê: Grum" })).toBeVisible();
    await assertA11y(page);
  });
});
