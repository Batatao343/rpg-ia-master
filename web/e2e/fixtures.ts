import { expect, test as base, type Page, type Request, type Route } from "@playwright/test";
import type { GameResponse, SaveSummary } from "../src/types";

const ART = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='360'%3E%3Crect width='100%25' height='100%25' fill='%23120f18'/%3E%3C/svg%3E";

const card = (id: string, name: string, type = "ativa") => ({
  id, name, type, description: `${name} de teste`, effect_kind: "damage", target_kind: "enemy" as const,
  subclass: "", prepared: true, cost: 1, frequency: "turno", spent: false, ready: true,
  has_rupture: false, rupture_ready: false, trigger: type === "reacao" ? "ao_ser_alvo" : "", evolved: null,
});

export function gameState(gameId = "game-a", name = "Ayla"): GameResponse {
  return {
    game_id: gameId, message: "A fogueira crepita em silêncio.", message_type: "STORY",
    current_location: "Porto Cinzento", narrative_summary: "Ayla chegou ao porto.", simulated: true,
    player_stats: {
      name, class_name: "Devoto do Abismo", race: "Humano", hp: 20, max_hp: 20,
      vitalidade: 20, max_vitalidade: 20, ferimentos: {}, dead: false, estado_terminal: false,
      entropy: 8, max_entropy: 10,
      abyss_charge: 0, abyss_tier: "nenhum", defense: 12, gold: 25, level: 1, xp: 0,
      cards: [card("golpe", "Golpe do Véu"), card("aparar", "Aparar", "reacao")],
      virtudes: { forca: 2, agilidade: 2, corpo: 2, mente: 2, carisma: 2 }, xp_next_level: 100,
      pending_choices: [], level_up: {},
    },
    inventory: [{ id: "tocha", name: "Tocha", qty: 1, type: "consumable", equipped: false, slot: null, unique: false }],
    world: {
      location: "Porto Cinzento", location_id: "porto", day: 1, period: "Amanhecer",
      visited: ["porto", "brumalta"], danger: 1, weather: "Névoa", controlled: {}, danger_overrides: {},
      turn_count: 2, map_overlays: { control_changes: [], threats: [], looming_threat: "" }, blocked_routes: [],
      interiors: { here: [], exit_to: null },
    },
    quest: {
      main: { objective: "Encontre o sino perdido", climax: "", current_step: 0, total: 2, arc_title: "O Sino", beats: [] },
      side: [{ id: "q1", title: "Rastros na névoa", description: "Siga as pegadas.", status: "active", origin_name: "Borin", origin_entity_id: "borin", location_id: "brumalta", created_turn: 1, resolved_turn: 0, reward_hint: "Um mapa" }],
      markers: [{ quest_id: "q1", location_id: "brumalta" }],
    },
    combat: {
      active: false, round: 0, order: [], enemies: [], cards: [],
      scene: { zones: [], positions: [] },
      wounds: { vitality: 20, max_vitality: 20, slots: {}, by_severity: { leve: [], grave: [], critico: [] } },
      chase: {}, player_conditions: [], cooldowns: {}, last_player_action: null, reactions: [], suggestions: [],
    },
    npcs: [{ name: "Borin", role: "barqueiro", location: "Porto Cinzento", relationship: 6, last_memory: "Prometeu mostrar a rota." }],
    chronicle: [{ chapter_id: "c1", title: "Chegada", started_turn: 0, location: "Porto Cinzento", entries: [{ text: "Ayla chegou ao porto.", turn: 0, kind: "milestone" }] }],
    factions: [], party: [], death_pending: false, game_over: false,
    continuity: { session_action_count: 0, canonical_turn: 2, timeline_epoch: 1, last_checkpoint_turn: 1, death_history: [] },
    combat_simulation: { enabled: false, finished: false, outcome: null },
    visual: {
      scene: { location_id: "porto", location_name: "Porto Cinzento", scope: "exact", asset: { asset_id: "scene-porto", subject_type: "location", subject_id: "porto", title: "Porto", alt: "Porto Cinzento sob névoa", placeholder_color: "#120f18", variants: { thumbnail: { url: ART, width: 320, height: 180, bytes: 1, sha256: "a" }, display: { url: ART, width: 640, height: 360, bytes: 1, sha256: "b" } } } },
      cue: null,
    },
  };
}

