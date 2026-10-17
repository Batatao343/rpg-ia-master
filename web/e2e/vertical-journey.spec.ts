// SPEC-212: jornada vertical J-V1 (V01..V09) contra a stack REAL com MockLLM.
// Uma sessão contínua: criar -> conversar -> combater -> vencer/morrer -> abas -> salvar/reabrir ->
// exportar. Os asserts de régua (duplicação, segredo, latência, XP, a11y...) vêm do oráculo Python
// em evals/evaluators/gameplay_gate.py via `scanTrace`; este arquivo só observa e registra.
//
// Provisionamento (feito pelo gate; sem ele a jornada fica SKIPPED e o gate a trata como `not_provisioned`):
//   RPG_VJ_BASE_URL     API real que também serve web/dist (perfil `local`, RPG_FORCE_MOCK=1,
//                       RPG_CLIENT_LATENCY_REPORT=1)
//   RPG_VJ_PYTHON       interpretador do projeto (uv) — roda `python -m evals.evaluators.gameplay_gate`
//   RPG_VJ_SERVICE_KEY  chave de serviço do GoTrue LOCAL (cria o usuário sintético já confirmado)
//   RPG_VJ_API_LOG      arquivo de log da API (linhas JSON `evt: "turn"` do rpg.turn)
//   RPG_VJ_AUTH_URL     (opcional) GoTrue local, default http://127.0.0.1:55321
import { test, expect, type Page, type BrowserContext } from "@playwright/test";
import {
  Guards, TurnLedger, axeRows, createConfirmedUser, deleteUser, piiFindings, readZip, scanTrace,
  serverTurnLines, vjEnv, verticalProvisioned, viewportName, writeTrace, type TurnRecord,
} from "./vertical-support";
import { randomUUID } from "node:crypto";

const HERO = "Mira";
const TABS = ["Codex", "Personagem", "Combate", "Bestiário", "Mapa"] as const;
const MAX_COMBAT_ATTEMPTS = 8;
const MAX_ROUNDS = 14;
const MAX_DEATH_TURNS = 30;

interface Played extends TurnRecord {
  prose: string; ui_xp: number | null; xp_before: number | null; xp_after: number | null;
  turn_before: number | null; turn_after: number | null; history_player_before: number;
  server_lines_added: number; client: Record<string, number | null> | null; server: Record<string, unknown> | null;
}

