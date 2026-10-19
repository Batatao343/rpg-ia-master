// SPEC-216 Etapa 0 (eval authoring, congelado ANTES do produto): jornadas mobile single-pane.
// Cada jornada roda uma vez por projeto Playwright `mobile-320` (320x568) e `mobile-390` (390x844),
// com toque (hasTouch/isMobile). Só toque (sem hover nem arrastar) e sem sleep fixo.
//
// Contrato de UI que o produto deve satisfazer (ver handoffs/SPEC-216-eval-authoring-result.md):
//  - barra inferior: navigation "Superfícies" com botões Chat/Codex/Personagem/Combate/Bestiário/Mapa,
//    `aria-current="page"` só no ativo, alvos >= 44px;
//  - título da superfície: [data-testid="surface-title"] (heading, tabindex -1) recebe o foco ao trocar;
//  - exatamente UMA superfície visível: região "Chat da aventura" OU "Painel de contexto";
//    sem `aside.hud` / `.tactical-dock`;
//  - narração de início de combate no chat + botão "Ir para o combate"; troca automática só DEPOIS da narração;
//  - mira por toque na MESMA máquina do desktop: carta -> alvo; botão "Cancelar mira"; "Detalhes de <Carta>".
import AxeBuilder from "@axe-core/playwright";
import type { Locator, Page } from "@playwright/test";
import { test, expect, DeterministicBackend } from "./fixtures";

const SURFACES = ["Chat", "Codex", "Personagem", "Combate", "Bestiário", "Mapa"] as const;
const CONTEXT = SURFACES.slice(1);
type Surface = (typeof SURFACES)[number];
const KEYBOARD_PX = { 320: 260, 390: 336 } as Record<number, number>;

async function assertA11y(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(blocking, "A11Y serious/critical: " + blocking.map((v) => `${v.id}: ${v.help}`).join("\n")).toEqual([]);
}

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).tap();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

const tabBar = (page: Page) => page.getByRole("navigation", { name: "Superfícies" });
const tabBtn = (page: Page, name: Surface) => tabBar(page).getByRole("button", { name, exact: true });
const composer = (page: Page) => page.getByRole("textbox", { name: "Sua ação" });
const title = (page: Page) => page.getByTestId("surface-title");
const combatPanel = (page: Page) => page.locator("#ws-panel-combate");
const actions = (b: DeterministicBackend) => b.requests.filter((r) => r.path.startsWith("/game/action"));

async function go(page: Page, name: Surface) {
  await tabBtn(page, name).tap();
  await expect(tabBtn(page, name)).toHaveAttribute("aria-current", "page");
}

async function noOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

/** R1: exatamente uma superfície de conteúdo (chat OU contexto) com área visível; sem gaveta/dock. */
async function expectSingleSurface(page: Page, which: "chat" | "context") {
  await expect.poll(() => page.evaluate(() => {
    const seen = (label: string) => {
      const el = document.querySelector(`[aria-label="${label}"]`) as HTMLElement | null;
      if (!el) return false;
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none";
    };
    return { chat: seen("Chat da aventura"), context: seen("Painel de contexto") };
  })).toEqual(which === "chat" ? { chat: true, context: false } : { chat: false, context: true });
  await expect(page.locator(".tactical-dock, aside.hud")).toHaveCount(0);
}

/** Cartas/alvos da SPEC-205 (mesmo contrato do desktop), 2 inimigos. */
function setupCombat(backend: DeterministicBackend) {
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  backend.combatHits = true;
}
const card = (page: Page, name: string) => combatPanel(page).getByRole("button", { name: new RegExp(`Jogar Carta ${name}`) });

async function fakeMicrophone(page: Page) {
  await page.addInitScript(() => {
    const audit = { captures: 0, stops: 0, releases: 0 };
    Object.assign(window, { voiceAudit: audit });
    const NativeXHR = XMLHttpRequest;
    class ObservedXHR extends NativeXHR { constructor() { super(); Object.assign(window, { voiceXHR: this }); } }
    Object.defineProperty(window, "XMLHttpRequest", { value: ObservedXHR });
    const stream = { getTracks: () => [{ stop() { audit.releases++; } }] };
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: async () => { audit.captures++; return stream; } } });
    class FakeRecorder {
      static isTypeSupported(type: string) { return type === "audio/mp4"; }
      state = "inactive"; mimeType = "audio/mp4";
      ondataavailable?: (event: { data: Blob }) => void; onstop?: () => void;
      start() { this.state = "recording"; }
      stop() {
        audit.stops++; this.state = "inactive";
        queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(["binary-voice-fixture"], { type: "audio/mp4" }) }); this.onstop?.(); });
      }
    }
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: FakeRecorder });
  });
}
const voiceAudit = (page: Page) => page.evaluate(() => (window as unknown as { voiceAudit: { captures: number; stops: number; releases: number } }).voiceAudit);