const fixtureEnemy = (id: string, name: string, vit = 6) => ({ id, name, hp: vit, max_hp: 6, vitalidade: vit, max_vitalidade: 6,
  esquiva: 9, protecao: 0, integridade_atual: null, integridade_max: null, recursos_visiveis: {}, conditions: [],
  revealed_cards: [], revealed_resistances: [] });

/** SPEC-205: recalcula `valid_targets` como o servidor atual (inimigos vivos; suporte mira o herói). */
function refreshTargets(state: GameResponse) {
  const alive = state.combat.enemies.map((e) => e.id);
  state.combat.cards = state.combat.cards.map((c) => {
    if (c.valid_targets === undefined || c.type !== "ativa" || c.invalid_reason === "no_entropy") return c;
    const targets = c.target_kind === "self" ? ["player"] : alive;
    return { ...c, valid_targets: targets, invalid_reason: targets.length ? null : "no_valid_target" };
  });
  state.combat.basic_actions = (state.combat.basic_actions ?? []).map((a) =>
    a.kind === "attack" ? { ...a, valid_targets: alive, invalid_reason: alive.length ? null : "no_valid_target" } : a);
  state.combat.scene = { ...state.combat.scene, positions: state.combat.scene.positions.filter((p) =>
    p.participant_id === "player" || alive.includes(p.participant_id)) };
}

type Deferred = { promise: Promise<void>; resolve: () => void };
const deferred = (): Deferred => {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
};

// SPEC-210: grafo do fixture. `docas_velhas` é adjacente ao porto; `torre_proibida` só toca Brumalta
// (não alcançada). Os campos sentinela jamais podem chegar à rede/DOM enquanto o nó não for alcançado.
export const MAP_UNREACHED = { name: "Torre Proibida", lore: "SEGREDO-LORE-TORRE", treasure: "BAU-SENTINELA-TORRE", travelTimeId: "ilha_sem_nome" };
const MAP_GRAPH: Record<string, { name: string; coords: { x: number; y: number }; region_id: string; danger: number; lore_seed: string; links: string[] }> = {
  porto: { name: "Porto Cinzento", coords: { x: 30, y: 55 }, region_id: "costa", danger: 1, lore_seed: "Cais sob névoa", links: ["brumalta", "docas_velhas"] },
  brumalta: { name: "Brumalta", coords: { x: 70, y: 35 }, region_id: "serra", danger: 2, lore_seed: "Cidade muralhada", links: ["porto", "torre_proibida"] },
  docas_velhas: { name: "Docas Velhas", coords: { x: 15, y: 70 }, region_id: "costa", danger: 3, lore_seed: "DOCAS-LORE-OCULTA", links: ["porto"] },
  torre_proibida: { name: MAP_UNREACHED.name, coords: { x: 90, y: 10 }, region_id: "serra", danger: 5, lore_seed: MAP_UNREACHED.lore, links: ["brumalta"] },
};

export class DeterministicBackend {
  dossiers: unknown = null;
  authRequired = true;
  authenticated = true;
  userId = "fixture-user";
  saves: SaveSummary[] = [];
  states = new Map<string, GameResponse>();
  histories = new Map<string, Array<{ id: string; turn: number; epoch: number; role: "player" | "narrator"; text: string; type: "STORY" }>>();
  requests: Array<{ path: string; method: string; body: Record<string, unknown> | null }> = [];
  protectedBeforeAuth = 0;
  refreshCount = 0;
  unexpectedAllowed: RegExp[] = [];
  /** Falhas inesperadas coletadas pelo guard global (verificadas no teardown). */
  guardFailures: string[] = [];
  expectedConsole: RegExp[] = [];
  operations = new Map<string, { signature: string; response: GameResponse; gameId: string; ownerId: string }>();
  failNextTurn = false;
  /** SPEC-205: ações estruturadas de combate ferem o alvo (-4 Vitalidade) em vez de encerrar o combate. */
  combatHits = false;
  /** SPEC-205 R9: alvos que o servidor já considera inválidos (cliente com estado velho) → `invalid_target`. */
  staleTargets = new Set<string>();
  private delayedStream: Deferred | null = null;
  private expirePaths = new Set<string>();
  private refreshGate: Deferred | null = null;
  private unauthorizedSeen = 0;
  artPolls = 0;

