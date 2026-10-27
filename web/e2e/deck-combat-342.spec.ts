// SPEC-342: acabamento do front do combate por cartas (testes de produto; não governados).
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";
import { actions, armDeck, openCombat, HAND } from "./deck-342-helpers";

const card = (page: import("@playwright/test").Page, id: string) => page.locator(`.deck-card[data-card="${id}"]`);

for (const width of [1440, 390]) {
  test.describe(`baralho 342 @${width}`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 }, hasTouch: width === 390, isMobile: width === 390 });

    test("spare reaches request", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await expect(page.locator("[data-spare]")).toHaveCount(1);
      await page.locator("[data-spare]").click();
      await expect(page.locator("[data-spare]")).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText("Nesta rodada, golpes derrubam sem matar.")).toBeVisible();
      for (const id of ["golpe", "corte"]) {
        await card(page, id).click();
        await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
        await page.locator("[data-play-confirm]").click();
      }
      await page.locator("[data-end-turn]").click();
      await expect.poll(() => actions(backend).length).toBe(1);
      const body = actions(backend)[0].body!;
      expect(String(body.input_text)).toMatch(/Sem matar\.$/);
      expect(String(body.input_text)).toMatch(/^Encerro a rodada: Golpe do Véu, Corte Largo\./);
      expect((body.jogadas as unknown[]).length).toBe(2);
    });

    test("single targeting flow: arena is the only selector", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await card(page, "golpe").click();
      await expect(page.locator("[data-target-pick]")).toHaveCount(0);
      await expect(page.locator(".deck-target")).toHaveCount(0);
      await expect(page.locator("button[data-target].is-valid")).toHaveCount(2);
      await expect(page.locator("button[data-target].is-valid").first()).toBeFocused();
      await expect(page.getByText("Mirando Golpe do Véu: escolha o alvo na arena.").first()).toBeVisible();
      await page.getByRole("button", { name: /Alvo: Bandoleiro/ }).click();
      await expect(page.getByText("62 %")).toBeVisible();
      await expect(page.getByText("Seu golpe")).toBeVisible();
      await expect(page.locator("[data-play-confirm]")).toBeFocused();
      await expect(page.locator("[data-play-confirm]")).toHaveText("Jogar em Bandoleiro");
      await page.locator("[data-other-target]").click();
      await expect(page.getByText("Mirando Golpe do Véu: escolha o alvo na arena.").first()).toBeVisible();
      await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
      await page.locator("[data-play-confirm]").click();
      await expect(page.locator(".play-queue__item")).toHaveCount(1);
      await expect(page.locator("button[data-target]")).toHaveCount(0);
    });

    test("ally card targets allies in arena", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await card(page, "cura").click();
      await expect(page.getByRole("button", { name: /Alvo: Ayla/ })).toBeVisible();
      await expect(page.locator("button[data-target].is-valid")).toHaveCount(1);
      await expect(page.locator("[data-play-confirm]")).toBeFocused();
    });

    test("maneuver and card aim are exclusive", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await card(page, "golpe").click();
      await page.locator(".ws-combat__fold summary").click();
      await page.locator("[data-basic='attack']").click();
      await expect(card(page, "golpe")).toHaveAttribute("aria-pressed", "false");
      await expect(page.locator("[data-deck-aim]")).toHaveCount(0);
      await expect(page.locator(".aimbar")).toHaveCount(1);
      await card(page, "corte").click();
      await expect(page.locator("[data-basic='attack']")).toHaveAttribute("aria-pressed", "false");
      await page.keyboard.press("Escape");
      await expect(page.locator(".aimbar")).toHaveCount(0);
    });

    test("scene strip shows cards, objective, clock and next-round omen", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      const strip = page.locator("details.scene-strip");
      await expect(strip.locator("summary")).toContainText("Névoa Cinza do Ermo");
      await expect(strip.locator("summary")).toContainText("Resista até a rodada 6 (faltam 5)");
      await expect(strip.locator("summary")).toContainText("Relógio do Abismo: desperta na rodada 5");
      await expect(page.locator("[data-scene-omen]")).toContainText("Na próxima rodada: a névoa engole os contornos");
      await expect(page.locator("[data-scene-omen]")).toBeVisible();
      await strip.locator("summary").click();
      await expect(strip).toContainText("No Ermo o frio é o Abismo drenando calor.");
      await expect(page.locator(".tchip__omen[data-omen='known']")).toContainText("ergue a lâmina");
      await expect(page.locator(".tchip__omen[data-omen='known']")).toContainText("4–8");
      await expect(page.locator(".tchip__omen[data-omen='veiled']")).toContainText("Intenção velada");
    });

    test("veiled intent only when intent flag on", async ({ page, backend }) => {
      armDeck(backend, { intent: false });
      await openCombat(page);
      await expect(page.locator(".tchip__omen")).toHaveCount(0);
    });

    test("no scene data: strip is only the round", async ({ page, backend }) => {
      armDeck(backend, { scene: false });
      await openCombat(page);
      await expect(page.locator("details.scene-strip")).toHaveCount(0);
      await expect(page.locator("p.scene-strip")).toHaveText("Rodada 1");
    });

    test("focus after arm / single target / remove", async ({ page, backend }) => {
      armDeck(backend, { enemies: [["e1", "Saqueador"]] });
      await openCombat(page);
      await card(page, "golpe").click();
      await expect(page.locator("[data-play-confirm]")).toBeFocused(); // 1 alvo: direto no "Jogar em X"
      await page.locator("[data-play-confirm]").click();
      await card(page, "corte").click();
      await page.locator("[data-play-confirm]").click();
      await page.locator(".play-queue__item").first().click();
      await page.getByRole("button", { name: "Cancelar Golpe do Véu" }).click();
      await expect(page.locator(".play-queue__item").first()).toBeFocused();
      await page.locator(".play-queue__item").first().click();
      await page.getByRole("button", { name: "Cancelar Corte Largo" }).click();
      await expect(page.locator(".deck-card").first()).toBeFocused();
    });

    test("end during busy keeps focus (aria-disabled)", async ({ page, backend }) => {
      armDeck(backend, { enemies: [["e1", "Saqueador"]] });
      await openCombat(page);
      await expect(page.locator("[data-end-turn]")).toHaveAttribute("aria-disabled", "true");
      await expect(page.locator("[data-end-turn]")).not.toHaveAttribute("disabled", "");
    });

    test("all blocked opens maneuvers", async ({ page, backend }) => {
      armDeck(backend, { hand: [{ ...HAND[0], jogavel: false }] });
      await openCombat(page);
      await expect(page.getByText("Nenhuma carta responde agora. Recorra às manobras abaixo, ou passe a vez.")).toBeVisible();
      await expect(page.locator(".ws-combat__fold")).toHaveAttribute("open", "");
      await page.locator(".ws-combat__fold summary").click();
      await expect(page.locator(".ws-combat__fold")).not.toHaveAttribute("open", "");
    });

    test("pilhas explain exaurida", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      const piles = page.locator(".deck-hand__piles");
      await expect(piles).toContainText("Compra 8 · Descarte 2 · Exaurida 1");
      await piles.click();
      await expect(piles).toHaveAttribute("aria-expanded", "true");
      await page.getByRole("button", { name: "Exaurida", exact: true }).click();
      await expect(page.getByText("Exaurida: cartas gastas que só voltam depois do conflito ou de um descanso.")).toBeVisible();
    });

    test("axe: no serious/critical in combat", async ({ page, backend }) => {
      armDeck(backend);
      await openCombat(page);
      await card(page, "golpe").click();
      const results = await new AxeBuilder({ page }).include(".ws-combat").analyze();
      const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  });
}

