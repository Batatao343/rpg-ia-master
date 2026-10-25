// SPEC-208: design system de efeitos. Roda nos projetos `chromium` (reduced-motion: estado estático
// equivalente) e `chromium-motion` (no-preference: o efeito acontece). Cada título começa com o id
// do efeito em design/effects.registry.ts (verificado por tests/design.test.mjs).
// Asserts em estado final/atributos/estilos computados — nunca em frames intermediários.
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type DeterministicBackend } from "./fixtures";
import type { Locator, Page, TestInfo } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const isMotion = (info: TestInfo) => info.project.name === "chromium-motion";
const NEAR_ZERO = 0.0001; // transition-duration 0.01ms (bloco global de reduced-motion)

test.beforeEach(async ({ page, backend }, info) => {
  await page.emulateMedia({ reducedMotion: isMotion(info) ? "no-preference" : "reduce" });
  // Google Fonts é externo e intermitente: não é sinal de efeito.
  backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
  backend.allowConsole(/ERR_CONNECTION_CLOSED|Failed to load resource/);
});

/** Espera o layout parar de mexer (hint/ofertas entram depois do primeiro paint) e devolve a caixa. */
async function stableBox(loc: Locator) {
  let prev = await loc.boundingBox();
  for (let i = 0; i < 20; i++) {
    await loc.page().waitForTimeout(120);
    const now = await loc.boundingBox();
    if (prev && now && Math.abs(now.x - prev.x) < 0.5 && Math.abs(now.y - prev.y) < 0.5) return now;
    prev = now;
  }
  return prev!;
}

async function a11y(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, `${label}: ` + blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
}

const css = (loc: Locator, prop: string, pseudo?: string) =>
  loc.evaluate((el, [p, ps]) => getComputedStyle(el, ps || null).getPropertyValue(p), [prop, pseudo ?? ""] as const);
const seconds = (value: string) => value.split(",").map((v) => parseFloat(v));
const panel = (page: Page) => page.locator("#ws-panel-combate");
const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const submit = (page: Page) => page.getByRole("button", { name: "Agir" });
const tabs = (page: Page) => page.getByRole("region", { name: "Painel de contexto" }).getByRole("tablist", { name: "Abas do painel" });
const streams = (b: DeterministicBackend) => b.requests.filter((r) => r.path === "/game/action/stream");