  constructor() {
    const a = gameState("game-a", "Ayla");
    const b = gameState("game-b", "Breno");
    b.current_location = "Brumalta"; b.world.location = "Brumalta"; b.world.location_id = "brumalta";
    this.states.set(a.game_id, a); this.states.set(b.game_id, b);
    this.saves = [this.summary(a), this.summary(b)];
    this.histories.set("game-a", [{ id: "a0", turn: 0, epoch: 1, role: "narrator", text: "Ayla chegou ao porto.", type: "STORY" }]);
    this.histories.set("game-b", [{ id: "b0", turn: 0, epoch: 1, role: "narrator", text: "Breno observa Brumalta.", type: "STORY" }]);
  }

  private summary(state: GameResponse): SaveSummary {
    return { game_id: state.game_id, name: state.player_stats.name, class_name: state.player_stats.class_name,
      level: state.player_stats.level, location: state.current_location, day: state.world.day,
      game_over: !!state.game_over, combat_simulation: false, updated_at: 1 };
  }

  /** SPEC-205: combate ativo no contrato atual (`valid_targets`/`invalid_reason`/`basic_actions`). */
  armCombat(gid: string, enemies: Array<[string, string]> = [["e1", "Saqueador"]]) {
    const state = this.states.get(gid)!;
    const [golpe, aparar] = state.player_stats.cards;
    state.combat.active = true; state.combat.round = 1;
    state.combat.enemies = enemies.map(([id, name]) => fixtureEnemy(id, name));
    state.combat.cards = [
      { ...golpe, valid_targets: [], invalid_reason: null },
      { ...golpe, id: "folego", name: "Fôlego", description: "Recupera o fôlego", effect_kind: "cura", target_kind: "self",
        valid_targets: ["player"], invalid_reason: null },
      { ...golpe, id: "cataclismo", name: "Cataclismo", description: "Ruína em área", cost: 9, ready: false,
        valid_targets: [], invalid_reason: "no_entropy" },
      aparar,
    ];
    state.combat.basic_actions = [
      { kind: "attack", valid_targets: [], invalid_reason: null, cost: 0 },
      { kind: "maneuver", maneuver: "guardar", valid_targets: [], invalid_reason: null, cost: 0 },
      { kind: "flee", valid_targets: [], invalid_reason: null, cost: 0 },
    ];
    const pos = (id: string, name: string) => ({ participant_id: id, participant_name: name, zone_id: "ponte", distance: "proximo",
      posture: "neutro", concealment: "visivel", engaged_with: [], engaged_names: [] });
    state.combat.scene = { zones: [{ id: "ponte", name: "Ponte", connections: [] }],
      positions: [pos("player", state.player_stats.name), ...enemies.map(([id, name]) => pos(id, name))] };
    refreshTargets(state);
    return state;
  }

  /** Resolve ação estruturada de combate de forma determinística (só com `combatHits`). */
  private combatHit(current: GameResponse, body: Record<string, unknown> | null): boolean {
    if (!this.combatHits || !current.combat.active || !body || (!body.card_id && !body.action_kind)) return false;
    const card = current.combat.cards.find((c) => c.id === body.card_id);
    current.combat.round += 1; current.message_type = "COMBAT";
    if (card) current.player_stats.entropy -= card.cost;
    if (card?.target_kind === "self") {
      current.message = `Você usa ${card.name} e recupera o fôlego.`;
      return true;
    }
    const target = current.combat.enemies.find((e) => e.id === body.target_id);
    if (target) {
      target.vitalidade -= 4; target.hp = target.vitalidade;
      current.message = `${card?.name ?? "Seu ataque"} atinge ${target.name}.`;
      if (target.vitalidade <= 0) current.combat.enemies = current.combat.enemies.filter((e) => e !== target);
    } else current.message = "O golpe corta o ar.";
    if (!current.combat.enemies.length) { current.combat.active = false; current.message = "O último saqueador cai; o combate termina."; }
    refreshTargets(current);
    return true;
  }

