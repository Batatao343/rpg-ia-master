import { expect, test as base, type Page, type Route } from "@playwright/test";
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
      mana: 0, max_mana: 0, stamina: 0, max_stamina: 0, entropy: 8, max_entropy: 10,
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

type Deferred = { promise: Promise<void>; resolve: () => void };
const deferred = (): Deferred => {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
};

export class DeterministicBackend {
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
  expectedConsole: RegExp[] = [];
  operations = new Map<string, { signature: string; response: GameResponse }>();
  failNextTurn = false;
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

  private actionResult(gid: string, input: string): GameResponse {
    const current = structuredClone(this.states.get(gid) ?? gameState(gid));
    current.world.turn_count += 1;
    current.continuity = { ...(current.continuity!), canonical_turn: current.world.turn_count };
    if (/Brumalta/i.test(input)) {
      current.current_location = "Brumalta"; current.world.location = "Brumalta"; current.world.location_id = "brumalta";
      current.message = "A trilha termina nos portões de Brumalta.";
    } else if (/Borin|convers/i.test(input)) {
      current.message = "Borin, o barqueiro, responde sem desviar o olhar."; current.message_type = "NPC";
    } else if (current.combat.active) {
      current.combat.round += 1; current.combat.active = false; current.combat.enemies = [];
      current.message = "O último saqueador cai; o combate termina."; current.message_type = "COMBAT";
    } else if (/rastro|quest|pegada/i.test(input)) {
      current.quest.side = current.quest.side.map((q) => ({ ...q, status: "completed", resolved_turn: current.world.turn_count }));
      current.quest.main.current_step = 1; current.message = "Os rastros revelam a passagem secreta.";
    } else current.message = `O mundo responde a: ${input}`;
    this.states.set(gid, current);
    const history = this.histories.get(gid) ?? [];
    const turn = current.world.turn_count;
    history.push({ id: `${gid}-${turn}-p`, turn, epoch: 1, role: "player", text: input, type: "STORY" });
    history.push({ id: `${gid}-${turn}-n`, turn, epoch: 1, role: "narrator", text: current.message, type: "STORY" });
    this.histories.set(gid, history);
    return current;
  }

  private async handleApi(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const body = this.parseBody(route);
    this.requests.push({ path, method: request.method(), body });

    if (path === "/auth/config") return this.json(route, { required: this.authRequired, authenticated: this.authenticated, user_id: this.authenticated ? this.userId : undefined });
    if (path === "/auth/signup" || path === "/auth/login") { this.authenticated = true; return this.json(route, { authenticated: true, csrf_token: "fixture" }); }
    if (path === "/auth/logout") { this.authenticated = false; return this.json(route, null); }
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
    if (path === "/game/action/stream") {
      const gid = String(body?.game_id ?? "game-a"); const input = String(body?.input_text ?? ""); const actionId = String(body?.action_id ?? "");
      const result = this.actionResult(gid, input); this.operations.set(actionId, { signature: JSON.stringify(body), response: result });
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
      const result = this.actionResult(gid, input); this.operations.set(actionId, { signature, response: result }); return this.json(route, result);
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
    const artMatch = path.match(/^\/game\/([^/]+)\/art\/([^/]+)$/);
    if (artMatch) {
      this.artPolls += 1;
      // React StrictMode cancela a primeira consulta durante o remount de
      // desenvolvimento; a segunda mantém o estado pending observável.
      if (this.artPolls <= 2) return this.json(route, { status: "pending", placeholder: true });
      return this.json(route, { status: "ready", placeholder: false, assets: [{ asset_id: "portrait", variant: "full", url: ART, width: 512, height: 768 }] });
    }
    if (path === "/game/chronicle/search") return this.json(route, { mode: "lexical_fallback", index_current: true, hits: [] });
    if (path === "/game/codex") return this.json(route, { locations: [], factions: [], characters: [], creatures: [], secrets: [] });
    return this.json(route, { detail: `fixture route missing: ${path}` }, 404);
  }

  async install(page: Page) {
    await page.route("**/*", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.startsWith("/auth/") || path.startsWith("/data/") || path.startsWith("/game/")) return this.handleApi(route);
      return route.continue();
    });
  }
}

type Fixtures = { backend: DeterministicBackend };
export const test = base.extend<Fixtures>({
  backend: [async ({ page }, use) => {
    const backend = new DeterministicBackend();
    const failures: string[] = [];
    page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error" && !backend.expectedConsole.some((p) => p.test(message.text()))) {
        failures.push(`console.error: ${message.text()}`);
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 500 && !backend.unexpectedAllowed.some((p) => p.test(response.url()))) failures.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    page.on("requestfailed", (request) => {
      if (!backend.unexpectedAllowed.some((p) => p.test(request.url()))) failures.push(`requestfailed: ${request.url()} (${request.failure()?.errorText})`);
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