for (const [width, height] of [[1440, 900], [1280, 720]] as const) {
  test.describe(`efeitos @${width}x${height}`, () => {
    test.use({ viewport: { width, height } });

    // ---------- It.1: controles ----------
    test("ctrl.hover: botão acionável ganha elevação sem mover o layout", async ({ page }, info) => {
      await openGame(page);
      const btn = submit(page);
      await btn.scrollIntoViewIfNeeded(); // o composer pode ficar sob a dobra (M07); o scroll não é do efeito
      const before = await stableBox(btn);
      await btn.hover();
      if (isMotion(info)) {
        await expect.poll(() => css(btn, "box-shadow")).not.toBe("none");
        // R8: só transform transita (pressionar, --dur-instant); a sombra de hover troca no ato
        expect(await css(btn, "transition-property")).toBe("transform");
        expect(seconds(await css(btn, "transition-duration")).some((d) => Math.abs(d - 0.08) < 0.005)).toBe(true);
      } else {
        expect(seconds(await css(btn, "transition-duration")).every((d) => d <= NEAR_ZERO)).toBe(true);
      }
      const after = await btn.boundingBox();
      expect(after!.y).toBeCloseTo(before!.y, 0); // sem layout shift
      expect(after!.height).toBeCloseTo(before!.height, 0);
    });

    test("ctrl.press: pressionar afunda 1px e solta sem enviar", async ({ page, backend }, info) => {
      await openGame(page);
      const btn = submit(page);
      await btn.scrollIntoViewIfNeeded();
      const box = await stableBox(btn);
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      if (isMotion(info)) await expect.poll(() => css(btn, "transform")).not.toBe("none");
      else expect(seconds(await css(btn, "transition-duration")).every((d) => d <= NEAR_ZERO)).toBe(true);
      await page.mouse.move(box.x + box.width / 2, box.y - 60); // solta fora: não é clique
      await page.mouse.up();
      expect(streams(backend)).toHaveLength(0);
    });

    test("ctrl.focus: foco por teclado tem anel visível sem hover", async ({ page }) => {
      await openGame(page);
      await composer(page).focus();
      await page.keyboard.press("Tab");
      const focused = page.locator(":focus-visible");
      await expect(focused).toHaveCount(1);
      expect(await css(focused, "outline-style")).toBe("solid");
      expect(parseFloat(await css(focused, "outline-width"))).toBeGreaterThanOrEqual(2);
      await a11y(page, "foco");
    });

    test("ctrl.pending: botão pendente tem texto, aria-busy e a UI segue operável", async ({ page, backend }) => {
      await openGame(page);
      backend.delayStream();
      await composer(page).fill("olho ao redor");
      await submit(page).click();
      const btn = page.locator('[data-effect="chat.pending"]');
      await expect(btn).toHaveAttribute("aria-busy", "true");
      // SPEC-320 R4: sem "Enviando…"; antes do ack o rótulo é "Agir", depois "Aguardando o narrador".
      await expect(btn).toHaveText(/^(Agir|Aguardando o narrador)$/);
      await expect(btn).toBeDisabled();
      expect(await css(btn, "cursor")).toBe("not-allowed");
      // R6: nenhum efeito bloqueia o resto — trocar de aba durante o pendente responde na hora.
      const t0 = Date.now();
      await tabs(page).getByRole("tab", { name: "Mapa" }).click();
      await expect(tabs(page).getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
      expect(Date.now() - t0).toBeLessThan(1500);
      await a11y(page, "pendente");
      backend.releaseStream();
      await expect(btn).not.toHaveAttribute("aria-busy", "true");
      await expect(btn).toHaveText("Agir");
    });

    test("ctrl.pending: falha reabilita o botão e mostra o erro sem duplicar a ação", async ({ page, backend }) => {
      backend.allowFailure(/\/game\/action/);
      backend.allowConsole(/.*/);
      await openGame(page);
      backend.failNextTurn = true;
      await composer(page).fill("examino a porta");
      await submit(page).click();
      await expect(page.getByRole("alert").first()).toBeVisible();
      await expect(submit(page)).toBeEnabled();
      await expect(page.locator('[data-effect="chat.pending"]')).toHaveAttribute("data-effect-state", "idle");
      await a11y(page, "erro");
    });

    test("choice.select: o cartão inteiro seleciona e a seleção persiste com marcador textual", async ({ page, backend }) => {
      backend.saves = [];
      await page.goto("/");
      await expect(page.getByText("Valoria aguarda")).toBeVisible();
      await page.getByRole("button", { name: /Vocação/ }).click();
      const card = page.locator('article.card[data-effect="choice.select"]').nth(1);
      await expect(card).toHaveAttribute("data-effect-state", "idle");
      const box = (await card.boundingBox())!;
      // M01: na área da arte (longe do botão-título) o alvo clicável é o controle do cartão.
      const hit = await page.evaluate(([x, y]) => {
        const el = document.elementFromPoint(x, y);
        return !!el?.closest("button.card__select") || el?.classList.contains("card__select");
      }, [box.x + box.width / 2, box.y + box.height * 0.2] as const);
      expect(hit).toBe(true);
      await page.mouse.click(box.x + box.width / 2, box.y + box.height * 0.2);
      await expect(card).toHaveAttribute("data-effect-state", "selected");
      await expect(card.getByRole("button", { name: "Médico do Véu" })).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator('article.card[data-effect="choice.select"]').first()).toHaveAttribute("data-effect-state", "idle");
      expect(await css(card, "content", "::before")).toContain("Selecionado");
      await page.getByRole("button", { name: /Região/ }).click();
      await page.getByRole("button", { name: /Vocação/ }).click();
      await expect(card).toHaveAttribute("data-effect-state", "selected"); // persiste ao voltar
      await page.locator('article.card[data-effect="choice.select"]').first().getByRole("button").focus();
      await page.keyboard.press("Enter");
      await expect(page.locator('article.card[data-effect="choice.select"]').first()).toHaveAttribute("data-effect-state", "selected");
      await a11y(page, "criação");
    });

    // ---------- It.1b: chat ----------
    test("chat.pending: composer bloqueia reenvio durante o pendente (uma só ação enviada)", async ({ page, backend }) => {
      await openGame(page);
      backend.delayStream();
      await composer(page).fill("canto uma cantiga");
      await composer(page).press("Enter");
      await expect(page.locator('[data-effect="chat.pending"]')).toHaveAttribute("aria-busy", "true");
      await composer(page).fill("canto outra");
      await composer(page).press("Enter");
      backend.releaseStream();
      await expect(page.locator('[data-effect="chat.pending"]')).toHaveText("Agir");
      expect(streams(backend)).toHaveLength(1);
    });

    test("turn.status.ink: traço de tinta anima só com efeitos e fica estático sem eles", async ({ page, backend }, info) => {
      await openGame(page);
      backend.delayStream();
      await composer(page).fill("olho ao redor");
      await composer(page).press("Enter");
      const ink = page.locator('[data-effect="turn.status.ink"]');
      await expect(ink).toBeVisible();
      expect(await css(ink, "animation-name")).toBe(isMotion(info) ? "turn-ink" : "none");
      backend.releaseStream();
      await expect(ink).toHaveCount(0);
    });

    test("M09: entradas do chat não animam (histórico nem bloco novo) e não há blur", async ({ page }) => {
      await openGame(page);
      const entries = page.locator(".story article.msg");
      await expect(entries.first()).toBeVisible();
      const initial = await entries.count();
      await composer(page).fill("olho ao redor");
      await submit(page).click();
      await expect(entries).toHaveCount(initial + 2);
      await expect(entries.nth(initial + 1)).toBeVisible();
      for (let i = 0; i < initial + 2; i++) {
        expect(await css(entries.nth(i), "filter")).toBe("none");
        expect(await css(entries.nth(i), "animation-name")).toBe("none");
        expect(await css(entries.nth(i), "opacity")).toBe("1"); // o bloco novo já chega legível
      }
      expect(await page.evaluate(() => document.querySelectorAll(".story article.msg").length
        && document.getAnimations().filter((a) => ((a.effect as KeyframeEffect | null)?.target as Element | null)?.matches?.(".story article.msg")).length)).toBe(0);
    });

    // ---------- It.2: shell ----------
    test("tab.indicator: um indicador na aba ativa, acompanha clique e setas", async ({ page }) => {
      await openGame(page);
      const list = tabs(page);
      const bars = list.locator(".sel__bar");
      await expect(bars).toHaveCount(1);
      await expect(list.getByRole("tab", { name: "Personagem" }).locator(".sel__bar")).toHaveCount(1);
      await list.getByRole("tab", { name: "Mapa" }).click();
      await expect(list.getByRole("tab", { name: "Mapa" })).toHaveAttribute("aria-selected", "true");
      await expect(list.getByRole("tab", { name: "Mapa" }).locator(".sel__bar")).toHaveCount(1);
      await expect(bars).toHaveCount(1);
      await page.keyboard.press("ArrowLeft");
      await expect(list.getByRole("tab", { name: "Bestiário" })).toHaveAttribute("aria-selected", "true");
      await expect(list.getByRole("tab", { name: "Bestiário" }).locator(".sel__bar")).toHaveCount(1);
      // posição final: a barra termina dentro da aba ativa
      await expect.poll(async () => {
        const tab = (await list.getByRole("tab", { name: "Bestiário" }).boundingBox())!;
        const bar = (await bars.boundingBox())!;
        return bar.x >= tab.x - 1 && bar.x + bar.width <= tab.x + tab.width + 1;
      }).toBe(true);
      await a11y(page, "abas");
    });

    test("tab.content: painel que abre faz cross-fade curto; foco e scroll do chat não mudam", async ({ page }, info) => {
      await openGame(page);
      const story = page.getByRole("region", { name: "Narrativa" });
      await composer(page).focus();
      await tabs(page).getByRole("tab", { name: "Mapa" }).click();
      const panelEl = page.locator("#ws-panel-mapa");
      await expect(panelEl).toBeVisible();
      expect(await css(panelEl, "animation-name")).toBe(isMotion(info) ? "panel-in" : "none");
      await expect(story).toBeVisible(); // o chat continua montado
      await expect(composer(page)).toBeVisible();
    });

    test("split.toggle: colunas animam no modo split e param durante o arraste", async ({ page }, info) => {
      await openGame(page);
      const ws = page.locator(".ws");
      const dur = seconds(await css(ws, "transition-duration"));
      if (isMotion(info)) expect(dur.some((d) => d > 0.2)).toBe(true);
      else expect(dur.every((d) => d <= NEAR_ZERO)).toBe(true);
      await ws.evaluate((el) => el.classList.add("is-dragging"));
      expect(await css(ws, "transition-property")).not.toContain("grid-template-columns");
    });

    // ---------- It.3: combate ----------
    function armed(backend: DeterministicBackend) {
      const state = backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
      state.combat.cards[0].valid_targets = ["e1"]; // e2 fica inválido
      state.combat.cards[0].invalid_reason = null;
      return state;
    }
    const golpe = (page: Page) => panel(page).getByRole("button", { name: /Jogar Carta Golpe do Véu/ });

    test("card.hover: carta disponível sobe e mostra elevação; sem hover ela segue legível", async ({ page, backend }, info) => {
      armed(backend);
      await openGame(page);
      const card = golpe(page);
      await expect(card).toContainText("1E");
      await card.hover();
      await expect.poll(() => css(card, "border-top-color")).not.toBe(await css(panel(page).getByRole("button", { name: /Cataclismo/ }), "border-top-color"));
      if (isMotion(info)) await expect.poll(() => css(card, "transform")).not.toBe("none");
      else { await page.waitForTimeout(150); expect(await css(card, "transform")).toBe("none"); }
      await expect(card).toContainText("Escolha o alvo");
    });

    test("card.blocked: carta indisponível não sobe e diz o motivo por texto", async ({ page, backend }) => {
      armed(backend);
      await openGame(page);
      const blocked = panel(page).getByRole("button", { name: /Jogar Carta Cataclismo/ });
      await expect(blocked).toHaveAttribute("aria-disabled", "true");
      await expect(blocked).toHaveAttribute("data-effect-state", "blocked");
      await blocked.hover();
      await page.waitForTimeout(200);
      expect(await css(blocked, "transform")).toBe("none");
      expect(await css(blocked, "cursor")).toBe("not-allowed");
      expect((await blocked.innerText()).length).toBeGreaterThan(10); // motivo textual presente
    });

    test("card.arm: clique arma (aria-pressed), Esc desarma, teclado funciona sem hover", async ({ page, backend }) => {
      armed(backend);
      await openGame(page);
      const card = golpe(page);
      await expect(card).toHaveAttribute("data-effect-state", "idle");
      await card.click();
      await expect(card).toHaveAttribute("aria-pressed", "true");
      await expect(card).toHaveAttribute("data-effect-state", "armed");
      expect(await css(card, "box-shadow")).not.toBe("none");
      await a11y(page, "armado");
      await page.keyboard.press("Escape");
      await expect(card).toHaveAttribute("aria-pressed", "false");
      await card.focus();
      await page.keyboard.press("Enter");
      await expect(card).toHaveAttribute("aria-pressed", "true");
      await page.keyboard.press("Escape");
      await expect(card).toHaveAttribute("data-effect-state", "idle");
    });

    test("target.valid: na mira, válido e inválido se distinguem por estado, contorno e rótulo", async ({ page, backend }) => {
      armed(backend);
      await openGame(page);
      await golpe(page).click();
      const valid = panel(page).locator('[data-target="e1"]');
      const invalid = panel(page).locator('[data-target="e2"]');
      await expect(valid).toHaveAttribute("data-effect-state", "valid");
      await expect(invalid).toHaveAttribute("data-effect-state", "invalid");
      await expect(valid).toHaveAttribute("aria-label", /^Alvo: Saqueador/);
      await expect(invalid).toHaveAttribute("aria-label", /alvo inválido/);
      expect(await css(valid, "outline-style")).toBe("solid");
      expect(await css(invalid, "border-top-style")).toBe("dashed");
      await a11y(page, "mira");
    });

    test("card.resolve: a carta só vira gasta depois da confirmação do servidor", async ({ page, backend }) => {
      backend.combatHits = true; // o servidor resolve a Carta sem encerrar o combate
      const state = backend.armCombat("game-a", [["e1", "Saqueador"]]);
      await openGame(page);
      const wrap = page.locator('[data-effect="card.resolve"]').filter({ hasText: "Fôlego" });
      await expect(wrap).toHaveAttribute("data-effect-state", "ready");
      state.combat.cards[1].spent = true; // o servidor vai confirmar o gasto
      backend.delayStream();
      await panel(page).getByRole("button", { name: /Jogar Carta Fôlego/ }).click();
      await expect.poll(() => streams(backend).length).toBe(1);
      await expect(wrap).toHaveAttribute("data-effect-state", "ready"); // nada otimista
      backend.releaseStream();
      await expect(wrap).toHaveAttribute("data-effect-state", "resolved");
      await expect.poll(() => css(wrap.locator(".combat-card"), "opacity")).toBe("0.52");
    });

    test("hit.feedback: a Vitalidade do alvo atualiza no lugar quando o servidor confirma", async ({ page, backend }, info) => {
      backend.combatHits = true;
      armed(backend).combat.cards[0].valid_targets = ["e1", "e2"];
      await openGame(page);
      const bar = panel(page).locator('[data-participant="e2"] [data-effect="hit.feedback"], [data-target="e2"] [data-effect="hit.feedback"]').first();
      await expect(bar).toHaveAttribute("data-pct", "100");
      await golpe(page).click();
      await panel(page).locator('[data-target="e2"]').click();
      await expect(panel(page).getByText("2/6")).toBeVisible(); // o número é a informação
      await expect(bar).toHaveAttribute("data-pct", "33");
      const dur = seconds(await css(bar.locator("> span"), "transition-duration"));
      if (isMotion(info)) expect(dur.some((d) => Math.abs(d - 0.24) < 0.01)).toBe(true);
      else expect(dur.every((d) => d <= NEAR_ZERO)).toBe(true);
    });

    // ---------- It.4: revelação ----------
    test("codex.entry.reveal: entrada nova ganha 'Novo'; dado oculto nunca aparece no DOM nem na rede", async ({ page, backend }, info) => {
      const SENTINEL = "SENTINELA_OCULTA_9F3A";
      const sentUrls: string[] = [];
      page.on("request", (r) => sentUrls.push(r.url()));
      await page.route("**/game/codex**", (route) => {
        const known = [{ id: "porto", name: "Porto Cinzento", body: "Cais sob névoa." }];
        const grown = [...known, { id: "brumalta", name: "Brumalta", body: "Portões fechados." }];
        // o servidor só "descobre" Brumalta depois do primeiro turno (StrictMode repete o fetch inicial)
        const rows = backend.requests.some((r) => r.path.startsWith("/game/action")) ? grown : known;
        // campo extra que o cliente NUNCA deve renderizar nem propagar a atributos
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          locations: rows.map((r) => ({ ...r, internal_note: SENTINEL })), factions: [], characters: [], creatures: [], secrets: [] }) });
      });
      // SPEC-211: o Codex agora lê os dossiês; o mesmo cenário chega por `/game/codex/dossiers`.
      await page.route("**/game/codex/dossiers**", (route) => {
        const stamp = { knowledge_kind: "fact", certainty: "confirmed", source_kind: "canonical_event", source_ref: "visited:x",
          label: "Fato confirmado", first_seen_turn: null, last_updated_turn: null, stale: false };
        const rows = [{ id: "porto", name: "Porto Cinzento" }, ...(backend.requests.some((r) => r.path.startsWith("/game/action")) ? [{ id: "brumalta", name: "Brumalta" }] : [])];
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          version: 0, generated_at_turn: 0, bestiary: [], meta: { taxonomy_version: 1 },
          sections: { npcs: [], factions: [], secrets: [], chronicle_index: [],
            locations: rows.map((r) => ({ id: r.id, kind: "location", title: r.name, last_updated_turn: 0, version: 0, art: null,
              knowledge: stamp, notes: [], body: "", region: "", npcs: [], creatures: [], events: [], internal_note: SENTINEL })) } }) });
      });
      await openGame(page);
      await tabs(page).getByRole("tab", { name: "Codex" }).click();
      await page.getByRole("tablist", { name: "Seções do Codex" }).getByRole("tab", { name: /^Locais/ }).click();
      const entries = page.locator('li[data-effect="codex.entry.reveal"]');
      await expect(entries).toHaveCount(1);
      await expect(entries.first()).toHaveAttribute("data-effect-state", "settled");
      await expect(entries.first().locator(".reveal-new")).toHaveCount(0); // primeira leitura nunca é "Novo"
      await composer(page).fill("olho ao redor");
      await submit(page).click();
      await expect(entries).toHaveCount(2);
      const added = entries.filter({ hasText: "Brumalta" });
      await expect(added.locator(".reveal-new")).toHaveText("Novo");
      await expect(added).toHaveAttribute("data-effect-state", isMotion(info) ? "entering" : "settled");
      await expect(entries.filter({ hasText: "Porto Cinzento" })).toHaveAttribute("data-effect-state", "settled");
      // R7
      expect(await page.content()).not.toContain(SENTINEL);
      expect(await page.locator('link[rel="preload"], link[rel="prefetch"], link[rel="modulepreload"]').evaluateAll((els) => els.map((e) => (e as HTMLLinkElement).href).filter((h) => /brumalta|SENTINELA/i.test(h)))).toEqual([]);
      expect(sentUrls.filter((u) => u.includes(SENTINEL))).toEqual([]);
      await a11y(page, "codex");
    });

    test("map.marker: nó viajável tem cursor e halo; nó não descoberto não existe no DOM (SPEC-210)", async ({ page, backend }) => {
      backend.states.get("game-a")!.world.visited = ["porto"]; // brumalta e docas: só placa (adjacentes)
      await openGame(page);
      await tabs(page).getByRole("tab", { name: "Mapa" }).click();
      // O fog agora é server-side: nenhum marcador "fog" e nada de nó a 2 saltos no DOM.
      await expect(page.locator('[data-effect="map.marker"][data-effect-state="fog"]')).toHaveCount(0);
      const panelHtml = await page.locator("#ws-panel-mapa").innerHTML();
      expect(panelHtml).not.toMatch(/Torre Proibida|torre_proibida|SEGREDO-LORE|DOCAS-LORE-OCULTA|Cidade muralhada/);
      const node = page.locator('[data-effect="map.marker"][data-effect-state="travelable"][data-node-id="brumalta"]');
      await expect(node).toHaveCount(1);
      expect(await css(node, "cursor")).toBe("pointer");
      await node.locator(".worldmap__dot").hover();
      await expect.poll(() => css(node.locator(".worldmap__dot"), "box-shadow")).not.toBe("none");
      await expect(page.locator('[data-effect="map.marker"][data-effect-state="current"]')).toHaveAttribute("aria-label", /local atual/);
      await a11y(page, "mapa");
    });

    // ---------- atmosfera + kill switch ----------
    test("ember.pause: sem frames em reduce, com aba oculta e com ?effects=off", async ({ page }, info) => {
      await openGame(page);
      const canvas = page.locator(".ember-canvas");
      const frames = async () => Number((await canvas.getAttribute("data-frames")) ?? 0);
      if (!isMotion(info)) {
        await page.waitForTimeout(300);
        expect(await frames()).toBe(0);
        expect(await css(canvas, "display")).toBe("none");
        return;
      }
      await expect.poll(frames).toBeGreaterThan(3);
      await page.evaluate(() => {
        Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await page.waitForTimeout(100);
      const frozen = await frames();
      await page.waitForTimeout(300);
      expect(await frames()).toBe(frozen);
      await page.evaluate(() => {
        Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await expect.poll(frames).toBeGreaterThan(frozen);
    });

    test("R9: em combate nenhuma animação contínua roda atrás do chat; a informação segue visível", async ({ page, backend }) => {
      backend.armCombat("game-a", [["e1", "Saqueador"]]);
      await openGame(page);
      await expect(page.locator(".play.is-combat")).toHaveCount(1);
      await expect(page.locator(".combat-veil")).toBeVisible();
      await page.waitForTimeout(600); // a entrada única do véu (--dur-slow) termina
      const running = () => page.evaluate(() => document.getAnimations()
        .filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations === Infinity)
        .map((a) => `${(a as CSSAnimation).animationName ?? "?"}@${((a.effect as KeyframeEffect | null)?.target as Element | null)?.className ?? "?"}`));
      expect(await running()).toEqual([]);
      expect(Number(await css(page.locator(".combat-veil"), "opacity"))).toBeGreaterThan(0.5);
      await expect(page.locator(".combat-flag")).toBeVisible(); // a bandeira segue lá, só não pulsa
      await tabs(page).getByRole("tab", { name: "Mapa" }).click(); // farol do local atual parado em combate
      await page.waitForTimeout(200);
      expect(await running()).toEqual([]);
    });

    test("kill-switch: ?effects=off deixa tudo estático sem perder informação", async ({ page }, info) => {
      test.skip(!isMotion(info), "o kill switch é testado onde o movimento estaria ativo");
      await page.goto("/?effects=off");
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await expect(page.locator("html")).toHaveAttribute("data-effects", "off");
      await page.getByRole("button", { name: /^Ayla/ }).click();
      await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
      const btn = submit(page);
      expect(seconds(await css(btn, "transition-duration")).every((d) => d <= NEAR_ZERO)).toBe(true);
      expect(await css(page.locator(".ws"), "transition-duration")).toMatch(/^0(\.0+1?)?s|1e-05s/);
      await composer(page).fill("olho ao redor");
      await submit(page).click();
      await expect(page.locator(".story article.msg").last()).toBeVisible();
      await expect(tabs(page).locator(".sel__bar")).toHaveCount(1); // indicador segue como borda estática
      expect(await page.locator(".ember-canvas").evaluate((el) => getComputedStyle(el).display)).toBe("none");
    });
  });
}

