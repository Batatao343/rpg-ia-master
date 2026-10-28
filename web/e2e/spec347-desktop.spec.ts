// SPEC-347 Etapa 2/3 (1440): Arena compacta, tooltip fora dos controles, desfecho no topo. Sem rolar antes de medir.
import { test, expect } from "./fixtures";
import { actions, armDeck, openCombat, panel, roundLog } from "./deck-342-helpers";
import { measure } from "./spec347-helpers";

test.use({ viewport: { width: 1440, height: 900 } });

test("arena_tres_zonas_1440: chips legíveis e a 1ª carta inteira no painel sem rolar", async ({ page, backend }) => {
  const state = armDeck(backend, { zones: ["Veio de Calcário", "Boca do Abismo"], intent: true, scene: true, roundLog: roundLog(4) });
  state.combat.enemies[0].conditions = [{ name: "Sangramento", duration: 2 }, { name: "Rachadura", duration: 1 }] as never;
  state.combat.enemies[1].conditions = [{ name: "Medo", duration: 1 }, { name: "Atordoado", duration: 1 }] as never;
  await openCombat(page);
  const chips = page.locator(".arena--compact .tchip");
  await expect(chips.first()).toBeVisible();
  for (const box of await chips.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().width))) expect(box).toBeGreaterThanOrEqual(224);
  for (const lines of await page.locator(".tchip__vit").evaluateAll((els) => els.map((e) => e.getClientRects().length))) expect(lines).toBe(1);
  await expect(page.locator(".arena__empty-zones")).toContainText("Também na cena: Veio de Calcário · Boca do Abismo");
  expect(await panel(page).evaluate((el) => el.scrollTop)).toBe(0);
  const first = await measure(page.locator(".deck-card").first());
  expect(first.inView, JSON.stringify(first)).toBe(true);
});

test("rodada_uma_vez_e_sem_zero: iniciativa honesta no Baralho", async ({ page, backend }) => {
  const state = armDeck(backend, {});
  state.combat.order = [{ name: "Heróis", side: "hero", init: 0 }, { name: "Inimigos", side: "enemy", init: 0 }];
  await openCombat(page);
  await expect(page.locator(".arena__turn")).toHaveText(/^Na última rodada, (Heróis|Inimigos) agiram primeiro\.$/);
  const text = await page.locator(".ws-combat").first().textContent() ?? "";
  expect((text.match(/Rodada/g) ?? []).length).toBe(1);
  expect(text).not.toMatch(/\b0 · (Heróis|Inimigos)/);
});

test("off_iniciativa_honesta: sem 'Rodada N · iniciativa' nem '0 ·' com o Baralho desligado", async ({ page, backend }) => {
  const state = backend.armCombat("game-a", [["e1", "Saqueador"]]);
  state.combat.order = [{ name: "Heróis", side: "hero", init: 0 }, { name: "Inimigos", side: "enemy", init: 0 }];
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
  const tab = page.getByRole("tab", { name: "Combate" });
  if (await tab.count()) await tab.click();
  await expect(page.locator(".arena__turn")).toHaveText("Na última rodada, Heróis agiram primeiro.");
  const body = (await page.locator("body").textContent()) ?? "";
  expect(body).not.toMatch(/iniciativa:/);
  expect(body).not.toMatch(/\b0 · (Heróis|Inimigos)/);
  await expect(page.locator(".initiative")).toHaveCount(0);
});

