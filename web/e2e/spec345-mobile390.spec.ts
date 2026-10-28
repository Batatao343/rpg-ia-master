// SPEC-345 R14/R15 (P3 da 342): mira visível sem rolar e faixa de cena legível a 390 px.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("mira_visivel_sem_rolar: 'Mirando' não fica sob a barra fixa no 1º paint", async ({ page, backend }) => {
  armDeck(backend, { scene: true, intent: true });
  await openCombat(page);
  await page.locator('.deck-card[data-card="golpe"]').click();
  const bar = page.locator(".aimbar").first();
  await expect(bar).toBeVisible();
  // SEM rolar antes de medir: o ponto central da mira tem de pertencer à própria mira.
  const hit = await bar.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(r.height / 2, 12));
    return { inside: !!top && el.contains(top), inView: r.top >= 0 && r.bottom <= window.innerHeight };
  });
  expect(hit).toEqual({ inside: true, inView: true });
});

test("faixa_de_cena_legivel: só rodada + relógio, sem truncar", async ({ page, backend }) => {
  armDeck(backend, { scene: true });
  await openCombat(page);
  const spans = page.locator(".scene-strip summary > span:visible");
  await expect(spans.first()).toBeVisible();
  const rows = await spans.evaluateAll((els) => els.map((e) => ({ t: e.textContent ?? "", ok: e.scrollWidth <= e.clientWidth })));
  expect(rows.length).toBeLessThanOrEqual(2);
  expect(rows[0].t).toMatch(/^Rodada \d+/);
  for (const r of rows) expect(r.ok, r.t).toBe(true);
});

test("tabbar_h_definido_no_mobile: o scroll-margin da mira inclui a barra de superfícies", async ({ page, backend }) => {
  armDeck(backend, { scene: true });
  await openCombat(page);
  const px = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.style.height = "var(--tabbar-h)";
    document.body.appendChild(probe);
    const h = probe.getBoundingClientRect().height;
    probe.remove();
    return h;
  });
  expect(px).toBeGreaterThanOrEqual(48);
});
