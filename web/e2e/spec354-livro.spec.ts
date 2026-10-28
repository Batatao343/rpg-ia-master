// SPEC-354 Etapa 1 (R1): reabrir um save REAL pela lista de saves (página recém-carregada) abre o Livro no fim.
// A fixture (`fixtures/spec354/save-real.json`) é a gravação de GET /game/saves, /game/state e /game/history
// de um save real (Batatof, 51 entradas); só as imagens de cena foram acrescentadas a 4 narrações para
// reproduzir o carregamento tardio (300 ms por imagem) que o smoke viu.
import { readFileSync } from "node:fs";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";
import { armDeck } from "./deck-342-helpers";

const REAL = JSON.parse(readFileSync(new URL("./fixtures/spec354/save-real.json", import.meta.url), "utf-8"));
const GID: string = REAL.saves[0].game_id;
const ART = "/art/v1/location/ae-camara-seca.a4e7951c75d1.webp";
const THUMB = "/art/v1/location/ae-camara-seca.a4e7951c75d1.thumb.webp";

function withVisuals(entries: Array<Record<string, unknown>>) {
  let seen = 0;
  return entries.map((e) => {
    if (e.role !== "narrator" || (seen++ % 4 !== 0)) return e;
    return { ...e, visual: { subject_name: "Câmara Seca", caption: "Pedra fria", asset: {
      asset_id: `a-${String(e.id)}`, subject_type: "location", subject_id: "camara", title: "Câmara", alt: "Câmara seca", placeholder_color: "#222",
      variants: { thumbnail: { url: THUMB, width: 320, height: 180 }, display: { url: ART, width: 1280, height: 720 } } } } };
  });
}

async function loadSave(page: Page, backend: InstanceType<typeof import("./fixtures").DeterministicBackend>, combat = process.env.SPEC354_COMBAT === "1") {
  backend.saves = REAL.saves;
  backend.states.clear();
  backend.states.set(GID, structuredClone(process.env.SPEC354_SMOKE === "1" ? { ...REAL.smoke_state, game_id: GID } : REAL.state));
  if (combat) { backend.states.set("game-a", backend.states.get(GID)!); armDeck(backend); }
  backend.histories.clear();
  backend.histories.set(GID, withVisuals(REAL.history) as never);
  await page.route("**/art/v1/**", async (route) => { await new Promise((r) => setTimeout(r, 300)); await route.continue(); });
  if (process.env.SPEC354_SLOW === "1") {
    await page.route(/\/game\/(history|state)/, async (route) => { await new Promise((r) => setTimeout(r, 700)); await route.fallback(); });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  }
  // O guard global do fixture ignora rotas de arte reais; nada mais a liberar.
}

async function reopen(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp("^" + REAL.saves[0].name) }).dispatchEvent("click");
  await expect(page.locator("article.msg").last()).toBeAttached();
  await expect(page.locator("article.msg")).toHaveCount(REAL.history.length);
  await page.waitForTimeout(1500);
}

async function bookGeometry(page: Page) {
  return page.locator("section.story").evaluate((s) => {
    const arts = [...s.querySelectorAll("article.msg")];
    const last = arts[arts.length - 1].getBoundingClientRect();
    const box = s.getBoundingClientRect();
    return { top: s.scrollTop, height: s.scrollHeight, client: s.clientHeight,
      gap: s.scrollHeight - s.scrollTop - s.clientHeight, lastVisible: last.bottom > box.top && last.top < box.bottom };
  });
}

test.describe("reabrir save real 1440", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  test("reabrir_save_real_1440", async ({ page, backend }) => {
    await loadSave(page, backend);
    await reopen(page);
    const g = await bookGeometry(page);
    console.log("[354 1440]", JSON.stringify(g));
    expect(g.gap, `scrollTop ${g.top} de ${g.height}`).toBeLessThanOrEqual(48);
    expect(g.lastVisible).toBe(true);
  });
});

test.describe("reabrir save real 390", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  test("reabrir_save_real_390", async ({ page, backend }) => {
    await loadSave(page, backend);
    await reopen(page);
    const chronicle = page.locator("nav.mtabbar").getByRole("button", { name: "Crônica" });
    if (await chronicle.count()) await chronicle.dispatchEvent("click");
    await page.waitForTimeout(500);
    const g = await bookGeometry(page);
    console.log("[354 390]", JSON.stringify(g));
    expect(g.gap, `scrollTop ${g.top} de ${g.height}`).toBeLessThanOrEqual(48);
    expect(g.lastVisible).toBe(true);
  });
});

test.describe("regra SPEC-204 R7", () => {
  test.use({ viewport: { width: 1440, height: 900 } });
  test("subir_e_receber_narracao_nao_puxa", async ({ page, backend }) => {
    await loadSave(page, backend);
    await reopen(page);
    const story = page.locator("section.story");
    await story.hover();
    await page.mouse.wheel(0, -1500);
    await page.waitForTimeout(400);
    const before = await story.evaluate((s) => s.scrollTop);
    expect(before).toBeGreaterThan(0);
    // narração nova chega sem ação do jogador (ex.: resposta tardia); a posição de leitura é preservada
    await page.evaluate(() => {
      const log = document.querySelector("section.story .log")!;
      const art = document.createElement("article"); art.className = "msg msg--story"; art.textContent = "Nova narração tardia."; log.appendChild(art);
    });
    await page.waitForTimeout(300);
    expect(await story.evaluate((s) => s.scrollTop)).toBe(before);
  });
});