  private rejectStale(gid: string, body: Record<string, unknown> | null) {
    const target = String(body?.target_id ?? "");
    const state = this.states.get(gid);
    if (!target || !state?.combat.active || !this.staleTargets.has(target)) return null;
    // O alvo já caiu no servidor: o estado novo some com ele; nenhum turno, Entropia ou histórico.
    this.staleTargets.delete(target);
    state.combat.enemies = state.combat.enemies.filter((e) => e.id !== target);
    refreshTargets(state);
    return { code: 409, detail: { code: "invalid_target", invalid_reason: "target_dead",
      message: "O alvo escolhido deixou de ser válido. Escolha de novo." } };
  }

  allowFailure(pattern: RegExp) { this.unexpectedAllowed.push(pattern); }
  allowConsole(pattern: RegExp) { this.expectedConsole.push(pattern); }
  delayStream() { this.delayedStream = deferred(); }
  releaseStream() { this.delayedStream?.resolve(); this.delayedStream = null; }
  expireConcurrently(...paths: string[]) { this.expirePaths = new Set(paths); this.refreshGate = deferred(); }

  private json(route: Route, body: unknown, status = 200) {
    return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  }

  private parseBody(route: Route): Record<string, unknown> | null {
    const raw = route.request().postData();
    if (!raw) return null;
    try { return JSON.parse(raw) as Record<string, unknown>; } catch { return null; }
  }

