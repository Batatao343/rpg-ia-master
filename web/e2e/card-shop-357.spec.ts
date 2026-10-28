// SPEC-357 Etapa 6: painel "Técnicas à venda" (aba Combate fora de encontro). Preço/bloqueio vêm do servidor.
import { test, expect } from "./fixtures";

const oferta = (id: string, name: string, preco: number, extra: Record<string, unknown> = {}) => ({
  id, name, raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "Causa 2.", descricao: "Um golpe de cais.",
  conhecida: false, preco, destino: "baralho", bloqueio: null, ...extra,
});

function loja() {
  return {
    merchant_id: "quinquilharias_brekmar", merchant_name: "Quinquilharias da Maré", renova_em_dias: 2, motivo: null,
    ofertas: [
      oferta("neu1_br_a", "Sabre de Pirata", 40),
      oferta("neu1_br_b", "Arpão de Osso", 45, { bloqueio: "Faltam 15 de ouro." }),
      oferta("neu1_ge_c", "Lanterna de Aranha", 50, { conhecida: true, bloqueio: "Você já conhece essa Carta." }),
    ],
  };
}

async function open(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: /Combate/ }).or(page.getByRole("button", { name: /^Combate/ })).first().click();
}

test("loja_cartas_painel_e_compra: 3 ofertas, bloqueio visível e POST com card_id", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.player_stats.loja_cartas = loja() as never;
  let posted: Record<string, unknown> | null = null;
  await page.route("**/game/loja-cartas", async (route) => {
    posted = route.request().postDataJSON();
    const s = backend.states.get("game-a")!;
    const l = loja();
    l.ofertas[0] = { ...l.ofertas[0], conhecida: true, bloqueio: "Você já conhece essa Carta." } as never;
    s.player_stats.loja_cartas = l as never;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, log: "Sabre de Pirata entra no seu Acervo e no Baralho.", player_stats: {} }) });
  });
  await open(page);
  const panel = page.getByRole("region", { name: "Técnicas à venda" });
  await expect(panel.locator("article.combat-card")).toHaveCount(3);
  await expect(panel.locator("[data-loja-buy='neu1_br_b']")).toBeDisabled();
  await expect(panel.locator("[data-loja-buy='neu1_br_b']")).toHaveText("Faltam 15 de ouro.");
  await expect(panel.locator("[data-loja-buy='neu1_ge_c']")).toBeDisabled();
  const buy = panel.locator("[data-loja-buy='neu1_br_a']");
  await expect(buy).toHaveText("Comprar por 40 de ouro");
  await buy.click();
  await expect(panel.getByRole("status")).toContainText("Sabre de Pirata entra no seu Acervo");
  expect((posted as { card_id?: string } | null)?.card_id).toBe("neu1_br_a");
  await expect(panel.locator("[data-loja-buy='neu1_br_a']")).toBeDisabled();
  await expect(panel.locator("[data-loja-buy='neu1_br_b']")).toHaveText("Faltam 15 de ouro.");
});

test("loja_cartas_ausente: sem o bloco, sem painel", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("region", { name: "Técnicas à venda" })).toHaveCount(0);
});

test.describe("mobile 390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  test("loja_cartas_mobile: sem rolagem horizontal", async ({ page, backend }) => {
    backend.states.get("game-a")!.player_stats.loja_cartas = loja() as never;
    await open(page);
    await expect(page.getByRole("region", { name: "Técnicas à venda" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
