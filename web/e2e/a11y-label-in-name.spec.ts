// SPEC-396: WCAG 2.5.3 (Label in Name) — axe-core 4.14 `label-content-name-mismatch`.
// Cada teste abre uma tela e roda SÓ essa regra; o alvo (seletor) de cada nó aparece na mensagem.
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures";
import { armDeck, openCombat, HAND } from "./deck-342-helpers";

test.beforeEach(({ backend }) => {
  backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
  backend.allowConsole(/ERR_CONNECTION_CLOSED|Failed to load resource/);
});

async function labelInName(page: Page, where: string) {
  const r = await new AxeBuilder({ page }).withRules(["label-content-name-mismatch"]).analyze();
  const nodes = r.violations.flatMap((v) => v.nodes.map((n) => `${n.target.join(" ")} :: ${n.failureSummary?.split("\n").pop()}`));
  expect(nodes, `${where}: ${nodes.join("\n")}`).toEqual([]);
}

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await labelInName(page, "lista de jornadas");
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("topbar com Encerrar sessão e ficha de contexto", async ({ page }) => {
    await openGame(page);
    await expect(page.getByRole("button", { name: "Encerrar sessão" })).toBeVisible();
    await labelInName(page, "topbar");
    await page.getByRole("tab", { name: "Mapa" }).click();
    await labelInName(page, "aba Mapa");
    const ficha = page.getByRole("button", { name: "Fechar ficha" });
    if (await ficha.count()) await labelInName(page, "ficha de contexto");
  });

  test("combate legado: carta armada e alvos", async ({ page, backend }) => {
    const state = backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
    state.combat.cards[0].valid_targets = ["e1"];
    state.combat.cards[0].invalid_reason = null;
    await openGame(page);
    const golpe = page.locator("#ws-panel-combate").getByRole("button", { name: /Jogar Carta Golpe do Véu/ });
    await expect(golpe).toHaveAccessibleName(/^Jogar Carta Golpe do Véu/);
    await labelInName(page, "carta legada");
    await golpe.click();
    const valid = page.locator('#ws-panel-combate [data-target="e1"]');
    await expect(valid).toHaveAccessibleName(/^Alvo: Saqueador/);
    await expect(page.locator('#ws-panel-combate [data-target="e2"]')).toHaveAccessibleName(/alvo inválido/);
    await labelInName(page, "mira");
  });

  test("combate do baralho: descarte, alvo e fila com 2 itens", async ({ page, backend }) => {
    armDeck(backend, { nonlethal: true, hand: HAND.map((c, i) => (i === 1 ? { ...c, descartar_folego: 1 } : c)) });
    await openCombat(page);
    await expect(page.locator(".deck-card[data-card='golpe']")).toHaveAccessibleName(/^Golpe do Véu\s*, 1 de Fôlego/);
    await expect(page.locator(".deck-card[data-card='golpe']")).not.toHaveAccessibleDescription("");
    await expect(page.locator("[data-discard='corte']")).toHaveAccessibleName(/^Descartar \(1 Fôlego\)\s*: Corte Largo/);
    await labelInName(page, "mão do baralho");
    for (const id of ["golpe", "corte"]) {
      await page.locator(`.deck-card[data-card="${id}"]`).dispatchEvent("click");
      await page.locator("button[data-target='e1']").dispatchEvent("click").catch(() => {});
      await labelInName(page, `alvo (${id})`);
      await page.locator("[data-play-confirm]").dispatchEvent("click");
    }
    await expect(page.locator(".play-queue__item")).toHaveCount(2);
    await expect(page.locator("[data-end-turn]")).toHaveAccessibleName("Encerrar a rodada, 2 cartas");
    await expect(page.locator(".play-queue__item").first()).toHaveAccessibleName(/Golpe.*Saqueador/);
    await labelInName(page, "fila");
  });
});

test.describe("celular", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("menu ⋯ com Encerrar sessão", async ({ page }) => {
    await openGame(page);
    await labelInName(page, "topbar celular");
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await expect(page.getByRole("button", { name: "Encerrar sessão" })).toBeVisible();
    await labelInName(page, "menu aberto");
  });
});

test("código de suporte: antes e depois de copiar", async ({ page, backend, context }) => {
  backend.authenticated = false;
  backend.allowConsole(/status of 401/);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]).catch(() => {});
  const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
    ({ status, contentType: "application/json", body: JSON.stringify(body), headers });
  await page.route("**/auth/config", (route) => route.fulfill(json({ required: true, authenticated: false, lifecycle_available: true,
    email_confirmation_required: true, captcha: { required: false, site_key: null, provider: "turnstile" } })));
  await page.route("**/auth/login", (route) => route.fulfill(json(
    { detail: "credentials_invalid", code: "credentials_invalid", request_id: "e2e0req1-aaaa-bbbb-cccc-ddddeeeeffff" },
    401, { "X-Request-ID": "e2e0req1-aaaa-bbbb-cccc-ddddeeeeffff" })));
  await page.goto("/");
  await page.getByLabel("E-mail").fill("alguem@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaErrada123!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  const copy = page.getByRole("button", { name: "Copiar código de suporte" });
  await expect(copy).toBeVisible();
  await labelInName(page, "suporte antes");
  await copy.click();
  await expect(page.locator(".support-code-copy")).toHaveText("Copiado");
  await labelInName(page, "suporte depois");
});