test.describe("baralho 342 mobile 390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("mobile budget 390: <= 12 interactive and first card whole", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    const count = await page.evaluate(() => {
      const root = document.querySelector(".ws-combat")!;
      const vw = window.innerWidth;
      const els = Array.from(root.querySelectorAll<HTMLElement>("button, summary, a[href], input, select, textarea, [tabindex]:not([tabindex='-1'])"));
      return els.filter((el) => {
        const d = el.closest("details");
        if (d && !d.open && el.tagName !== "SUMMARY") return false;
        if (el.closest("[hidden]")) return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.right > 0 && r.left < vw;
      }).length;
    });
    expect(count).toBeLessThanOrEqual(12);
    await expect(page.locator(".deck-card").first()).toBeInViewport({ ratio: 1 });
  });

  test("end bar sticky 390", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await page.locator("[data-end-turn]").scrollIntoViewIfNeeded();
    await page.locator(".ws-panel:visible, [role=region][aria-label=Combate]").first().evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await expect(page.locator("[data-end-turn]")).toBeInViewport();
  });

  test("coarse targets >= 44", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await card(page, "golpe").click();
    await page.getByRole("button", { name: /Alvo: Saqueador/ }).click();
    await page.locator("[data-play-confirm]").click();
    await page.locator(".play-queue__item").first().click();
    const small = await page.evaluate(() => {
      const sel = [".deck-hand__piles", ".deck-hand__list button", ".play-queue__item", ".play-queue__ops button", ".play-queue__clear",
        ".play-queue__submit", ".mech-log summary", ".ws-combat__fold summary", ".scene-strip summary", ".play-queue__end .actionchip"];
      const out: string[] = [];
      for (const s of sel) for (const el of document.querySelectorAll(`.ws-combat ${s}`)) {
        const r = el.getBoundingClientRect();
        if (r.width && (r.width < 43.5 || r.height < 43.5)) out.push(`${s}: ${r.width.toFixed(1)}x${r.height.toFixed(1)}`);
      }
      return out;
    });
    expect(small).toEqual([]);
  });

  test("touch tap arms si card and shows rules in aimbar", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    await card(page, "folego").tap();
    await expect(page.locator("[data-deck-aim]")).toBeVisible();
    await expect(page.locator("[data-card-rules]")).toContainText("Recupera o ritmo.");
    await expect(page.locator(".play-queue__item")).toHaveCount(0);
    await page.locator("[data-play-confirm]").tap();
    await expect(page.locator(".play-queue__item")).toHaveCount(1);
    await card(page, "golpe").tap();
    await expect(page.locator("[data-card-rules]")).toContainText("Sangria");
    await expect(page.locator("[data-card-rules]")).toContainText("Causa 1 de dano por rodada");
    await expect(page.locator(".kw__tip")).toHaveCount(0);
  });

  test("hand rail shows >= 2 cards", async ({ page, backend }) => {
    armDeck(backend);
    await openCombat(page);
    const n = await page.evaluate(() => Array.from(document.querySelectorAll(".deck-card")).filter((c) => {
      const r = c.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth;
    }).length);
    expect(n).toBeGreaterThanOrEqual(2);
  });
});

