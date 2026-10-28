// SPEC-345 R7–R11: layout mobile (360x800) e desktop (1440x900) com o backend fake do e2e.
import type { Page } from "@playwright/test";
import { test, expect, DeterministicBackend } from "./fixtures";

test.describe.configure({ timeout: 90_000 });

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}
const tabBar = (page: Page) => page.getByRole("navigation", { name: "Superfícies" });

function armWounds(backend: DeterministicBackend, leve: number) {
  const state = backend.armCombat("game-a");
  state.combat.wounds.slots = { leve, grave: 2, critico: 2 };
}

test.describe("mobile 360x800", () => {
  test.use({ viewport: { width: 360, height: 800 }, hasTouch: true, isMobile: true });

  test("tabbar_sem_sobreposicao + ponto visivel + alvo de toque", async ({ page, backend }) => {
    backend.armCombat("game-a");
    await openGame(page);
    await expect(tabBar(page).getByRole("button")).toHaveCount(6);
    const rows = await tabBar(page).getByRole("button").evaluateAll((btns) => btns.map((b) => {
      const el = b as HTMLElement;
      const range = document.createRange();
      range.selectNodeContents(el);
      const t = range.getBoundingClientRect();
      const r = el.getBoundingClientRect();
      const dot = el.querySelector(".mtabbar__dot")?.getBoundingClientRect();
      return { fits: el.scrollWidth <= el.clientWidth, left: t.left, right: t.right, w: r.width, h: r.height,
        dotInside: dot ? dot.left >= r.left && dot.right <= r.right && dot.top >= r.top && dot.bottom <= r.bottom : null };
    }));
    expect(rows).toHaveLength(6);
    for (const r of rows) { expect(r.fits).toBe(true); expect(r.w).toBeGreaterThanOrEqual(44); expect(r.h).toBeGreaterThanOrEqual(44); }
    for (let i = 1; i < rows.length; i += 1) expect(rows[i].left - rows[i - 1].right).toBeGreaterThanOrEqual(2);
    expect(rows.filter((r) => r.dotInside !== null).every((r) => r.dotInside)).toBe(true);
  });

  test("cabecalho_lugar_inteiro_em_combate", async ({ page, backend }) => {
    const state = backend.armCombat("game-a");
    state.current_location = "Nova Arcádia"; state.world.location = "Nova Arcádia";
    await openGame(page);
    const place = page.locator(".ws-mhead__place");
    await expect(place).toHaveText(/nova arc/i);
    expect(await place.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await expect(page.locator(".ws-mhead").getByText("Em combate, rodada 1")).toBeAttached();
    await expect(page.locator(".ws-mhead .ws-stat--fight")).toContainText("R1");
  });

  test("primeiro_turno_respira", async ({ page, backend }) => {
    backend.states.get("game-a")!.world.turn_count = 1;
    await openGame(page);
    const banner = page.locator(".banner");
    const hint = page.locator(".onboard");
    await expect(hint).toBeVisible();
    expect(await hint.evaluate((el) => el.tagName)).toBe("DETAILS");
    expect(await hint.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
    const heights = await Promise.all([banner, hint].map(async (l) => ((await l.count()) ? (await l.first().boundingBox())?.height ?? 0 : 0)));
    expect(heights[0] + heights[1]).toBeLessThanOrEqual(240);
    const msg = page.locator(".msg--story").first();
    await expect(msg).toBeInViewport();
  });

  for (const leve of [4, 5]) {
    test(`trilha_ferimentos_uma_linha (leve ${leve})`, async ({ page, backend }) => {
      armWounds(backend, leve);
      await openGame(page);
      await tabBar(page).getByRole("button", { name: "Combate", exact: true }).click();
      const same = await page.locator(".wound-severity__slots").evaluateAll((els) =>
        els.map((el) => new Set(Array.from(el.children).map((c) => (c as HTMLElement).offsetTop)).size));
      expect(same.length).toBeGreaterThan(0);
      for (const n of same) expect(n).toBe(1);
    });
  }

  test("preparacao_sem_faixa", async ({ page, backend }) => {
    backend.states.get("game-a")!;
    await openGame(page);
    await tabBar(page).getByRole("button", { name: "Combate", exact: true }).click();
    const head = page.locator(".deck__head").first();
    await expect(head).toBeVisible(); // falha se o cabeçalho não renderizar
    {
      const [headBg, panelBg] = await head.evaluate((el) => [getComputedStyle(el).backgroundColor,
        getComputedStyle(el.closest(".tabpanel") as Element).backgroundColor]);
      expect(headBg).toBe(panelBg);
      // R7.4: cobre o recuo do painel e não cola no título do Acervo
      const geo = await head.evaluate((el) => ({ mt: parseFloat(getComputedStyle(el).marginTop), pb: parseFloat(getComputedStyle(el).paddingBottom) }));
      expect(geo.mt).toBeLessThan(0);
      expect(geo.pb).toBeGreaterThanOrEqual(6);
      const msg = page.locator(".deck__msg:empty").first();
      await expect(msg).toBeAttached();
      const msgH = await msg.evaluate((el) => el.getBoundingClientRect().height);
      expect(msgH).toBe(0);
    }
  });
});

test.describe("desktop 1440x900", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("desktop_inalterado: chip 'em combate' e onboarding aberto", async ({ page, backend }) => {
    backend.armCombat("game-a");
    backend.states.get("game-a")!.world.turn_count = 1;
    await openGame(page);
    await expect(page.locator(".ws-stat--fight").first()).toContainText("em combate");
    const hint = page.locator(".onboard");
    if (await hint.count()) expect(await hint.first().evaluate((el) => el.tagName)).toBe("ASIDE");
  });
});

// Prints "depois" (opt-in): RPG_SPEC345_PRINTS=1. Nomes iguais aos de docs/spec345/prints/ (fixture backend, sem API real).
test.describe("prints depois (360x800)", () => {
  test.skip(!process.env.RPG_SPEC345_PRINTS, "opt-in");
  test.use({ viewport: { width: 360, height: 800 }, hasTouch: true, isMobile: true });
  const dir = "../docs/spec345/prints/depois/";

  test("prints", async ({ page, backend }) => {
    backend.states.get("game-a")!.world.turn_count = 1;
    await openGame(page);
    await page.screenshot({ path: `${dir}off-360_06-jogo.png` });
    const state = backend.armCombat("game-a", [["e1", "Bandido 1"], ["e2", "Bandido 2"]]);
    state.combat.enemies[0].vitalidade = 0;
    state.combat.wounds.slots = { leve: 4, grave: 2, critico: 2 };
    state.current_location = "Nova Arcádia"; state.world.location = "Nova Arcádia";
    await page.reload();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await expect(page.locator(".ws-mhead .ws-stat--fight")).toBeVisible();
    await page.screenshot({ path: `${dir}on-360_07-conflito-inicio.png` });
    await tabBar(page).getByRole("button", { name: "Combate", exact: true }).click();
    await page.screenshot({ path: `${dir}off-360_08-conflito-painel-mobile.png` });
    await page.locator(".wound-track").first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${dir}on-360_19-r3-pos.png` });
  });
});
