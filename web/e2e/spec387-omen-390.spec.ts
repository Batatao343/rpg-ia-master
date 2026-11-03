// SPEC-387 R32: a 390, a barra fixa (Sem matar / Fugir / Encerrar a rodada) não cobre a linha do presságio.
import { test, expect } from "./fixtures";
import { armDeck, openCombat } from "./deck-342-helpers";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("a linha do presságio não intersecta a barra de envio na rolagem padrão (390)", async ({ page, backend }) => {
  armDeck(backend);
  await openCombat(page);
  const omen = page.locator(".tchip__omen[data-omen='known']").first();
  await expect(omen).toBeVisible();
  await omen.scrollIntoViewIfNeeded();
  const bar = page.locator(".play-queue__end").first();
  await expect(bar).toBeVisible();
  const [o, b] = [await omen.boundingBox(), await bar.boundingBox()];
  expect(o && b).toBeTruthy();
  if (o && b) {
    const overlap = o.y < b.y + b.height && o.y + o.height > b.y;
    expect(overlap, `presságio ${JSON.stringify(o)} cobre a barra ${JSON.stringify(b)}`).toBe(false);
  }
  const reserved = await page.locator(".ws-combat").first().evaluate((el) => getComputedStyle(el).paddingBottom);
  expect(parseFloat(reserved)).toBeGreaterThan(0);
});