test.describe.configure({ mode: "serial" });
test.describe("J-V1 jornada vertical", () => {
  test.skip(!verticalProvisioned(), "not_provisioned: stack real + MockLLM ausente (ver cabeçalho)");

  let context: BrowserContext;
  let page: Page;
  let vp = "1440x900";
  let user: { id: string; email: string; password: string };
  const guards = new Guards("");
  const ledger = new TurnLedger();
  const played: Played[] = [];
  const surfaces: Record<string, string> = {};
  const trace: Record<string, any> = {
    speaker: { steps: [] }, roster: { manifest_ids: [], frames: [] }, gesture: { actions: [] },
    a11y: { tabs: [] }, secrets: { surfaces, revealed_secret_ids: [] },
  };
  let gameId = "";
  let deathGameId = "";
  let worldTurnStart = 0;
  let historyPlayerStart = 0;
  let victoryTurn: Played | null = null;
  const extraTurns: Array<Record<string, unknown>> = [];
  const attempts: Record<string, number> = {};

  // --- helpers -------------------------------------------------------------------------------------------
  const composer = () => page.getByRole("textbox", { name: "Sua ação" });
  const panelTab = (name: string) => page.getByRole("tablist", { name: "Abas do painel" }).getByRole("tab", { name, exact: true });
  const csrfHeaders = async () => {
    const cookie = (await context.cookies()).find((c) => c.name === "rpg_csrf");
    return { "X-CSRF-Token": decodeURIComponent(cookie?.value ?? ""), Origin: vjEnv().base };
  };
  const apiState = async (id = gameId) => (await (await page.request.get(`/game/state?game_id=${id}`)).json()) as Record<string, any>;
  const apiHistory = async (id = gameId) => (await (await page.request.get(`/game/history?game_id=${id}`)).json()) as { entries: Array<Record<string, any>> };
  const playerLines = async (id = gameId) => (await apiHistory(id)).entries.filter((e) => e.role === "player").length;

  /** Fecha um turno já enviado: espera o ledger, junta beacon do cliente + linha rpg.turn do servidor. */
  async function track(actionId: string, label: string, before: Record<string, any>, linesBefore: number,
    histBefore: number): Promise<Played> {
    const rec = await ledger.settled(actionId);
    rec.label = label;
    expect(rec.accepted, `${label}: turno recusado (${rec.http_status} ${JSON.stringify(rec.error_detail)})`).toBe(true);
    const state = rec.state!;
    const beacon = await ledger.beaconFor(actionId);
    let added = 0;
    for (let i = 0; i < 50 && added < 1; i++) {
      added = serverTurnLines().length - linesBefore;
      if (!added) await page.waitForTimeout(100);
    }
    const lines = serverTurnLines().slice(linesBefore);
    // O chip dura 4,5 s: só vale como UI deste turno quando o recibo trouxe XP (senão é do turno anterior).
    const gained = Number(state.turn_outcome?.xp_delta ?? 0) > 0;
    let uiXp: number | null = null;
    for (let i = 0; gained && i < 20 && uiXp === null; i++) {
      const chips = await page.locator(".outcome-chip").allTextContents();
      const hit = chips.map((c) => /^\+(\d+) XP$/.exec(c.trim())?.[1]).find(Boolean);
      if (hit) uiXp = Number(hit); else await page.waitForTimeout(100);
    }
    const row: Played = {
      ...rec, prose: String(state.message ?? ""), ui_xp: uiXp,
      xp_before: before.player_stats?.xp ?? null, xp_after: state.player_stats?.xp ?? null,
      turn_before: before.world?.turn_count ?? null, turn_after: state.world?.turn_count ?? null,
      history_player_before: histBefore, server_lines_added: added,
      client: beacon ? { ack_ms: beacon.ack_ms, first_phase_ms: beacon.first_phase_ms, ttfmc_ms: beacon.ttfmc_ms,
        ttlt_ms: beacon.ttlt_ms, state_ms: beacon.state_ms } : null,
      server: lines.length ? lines[lines.length - 1] : null,
    };
    played.push(row);
    surfaces[`prose.${played.length}`] = row.prose;
    if (!state.death_pending) await expect(composer()).toBeEnabled(); // a queda bloqueia o composer (DeathModal)
    return row;
  }

  /** Subida de nível (SPEC-199/209): "Depois" adia; a escolha de subclasse (nível 3) é obrigatória. */
  async function settleLevelUp() {
    const modal = page.getByRole("dialog", { name: /nível|level/i }).or(page.locator(".overlay--levelup"));
    if (!(await modal.first().isVisible().catch(() => false))) return;
    const later = modal.first().getByRole("button", { name: "Depois" });
    if (await later.isEnabled().catch(() => false)) await later.click();
    else {
      await modal.first().locator(".lvlup__card").first().click();
      await modal.first().getByRole("button", { name: "Confirmar" }).click();
    }
    await expect(modal.first()).toHaveCount(0);
  }

  const isActionRequest = (r: { url(): string; method(): string }) =>
    /\/game\/action(\/stream)?$/.test(new URL(r.url()).pathname) && r.method() === "POST";

  async function submit(label: string, text: string, opts: { id?: string } = {}): Promise<Played> {
    const id = opts.id ?? gameId;
    const before = await apiState(id);
    const linesBefore = serverTurnLines().length;
    const histBefore = await playerLines(id);
    await settleLevelUp();
    await composer().fill(text);
    const sent = page.waitForRequest(isActionRequest);
    await page.getByRole("button", { name: "Agir", exact: true }).click();
    return track(String((await sent).postDataJSON().action_id), label, before, linesBefore, histBefore);
  }

  /** Ação estruturada de combate por gesto: `clicks` conta os cliques reais; `aimed` = precisa escolher alvo. */
  async function gesture(label: string, kind: "card_target" | "card_self" | "basic_single" | "basic_target",
    click: () => Promise<void>, aimTarget: string | null): Promise<Played> {
    const before = await apiState();
    const linesBefore = serverTurnLines().length;
    await settleLevelUp();
    const sent = page.waitForRequest(isActionRequest);
    let clicks = 1;
    await click();
    if (aimTarget) {
      await page.locator(`#ws-panel-combate [data-target="${aimTarget}"]`).click();
      clicks += 1;
    }
    const row = await track(String((await sent).postDataJSON().action_id), label, before, linesBefore, 0);
    const after = row.state!;
    const changed = after.combat.round !== before.combat.round
      || JSON.stringify(after.combat.enemies) !== JSON.stringify(before.combat.enemies)
      || !after.combat.active || after.player_stats.entropy !== before.player_stats.entropy;
    trace.gesture.actions.push({ kind: kind === "basic_target" ? "card_target" : kind, clicks,
      confirm_dialogs: await page.getByRole("dialog").count(), shows_result: changed });
    if (after.combat.active) {
      // quem caiu/fugiu/rendeu sai da arena por evento (final_status), nunca por troca de identidade.
      const gone = ((after.combat.encounter_view?.participants ?? []) as Array<Record<string, any>>)
        .filter((p) => p.role === "hostile" && ["morto", "fugiu", "rendido", "capturado", "ausente"].includes(String(p.status)))
        .map((p) => String(p.participant_id));
      (trace.roster.frames as any[]).push({ ids: await uiParticipants(), resolved_ids: gone });
    }
    return row;
  }

  /** O que a oráculo de turnos precisa de cada ação aceita (inclui `receipt_id`, XP, contador). */
  const turnRow = (p: Played) => ({
    action_id: p.action_id, accepted: p.accepted, receipt_id: p.state?.turn_outcome?.receipt_id ?? null,
    world_turn_after: p.turn_after, xp_after: p.xp_after,
  });

  async function snapshotTabs(label: string) {
    const dump: Record<string, string> = {};
    for (const tab of TABS) {
      await panelTab(tab).click();
      await expect(panelTab(tab)).toHaveAttribute("aria-selected", "true");
      const panel = page.locator(`[role="tabpanel"]:visible`).first();
      await expect(panel).toBeVisible();
      // as abas de dossiê carregam sob demanda: espera sair do estado "Consultando…".
      await expect.poll(async () => (await panel.innerText()).toLowerCase().includes("consultando os registros"),
        { message: `${tab}: ainda carregando` }).toBe(false);
      dump[tab] = await panel.innerText();
      surfaces[`tab.${label}.${tab.toLowerCase()}`] = dump[tab];
    }
    return dump;
  }

  async function openSaveByName(name: string) {
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor({ timeout: 30_000 });
    await page.getByRole("button", { name: new RegExp(`^${name}`) }).first().click();
    await composer().waitFor({ timeout: 30_000 });
  }

  async function login() {
    await page.goto("/");
    await page.getByLabel("E-mail", { exact: true }).fill(user.email);
    await page.getByLabel("Senha", { exact: true }).fill(user.password);
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
  }

  const uiParticipants = () => page.evaluate(() => Array.from(document.querySelectorAll(".arena .tchip--enemy"))
    .map((el) => (el as HTMLElement).dataset.participant ?? (el as HTMLElement).dataset.target ?? "")
    .filter((id) => id && id !== "player"));

  // --- ciclo de vida da sessão -------------------------------------------------------------------------------
  test.beforeAll(async ({ browser }, info) => {
    user = await createConfirmedUser();
    vp = viewportName(info);
    context = await browser.newContext({
      viewport: info.project.use.viewport ?? { width: 1440, height: 900 },
      reducedMotion: "reduce", locale: "pt-BR", timezoneId: "America/Sao_Paulo",
      baseURL: vjEnv().base, acceptDownloads: true,
    });
    page = await context.newPage();
    (guards as any).origin = vjEnv().base;
    guards.install(page);
    ledger.install(page);
  });

  test.afterAll(async () => {
    await context?.close();
    if (user) await deleteUser(user.id);
  });

  // --- V01 (R1) -----------------------------------------------------------------------------------------------
  test("V01 create_character_and_open_chat", async () => {
    await login();
    await page.getByRole("button", { name: "Continuar", exact: true }).click();
    await page.getByRole("button", { name: /Origem/ }).click();
    await page.getByRole("radiogroup", { name: "Origem (raça)" }).getByRole("button", { name: "Humano", exact: true }).click();
    await page.getByRole("button", { name: /Vocação/ }).click();
    await page.getByRole("radiogroup", { name: "Vocação (classe)" }).getByRole("button", { name: "Devoto do Abismo", exact: true }).click();
    await page.getByRole("button", { name: /Região/ }).click();
    await page.getByRole("radiogroup", { name: "Região inicial" }).getByRole("button", { name: /Nova Arcádia/ }).click();
    await page.getByRole("button", { name: /Identidade/ }).click();
    await page.getByLabel("Nome do herói").fill(HERO);
    await page.getByRole("button", { name: "Tecer o prólogo" }).click();
    await page.getByRole("button", { name: "Começar a jornada" }).click();
    await composer().waitFor({ timeout: 60_000 });

    const saves = (await (await page.request.get("/game/saves")).json()) as Array<Record<string, any>>;
    const mine = saves.find((s) => s.name === HERO);
    expect(mine, "save recém-criado na lista").toBeTruthy();
    gameId = mine!.game_id;
    const state = await apiState();
    expect(state.player_stats.race).toBe("Humano");
    expect(state.player_stats.class_name).toBe("Devoto do Abismo");
    expect(String(state.message).trim().length, "cena inicial narrada").toBeGreaterThan(20);
    expect(state.speaker?.kind).toBe("narrator");
    await expect(page.getByText(String(state.message).split("\n")[0].slice(0, 40)).first()).toBeVisible();
    worldTurnStart = state.world.turn_count;
    historyPlayerStart = await playerLines();
    surfaces["prose.opening"] = String(state.message);
  });

  // --- V02 (R2) -----------------------------------------------------------------------------------------------
  test("V02 interlocutor_narrator_vs_npc", async () => {
    const state = await apiState();
    const npcs = (state.npcs ?? []) as Array<Record<string, any>>;
    expect(npcs.length, "o prólogo semeou um NPC em cena").toBeGreaterThan(0);
    const npc = npcs[0];
    const npcName = String(npc.name);

    const ask = await submit("V02a ask_narrator", `Quem é ${npcName}?`);
    trace.speaker.steps.push({
      expected: { kind: "narrator", id: "narrator" },
      actual: { kind: ask.state?.speaker?.kind, id: ask.state?.speaker?.id },
      selector_in_dom: false,
    });

    const talk = await submit("V02b address_npc", `${npcName}, o que você sabe sobre a dívida que carrego?`);
    const spoke = talk.state?.speaker ?? {};
    trace.speaker.steps.push({
      expected: { kind: "npc", id: spoke.id },
      actual: { kind: spoke.kind, id: spoke.id },
      ui_label: await page.locator(".msg__role", { hasText: new RegExp(`^${npcName}$`) }).count() ? npcName : "",
      expected_label: npcName,
      selector_in_dom: (await page.getByRole("radio", { name: /narrador/i }).count()
        + await page.getByRole("tab", { name: /narrador/i }).count()
        + await page.getByRole("button", { name: /^narrador$/i }).count()) > 0,
    });
    expect(spoke.kind, "fala dirigida é roteada ao NPC").toBe("npc");
    expect(String(spoke.name).toLowerCase()).toContain(npcName.toLowerCase().split(" ")[0]);
  });

  // --- V03 (R3) -----------------------------------------------------------------------------------------------
  test("V03 threat_opens_combat_split_with_manifest", async () => {
    let state: Record<string, any> = await apiState();
    let n = 0;
    while (!state.combat?.active && n < MAX_COMBAT_ATTEMPTS) {
      n += 1;
      const turn = await submit(`V03 threat#${n}`, "Ataco o vulto nas sombras");
      state = turn.state!;
      if (!state.combat?.active) await submit(`V03 explore#${n}`, "Sigo adiante pela rua.");
    }
    attempts.combat_start = n;
    expect(state.combat?.active, `combate não abriu em ${MAX_COMBAT_ATTEMPTS} tentativas (aleatoriedade do dado sem seed; ver handoff)`).toBe(true);
    const view = state.combat.encounter_view;
    expect(view?.participants?.length, "manifesto SPEC-203").toBeGreaterThan(0);
    // Só os hostis: aliados transitórios (NPC em cena) não entram no manifesto (achado no handoff).
    const manifest = view.participants.filter((p: any) => p.role === "hostile").map((p: any) => p.participant_id as string);
    trace.roster.manifest_ids = manifest;
    // SPEC-204 R10: o combate abre a aba Combate em split.
    await expect(panelTab("Combate")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("region", { name: "Painel de contexto" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Chat da aventura" })).toBeVisible();
    const shown = await uiParticipants();
    expect(shown.sort(), "a UI mostra exatamente os participant_id do manifesto").toEqual([...manifest].sort());
    trace.roster.frames.push({ ids: shown });
  });

  // --- V04 (R4) -----------------------------------------------------------------------------------------------
  test("V04 card_gesture_without_confirmation", async () => {
    const panel = page.locator("#ws-panel-combate");
    let state = await apiState();
    expect(state.combat.active).toBe(true);
    const cards = state.combat.cards as Array<Record<string, any>>;
    const targeted = cards.find((c) => c.type === "ativa" && c.target_kind === "enemy"
      && (c.valid_targets ?? []).length > 0 && !c.invalid_reason);
    expect(targeted, "há Carta ativa com alvo válido (valid_targets, SPEC-205)").toBeTruthy();
    const open = () => panel.getByRole("button", { name: new RegExp(`Jogar Carta ${targeted!.name}`) }).click();
    // R4: Carta com alvo = selecionar + clicar o participant_id (sempre 2 cliques, mesmo com 1 alvo válido).
    state = (await gesture("V04 card_target", "card_target", open, targeted!.valid_targets[0])).state!;
    if (state.combat.active) {
      const self = (state.combat.cards as Array<Record<string, any>>).find((c) => c.type === "ativa"
        && c.target_kind === "self" && (c.valid_targets ?? []).length > 0 && !c.invalid_reason);
      if (self) {
        // Carta de suporte: com aliado em cena há mais de um alvo válido e a UI pede a mira (2 cliques);
        // sem aliado é um clique só (R4: "sem alvo = um clique").
        const several = (self.valid_targets as string[]).length > 1;
        await gesture("V04 card_self", several ? "card_target" : "card_self",
          () => panel.getByRole("button", { name: new RegExp(`Jogar Carta ${self.name}`) }).click(),
          several ? self.valid_targets[0] : null);
      }
    }
    expect(trace.gesture.actions.length).toBeGreaterThan(0);
  });

  // --- V05 (R5) -----------------------------------------------------------------------------------------------
  test("V05 victory_and_defeat_outcomes", async () => {
    // (a) vitória: continua o combate com Ataque básico até o desfecho.
    let state = await apiState();
    let rounds = 0;
    while (state.combat?.active && rounds < MAX_ROUNDS) {
      rounds += 1;
      const basic = (state.combat.basic_actions as Array<Record<string, any>>).find((a) => a.kind === "attack");
      const targets = (basic?.valid_targets ?? []) as string[];
      const row = await gesture(`V05 basic#${rounds}`, targets.length > 1 ? "basic_target" : "basic_single",
        () => page.locator("#ws-panel-combate").getByRole("button", { name: "Ataque básico" }).click(),
        targets.length > 1 ? targets[0] : null);
      state = row.state!;
      if (state.death_pending) break;
    }
    attempts.victory_rounds = rounds;
    expect(state.death_pending, "campanha de vitória não deve cair (aleatoriedade do dado; ver handoff)").toBeFalsy();
    expect(state.combat?.active, "combate encerrou").toBeFalsy();
    const result = state.combat_result ?? {};
    expect(result.outcome, "combat_result.outcome (SPEC-203 R7)").toBe("victory");
    trace.roster.outcome_ids = (result.participants ?? []).map((p: any) => p.participant_id);
    await expect(page.getByRole("region", { name: "Desfecho do combate" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Vitória" })).toBeVisible();
    victoryTurn = played[played.length - 1];
    // O turno seguinte é exploração sem mensagem de combate extra (SPEC-203 R6).
    await settleLevelUp(); // a vitória rende XP: o modal de nível cobre o painel de desfecho
    await page.getByRole("button", { name: "Continuar", exact: true }).click();
    await expect(page.getByRole("region", { name: "Desfecho do combate" })).toHaveCount(0);
    const explore = await submit("V05 explore_after_victory", "Observo o local com calma.");
    expect(explore.state?.combat?.active).toBeFalsy();
    expect(explore.state?.message_type).toBe("STORY");
    expect(Object.keys(explore.state?.combat_result ?? {}), "sem combat_result fora do turno de término").toEqual([]);

    // (b) derrota: segunda campanha-semente, perigosa e frágil, criada pela API e aberta pela UI.
    const created = await page.request.post("/game/new", {
      headers: await csrfHeaders(),
      data: { name: "Tessa", class_name: "Arcanista Cinzento", race: "Humano", region: "Montanhas Afiadas", action_id: randomUUID() },
    });
    expect(created.ok(), await created.text()).toBe(true);
    deathGameId = (await created.json()).game_id;
    await page.reload();
    await openSaveByName("Tessa");
    let dead = false;
    for (let i = 1; i <= MAX_DEATH_TURNS && !dead; i++) {
      const turn = await submit(`V05d fight#${i}`, "Ataco o vulto nas sombras", { id: deathGameId });
      dead = !!turn.state?.death_pending;
    }
    attempts.death_turns = played.filter((p) => p.label.startsWith("V05d")).length;
    expect(dead, "a campanha de derrota caiu (death_pending)").toBe(true);
    const modal = page.getByRole("dialog", { name: /Você tombou/ });
    await expect(modal).toBeVisible();
    await modal.getByRole("button", { name: "Continuar do checkpoint" }).click();
    await expect(modal).toHaveCount(0);
    const restored = await apiState(deathGameId);
    expect(restored.death_pending).toBeFalsy();
    expect(restored.player_stats.vitalidade).toBeGreaterThan(0);
    // volta à campanha principal para os passos seguintes.
    await page.reload();
    await openSaveByName(HERO);
  });

  // --- V06 (R6) -----------------------------------------------------------------------------------------------
  test("V06 xp_in_structured_ui_and_idempotent_receipt", async () => {
    expect(victoryTurn, "turno de vitória registrado").toBeTruthy();
    const won = victoryTurn!;
    const outcome = won.state?.turn_outcome ?? {};
    expect(outcome.receipt_id, "turn_outcome.receipt_id (SPEC-199)").toBeTruthy();
    expect(String(won.prose)).not.toMatch(/\d+\s*XP|\[RESULTADO\]/i);
    // Replay forçado do MESMO action_id/corpo: mesmo recibo, sem XP em dobro, sem turno novo.
    const xpBefore = (await apiState()).player_stats.xp;
    const turnBefore = (await apiState()).world.turn_count;
    const replay = await page.request.post("/game/action", {
      headers: { ...(await csrfHeaders()), "content-type": "application/json" }, data: won.request_json,
    });
    expect(replay.ok(), await replay.text()).toBe(true);
    const replayed = (await replay.json()) as Record<string, any>;
    played.push({ ...won, label: "V06 replay", replay: true, state: replayed, transport: "post",
      prose: String(replayed.message ?? ""), xp_after: replayed.player_stats?.xp ?? null,
      turn_after: replayed.world?.turn_count ?? null } as Played);
    expect(replayed.turn_outcome?.receipt_id).toBe(outcome.receipt_id);
    expect((await apiState()).player_stats.xp).toBe(xpBefore);
    expect((await apiState()).world.turn_count).toBe(turnBefore);
  });

  // --- V07 (R7, R15) ----------------------------------------------------------------------------------------
  test("V07 context_tabs_coherent_and_accessible", async () => {
    const state = await apiState();
    const dump = await snapshotTabs("v07");
    // innerText aplica text-transform (MIRA): comparar sem caixa.
    const low = (tab: string) => dump[tab].toLowerCase();
    expect(low("Personagem")).toContain(HERO.toLowerCase());
    expect(low("Personagem")).toContain("devoto do abismo");
    expect(low("Personagem")).toContain(`${state.player_stats.vitalidade}/${state.player_stats.max_vitalidade}`);
    const prepared = (state.player_stats.cards as Array<Record<string, any>>).filter((c) => c.prepared).map((c) => String(c.name));
    expect(prepared.length).toBeGreaterThan(0);
    expect(low("Combate"), "a aba Combate lista as Cartas preparadas").toContain(prepared[0].toLowerCase());
    expect(low("Mapa")).toContain(String(state.current_location).toLowerCase());
    const dossiers = (await (await page.request.get(`/game/codex/dossiers?game_id=${gameId}`)).json()) as Record<string, any>;
    for (const creature of (dossiers.bestiary ?? []) as Array<Record<string, any>>) {
      expect(low("Bestiário"), "criatura do dossiê aparece na aba").toContain(String(creature.title).toLowerCase());
    }
    for (const tab of TABS) {
      await panelTab(tab).click();
      // Placeholder honesto: nenhuma imagem quebrada ou sem alt (nunca arte errada/vazia).
      const broken = await page.locator(`[role="tabpanel"]:visible img`).evaluateAll((imgs) =>
        (imgs as HTMLImageElement[]).filter((i) => !i.alt || (i.complete && i.naturalWidth === 0)).map((i) => i.src));
      expect(broken, `${tab}: imagem sem alt ou quebrada`).toEqual([]);
      trace.a11y.tabs.push(await axeRows(page, vp, tab));
    }
  });

  // --- V08 (R8, R11) ----------------------------------------------------------------------------------------
  test("V08 save_reload_and_no_duplicate_turn", async () => {
    const before = await apiState();
    const domBefore = await page.locator("article.msg").count();
    await page.reload();
    await openSaveByName(HERO);
    const after = await apiState();
    for (const key of ["current_location"] as const) expect(after[key]).toBe(before[key]);
    expect(after.player_stats.vitalidade).toBe(before.player_stats.vitalidade);
    expect(after.player_stats.xp).toBe(before.player_stats.xp);
    expect(after.world.turn_count).toBe(before.world.turn_count);
    expect(JSON.stringify(after.inventory)).toBe(JSON.stringify(before.inventory));
    await expect.poll(() => page.locator("article.msg").count(), { message: "histórico visível reaberto sem duplicar" }).toBe(domBefore);

    // Reload no meio do SSE: o turno é aceito no servidor, a aba recarrega antes da resposta chegar.
    const turnStart = (await apiState()).world.turn_count;
    const playerStart = await playerLines();
    let actionId = "";
    await page.route("**/game/action/stream", async (route) => {
      actionId = String(route.request().postDataJSON().action_id);
      await route.fetch(); // o servidor termina o turno...
      await new Promise((r) => setTimeout(r, 1500)); // ...mas a resposta fica retida
      await route.abort("failed").catch(() => undefined);
    });
    await composer().fill("Aguardo em silêncio e escuto a cidade.");
    await page.getByRole("button", { name: "Agir", exact: true }).click();
    await expect.poll(() => actionId).not.toBe("");
    guards.induced = true;
    await page.reload();
    await page.unroute("**/game/action/stream");
    guards.induced = false;
    await openSaveByName(HERO);
    // A operação pendente é resolvida (retomada ou já concluída): exatamente UM turno novo.
    const resume = page.getByRole("button", { name: "Consultar / retomar ação pendente" });
    if (await resume.isVisible().catch(() => false) && await resume.isEnabled().catch(() => false)) await resume.click();
    await expect.poll(async () => (await apiState()).world.turn_count, { timeout: 30_000 }).toBe(turnStart + 1);
    expect(await playerLines()).toBe(playerStart + 1);
    const settled = await apiState();
    extraTurns.push({ action_id: actionId, accepted: true, receipt_id: settled.turn_outcome?.receipt_id ?? null,
      world_turn_after: turnStart + 1, xp_after: settled.player_stats.xp });

    // Reenvio explícito do mesmo action_id depois do reload (retry do cliente).
    const retryBody = JSON.stringify({ game_id: gameId, input_text: "Aguardo em silêncio e escuto a cidade.", action_id: actionId });
    const retry = await page.request.post("/game/action", { headers: { ...(await csrfHeaders()), "content-type": "application/json" }, data: retryBody });
    expect([200, 409], "retry do mesmo action_id: replay (200) ou conflito de assinatura (409), nunca turno novo").toContain(retry.status());
    expect((await apiState()).world.turn_count).toBe(turnStart + 1);
    if (retry.status() === 200) extraTurns.push({ ...extraTurns[extraTurns.length - 1] });
  });

  // --- V09 (R9 + transversais R10-R15) --------------------------------------------------------------------
  test("V09 audit_export_and_transversal_oracles", async () => {
    // Export sob demanda pelo dono (SPEC-207): lista de saves -> botão ⇩ -> (reauth) -> download.
    await page.reload();
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor({ timeout: 30_000 });
    await page.getByRole("button", { name: `Exportar sessão de ${HERO} para auditoria` }).click();
    const dialog = page.getByRole("dialog", { name: "Exportar sessão para auditoria" });
    await expect(dialog).toBeVisible();
    const password = dialog.getByLabel("Confirme sua senha");
    if (await password.isVisible().catch(() => false)) {
      await password.fill(user.password);
      await dialog.getByRole("button", { name: "Confirmar" }).click();
    }
    const download = page.waitForEvent("download", { timeout: 60_000 });
    await dialog.getByRole("button", { name: `Exportar ${HERO}` }).click();
    const path = await (await download).path();
    const { readFileSync } = await import("node:fs");
    const files = readZip(readFileSync(path));
    const manifest = JSON.parse(files["manifest.json"]);
    expect(manifest.format).toBe("valoria-audit-export-v1");
    expect(manifest.export_schema_version).toBe(1);
    for (const name of ["state/final_snapshot.json", "state/deltas.jsonl", "timings.jsonl", "errors.jsonl", "knowledge_visibility.jsonl"]) {
      expect(files, `arquivo obrigatório ${name}`).toHaveProperty([name]);
    }
    const sessionFiles = Object.keys(files).filter((n) => n.startsWith("sessions/"));
    const sessionRows = sessionFiles.flatMap((n) => files[n].split("\n").filter(Boolean).map((l) => JSON.parse(l)));
    const exportRefs = sessionRows.map((r) => String(r.action_ref)).filter((r) => r && r !== "null");
    expect(piiFindings(files, [user.email, user.id, gameId, deathGameId]), "PII redigida (SPEC-207)").toEqual([]);
    const final = JSON.parse(files["state/final_snapshot.json"]);
    const revealed = (files["knowledge_visibility.jsonl"].split("\n").filter(Boolean).map((l) => JSON.parse(l))
      .flatMap((r) => r.player_revealed_secret_ids ?? [])) as string[];
    surfaces["export.sessions"] = sessionRows.map((r) => `${r.player_text ?? ""}\n${r.narration ?? ""}`).join("\n");
    surfaces["api.state"] = JSON.stringify(await apiState());
    surfaces["api.history"] = JSON.stringify(await apiHistory());
    trace.secrets.revealed_secret_ids = revealed;
    expect(final.private_reference, "export marca segredos como privados").toBeTruthy();

    // --- oráculos transversais sobre o trace inteiro ---
    const main = played.filter((p) => p.game_id === gameId);
    const accepted = main.filter((p) => !p.replay);
    trace.console = guards.section();
    trace.turns = {
      turns: [...main.map((p) => ({ ...turnRow(p), kind: p.replay ? "replay" : "submit" })), ...extraTurns],
      world_turn_delta: (await apiState()).world.turn_count - worldTurnStart,
      history_player_delta: (await playerLines()) - historyPlayerStart,
      export_action_refs: exportRefs,
    };
    trace.xp = { turns: main.map((p) => ({ prose: p.prose, turn_outcome: p.state?.turn_outcome ?? null, ui_xp: p.ui_xp,
      ui_checked: !p.replay, xp_before: p.xp_before, xp_after: p.xp_after })) };
    trace.latency = { turns: accepted.map((p) => ({ action_id: p.action_id, transport: p.transport, client: p.client, server: p.server })) };
    trace.attempts = attempts;
    trace.viewport = vp;
    const file = writeTrace(vp, { ...trace, played: played.map((p) => ({ label: p.label, action_id: p.action_id, http_status: p.http_status })) });
    const verdict = scanTrace(trace);
    expect(verdict.problems, `oráculos J-V1 (trace em ${file})`).toEqual({});
    test.info().annotations.push({ type: "latency_baseline", description: JSON.stringify(verdict.baseline) });
    test.info().annotations.push({ type: "attempts", description: JSON.stringify(attempts) });
  });
});