// ---------- R8: custo de frame ----------
// Mede cada fluxo (criação, chat, combate+abas) sob CPU 4x com os efeitos DESLIGADOS (kill switch real:
// localStorage + evento storage, que também desliga os primitivos JS) e LIGADOS. Contra o build
// (`RPG_E2E_SERVER=preview`) vale o critério absoluto da spec: zero long task > 50 ms e frame p95
// <= 16,7 ms com os efeitos ligados. Contra o dev server (React em modo desenvolvimento, bem mais
// lento) é só um alarme de regressão grosseira — números de aceite vêm do build (docs/spec208).
type Perf = { long: number[]; at: number[]; marks: Array<[string, number]>; frames: number[]; stop?: () => void };
type FlowResult = { flow: string; effects: "on" | "off"; frames: number; frameP50Ms: number; frameP90Ms: number;
  frameP95Ms: number; maxFrameMs: number; slowFrames: number; longTasks: string[]; maxLongTaskMs: number };
const q = (sorted: number[], p: number) => Math.round((sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] ?? 0) * 10) / 10;

async function measureFlow(page: Page, flow: string, effects: "on" | "off", run: (mark: (label: string) => Promise<void>) => Promise<void>): Promise<FlowResult> {
  const cdp = await page.context().newCDPSession(page);
  await page.evaluate((mode) => {
    try { if (mode === "off") localStorage.setItem("rpg.effects", "off"); else localStorage.removeItem("rpg.effects"); } catch { /* */ }
    window.dispatchEvent(new StorageEvent("storage", { key: "rpg.effects" }));
    const w = window as unknown as { __perf?: Perf };
    w.__perf?.stop?.();
    const perf: Perf = { long: [], at: [], marks: [], frames: [] };
    w.__perf = perf;
    const obs = new PerformanceObserver((list) => list.getEntries().forEach((e) => { perf.long.push(Math.round(e.duration)); perf.at.push(e.startTime); }));
    obs.observe({ entryTypes: ["longtask"] });
    let last = performance.now(); let alive = true;
    const tick = (now: number) => { if (!alive) return; perf.frames.push(now - last); last = now; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    perf.stop = () => { alive = false; obs.disconnect(); };
  }, effects);
  if (effects === "off") await expect(page.locator("html")).toHaveAttribute("data-effects", "off");
  else await expect(page.locator("html")).not.toHaveAttribute("data-effects", "off");
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  const mark = async (label: string) => { await page.evaluate((l) => { (window as unknown as { __perf: Perf }).__perf.marks.push([l, performance.now()]); }, label); };
  try { await run(mark); } finally { await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 }); }
  const perf = await page.evaluate(() => { const p = (window as unknown as { __perf: Perf }).__perf; p.stop?.(); return p; });
  await cdp.detach();
  const frames = perf.frames.slice(2).sort((a, b) => a - b);
  return { flow, effects, frames: frames.length, frameP50Ms: q(frames, 0.5), frameP90Ms: q(frames, 0.9), frameP95Ms: q(frames, 0.95),
    maxFrameMs: q(frames, 1), slowFrames: frames.filter((f) => f > 33.4).length, longTasks: perf.long.map((d, i) => `${d}ms@${[...perf.marks].reverse().find(([, t]) => t <= perf.at[i] + 1)?.[0] ?? "início"}`),
    maxLongTaskMs: Math.max(0, ...perf.long) };
}