test("tooltip_nao_cobre_botao: o tooltip do Espólio abre acima e não intersecta os botões da carta", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.player_stats.espolio_pendente = { id: "esp1", origem: "vitoria", recusa_ouro: 5, ofertas: [
    { id: "c1", name: "Estocada", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "Causa 2. **Sangria** 1.", descricao: "", conhecida: false },
    { id: "c2", name: "Aparar", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "**Rachadura** no alvo.", descricao: "", conhecida: false },
    { id: "c3", name: "Corte", raridade: "comum", custo_folego: 1, custo_entropia: 0, texto: "Causa 3. **Sangria** 2.", descricao: "", conhecida: false },
  ] } as never;
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: /Combate/ }).click();
  const card = page.locator("article.combat-card.espolio__card").nth(2);
  await expect(card).toBeVisible();
  await card.locator(".kw").first().hover();
  const tip = page.locator("[role=tooltip]");
  await expect(tip).toBeVisible();
  const overlap = await card.evaluate((el) => {
    const t = document.querySelector("[role=tooltip]")!.getBoundingClientRect();
    return Array.from(el.querySelectorAll("button")).filter((b) => {
      const r = b.getBoundingClientRect();
      return r.left < t.right && r.right > t.left && r.top < t.bottom && r.bottom > t.top;
    }).length;
  });
  expect(overlap).toBe(0);
});

test("forja_via_fechada_mostra_motivo: aria-disabled, motivo visível e nenhum request", async ({ page, backend }) => {
  const state = backend.states.get("game-a")!;
  state.player_stats.forja = {
    permitido: true, motivo: "", baralho_min: 3,
    baralho: [{ id: "golpe", name: "Golpe do Véu", copias: 1, esquecivel: true, bloqueio: null }],
    esquecer: { descanso: false, templo: false, ouro: 30, motivos: { descanso: "Só dá para esquecer uma Carta depois de um descanso longo.", templo: "Só um templo ou curandeiro ajuda a esquecer uma Carta." } },
    afiar: { material: null, afiaveis: [], afiadas: [] },
    purgar: { medico: false, templo: false, ouro: 20, motivos: { medico: "Não há um Médico de Campo com você.", templo: "Só um templo ou curandeiro trata uma Cicatriz." } }, cicatrizes: [],
  } as never;
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await page.getByRole("tab", { name: /Combate/ }).click();
  await page.locator("[data-forja-row='golpe']").click();
  const rest = page.locator("[data-forja-forget='golpe:descanso']");
  await expect(rest).toHaveAttribute("aria-disabled", "true");
  await expect(page.locator("[data-forja-why]")).toContainText("Esquecer (descanso): Só dá para esquecer uma Carta depois de um descanso longo.");
  await expect(rest).toHaveAttribute("aria-describedby", "forja-why-forget");
  await rest.dispatchEvent("click"); // aria-disabled: o clique não faz nada
  await expect(page.locator("[data-forja-confirm]")).toHaveCount(0);
  expect(actions(backend)).toHaveLength(0);
});

test("desfecho_abre_no_topo_1440: Continuar visível e livre depois de rolar o painel até o fim", async ({ page, backend }) => {
  backend.unexpectedAllowed.push(/combat\/preview/); // a prévia é abortada ao enfileirar (esperado)
  armDeck(backend, { enemies: [["e1", "Saqueador"]] });
  await openCombat(page);
  await page.keyboard.press("1");
  await page.locator("[data-play-confirm]").press("Enter");
  await expect(page.locator(".play-queue__item")).toHaveCount(1);
  await panel(page).evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await page.locator("[data-end-turn]").dispatchEvent("click"); // sem rolar: dispatchEvent não move a página
  const next = page.locator(".combat-outcome__continue");
  await expect(next).toBeVisible();
  await page.waitForTimeout(300);
  const b = await measure(next);
  expect(b.free && b.inView, JSON.stringify(b)).toBe(true);
});

test("registro_acima_da_arena_1440: todas as entradas, ordem DOM e a 1ª carta ainda inteira", async ({ page, backend }) => {
  armDeck(backend, { roundLog: roundLog(4) });
  await openCombat(page);
  const board = page.locator("[data-roundboard]");
  await expect(board.locator(".roundboard__row")).toHaveCount(4);
  await expect(board.locator('[data-origem="reacao"]')).toContainText("Contra-ataque");
  const above = await page.evaluate(() => {
    const b = document.querySelector("[data-roundboard]")!, a = document.querySelector(".arena")!;
    return !!(b.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(above).toBe(true);
  expect(await panel(page).evaluate((el) => el.scrollTop)).toBe(0);
  expect((await measure(page.locator(".deck-card").first())).inView).toBe(true);
});
