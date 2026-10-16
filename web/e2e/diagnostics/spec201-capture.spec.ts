// SPEC-201 — captura de diagnóstico (NÃO é gate). Somente leitura do produto:
// gera PNGs 1440x900 / 1280x800 + dados brutos em docs/spec201/.
// Rodar:  cd web && RPG_SPEC201=1 npx playwright test e2e/diagnostics --grep @spec201 --workers=1
// (sem RPG_SPEC201=1 o arquivo se auto-pula: nao entra no gate F01-F16).
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, gameState } from "../fixtures";
import type { Page } from "@playwright/test";
import type { GameResponse } from "../../src/types";

test.skip(!process.env.RPG_SPEC201, "diagnostico SPEC-201: opt-in via RPG_SPEC201=1");

const SENTINEL = "SEGREDO_SENTINELA_XYZ";
const ROOT = resolve(process.cwd(), "..", "docs", "spec201");
const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
] as const;

function save(page: Page, vp: string, name: string, motion: string) {
  const dir = join(ROOT, "capturas", vp);
  mkdirSync(dir, { recursive: true });
  return page.screenshot({ path: join(dir, `${name}${motion === "no-preference" ? "--motion" : ""}.png`) });
}
function record(key: string, data: unknown) {
  const dir = join(ROOT, "dados");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${key}.json`), JSON.stringify(data, null, 2));
}

function combatState(base: GameResponse): GameResponse {
  const s = structuredClone(base);
  const card = (id: string, name: string, over: Record<string, unknown> = {}) => ({
    id, name, type: "ativa", description: `${name}: golpe de teste.`, effect_kind: "damage", target_kind: "enemy" as const,
    subclass: "", prepared: true, cost: 2, frequency: "turno", spent: false, ready: true,
    has_rupture: false, rupture_ready: false, trigger: "", evolved: null, ...over,
  });
  s.combat.active = true; s.combat.round = 2;
  s.combat.order = [{ name: "Ayla", side: "hero", init: 14 }, { name: "Saqueador", side: "enemy", init: 11 }, { name: "Cão de Rebite", side: "enemy", init: 8 }];
  const enemy = (id: string, name: string, v: number) => ({
    id, name, hp: v, max_hp: 14, vitalidade: v, max_vitalidade: 14, esquiva: 8, protecao: 1,
    integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [], revealed_cards: [], revealed_resistances: [],
  });
  s.combat.enemies = [enemy("e1", "Saqueador", 9), enemy("e2", "Cão de Rebite", 14)];
  s.combat.cards = [
    card("golpe", "Golpe do Véu", { has_rupture: true, rupture_ready: true }),
    card("tiro", "Tiro Sombrio", { cost: 4, ready: false }),
    card("rasga", "Rasgo", { spent: true }),
    { ...card("aparar", "Aparar"), type: "reacao", trigger: "ao_ser_alvo" },
  ];
  s.combat.scene = {
    zones: [{ id: "z1", name: "Cais", connections: ["z2"] }, { id: "z2", name: "Armazém", connections: ["z1"] }],
    positions: [
      { participant_id: "p", participant_name: "Ayla", zone_id: "z1", distance: "proximo", posture: "neutro", concealment: "visivel", engaged_with: ["e1"], engaged_names: ["Saqueador"] },
      { participant_id: "e1", participant_name: "Saqueador", zone_id: "z1", distance: "proximo", posture: "exposto", concealment: "visivel", engaged_with: ["p"], engaged_names: ["Ayla"] },
    ],
  };
  s.combat.wounds = { vitality: 14, max_vitality: 20, slots: { leve: 1 }, by_severity: { leve: [{ regiao: "braço", detail: "corte" }], grave: [], critico: [] } };
  s.player_stats.vitalidade = 14; s.player_stats.hp = 14;
  s.message = "O Saqueador avança, lâmina erguida."; s.message_type = "COMBAT";
  return s;
}

async function openGame(page: Page, name = "Ayla") {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.getByLabel("Sua ação")).toBeVisible();
}
async function tab(page: Page, label: RegExp) {
  await page.getByRole("tab", { name: label }).click();
}

async function targetSizes(page: Page, selectors: string[]) {
  const out: Record<string, { n: number; minW: number; minH: number }> = {};
  for (const sel of selectors) {
    out[sel] = await page.locator(sel).evaluateAll((els) => {
      const r = els.map((e) => e.getBoundingClientRect()).filter((b) => b.width > 0);
      return { n: r.length, minW: Math.round(Math.min(...r.map((b) => b.width), 9999)), minH: Math.round(Math.min(...r.map((b) => b.height), 9999)) };
    });
  }
  return out;
}
async function settle(page: Page) { await page.waitForTimeout(250); }

for (const vp of VIEWPORTS) {
  for (const motion of ["reduce", "no-preference"] as const) {
    test.describe(`@spec201 ${vp.name} ${motion}`, () => {
      test.use({ viewport: { width: vp.width, height: vp.height }, reducedMotion: motion });
      const full = motion === "reduce"; // no-preference: só estados com motion
      const shot = (page: Page, name: string) => save(page, vp.name, name, motion);

      test("auth + saves + create", async ({ page, backend }) => {
        backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
        if (full) {
          backend.authenticated = false;
          await page.goto("/");
          await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
          await settle(page); await shot(page, "auth-default");
          await page.route("**/auth/login", (r) => r.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "bad" }) }));
          await page.getByLabel("E-mail").fill("x@example.test"); await page.getByLabel("Senha").fill("errada-errada");
          await page.getByRole("button", { name: /Entrar/ }).first().click().catch(() => undefined);
          await settle(page); await shot(page, "auth-error");
          backend.authenticated = true;
        }
        await page.goto("/");
        await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
        await settle(page); await shot(page, "saves-default");
        if (full) {
          await page.getByRole("button", { name: /^Ayla/ }).hover(); await shot(page, "saves-hover");
          await page.keyboard.press("Tab"); await shot(page, "saves-focus");
        }
        // criação
        await page.route("**/game/saves", (r) => r.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
        await page.goto("/");
        await expect(page.getByText("Valoria aguarda")).toBeVisible();
        await settle(page); await shot(page, "create-step1-mundo");
        await page.getByRole("button", { name: /Origem/ }).click();
        await settle(page);
        await shot(page, "create-step2-origem-default");
        if (full) {
          await page.getByRole("button", { name: /Vocação/ }).click(); await settle(page); await shot(page, "create-step3-vocacao-default");
          const cardEl = page.locator(".card").nth(1); // fixture: 2 classes; o 2o nao vem pre-selecionado
          const cursor = await cardEl.evaluate((e) => getComputedStyle(e).cursor);
          await cardEl.hover(); await shot(page, "create-card-hover");
          // diagnóstico de hitbox: o que está sob o cursor em 3 pontos do cartão
          const box = (await cardEl.boundingBox())!;
          const probe = async (fx: number, fy: number) => page.evaluate(([x, y]) => {
            const el = document.elementFromPoint(x, y);
            return { tag: el?.tagName, cls: el?.className?.toString() ?? "", insideButton: !!el?.closest("button") };
          }, [box.x + box.width * fx, box.y + box.height * fy]);
          const pts = { topLeftCorner: await probe(0.08, 0.06), center: await probe(0.5, 0.5), bottom: await probe(0.5, 0.94) };
          const btn = cardEl.locator("button.card__select");
          const before = await btn.getAttribute("aria-pressed");
          await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
          const afterCenter = await btn.getAttribute("aria-pressed");
          const bb = (await btn.boundingBox())!;
          record(`create-hitbox-${vp.name}`, { cardCursor: cursor, card: box, button: bb, buttonAreaRatio: +((bb.width * bb.height) / (box.width * box.height)).toFixed(3), pts, pressedBefore: before, pressedAfterClickCenter: afterCenter });
          await btn.click(); await shot(page, "create-card-selected");
          await btn.focus(); await shot(page, "create-card-focus");
          await page.getByRole("button", { name: /Identidade/ }).click(); await settle(page);
          await shot(page, "create-step5-identidade-empty");
        }
      });

      test("play: narrativa, composer e abas", async ({ page, backend }) => {
        backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
        await openGame(page);
        await settle(page); await shot(page, "play-default");
        if (!full) return;
        await page.getByLabel("Sua ação").fill("Examino o sino quebrado");
        await page.getByRole("button", { name: "Agir" }).hover(); await shot(page, "play-composer-hover");
        await page.getByLabel("Sua ação").focus(); await shot(page, "play-composer-focus");
        const tabs: Array<[string, RegExp]> = [["ficha", /Ficha/], ["combate", /Combate/], ["personagens", /Pessoas/], ["mapa", /Mapa/], ["faccoes", /Fações/], ["missoes", /Missões/], ["cronica", /Crônica/], ["codex", /Codex/]];
        for (const [id, label] of tabs) {
          await tab(page, label); await settle(page); await shot(page, `hud-tab-${id}`);
        }
        await tab(page, /Ficha/);
        backend.delayStream();
        await page.getByRole("button", { name: "Agir" }).click();
        await page.waitForTimeout(300); await shot(page, "play-composer-pending");
        backend.releaseStream(); await settle(page); await shot(page, "play-after-turn");
        backend.failNextTurn = true; backend.allowFailure(/game\/action/);
        await page.getByLabel("Sua ação").fill("Falho de propósito");
        await page.getByRole("button", { name: "Agir" }).click(); await page.waitForTimeout(600);
        await shot(page, "play-composer-error");
        await page.getByRole("tab", { name: /Ficha/ }).focus(); await page.keyboard.press("ArrowRight");
        record(`tablist-arrow-keys-${vp.name}`, { selectedAfterArrowRight: await page.getByRole("tab", { selected: true }).first().textContent() });
      });

      test("combate ativo (fixture) e overlays", async ({ page, backend }) => {
        backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
        const a = backend.states.get("game-a")!;
        const base = structuredClone(a);
        backend.states.set("game-a", combatState(a));
        await openGame(page);
        await settle(page); await shot(page, "combat-active");
        if (full) {
          const play = page.getByRole("button", { name: "Jogar Carta" }).first();
          await play.hover(); await shot(page, "combat-card-hover");
          await play.focus(); await shot(page, "combat-card-focus");
          const bb = (await play.boundingBox())!;
          await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await page.mouse.down(); await shot(page, "combat-card-pressed"); await page.mouse.move(2, 2); await page.mouse.up();
          const disabled = page.locator(".combat-card__play:disabled").first();
          record(`combat-card-states-${vp.name}`, {
            disabledCount: await page.locator(".combat-card__play:disabled").count(),
            titleAttrs: await page.locator(".combat-card [title]").evaluateAll((els) => els.map((e) => e.getAttribute("title"))),
            disabledStateText: await disabled.evaluate((e) => e.closest(".combat-card")?.querySelector(".combat-card__state")?.textContent),
            tacticalDockInChatColumn: await page.locator(".tactical-dock").count(),
            dockRect: await page.locator(".tactical-dock").evaluate((e) => { const r = e.getBoundingClientRect(); return { y: Math.round(r.y), h: Math.round(r.height), viewportH: window.innerHeight }; }),
            storyRect: await page.locator("section.story").evaluate((e) => { const r = e.getBoundingClientRect(); return { y: Math.round(r.y), h: Math.round(r.height) }; }),
            targets: await targetSizes(page, [".combat-card__play", ".combat-card__rupture", ".actionchip", ".reaction-chip, .reaction button", ".iconbtn", ".tab"]),
          });
        }
        await tab(page, /Combate/); await settle(page); await shot(page, "combat-hud-tab");
        const dead = combatState(base);
        dead.death_pending = true; dead.player_stats.vitalidade = 0; dead.player_stats.hp = 0; dead.player_stats.estado_terminal = true;
        dead.death = { pending: true, last_action: null, last_action_label: "", entered_terminal: true, stabilization: "falhou", stabilization_attempts: 2, killer: "Saqueador", will_restore_turn: 1, will_lose_turns: 1, retained: ["XP"], reverted: ["ouro"] };
        backend.states.set("game-a", dead);
        await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
        await expect(page.getByRole("dialog")).toBeVisible(); await settle(page); await shot(page, "overlay-death");
        const lu = structuredClone(base);
        lu.player_stats.level = 2;
        lu.player_stats.pending_choices = [{ id: "c1", level: 2, kind: "carta" }];
        lu.player_stats.level_up = { pending: lu.player_stats.pending_choices, eligible: [{ id: "x1", name: "Golpe Pesado", description: "Golpe lento.", tier: 1, cost: 2, frequency: "turno" }], evolvable: [], subclasses: [], virtue_cards: [] } as never;
        backend.states.set("game-a", lu);
        await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
        await expect(page.getByRole("dialog")).toBeVisible({ timeout: 8000 }); await page.waitForTimeout(700); await shot(page, "overlay-levelup");
        const over = structuredClone(base); over.game_over = true;
        backend.states.set("game-a", over);
        await page.reload(); await page.getByRole("button", { name: /^Ayla/ }).click();
        await settle(page); await shot(page, "overlay-gameover");
      });

      test("account + simulador", async ({ page, backend }) => {
        test.skip(!full, "baseline reduce somente"); test.setTimeout(60_000);
        backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
        await openGame(page);
        await page.getByRole("button", { name: /^Conta/ }).click({ timeout: 8000 }).catch(() => undefined);
        await page.waitForTimeout(500); await shot(page, "account-default");
        await page.route("**/data/combat-simulator", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          classes: ["Devoto do Abismo"], levels: [1, 3, 5, 10], quantities: [1, 2, 3],
          enemies: [{ id: "mon_a", name: "Cão de Rebite", category: "lacaio", regions: ["costa"] }, { id: "mon_b", name: "Guardião", category: "elite", regions: ["serra"] }] }) }));
        await page.goto("/");
        await page.getByRole("button", { name: /Simular combate|Laboratório/i }).first().click({ timeout: 8000 }).catch(() => undefined);
        await page.waitForTimeout(500); await shot(page, "simulator-default");
      });
    });
  }
}

test.describe("@spec201 dados", () => {
  test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });

  test("sentinela secreto: DOM e rede", async ({ page, backend }) => {
    backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
    const bodies: string[] = [];
    page.on("response", async (r) => { try { if (r.url().includes("/data/") || r.url().includes("/game/")) bodies.push(`${new URL(r.url()).pathname}::${await r.text()}`); } catch { /* ignore */ } });
    await page.route("**/data/map", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ start_location: "porto", locations: [
      { id: "porto", name: "Porto Cinzento", region: "Costa", region_id: "costa", coords: { x: 30, y: 55 }, danger: 1, tags: [], connections: ["brumalta", "cripta"], lore_seed: "Cais", start: true },
      { id: "brumalta", name: "Brumalta", region: "Serra", region_id: "serra", coords: { x: 70, y: 35 }, danger: 2, tags: [], connections: ["porto"], lore_seed: "Cidade" },
      { id: "cripta", name: `Cripta ${SENTINEL}`, region: "Abismo", region_id: "abismo", coords: { x: 50, y: 80 }, danger: 5, tags: [], connections: ["porto"], lore_seed: `Lore ${SENTINEL}` },
    ] }) }));
    await openGame(page);
    await tab(page, /Mapa/); await settle(page);
    await tab(page, /Codex/); await settle(page);
    const html = await page.content();
    const attrs = await page.evaluate((s) => Array.from(document.querySelectorAll("*")).filter((e) => Array.from(e.attributes).some((a) => a.value.includes(s))).map((e) => e.tagName), SENTINEL);
    const leakedPaths = bodies.filter((b) => b.includes(SENTINEL)).map((b) => b.split("::")[0]);
    record("sentinel", { domContainsSentinel: html.includes(SENTINEL), attrHits: attrs, networkLeakPaths: leakedPaths, note: "DOM limpo; a resposta de /data/map entrega nos nao visitados ao cliente (mascarados so na renderizacao)." });
    expect(html.includes(SENTINEL), "sentinela no DOM").toBe(false);
    expect(attrs).toEqual([]);
  });

  test("axe + reduced-motion + medicoes", async ({ page, backend }) => {
    test.setTimeout(180_000);
    backend.allowConsole(/Failed to load resource/); backend.allowFailure(/fonts\.(googleapis|gstatic)\.com/);
    const hist = Array.from({ length: 60 }, (_, i) => ({ id: `h${i}`, turn: i, epoch: 1, role: i % 2 ? "player" : "narrator", text: `Mensagem ${i}. ${"A névoa cobre o cais e o sino ecoa. ".repeat(6)}`, type: "STORY" as const }));
    backend.histories.set("game-a", hist as never);
    await page.addInitScript(() => {
      const w = window as unknown as { __frames: number[] };
      w.__frames = [];
      let last = performance.now();
      const loop = (t: number) => { w.__frames.push(t - last); last = t; requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    });
    const frameStats = async () => page.evaluate(() => {
      const w = window as unknown as { __frames: number[] };
      const f = w.__frames.slice(); w.__frames.length = 0;
      const s = f.slice().sort((a, b) => a - b);
      return { n: f.length, p50: +(s[Math.floor(s.length * 0.5)] ?? 0).toFixed(1), p95: +(s[Math.floor(s.length * 0.95)] ?? 0).toFixed(1), max: +(s[s.length - 1] ?? 0).toFixed(1), long: f.filter((x) => x > 33).length };
    });
    const reps: Array<Record<string, unknown>> = [];
    for (let i = 0; i < 3; i++) {
      for (const noBlur of [false, true]) {
        await page.emulateMedia({ reducedMotion: "no-preference" });
        await page.goto("/");
        await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
        if (noBlur) await page.addStyleTag({ content: ".msg{filter:none !important}" });
        await frameStats();
        await page.getByRole("button", { name: /^Ayla/ }).click();
        await expect(page.getByLabel("Sua ação")).toBeVisible();
        await page.waitForTimeout(1500);
        const mount = await frameStats();
        const msgCount = await page.locator(".msg").count();
        await frameStats();
        await page.locator(".story").evaluate(async (el) => { for (let y = el.scrollHeight; y > 0; y -= 200) { el.scrollTop = y; await new Promise((r) => requestAnimationFrame(() => r(null))); } });
        const scroll = await frameStats();
        reps.push({ rep: i + 1, noBlur, msgCount, mountFrames: mount, scrollFrames: scroll });
      }
    }
    const idle: Array<Record<string, unknown>> = [];
    for (const rm of ["no-preference", "reduce"] as const) {
      for (let i = 0; i < 3; i++) {
        await page.emulateMedia({ reducedMotion: rm });
        await page.goto("/");
        await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
        await page.waitForTimeout(500);
        const cdp = await page.context().newCDPSession(page);
        await cdp.send("Performance.enable");
        const m = async () => Object.fromEntries(((await cdp.send("Performance.getMetrics")) as { metrics: Array<{ name: string; value: number }> }).metrics.map((x) => [x.name, x.value]));
        const a = await m(); await frameStats(); await page.waitForTimeout(3000); const b = await m(); const fr = await frameStats();
        idle.push({ reducedMotion: rm, rep: i + 1, taskDurationMsPer3s: +(((b.TaskDuration ?? 0) - (a.TaskDuration ?? 0)) * 1000).toFixed(1), scriptDurationMsPer3s: +(((b.ScriptDuration ?? 0) - (a.ScriptDuration ?? 0)) * 1000).toFixed(1), rafFrames: fr.n, canvasDisplay: await page.locator(".ember-canvas").evaluate((e) => getComputedStyle(e).display) });
        await cdp.detach();
      }
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openGame(page);
    const movingInReduce = await page.evaluate(() => Array.from(document.querySelectorAll("*")).filter((e) => { const s = getComputedStyle(e); return s.animationName !== "none" && parseFloat(s.animationDuration) > 0.011; }).map((e) => `${e.tagName}.${e.className}`).slice(0, 20));
    const liveRegions = await page.evaluate(() => Array.from(document.querySelectorAll("[aria-live],[role=status],[role=alert],[role=log]")).map((e) => `${e.tagName}.${e.className}|${e.getAttribute("aria-live") ?? e.getAttribute("role")}`));
    const storyAttrs = await page.locator("section.story").evaluate((e) => ({ role: e.getAttribute("role"), live: e.getAttribute("aria-live"), tabindex: e.getAttribute("tabindex") }));
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const contrast = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      return { faint: cs.getPropertyValue("--faint"), muted: cs.getPropertyValue("--muted"), bg: cs.getPropertyValue("--bg") };
    });
    await tab(page, /Mapa/); await settle(page);
    const mapTargets = await targetSizes(page, [".worldmap__node"]);
    const nodeCursor = await page.locator(".worldmap__node").first().evaluate((e) => getComputedStyle(e).cursor);
    await tab(page, /Codex/); await settle(page);
    const sizes = { ...(await targetSizes(page, [".iconbtn", ".tab", ".btn", ".msg__cost-button", ".codex-cat"])), ...mapTargets, nodeCursor };
    record("medicoes", { sizes, gameStateRef: gameState().game_id, reps, idle, movingInReduce, liveRegions, storyAttrs, contrast, axeViolations: axe.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })) });
  });
});