const rect = async (l: Locator) => (await l.boundingBox())!;
const intersects = (a: { x: number; y: number; width: number; height: number }, b: typeof a) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("https://fonts.googleapis.com/**", (route) => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
});

test("M01 one_surface_visible", async ({ page }) => {
  await openGame(page);
  await expectSingleSurface(page, "chat");
  await expect(tabBar(page).getByRole("button")).toHaveCount(SURFACES.length);
  await expect(tabBtn(page, "Chat")).toHaveAttribute("aria-current", "page");
  // R2/R9: alvos >= 44px, barra dentro da viewport, topbar não a sobrepõe.
  for (const name of SURFACES) {
    const box = await rect(tabBtn(page, name));
    expect(box.width, `${name} largura`).toBeGreaterThanOrEqual(44);
    expect(box.height, `${name} altura`).toBeGreaterThanOrEqual(44);
  }
  const vh = page.viewportSize()!.height;
  const bar = await rect(tabBar(page));
  expect(bar.y + bar.height).toBeLessThanOrEqual(vh + 0.5);
  expect(intersects(await rect(page.locator("header.topbar")), bar)).toBe(false);
  await noOverflow(page);
  for (const name of CONTEXT) {
    await go(page, name);
    await expectSingleSurface(page, "context");
    await expect(page.getByRole("tablist", { name: "Abas do painel" })).toHaveCount(0);  // a barra inferior é a única navegação
    await noOverflow(page);
  }
  await go(page, "Chat");
  await expectSingleSurface(page, "chat");
  await expect(composer(page)).toBeVisible();
});

test("M02 switch_and_back_preserves_state", async ({ page, backend }) => {
  const history = backend.histories.get("game-a")!;
  for (let i = 1; i <= 30; i++) {
    history.push({ id: `m02-p${i}`, turn: i, epoch: 1, role: "player", text: `Passo antigo ${i}`, type: "STORY" });
    history.push({ id: `m02-n${i}`, turn: i, epoch: 1, role: "narrator", text: `Registro extenso ${i}. `.repeat(12), type: "STORY" });
  }
  backend.delayStream();
  await openGame(page);
  await composer(page).fill("Ação lenta de Ayla");
  await page.getByRole("button", { name: "Agir" }).tap();
  await expect.poll(() => backend.requests.filter((r) => r.path === "/game/action/stream").length).toBe(1);
  const pendingKeys = () => page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("valoria:pending")).sort());
  const pendingBefore = await pendingKeys();
  expect(pendingBefore).toHaveLength(1);
  const draft = "Rascunho de Ayla ainda não enviado";
  await composer(page).fill(draft);
  const story = page.getByRole("region", { name: "Narrativa" });
  await story.evaluate((el) => { el.scrollTop = 240; el.dispatchEvent(new Event("scroll")); });
  expect(await story.evaluate((el) => el.scrollHeight - el.clientHeight - el.scrollTop)).toBeGreaterThan(200);

  for (const name of [...CONTEXT, "Mapa", "Codex"] as Surface[]) {
    await go(page, name);
    await go(page, "Chat");
    await expect(composer(page)).toHaveValue(draft);
    expect(await story.evaluate((el) => el.scrollTop)).toBe(240);
    expect(await pendingKeys()).toEqual(pendingBefore);
    await expect(page.getByRole("button", { name: "Agir" })).toHaveAttribute("aria-busy", "true");
  }
  // Sem segundo turno e sem segundo draft: a troca de superfície não envia nada.
  expect(backend.requests.filter((r) => r.path === "/game/action/stream")).toHaveLength(1);
  backend.releaseStream();
  await expect(page.getByText("O mundo responde a: Ação lenta de Ayla")).toBeVisible();
  await expect(composer(page)).toHaveValue(draft);
});