  private actionResult(gid: string, input: string, body: Record<string, unknown> | null = null): GameResponse {
    const current = structuredClone(this.states.get(gid) ?? gameState(gid));
    current.speaker = { kind: "narrator", id: "narrator", name: "Narrador", reason: "classify_story" };
    current.world.turn_count += 1;
    current.combat_result = {};  // SPEC-203: só no turno de término
    current.continuity = { ...(current.continuity!), canonical_turn: current.world.turn_count };
    if (this.combatHit(current, body)) {
      // SPEC-205: resolvido acima (dano determinístico no alvo declarado).
    } else if (/emboscada/i.test(input) && !current.combat.active) {
      // SPEC-216: encontro começa pelo chat (combat.active falso -> verdadeiro).
      this.states.set(gid, current);
      this.armCombat(gid, [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
      current.message = "Saqueadores saltam da névoa; o combate começa."; current.message_type = "COMBAT";
    } else if (/Brumalta/i.test(input)) {
      current.current_location = "Brumalta"; current.world.location = "Brumalta"; current.world.location_id = "brumalta";
      current.message = "A trilha termina nos portões de Brumalta.";
    } else if (/Borin|convers/i.test(input)) {
      current.message = "Borin, o barqueiro, responde sem desviar o olhar."; current.message_type = "NPC";
      // SPEC-202: speaker canônico do turno (indicador passivo no StoryLog).
      current.speaker = { kind: "npc", id: "borin", name: "Borin", reason: "direct_address" };
    } else if (current.combat.active) {
      current.combat.round += 1; current.combat.active = false; current.combat.enemies = [];
      current.message = "O último saqueador cai; o combate termina."; current.message_type = "COMBAT";
      // SPEC-203: desfecho mecânico derivado + recibo SPEC-199 do turno de término.
      const receipt = `rc-${current.world.turn_count}`;
      current.combat.phase = "ended"; current.combat.outcome = "victory";
      current.turn_outcome = { receipt_id: receipt, turn: current.world.turn_count, xp_delta: 50,
        level_delta: 0, gold_delta: 0, items_gained: [], quests_completed: [], source: "combat" };
      current.combat_result = { encounter_id: `${gid}:0:1`, outcome: "victory",
        participants: [{ participant_id: "enemy_saqueador_1", species_label: "Saqueador", final_status: "morto" }],
        xp_event_ref: receipt, loot_ref: null, ended_round: current.combat.round,
        result_event_id: `res-${current.world.turn_count}` };
    } else if (/rastro|quest|pegada/i.test(input)) {
      current.quest.side = current.quest.side.map((q) => ({ ...q, status: "completed", resolved_turn: current.world.turn_count }));
      current.quest.main.current_step = 1; current.message = "Os rastros revelam a passagem secreta.";
    } else current.message = `O mundo responde a: ${input}`;
    if (/vitória/i.test(input)) {  // SPEC-199: turno com ganho estruturado
      current.message = "O último saqueador cai.";
      current.turn_outcome = { receipt_id: `rc-${current.world.turn_count}`, turn: current.world.turn_count,
        xp_delta: 50, level_delta: 0, gold_delta: 0, items_gained: [], quests_completed: [], source: "combat" };
    }
    this.states.set(gid, current);
    const history = this.histories.get(gid) ?? [];
    const turn = current.world.turn_count;
    history.push({ id: `${gid}-${turn}-p`, turn, epoch: 1, role: "player", text: input, type: "STORY" });
    history.push({ id: `${gid}-${turn}-n`, turn, epoch: 1, role: "narrator", text: current.message, type: "STORY" });
    this.histories.set(gid, history);
    return current;
  }

  // SPEC-210: GET /game/map com fog server-side (contrato de services/map_view.py). Grafo do
  // fixture com nós NÃO alcançados que carregam dados sentinela: nada deles pode sair daqui.
  private mapView(route: Route, gid: string) {
    const state = this.states.get(gid);
    if (!state) return this.json(route, { detail: "missing" }, 404);
    const cur = state.world.location_id;
    const visited = new Set<string>(state.world.visited);
    visited.add(cur);
    const ids = new Set<string>(visited);
    for (const c of MAP_GRAPH[cur]?.links ?? []) ids.add(c);
    const nodes = [...ids].filter((id) => MAP_GRAPH[id]).sort().map((id) => {
      const g = MAP_GRAPH[id];
      const st = id === cur ? "atual" : visited.has(id) ? "visitado" : "adjacente";
      const base: Record<string, unknown> = { id, state: st, name: g.name, coords: g.coords };
      if (st !== "atual") base.reachable = (MAP_GRAPH[cur]?.links ?? []).includes(id);
      if (st !== "adjacente") Object.assign(base, { region_id: g.region_id, danger: g.danger, lore_seed: g.lore_seed, art: { location_id: id, scope: "placeholder", asset: null } });
      return base;
    });
    const sent = new Set(nodes.map((n) => n.id as string));
    const edges: { a: string; b: string; blocked: boolean }[] = [];
    for (const id of sent) for (const c of MAP_GRAPH[id].links) if (sent.has(c) && id < c) edges.push({ a: id, b: c, blocked: false });
    const travel_options = (MAP_GRAPH[cur]?.links ?? []).map((id) => ({ location_id: id, name: MAP_GRAPH[id].name, periods: 2, reachable: true, blocked: false, reason: "" }));
    const content = JSON.stringify({ nodes, edges, travel_options });
    const map_version = `fx-${[...content].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7).toString(16)}`;
    return this.json(route, {
      game_id: gid, turn_count: state.world.turn_count, map_version, current_id: cur, anchor_id: cur, nodes, edges,
      interiors: { here: [], exit_to: null }, travel_options, travel_gate: { blocked: !!state.combat.active, reason: state.combat.active ? "Em combate: fuga é uma ação do encontro." : "" },
      looming_threat: "",
    });
  }

  private async handleApi(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const body = this.parseBody(route);
    this.requests.push({ path, method: request.method(), body });

    if (path === "/auth/config") return this.json(route, { required: this.authRequired, authenticated: this.authenticated, user_id: this.authenticated ? this.userId : undefined });
    if (path === "/auth/signup" || path === "/auth/login") { this.authenticated = true; return this.json(route, { authenticated: true, csrf_token: "fixture" }); }
    if (path === "/auth/logout" || path === "/auth/refresh/logout") { this.authenticated = false; return this.json(route, null); }
    if (path === "/auth/refresh") {
      this.refreshCount += 1;
      if (this.refreshGate) await this.refreshGate.promise;
      this.expirePaths.clear(); this.authenticated = true;
      return this.json(route, { authenticated: true });
    }

    if (this.authRequired && !this.authenticated) {
      this.protectedBeforeAuth += 1;
      return this.json(route, { detail: "auth required" }, 401);
    }
    if (this.expirePaths.has(path)) {
      this.unauthorizedSeen += 1;
      if (this.unauthorizedSeen >= 2) this.refreshGate?.resolve();
      return this.json(route, { detail: "expired" }, 401);
    }

    // Default fixture data must never imply a real balance or expose another
    // owner's account data. Account E2E scenarios install their own route stubs.
    if (path === "/account/balance") return this.json(route, { available_milli: "0", reserved_milli: "0" });
    if (path === "/game/saves") return this.json(route, this.saves);
    if (path === "/data/options") return this.json(route, {
      races: ["Humano", "Elfo"], classes: ["Devoto do Abismo", "Médico do Véu"], regions: ["Porto Cinzento", "Brumalta"],
      races_full: [{ id: "humano", name: "Humano", desc: "Adaptável", traits: [{ id: "tenaz", name: "Tenaz", desc: "Resiste", effects: { defense_bonus: 1 } }] }], visuals: { races: {}, classes: {} },
    });
    if (path === "/data/onboarding") return this.json(route, {
      world_intro: { title: "Valoria aguarda", paragraphs: ["A névoa cerca os reinos."] },
      races: { humano: { name: "Humano", tagline: "Tenaz", description: "Sobrevive onde outros caem." } },
      classes: { "Devoto do Abismo": { tagline: "Guarda", description: "Encara o vazio.", playstyle: "Protege aliados." }, "Médico do Véu": { tagline: "Cirurgião", description: "Costura destinos.", playstyle: "Sustenta aliados." } },
      regions: { porto: { name: "Porto Cinzento", tagline: "Névoa", description: "Um cais antigo.", hook: "Um sino desapareceu.", bonus: "+1 rumor" }, brumalta: { name: "Brumalta", tagline: "Muralhas", description: "Cidade elevada.", hook: "Portões fechados.", bonus: "+1 defesa" } },
    });
    if (path === "/game/map") return this.mapView(route, url.searchParams.get("game_id") ?? "");
    if (path === "/data/map") return this.json(route, { start_location: "porto", locations: [
      { id: "porto", name: "Porto Cinzento", region: "Costa", region_id: "costa", coords: { x: 30, y: 55 }, danger: 1, tags: [], connections: ["brumalta"], lore_seed: "Cais sob névoa", start: true },
      { id: "brumalta", name: "Brumalta", region: "Serra", region_id: "serra", coords: { x: 70, y: 35 }, danger: 2, tags: [], connections: ["porto"], lore_seed: "Cidade muralhada" },
    ] });
    if (path === "/game/prologue") return this.json(route, { mock: true, scenario: { prologue: "A névoa chama pelo seu nome.", opening_scene_brief: "No cais", arc_title: "O Chamado", beats: ["Ouvir o sino"], climax: "Encontrar a torre", seed_npcs: [{ name: "Borin", role: "barqueiro", attitude: "neutro", persona: "lacônico" }] } });
    if (path === "/game/new") {
      const state = gameState("game-created", String(body?.name ?? "Herói"));
      state.player_stats.race = String(body?.race ?? "Humano"); state.player_stats.class_name = String(body?.class_name ?? "Devoto do Abismo");
      state.current_location = String(body?.region ?? "Porto Cinzento"); state.world.location = state.current_location;
      this.states.set(state.game_id, state); this.saves = [this.summary(state), ...this.saves]; this.histories.set(state.game_id, []);
      return this.json(route, state);
    }
    if (path === "/game/state") return this.json(route, this.states.get(url.searchParams.get("game_id") ?? "") ?? { detail: "missing" }, this.states.has(url.searchParams.get("game_id") ?? "") ? 200 : 404);
    if (path === "/game/history") {
      const gid = url.searchParams.get("game_id") ?? "";
      return this.json(route, { entries: this.histories.get(gid) ?? [], next_cursor: null, epoch: 1, partial_history: false });
    }
    const opMatch = path.match(/^\/game\/([^/]+)\/operations\/([^/]+)$/);
    if (opMatch) {
      const found = this.operations.get(opMatch[2]);
      return this.json(route, found ? { status: "completed", response: found.response } : { status: "missing", response: null });
    }
    const costMatch = path.match(/^\/game\/([^/]+)\/operations\/([^/]+)\/cost$/);
    if (costMatch) {
      const [, gameId, operationId] = costMatch;
      const found = this.operations.get(operationId);
      if (!found || found.gameId !== gameId || found.ownerId !== this.userId) {
        return this.json(route, { detail: "operation not found" }, 404);
      }
      return this.json(route, {
        history_id: null, cost_milli: null, technical_cost_usd: null,
        technical_cost_basis: null, technical_cost_exact: false,
      });
    }
    if (path === "/game/action/stream") {
      const gid = String(body?.game_id ?? "game-a"); const input = String(body?.input_text ?? ""); const actionId = String(body?.action_id ?? "");
      const stale = this.rejectStale(gid, body);  // SSE de erro como o api.py real (`http_error`)
      if (stale) return route.fulfill({ status: 200, contentType: "text/event-stream", body: `event: error\ndata: ${JSON.stringify(stale)}\n\n` });
      const result = this.actionResult(gid, input, body); this.operations.set(actionId, { signature: JSON.stringify(body), response: result, gameId: gid, ownerId: this.userId });
      if (this.delayedStream) await this.delayedStream.promise;
      if (this.failNextTurn) return route.abort("failed");
      const sse = `event: phase\ndata: {"node":"storyteller"}\n\nevent: narrative\ndata: ${JSON.stringify({ chunk: result.message, done: true })}\n\nevent: state\ndata: ${JSON.stringify(result)}\n\n`;
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: sse });
    }
    if (path === "/game/action") {
      const gid = String(body?.game_id ?? "game-a"); const input = String(body?.input_text ?? ""); const actionId = String(body?.action_id ?? "");
      if (this.failNextTurn) { this.failNextTurn = false; return route.abort("failed"); }
      const signature = JSON.stringify(body); const existing = this.operations.get(actionId);
      if (existing && existing.signature !== signature) return this.json(route, { detail: "idempotency conflict" }, 409);
      if (existing) return this.json(route, existing.response);
      const stale = this.rejectStale(gid, body);
      if (stale) return this.json(route, { detail: stale.detail }, 409);
      const result = this.actionResult(gid, input, body); this.operations.set(actionId, { signature, response: result, gameId: gid, ownerId: this.userId }); return this.json(route, result);
    }
    if (path === "/game/death") {
      const gid = String(body?.game_id ?? "game-a"); const state = structuredClone(this.states.get(gid) ?? gameState(gid));
      state.death_pending = false; state.game_over = body?.choice === "accept"; state.player_stats.hp = state.game_over ? 0 : 12; state.player_stats.vitalidade = state.player_stats.hp;
      this.states.set(gid, state); return this.json(route, state);
    }
    if (path === "/game/levelup") {
      const gid = String(body?.game_id ?? "game-a"); const state = this.states.get(gid)!;
      state.player_stats.pending_choices = []; state.player_stats.level_up = {};
      return this.json(route, { ok: true, player_stats: { pending_choices: [], level_up: {}, level: state.player_stats.level } });
    }
    if (path === "/game/cards/prepare") {  // SPEC-209: mesma regra do servidor (combate/limite/Acervo)
      const gid = String(body?.game_id ?? "game-a"); const state = this.states.get(gid)!;
      const wanted = ((body?.prepared as string[]) ?? []); const ps = state.player_stats;
      if (state.combat.active || ps.can_reorganize?.allowed === false)
        return this.json(route, { detail: ps.can_reorganize?.reason || "Não é possível reorganizar as Cartas em combate." }, 409);
      if (wanted.some((id) => !ps.cards.some((c) => c.id === id))) return this.json(route, { detail: "Cartas fora do Acervo." }, 400);
      if (wanted.length > (ps.prepared_slots ?? 0)) return this.json(route, { detail: `Máximo ${ps.prepared_slots} Cartas preparadas neste nível.` }, 400);
      ps.cards = ps.cards.map((c) => ({ ...c, prepared: wanted.includes(c.id) }));
      return this.json(route, { ok: true, prepared_cards: wanted, cards: ps.cards, prepared_slots: ps.prepared_slots });
    }
    const artMatch = path.match(/^\/game\/([^/]+)\/art\/([^/]+)$/);
    if (artMatch) {
      this.artPolls += 1;
      // React StrictMode cancela a primeira consulta durante o remount de
      // desenvolvimento; a segunda mantém o estado pending observável.
      if (this.artPolls <= 2) return this.json(route, { status: "pending", placeholder: true });
      return this.json(route, { status: "ready", placeholder: false, assets: [{ asset_id: "portrait", variant: "full", url: ART, width: 512, height: 768 }] });
    }
    if (path === "/game/chronicle/search") return this.json(route, { mode: "lexical_fallback", index_current: true, hits: [] });
    // SPEC-211: dossiês (vazios por padrão; testes definem `backend.dossiers`).
    if (path === "/game/codex/dossiers") return this.json(route, this.dossiers ?? { version: 0, generated_at_turn: 0, sections: { npcs: [], locations: [], factions: [], secrets: [], chronicle_index: [] }, bestiary: [], meta: { taxonomy_version: 1 } });
    if (path === "/game/codex") return this.json(route, { locations: [], factions: [], characters: [], creatures: [], secrets: [] });
    return this.json(route, { detail: `fixture route missing: ${path}` }, 404);
  }

