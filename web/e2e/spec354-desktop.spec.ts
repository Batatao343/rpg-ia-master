// SPEC-354 (1440): mão sem rolar com registro e 2 inimigos (R3), toast no fluxo (R7), alvos de toque (R8). Sem rolar antes de medir.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, panel } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

const base = { ator_id: "player", ator_nome: "Ayla", lado: "heroi", carta_id: "golpe", carta_nome: "Golpe do Véu", alvo_id: "e1", alvo_nome: "Saqueador", origem: "turno", rotulo: null, resultado: "acerto", dano: 5, efeito: null };
const log6 = [
  base,
  { ...base, ator_id: "e1", ator_nome: "Saqueador", lado: "inimigo", carta_id: null, carta_nome: "Talho", alvo_id: "player", alvo_nome: "Ayla", resultado: "erro", dano: null },
  { ...base, carta_nome: "Corte Largo", alvo_id: "e2", alvo_nome: "Bandoleiro", dano: null, efeito: "Sangrando" },
  { ...base, ator_id: "e2", ator_nome: "Bandoleiro", lado: "inimigo", carta_nome: "Talho", alvo_id: "player", alvo_nome: "Ayla", resultado: "critico", dano: 7 },
  { ...base, carta_id: null, carta_nome: "Sangrando", alvo_id: null, alvo_nome: null, rotulo: "Dano contínuo", resultado: "efeito", dano: 1, efeito: "−1 Vitalidade" },
  { ...base, ator_id: "e2", ator_nome: "Bandoleiro", lado: "inimigo", carta_id: null, carta_nome: null, alvo_id: null, alvo_nome: null, resultado: "efeito", dano: null, efeito: "abatido", tipo: "queda" },
];

test.describe("tabuleiro 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("mao_sem_rolar_1440_registro_dois_inimigos", async ({ page, backend }) => {
    const state = armDeck(backend, { zones: ["Veio de Calcário", "Boca do Abismo"], intent: true, scene: true, roundLog: log6 });
    state.combat.enemies[0].conditions = [{ name: "Sangramento", duration: 2 }, { name: "Rachadura", duration: 1 }] as never;
    state.combat.enemies[1].conditions = [{ name: "Medo", duration: 1 }, { name: "Atordoado", duration: 1 }] as never;
    state.combat.player_conditions = [{ name: "Sangrando", dot: 1, duration: 2 }] as never;
    await openCombat(page);
    await expect(page.locator("[data-roundboard]")).toBeVisible();
    expect(await panel(page).evaluate((el) => el.scrollTop)).toBe(0);
    if (process.env.PROBE) console.log("[probe]", JSON.stringify(await page.evaluate(() => {
      const q = (sel: string) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height)]; };
      return { panel: q(".ws-panel"), tabs: q(".ws-tabs"), ctxHead: q(".ws-ctx-head"), strip: q(".scene-strip"), round: q("[data-roundboard]"), arena: q(".arena"), turn: q(".arena__turn"), hand: q(".deck-hand"), card: q(".deck-card"), combat: q(".ws-combat"), omen: q(".tchip") };
    })));
    const first = await measure(page.locator(".deck-card").first());
    expect(first.inView, JSON.stringify(first)).toBe(true);
    expect(first.free, JSON.stringify(first)).toBe(true);
    // uma coluna: nenhuma linha do registro quebra
    for (const h of await page.locator(".roundboard__list:not(.roundboard__list--efeitos) .roundboard__row").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)))) expect(h).toBeLessThan(40);
    await expect(page.getByText("Efeitos da rodada")).toBeVisible();
    await expect(page.getByText("Você sofre Sangrando · −1 Vitalidade")).toBeVisible();
  });
});

test.describe("toast 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("toast_nao_cobre_livro_1440", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await page.locator("#composer").fill("vitória");
    await page.getByRole("button", { name: "Agir" }).click();
    const chip = page.locator(".outcome-chip").first();
    await expect(chip).toBeVisible();
    const clash = await page.evaluate(() => {
      const story = document.querySelector("section.story")!.getBoundingClientRect();
      return [...document.querySelectorAll(".outcome-chip")].some((c) => {
        const r = c.getBoundingClientRect();
        return r.bottom > story.top && r.top < story.bottom && r.right > story.left && r.left < story.right;
      });
    });
    expect(clash, "o chip de ganhos intersecta o Livro").toBe(false);
  });

  test("vitoria_sem_toast_duplicado_1440", async ({ page, backend }) => {
    backend.armCombat("game-a", [["e1", "Saqueador"]]);
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    const tab = page.getByRole("tab", { name: "Combate" });
    if (await tab.count()) await tab.click();
    await page.locator("#composer").fill("ataco");
    await page.getByRole("button", { name: "Lutar", exact: true }).click();
    await expect(page.getByText("Vitória").first()).toBeVisible();
    await page.waitForTimeout(600);
    await expect(page.locator(".outcome-chip")).toHaveCount(0);
  });
});

test.describe("cabeçalho com toque 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 }, isMobile: true, hasTouch: true });

  test("cabecalho_44_coarse_1440", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).dispatchEvent("click");
    await page.locator(".ws-bar").waitFor();
    expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches), "a emulação não deu pointer: coarse").toBe(true);
    const small = await page.evaluate(() => [...document.querySelectorAll(".topbar button, .ws-bar button, .ws-tabs button, .ws-tabs [role=tab]")]
      .map((el) => { const r = el.getBoundingClientRect(); return { t: (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30), w: r.width, h: r.height }; })
      .filter((b) => b.w > 0 && (b.h < 43.5 || b.w < 43.5)));
    expect(small).toEqual([]);
  });
});
