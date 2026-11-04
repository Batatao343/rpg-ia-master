// SPEC-387 R32: a 390, a barra fixa (Sem matar / Fugir / Encerrar a rodada) não cobre a linha do presságio.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("a linha do presságio não intersecta a barra de envio na rolagem padrão (390)", async ({ page, backend }) => {
  armDeck(backend);
  await openCombat(page);
  const omen = page.locator(".tchip__omen[data-omen='known']").first();
  await expect(omen).toBeVisible();
  const bar = page.locator(".play-queue__end").first();
  await expect(bar).toBeVisible();
  const clear = async () => {
    const [o, b] = [await omen.boundingBox(), await bar.boundingBox()];
    expect(o && b).toBeTruthy();
    if (o && b) {
      const overlap = o.y < b.y + b.height && o.y + o.height > b.y;
      expect(overlap, `presságio ${JSON.stringify(o)} cobre a barra ${JSON.stringify(b)}`).toBe(false);
    }
  };
  await clear(); // rolagem padrão, sem nenhum scroll explícito (SPEC-387 R32 / Sol P3-4)
  await page.evaluate(() => {
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("*"))) {
      if (el.scrollHeight > el.clientHeight + 4 && /(auto|scroll)/.test(getComputedStyle(el).overflowY)) el.scrollTop = el.scrollHeight;
    }
    window.scrollTo(0, document.body.scrollHeight);
  });
  await page.waitForTimeout(150);
  if (await omen.isVisible()) await clear(); // rolado até o fim, o padding reservado importa
  const reserved = await page.locator(".ws-combat").first().evaluate((el) => getComputedStyle(el).paddingBottom);
  expect(parseFloat(reserved)).toBeGreaterThan(0);
});