const perfResults: FlowResult[] = [];
function checkPerf(results: FlowResult[]) {
  const strict = process.env.RPG_E2E_SERVER === "preview";
  for (const on of results.filter((r) => r.effects === "on")) {
    const off = results.find((r) => r.flow === on.flow && r.effects === "off")!;
    if (strict) {
      expect(on.maxLongTaskMs, `${on.flow}: long task com efeitos`).toBeLessThanOrEqual(50);
      expect(on.frameP95Ms, `${on.flow}: frame p95 com efeitos`).toBeLessThanOrEqual(16.7);
    } else {
      expect(on.maxLongTaskMs, `${on.flow}: long task (dev)`).toBeLessThanOrEqual(Math.max(250, off.maxLongTaskMs + 100));
      expect(on.frameP90Ms, `${on.flow}: frame p90 (dev)`).toBeLessThanOrEqual(Math.max(33.4, off.frameP90Ms * 2.1));
    }
  }
}
test.afterAll(() => {
  if (!perfResults.length) return;
  mkdirSync("test-results", { recursive: true });
  writeFileSync("test-results/effects-perf.json", JSON.stringify({ throttle: 4, server: process.env.RPG_E2E_SERVER ?? "dev", results: perfResults }, null, 2));
});

test("perf: 4x CPU — criação (hover e seleção de raça/classe/região)", async ({ page, backend }, info) => {
  test.skip(!isMotion(info), "medição só com movimento ativo");
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  backend.saves = [];
  await page.goto("/");
  await expect(page.getByText("Valoria aguarda")).toBeVisible();
  const flow = async (mark: (l: string) => Promise<void>) => {
    for (const step of [/Origem/, /Vocação/, /Região/]) {
      const stepBtn = page.getByRole("button", { name: step }).first();
      await mark(String(step));
      if (await stepBtn.count()) { await stepBtn.click(); await page.waitForTimeout(250); }
      const cards = page.locator('[data-effect="choice.select"]');
      const n = Math.min(3, await cards.count());
      for (let i = 0; i < n; i++) { await cards.nth(i).hover(); await page.waitForTimeout(120); }
      if (n) {
        const inner = cards.nth(n - 1).locator("button.card__select"); // raça/classe: botão no cartão; região: o cartão é o botão
        await ((await inner.count()) ? inner.first() : cards.nth(n - 1)).click();
        await page.waitForTimeout(200);
      }
    }
  };
  await measureFlow(page, "criação", "on", flow); // aquecimento (JIT/estilos): descartado
  const results = [await measureFlow(page, "criação", "off", flow), await measureFlow(page, "criação", "on", flow)];
  perfResults.push(...results);
  console.log("EFFECTS_PERF " + JSON.stringify(results));
  checkPerf(results);
});