test("M03 composer_visible_with_virtual_keyboard", async ({ page }) => {
  await openGame(page);
  const { width, height } = page.viewportSize()!;
  await composer(page).tap();
  // Teclado virtual: a viewport visual encolhe; o campo e o Agir seguem inteiros dentro dela.
  await page.setViewportSize({ width, height: height - KEYBOARD_PX[width] });
  await expect(composer(page)).toBeFocused();
  const vv = await page.evaluate(() => ({ h: window.visualViewport!.height, w: window.visualViewport!.width }));
  const field = await rect(composer(page));
  const act = await rect(page.getByRole("button", { name: "Agir" }));
  for (const box of [field, act]) {
    expect(box.y).toBeGreaterThanOrEqual(-0.5);
    expect(box.y + box.height).toBeLessThanOrEqual(vv.h + 0.5);
    expect(box.x + box.width).toBeLessThanOrEqual(vv.w + 0.5);
  }
  expect(intersects(field, act)).toBe(false);
  const bar = tabBar(page);
  if (await bar.isVisible()) expect(intersects(field, await rect(bar)) || intersects(act, await rect(bar))).toBe(false);
  // R4: input >= 16px (evita zoom automático do iOS/WebView).
  expect(await composer(page).evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
  await composer(page).fill("Examino a porta");
  await page.getByRole("button", { name: "Agir" }).tap();
  await expect(page.getByText("O mundo responde a: Examino a porta")).toBeVisible();
  await noOverflow(page);
});

test("M04 voice_flow_and_mic_release", async ({ page, backend, baseURL }) => {
  await fakeMicrophone(page);
  await page.context().addCookies([{ name: "rpg_csrf", value: "voice-csrf", url: baseURL }]);
  let uploads = 0;
  let finish!: () => void;
  const gate = new Promise<void>((resolve) => { finish = resolve; });
  await page.route("**/account/transcriptions", async (route) => {
    uploads++;
    await page.evaluate(() => (window as unknown as { voiceXHR: XMLHttpRequest }).voiceXHR.upload.dispatchEvent(new ProgressEvent("load")));
    await gate;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ text: "Examino a porta", billing_status: "settled" }) });
  });
  await openGame(page);
  await composer(page).fill("Com cuidado,");
  const record = page.getByRole("button", { name: "Gravar ação por voz" });
  const box = await rect(record);
  expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(44);
  await record.tap();
  await expect(page.locator('[data-voice-state="recording"]')).toBeVisible();
  await page.getByRole("button", { name: "Parar gravação" }).tap();
  await expect(page.locator('[data-voice-state="transcribing"]')).toBeVisible();
  await composer(page).fill("Silenciosamente,");  // transcript editável durante o upload
  finish();
  await expect(composer(page)).toHaveValue("Silenciosamente, Examino a porta");
  expect(uploads).toBe(1);
  expect(actions(backend)).toHaveLength(0);       // voz nunca envia ação sozinha
  await composer(page).fill("Examino a porta azul");
  await page.getByRole("button", { name: "Agir" }).tap();
  await expect(page.getByText("O mundo responde a: Examino a porta azul")).toBeVisible();
  expect(actions(backend)).toHaveLength(1);
  // R5: gravando e trocando de superfície libera o microfone e não envia nada.
  const before = await voiceAudit(page);
  await record.tap();
  await expect(page.locator('[data-voice-state="recording"]')).toBeVisible();
  await go(page, "Personagem");
  await expect.poll(async () => (await voiceAudit(page)).releases).toBeGreaterThan(before.releases);
  await go(page, "Chat");
  await expect(page.locator('[data-voice-state="recording"]')).toHaveCount(0);
  expect(actions(backend)).toHaveLength(1);
  await noOverflow(page);
});

test("M05 combat_own_screen_and_outcome_in_chat", async ({ page, backend }) => {
  // Registra a ordem real no DOM: a narração entra antes de a superfície Combate aparecer (§8 P4).
  await page.addInitScript(() => {
    const order: string[] = [];
    Object.assign(window, { __order: order });
    const check = () => {
      if (!order.includes("narration") && document.body?.innerText.includes("Saqueadores saltam da névoa")) order.push("narration");
      const panel = document.querySelector("#ws-panel-combate") as HTMLElement | null;
      if (!order.includes("combat") && panel && panel.getBoundingClientRect().width > 0 && getComputedStyle(panel).visibility !== "hidden") order.push("combat");
    };
    new MutationObserver(check).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
    setInterval(check, 16);
  });
  await openGame(page);
  await expectSingleSurface(page, "chat");
  await composer(page).fill("Atravesso a ponte e caio numa emboscada");
  await page.getByRole("button", { name: "Agir" }).tap();
  await expect(combatPanel(page)).toBeVisible();     // troca automática para a superfície Combate
  await expectSingleSurface(page, "context");
  await expect(tabBtn(page, "Combate")).toHaveAttribute("aria-current", "page");
  const order = await page.evaluate(() => (window as unknown as { __order: string[] }).__order);
  expect(order.indexOf("narration")).toBeGreaterThanOrEqual(0);
  expect(order.indexOf("narration")).toBeLessThan(order.indexOf("combat"));
  // Retorno rápido ao chat: narração + selo "Ir para o combate"; a superfície Combate não fica ao lado.
  await go(page, "Chat");
  await expectSingleSurface(page, "chat");
  await expect(page.getByText("Saqueadores saltam da névoa; o combate começa.")).toBeVisible();
  const cta = page.getByRole("button", { name: "Ir para o combate" });
  await expect(cta).toBeVisible();
  expect(Math.min(...Object.values(await rect(cta)).slice(2) as number[])).toBeGreaterThanOrEqual(44);
  await cta.tap();
  await expect(combatPanel(page)).toBeVisible();
  await expect(tabBtn(page, "Combate")).toHaveAttribute("aria-current", "page");
  // Desfecho: narração no chat, resultado na superfície Combate (sem XP no balão do chat).
  backend.combatHits = false;
  await card(page, "Golpe do Véu").tap();
  await combatPanel(page).getByRole("button", { name: /Alvo: Saqueador/ }).tap();
  const outcome = page.getByRole("region", { name: "Desfecho do combate" });
  await expect(outcome).toBeVisible();
  await expect(outcome.getByRole("heading", { name: "Vitória" })).toBeVisible();
  await go(page, "Chat");
  await expect(page.getByText("O último saqueador cai; o combate termina.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Narrativa" }).getByText(/XP/)).toHaveCount(0);
  await noOverflow(page);
});

