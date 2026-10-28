// SPEC-354 (390): nada sob a barra fixa (R2) e nunca um id cru na Arena (R9). Sem rolar antes de medir.
import { test, expect } from "./fixtures";
import { armDeck, openCombat, roundLog } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("fila_cheia_sem_sobreposicao_390: 'Desfazer fila' e a nota de 'Sem matar' ficam à vista acima da barra", async ({ page, backend }) => {
  await page.setViewportSize({ width: 390, height: 480 }); // celular baixo: a fila passa da linha da barra fixa
  const state = armDeck(backend, { nonlethal: true, zones: ["Veio de Calcário", "Boca do Abismo", "Ponte Velha"], roundLog: roundLog(8), enemies: [["e1", "Saqueador"], ["e2", "Bandoleiro"], ["e3", "Mercenário"], ["e4", "Arqueiro"]] });
  state.combat.enemies[0].conditions = [{ name: "Sangramento", duration: 2 }] as never;
  await openCombat(page);
  for (const id of ["golpe", "corte"]) {
    await page.locator(`.deck-card[data-card="${id}"]`).dispatchEvent("click");
    await page.locator("button[data-target='e1']").dispatchEvent("click").catch(() => {});
    await page.locator("[data-play-confirm]").dispatchEvent("click");
  }
  await expect(page.locator(".play-queue__item")).toHaveCount(2);
  await page.locator("[data-spare]").dispatchEvent("click");
  await page.waitForTimeout(500);
  const clear = await measure(page.locator(".play-queue__clear--inline"));
  const note = await measure(page.locator(".play-queue__spare"));
  expect(clear.free && clear.inView, JSON.stringify(clear)).toBe(true);
  expect(note.free && note.inView, JSON.stringify(note)).toBe(true);
  const bar = await page.locator(".play-queue__end").boundingBox();
  if (process.env.PROBE) console.log("[fila]", JSON.stringify({ clear, note, bar, st: await page.evaluate(() => [document.scrollingElement?.scrollTop, document.querySelector(".ws-panel")?.scrollTop, document.querySelector(".ws-panel")?.scrollHeight]) }));
  expect(clear.y + clear.h).toBeLessThanOrEqual(bar!.y + 0.5);
  expect(note.y + note.h).toBeLessThanOrEqual(bar!.y + 0.5);
});

test("sem_id_cru_na_arena_390: aliado que só chega como id aparece com nome", async ({ page, backend }) => {
  const state = armDeck(backend);
  state.combat.scene.positions.push({ participant_id: "npc_ketil", participant_name: "npc_ketil", zone_id: "ponte", distance: "proximo",
    posture: "neutro", concealment: "visivel", engaged_with: [], engaged_names: [] } as never);
  await openCombat(page);
  await expect(page.locator('[data-participant="npc_ketil"] strong')).toHaveText("Ketil");
  const raw = await page.locator(".ws-combat").evaluate((root) => {
    const out: string[] = [];
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.textContent ?? ""; if (/\b(npc|enemy|ally|bst)_[a-z0-9_]+\b/.test(t)) out.push(t.trim()); }
    return out;
  });
  expect(raw).toEqual([]);
});