test("perf: 4x CPU — chat (enviar ação, entrada nova) e combate (armar carta, Esc, 4 abas)", async ({ page, backend }, info) => {
  test.skip(!isMotion(info), "medição só com movimento ativo");
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openGame(page);
  const chat = async (mark: (l: string) => Promise<void>) => {
    const entries = page.locator(".story article.msg");
    for (const text of ["olho ao redor", "sigo pela trilha", "escuto o vento"]) {
      const before = await entries.count();
      await mark(text);
      await composer(page).fill(text);
      await submit(page).click();
      await expect.poll(() => entries.count(), { timeout: 20_000 }).toBeGreaterThan(before);
      await expect(submit(page)).toBeEnabled({ timeout: 20_000 });
      await page.waitForTimeout(500);
    }
  };
  await measureFlow(page, "chat", "on", chat);
  const chatResults = [await measureFlow(page, "chat", "off", chat), await measureFlow(page, "chat", "on", chat)];

  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  await page.reload();
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  const card = panel(page).getByRole("button", { name: /Jogar Carta Golpe do Véu/ });
  await expect(card).toBeVisible();
  const combat = async (mark: (l: string) => Promise<void>) => {
    await mark("hover"); await card.hover(); await mark("armar"); await card.click(); await page.waitForTimeout(250);
    await mark("Esc"); await page.keyboard.press("Escape");
    for (const name of ["Mapa", "Bestiário", "Codex", "Combate"]) {
      await mark(`aba ${name}`);
      await tabs(page).getByRole("tab", { name }).click();
      await page.waitForTimeout(300);
    }
  };
  await measureFlow(page, "combate", "on", combat);
  const combatResults = [await measureFlow(page, "combate", "off", combat), await measureFlow(page, "combate", "on", combat)];
  const results = [...chatResults, ...combatResults];
  perfResults.push(...results);
  console.log("EFFECTS_PERF " + JSON.stringify(results));
  checkPerf(results);
});