test.describe("baralho 342 desktop", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("keyword tip inside viewport", async ({ page, backend }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    armDeck(backend);
    await openCombat(page);
    await page.locator(".deck-card[data-card='golpe'] [data-keyword='Sangria']").hover();
    const tip = page.locator("[role=tooltip]");
    await expect(tip).toBeVisible();
    const box = (await tip.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(360);
    const inRail = await tip.evaluate((el) => !!el.closest(".deck-hand__rail"));
    expect(inRail).toBe(false);
  });

  test("shortcuts inert when combat tab hidden; listed in the sheet", async ({ page, backend }) => {
    armDeck(backend, { enemies: [["e1", "Saqueador"]] });
    await openCombat(page);
    await page.getByRole("tab", { name: "Personagem" }).click();
    await page.keyboard.press("1");
    await expect(page.locator(".deck-card[data-card='golpe']")).toHaveAttribute("aria-pressed", "false");
    await page.getByRole("tab", { name: "Combate" }).click();
    await page.keyboard.press("1");
    await expect(page.locator(".deck-card[data-card='golpe']")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("Escape");
    await page.getByRole("tab", { name: "Combate" }).focus();
    await page.keyboard.press("?");
    await expect(page.getByText("No combate com Baralho")).toBeVisible();
  });

  test("loot badge on tab", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.player_stats.espolio_pendente = { id: "esp1", origem: "vitoria", recusa_ouro: 5, ofertas: [
      { id: "c1", name: "Estocada", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "**Sangria** 1.", descricao: "", conhecida: false },
    ] } as never;
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("tab", { name: /espólio à espera/ })).toBeVisible();
    await page.getByRole("tab", { name: /Combate/ }).click();
    await expect(page.locator("article.combat-card.espolio__card")).toHaveCount(1);
    await expect(page.getByRole("tab", { name: /espólio à espera/ })).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 3, name: "Espólio" })).toBeVisible();
  });

  test("forge confirm inline + Esc restores focus", async ({ page, backend }) => {
    const state = backend.states.get("game-a")!;
    state.player_stats.forja = {
      permitido: true, motivo: "", baralho_min: 3,
      baralho: [{ id: "golpe", name: "Golpe do Véu", copias: 1, esquecivel: true }],
      esquecer: { descanso: true, templo: true, ouro: 30 }, afiar: { material: null, afiaveis: [], afiadas: [] },
      purgar: { medico: true, templo: true, ouro: 20 }, cicatrizes: [],
    } as never;
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await page.getByRole("tab", { name: /Combate/ }).click();
    await page.locator("[data-forja-row='golpe']").click();
    const forget = page.locator("[data-forja-forget='golpe:descanso']");
    await forget.click();
    await expect(page.getByText("Golpe do Véu sai do Baralho (segue no Acervo).")).toBeVisible();
    expect(actions(backend)).toHaveLength(0);
    await expect(page.locator("[data-forja-confirm]")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.locator("[data-forja-confirm]")).toHaveCount(0);
    await expect(forget).toBeFocused();
    await expect(page.getByRole("heading", { level: 3, name: "Forja do Baralho" })).toBeVisible();
  });
});