test("M06 touch_targeting_same_payload_as_desktop", async ({ page, backend, browser }) => {
  setupCombat(backend);
  // Referência desktop (SPEC-205): mesma sequência carta -> alvo por clique, num contexto isolado.
  const desktopBody = await (async () => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "pt-BR", reducedMotion: "reduce" });
    const dpage = await ctx.newPage();
    const probe = new DeterministicBackend();
    probe.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]); probe.combatHits = true;
    await probe.install(dpage);
    await dpage.goto("/");
    await dpage.getByRole("button", { name: /^Ayla/ }).click();
    const dtab = dpage.getByRole("tab", { name: "Combate" });
    if (await dtab.count()) await dtab.click();
    const dpanel = dpage.locator("#ws-panel-combate");
    await dpanel.getByRole("button", { name: /Jogar Carta Golpe do Véu/ }).click();
    await dpanel.getByRole("button", { name: /Alvo: Bandoleiro/ }).click();
    await expect.poll(() => probe.requests.filter((r) => r.path.startsWith("/game/action")).length).toBe(1);
    const body = probe.requests.find((r) => r.path.startsWith("/game/action"))!.body!;
    await ctx.close();
    return body;
  })();

  await openGame(page);
  await go(page, "Combate");
  // R7: nenhum seletor/alvo exige hover; toque seleciona a carta, não envia.
  await card(page, "Golpe do Véu").tap();
  await expect(combatPanel(page).getByText("Mirando Golpe do Véu: escolha um alvo").first()).toBeVisible();
  expect(actions(backend)).toHaveLength(0);
  // Cancelar explícito (substitui Esc): sem request, volta ao idle.
  const cancel = combatPanel(page).getByRole("button", { name: "Cancelar mira" });
  expect(Math.min((await rect(cancel)).width, (await rect(cancel)).height)).toBeGreaterThanOrEqual(44);
  await cancel.tap();
  await expect(combatPanel(page).getByText("Escolha uma carta ou ação")).toBeVisible();
  expect(actions(backend)).toHaveLength(0);
  // Detalhes sem hover: botão dedicado abre o detalhe da carta.
  await combatPanel(page).getByRole("button", { name: /Detalhes de Golpe do Véu/ }).tap();
  await expect(combatPanel(page).locator(".card-detail")).toContainText("Custo: 1E");
  await expect(combatPanel(page).locator(".card-detail")).toContainText("1× por turno");
  expect(actions(backend)).toHaveLength(0);
  // Carta + alvo por toque: um POST, payload idêntico ao desktop (menos o action_id).
  await card(page, "Golpe do Véu").tap();
  await combatPanel(page).getByRole("button", { name: /Alvo: Bandoleiro/ }).tap();
  await expect.poll(() => actions(backend).length).toBe(1);
  const mobileBody = actions(backend)[0].body!;
  const strip = (b: Record<string, unknown>) => { const { action_id, ...rest } = b; expect(String(action_id)).toMatch(/^[0-9a-f-]{36}$/); return rest; };
  expect(strip(mobileBody)).toEqual(strip(desktopBody));
  expect(mobileBody).toMatchObject({ card_id: "golpe", target_id: "e2" });
  await noOverflow(page);
});

test("M07 reduced_motion_focus_aria_and_a11y", async ({ page, backend }) => {
  setupCombat(backend);
  await openGame(page);
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  for (const name of CONTEXT) {
    await go(page, name);
    // R8: foco no título da superfície; um único aria-current; nenhuma animação de layout rodando.
    await expect(title(page)).toBeFocused();
    await expect(title(page)).toHaveText(name);
    await expect(tabBar(page).locator('[aria-current="page"]')).toHaveCount(1);
    expect(await page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length)).toBe(0);
    await assertA11y(page);
    await noOverflow(page);
  }
  await go(page, "Chat");
  await expect(title(page)).toBeFocused();
  await expect(title(page)).toHaveText("Chat");
  await expect(tabBar(page).locator('[aria-current="page"]')).toHaveCount(1);
  await assertA11y(page);
});