// ---------- §6 smoke + evidência (opt-in: RPG_EFFECTS_EVIDENCE=1) ----------
// Roteiro da spec em três modos (normal, reduced-motion, ?effects=off) com vídeo e trace; os arquivos
// vão para test-results/ e são copiados para docs/spec208/evidence/. Asserts mínimos: a mesma
// informação aparece nos três modos (estado/texto), só o movimento muda.
for (const mode of ["normal", "reduced", "effects-off"] as const) {
  test.describe(`smoke §6 ${mode}`, () => {
    test.use({ viewport: { width: 1280, height: 800 } }); // vídeo/trace: playwright.config (RPG_EFFECTS_EVIDENCE)
    test(`smoke §6 (${mode}): criar → chat → abas/split → combate → Codex/Mapa`, async ({ page, backend }, info) => {
      test.skip(!process.env.RPG_EFFECTS_EVIDENCE || !isMotion(info), "evidência opt-in (RPG_EFFECTS_EVIDENCE=1)");
      test.setTimeout(120_000);
      await page.emulateMedia({ reducedMotion: mode === "reduced" ? "reduce" : "no-preference" });
      const q = mode === "effects-off" ? "/?effects=off" : "/";
      // criação: hover e seleção (sem enviar)
      const saves = backend.saves;
      backend.saves = [];
      await page.goto(q);
      await expect(page.getByText("Valoria aguarda")).toBeVisible();
      await page.getByRole("button", { name: /Vocação/ }).click();
      const choice = page.locator('article.card[data-effect="choice.select"]').nth(1);
      await choice.hover(); await page.waitForTimeout(300);
      await choice.locator("button.card__select").click();
      await expect(choice).toHaveAttribute("data-effect-state", "selected");
      await page.waitForTimeout(500);
      // chat
      backend.saves = saves;
      await page.goto(q);
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).click();
      await composer(page).fill("olho ao redor");
      await submit(page).click();
      await expect(submit(page)).toBeEnabled();
      await page.waitForTimeout(500);
      // abas + split
      await page.getByRole("group", { name: "Modo de exibição" }).getByRole("button", { name: "Dividido" }).click();
      await page.waitForTimeout(400);
      for (const name of ["Mapa", "Codex", "Bestiário"]) { await tabs(page).getByRole("tab", { name }).click(); await page.waitForTimeout(400); }
      // combate: armar, mirar, executar, Esc
      const state = backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
      state.combat.cards[0].valid_targets = ["e1"];
      state.combat.cards[0].invalid_reason = null;
      backend.combatHits = true;
      await page.reload();
      await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
      await page.getByRole("button", { name: /^Ayla/ }).click();
      const card = panel(page).getByRole("button", { name: /Jogar Carta Golpe do Véu/ });
      await card.hover(); await page.waitForTimeout(300);
      await card.click();
      await expect(card).toHaveAttribute("data-effect-state", "armed");
      await expect(panel(page).locator('[data-target="e2"]')).toHaveAttribute("data-effect-state", "invalid");
      await page.waitForTimeout(400);
      await page.keyboard.press("Escape");
      await expect(card).toHaveAttribute("data-effect-state", "idle");
      await card.click();
      await panel(page).locator('[data-target="e1"]').click();
      await expect.poll(() => streams(backend).length).toBeGreaterThan(0);
      await page.waitForTimeout(800);
      for (const name of ["Mapa", "Codex", "Combate"]) { await tabs(page).getByRole("tab", { name }).click(); await page.waitForTimeout(400); }
      if (mode === "effects-off") await expect(page.locator("html")).toHaveAttribute("data-effects", "off");
      await page.screenshot({ path: `test-results/spec208-evidence-${mode}.png` });
    });
  });
}