  clientErrorBeacons = 0;

  async install(page: Page) {
    await page.route("**/*", async (route) => {
      const path = new URL(route.request().url()).pathname;
      // SPEC-244: beacon de erro do cliente. Aceito e contado; o teste decide se
      // algum erro de cliente é esperado olhando `clientErrorBeacons`.
      if (path === "/telemetry/client-error") {
        this.clientErrorBeacons += 1;
        return route.fulfill({ status: 204, body: "" });
      }
      if (path.startsWith("/auth/") || path.startsWith("/data/") || path.startsWith("/game/") || path.startsWith("/account/")) return this.handleApi(route);
      return route.continue();
    });
  }
}

type Fixtures = { backend: DeterministicBackend };
export const test = base.extend<Fixtures>({
  backend: [async ({ page }, use) => {
    const backend = new DeterministicBackend();
    const failures = backend.guardFailures;
    page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error" && !backend.expectedConsole.some((p) => p.test(message.text()))) {
        failures.push(`console.error: ${message.text()}`);
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 500 && !backend.unexpectedAllowed.some((p) => p.test(response.url()))) failures.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    // Uma navegação disparada pelo próprio teste (goto/reload) descarta o
    // documento anterior e o Chromium aborta (net::ERR_ABORTED) o que ele ainda
    // tinha em voo — boot da API, fontes. Isso não é falha da aplicação. Só
    // ignoramos esse caso exato: requisição emitida antes do commit do novo
    // documento de uma navegação do teste (o documento antigo segue pedindo
    // fontes até o commit) e abortada depois dele. Abortos da própria app
    // (AbortController, StrictMode) fora dessa janela seguem reprovando.
    const issuedAt = new WeakMap<Request, number>();
    let requestSeq = 0;
    let testNavigating = false;
    let navigationFence = -1;
    // Abortos vistos durante a navegação só são julgados quando ela termina:
    // o Chromium os reporta antes do commit que move a cerca.
    let undecided: { seq: number; line: string }[] = [];
    const decide = ({ seq, line }: { seq: number; line: string }) => { if (seq >= navigationFence) failures.push(line); };
    page.on("request", (request) => { issuedAt.set(request, requestSeq++); });
    page.on("framenavigated", (frame) => { if (testNavigating && frame === page.mainFrame()) navigationFence = requestSeq; });
    for (const method of ["goto", "reload", "goBack", "goForward"] as const) {
      const original = page[method].bind(page) as (...args: unknown[]) => Promise<unknown>;
      (page as unknown as Record<string, unknown>)[method] = async (...args: unknown[]) => {
        testNavigating = true;
        try { return await original(...args); } finally {
          testNavigating = false;
          undecided.forEach(decide); undecided = [];
        }
      };
    }
    page.on("requestfailed", (request) => {
      if (backend.unexpectedAllowed.some((p) => p.test(request.url()))) return;
      const errorText = request.failure()?.errorText ?? "";
      const line = `requestfailed: ${request.url()} (${errorText})`;
      if (errorText !== "net::ERR_ABORTED") return void failures.push(line);
      const entry = { seq: issuedAt.get(request) ?? Number.POSITIVE_INFINITY, line };
      if (testNavigating) undecided.push(entry); else decide(entry);
    });
    await backend.install(page);
    await use(backend);
    // Fecha a aplicação enquanto as rotas determinísticas ainda estão ativas;
    // evita que effects do React escapem para o proxy do Vite no teardown.
    await page.close();
    expect(failures, failures.join("\n")).toEqual([]);
  }, { auto: true }],
});

export { expect };
