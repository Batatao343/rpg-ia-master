// Espelha os DTOs da API (api.py :: GameResponse / blocos auxiliares).

// Fase 4.1: habilidade conhecida (id canônico + nome exibível)
// spec arvores-habilidade-classes (R10): tipo da habilidade — passiva/utilitária
// não é ação de combate clicável; ganham selo na ficha.
export type AbilityKind = "active" | "passive" | "utility";

export interface AbilityRef {
  id: string;
  name: string;
  branch: string | null;
  kind?: AbilityKind;
}

export interface PendingChoice {
  id: string;
  level: number;
  kind: "carta" | "virtude" | "ability" | "attribute";
}

export interface EligibleAbility {
  id: string;
  name: string;
  description: string;
  branch?: string | null;
  branch_name?: string | null;
  subclass?: string;
  tier: number | string;
  cost: number;
  resource_type?: string;
  frequency?: string;
  kind?: AbilityKind;
}

export interface BranchInfo {
  name: string;
  theme: string;
  lore_ref?: string | null;
  identity: string;
  description: string;
}

// Vazio ({}) quando não há escolha pendente — payload enxuto.
export interface LevelUpBlock {
  pending?: PendingChoice[];
  eligible?: EligibleAbility[];
  evolvable?: Array<{ id: string; name: string }>;
  current_branch?: string | null;
  branches?: Record<string, BranchInfo>;
}

export interface PlayerStats {
  name: string;
  class_name: string;
  race: string;
  hp: number;
  max_hp: number;
  vitalidade: number;
  max_vitalidade: number;
  ferimentos: Record<string, Array<Record<string, unknown>>>;
  dead: boolean;
  estado_terminal: boolean;
  mana: number;
  max_mana: number;
  stamina: number;
  max_stamina: number;
  // spec refatoracao-sistema-classes: Entropia (pool das 5 Posturas) + Carga do Abismo.
  entropy?: number;
  max_entropy?: number;
  abyss_charge?: number;
  abyss_tier?: string; // "nenhum"|"leve"|"moderado"|"severo" | "?" (Médico, oculto)
  defense: number;
  gold: number;
  level: number;
  xp: number;
  cards: CardView[];
  virtudes: Record<"forca" | "agilidade" | "corpo" | "mente" | "carisma", number>;
  xp_next_level: number | null; // null = nível máximo
  pending_choices: PendingChoice[];
  level_up: LevelUpBlock;
}

export interface NpcView {
  name: string;
  role: string;
  location: string;
  relationship: number; // 0..10
  last_memory: string;
}


export interface ControlChange {
  location_id: string;
  controller_name: string;
  turn: number;
}

export interface ThreatAlert {
  region_id: string;
  hint: string;
  turn: number;
}

export interface MapOverlays {
  control_changes: ControlChange[];
  threats: ThreatAlert[];
  looming_threat: string;
}

export interface InteriorRef {
  id: string;
  name: string;
  danger: number;
  tags: string[];
}

export interface WorldBlock {
  location: string;
  location_id: string;
  day: number;
  period: string;
  visited: string[];
  danger: number;
  weather: string; // Fase 6.5: rótulo do clima ("Miasma denso", "Nevasca"...)
  light?: { dark: boolean; lit: boolean; label: string }; // spec itens-vivos-e-luz: estado de luz
  controlled: Record<string, string>; // Fase 3.4: location_id -> NOME de quem domina (era faction_id)
  danger_overrides: Record<string, number>; // location_id -> perigo elevado (ascensão)
  turn_count: number; // Fase 3.2: dispara refetch do Codex quando o turno muda
  map_overlays: MapOverlays; // Fase 3.4
  blocked_routes: Array<{ a: string; b: string }>; // Fase 6.1: comércio cortado
  // spec mapa-sublocais: interiores do local atual + saída quando dentro de um
  interiors?: { here: InteriorRef[]; exit_to: { id: string; name: string } | null };
}

export interface Beat {
  description: string;
  status: "pending" | "done";
}

export interface MainQuest {
  objective: string;
  climax: string;
  current_step: number;
  total: number;
  arc_title: string;
  beats: Beat[];
}

export interface Quest {
  id: string;
  title: string;
  description: string;
  status: "active" | "completed" | "failed";
  origin_name: string;
  origin_entity_id: string;
  location_id: string;
  created_turn: number;
  resolved_turn: number;
  reward_hint: string;
}

export interface QuestMarker {
  quest_id: string;
  location_id: string;
}

export interface QuestBlock {
  main: MainQuest;
  side: Quest[];
  markers: QuestMarker[];
}

export interface Condition {
  name: string;
  dot: number;
  duration: number;
}

export interface EnemyView {
  id: string;
  name: string;
  hp: number;
  max_hp: number;
  vitalidade: number;
  max_vitalidade: number;
  esquiva: number | null;
  protecao: number | null;
  integridade_atual: number | null;
  integridade_max: number | null;
  recursos_visiveis: Record<string, number>;
  conditions: Condition[];
  revealed_cards: Array<{ id: string; name: string }>;
  revealed_resistances: string[];
}

export interface CardView {
  id: string;
  name: string;
  type: "ativa" | "reacao" | "passiva" | "virtude" | string;
  description: string;
  effect_kind: string;
  target_kind: "self" | "enemy";
  subclass: string;
  prepared: boolean;
  cost: number;
  frequency: string;
  spent: boolean;
  ready: boolean;
  has_rupture: boolean;
  rupture_ready: boolean;
  trigger: string;
  evolved: string | null;
}

export interface WoundView {
  regiao?: string;
  region?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface WoundTrackView {
  vitality: number;
  max_vitality: number;
  slots: Partial<Record<"leve" | "grave" | "critico", number>>;
  by_severity: Record<"leve" | "grave" | "critico", WoundView[]>;
}

export interface ScenePosition {
  participant_id: string;
  participant_name: string;
  zone_id: string;
  distance: "proximo" | "distante" | "separado" | string;
  posture: "protegido" | "neutro" | "exposto" | string;
  concealment: "visivel" | "escondido" | string;
  engaged_with: string[];
  engaged_names: string[];
}

export interface ConflictSceneView {
  zones: Array<{ id: string; name: string; connections: string[] }>;
  positions: ScenePosition[];
}

export interface ChaseView {
  track?: "pressionado" | "afastado" | "quase_livre" | "escapou" | "alcancado";
  steps?: string[];
  escaped?: boolean;
  caught?: boolean;
  pursuers?: string[];
  last_roll?: { total?: number; difficulty?: number; sucesso?: boolean };
}

export interface InitiativeSlot {
  name: string;
  side: string; // "hero" | "enemy"
  init: number;
}

export interface CombatBlock {
  active: boolean;
  round: number;
  order: InitiativeSlot[];
  enemies: EnemyView[];
  cards: CardView[];
  scene: ConflictSceneView;
  wounds: WoundTrackView;
  chase: ChaseView;
  player_conditions: Condition[];
  cooldowns: Record<string, number>;
  // spec polish-sessao (R4): chips mecânicos derivados da ficha
  suggestions?: string[];
  last_player_action?: {
    kind: "attack" | "card" | "item" | "maneuver" | "move" | "pass" | "flee";
    card_id: string | null;
    item_id: string | null;
    target_id: string | null;
    maneuver: string | null;
    direction: string | null;
    region: string | null;
    result: "ok" | "miss" | "hit" | "invalid" | "fled" | "flee_failed" | "pass";
    attempted: boolean;
    flee_destination_id: string | null;
  } | null;
  reactions?: Array<{ participant: string; card_id: string; custo: number }>;
}

export interface ActionOptions {
  action_id?: string;
  card_id?: string;
  target_id?: string;
  ruptura?: boolean;
  reaction_card_id?: string;
  action_kind?: "attack" | "maneuver" | "pass" | "flee";
  maneuver?: "engajar" | "desengajar" | "guardar" | "esconder" | "procurar";
}

export interface CombatSimulatorEnemy {
  id: string;
  name: string;
  category: "lacaio" | "padrao" | "elite" | "chefe" | "nomeado";
  regions: string[];
}

export interface CombatSimulatorOptions {
  classes: string[];
  levels: Array<1 | 3 | 5 | 10>;
  quantities: Array<1 | 2 | 3>;
  enemies: CombatSimulatorEnemy[];
}

export interface CombatSimulatorPayload {
  class_name: string;
  level: 1 | 3 | 5 | 10;
  enemy_id: string;
  quantity: 1 | 2 | 3;
}

export interface CombatSimulationMeta {
  enabled?: boolean;
  enemy_id?: string;
  quantity?: number;
  finished?: boolean;
  outcome?: "victory" | "defeat" | null;
}

export interface DeathView {
  pending: boolean;
  last_action: CombatBlock["last_player_action"];
  last_action_label: string;
  entered_terminal: boolean;
  stabilization: string;
  stabilization_attempts: number;
  killer: string;
}

// spec polish-sessao (R1): resumo de campanha salva (GET /game/saves)
export interface SaveSummary {
  game_id: string;
  name: string;
  class_name: string;
  level: number;
  location: string;
  day: number;
  game_over: boolean;
  combat_simulation: boolean;
  updated_at: number;
}

export interface ReputationPoint {
  turn: number;
  delta: number;
  value: number;
}

export interface FactionView {
  id: string;
  name: string;
  goal: string; // "" se o jogador ainda não souber o plano
  knows_goal: boolean;
  region: string;
  progress: number | null; // SNAPSHOT visto pelo jogador (null = desconhecido); nunca o ao vivo
  intel_stale: boolean; // true se o snapshot pode estar defasado
  disposition: "hostil" | "neutro" | "aliado";
  reputation: number; // -100..100
  completed: boolean;
  history: ReputationPoint[]; // Fase 3.4: derivado do event_log (reputation_changed)
  stability_label: "estável" | "instável" | "em colapso"; // Fase 3.4: nunca o número interno
}

export interface ChronicleEntry {
  text: string;
  turn: number;
  kind: "milestone" | "prose"; // milestone = determinístico (event_log); prose = menestrel LLM
  event_id?: string; // só milestones — auditoria
}

export interface ChronicleChapter {
  title: string;
  started_turn: number;
  location: string;
  entries: ChronicleEntry[];
}

export type MessageType = "STORY" | "COMBAT" | "NPC" | "LOOT";

// Fase 4.3: inventário estruturado (nome canônico vem da API — nunca title(id))
export interface InventoryEntry {
  id: string;
  name: string;
  qty: number;
  type: string; // weapon | armor | consumable | material | ...
  equipped: boolean;
  slot: string | null;
  unique: boolean; // Fase 6.2: um por mundo (◆)
}

// Fase 4.5: companheiro da party (HP bar no HUD)
export interface PartyMember {
  name: string;
  hp: number;
  max_hp: number;
  vitalidade: number;
  max_vitalidade: number;
  active: boolean;
  archetype: string;
  status: string; // "ativo" | "morto"
}

export interface GameResponse {
  game_id: string;
  message: string;
  message_type: MessageType;
  player_stats: PlayerStats;
  inventory: InventoryEntry[];
  current_location: string;
  narrative_summary: string;
  simulated: boolean;
  world: WorldBlock;
  quest: QuestBlock;
  combat: CombatBlock;
  npcs: NpcView[];
  chronicle: ChronicleChapter[];
  factions: FactionView[];
  party: PartyMember[];
  // spec checkpoints-morte: queda letal — o cliente abre a tela de morte.
  death_pending?: boolean;
  game_over?: boolean;
  death?: DeathView;
  combat_simulation: CombatSimulationMeta;
}

export interface CreateOptions {
  races: string[];
  classes: string[];
  regions: string[];
  // Fase 2.5b: raças completas (desc + traits) p/ os cards do wizard
  races_full?: RaceFull[];
}

// spec onboarding-valoria: raça canônica de origins.json (via /data/options)
export interface RaceTrait {
  id: string;
  name: string;
  desc: string;
  effects: Record<string, unknown>;
}

export interface RaceFull {
  id: string;
  name: string;
  desc: string;
  traits: RaceTrait[];
}

// spec onboarding-valoria: lore curado do wizard (GET /data/onboarding)
export interface RegionCard {
  name: string;
  tagline: string;
  description: string;
  hook: string;
  bonus: string;
}

export interface ClassCard {
  tagline: string;
  description: string;
  playstyle: string;
}

export interface RaceCard {
  name: string;
  tagline: string;
  description: string;
}

export interface OnboardingData {
  world_intro: { title: string; paragraphs: string[] };
  regions: Record<string, RegionCard>;
  classes: Record<string, ClassCard>;
  races: Record<string, RaceCard>;
}

export interface CreatePayload {
  name: string;
  race: string;
  class_name: string;
  region: string;
  level: number;
  backstory: string;
  // spec inicio-personalizado: cenário aprovado no passo de prólogo (opcional)
  scenario?: StartScenario | null;
}

// spec inicio-personalizado: cenário de abertura (POST /game/prologue)
export interface SeedNPC {
  name: string;
  role: string;
  attitude: string; // "hostil" | "neutro" | "aliado"
  persona: string;
}

export interface StartScenario {
  prologue: string;
  opening_scene_brief: string;
  arc_title: string;
  beats: string[];
  climax: string;
  seed_npcs: SeedNPC[];
}

export interface PrologueResponse {
  scenario: StartScenario;
  mock: boolean;
}

// Grafo do mundo (GET /data/map) — data/world_map.json
export interface MapLocation {
  id: string;
  name: string;
  region: string;
  region_id: string; // Fase 3.4: agrupa locais pra overlay de ameaça (threat_alerts)
  coords: { x: number; y: number };
  danger: number;
  tags: string[];
  connections: string[];
  lore_seed: string;
  start?: boolean;
}

export interface WorldMapData {
  start_location: string;
  locations: MapLocation[];
}

// Codex do jogador (GET /game/codex) — Fase 3.2. On-demand, fora do GameResponse.
export interface CodexLocation {
  id: string;
  name: string;
  body: string; // "" se doc hidden/secret ou não achado
}

export interface CodexFaction {
  id: string;
  name: string;
  goal: string; // "" se knows_goal for false (não-onisciência)
  knows_goal: boolean;
  body: string;
}

export interface CodexCharacter {
  name: string;
  role: string;
  location: string;
  body: string;
  // spec npcs-3-camadas (R8): fonte do conhecimento + traits revelados
  knowledge_source?: "met" | "mentioned" | "lore";
  revealed_traits?: Array<{ id: string; name: string; description: string }>;
}

export interface CodexCreature {
  id: string;
  tier: 1 | 2 | 3 | 4;
  tier_name: string; // "Rumores" | "Encontrada" | "Estudada" | "Dominada"
  name: string;
  regions: string[];
  description?: string;
  type?: string;
  max_hp?: number;
  defense?: number;
  attacks?: string[] | Array<{ name: string; type: string; bonus: number; damage: string }>;
  behavior?: Record<string, unknown>;
  loot?: string[];
}

export interface CodexSecret {
  entity_id: string;
  fact: string;
  turn: number;
}

export interface PlayerCodex {
  locations: CodexLocation[];
  factions: CodexFaction[];
  characters: CodexCharacter[];
  creatures: CodexCreature[];
  secrets: CodexSecret[];
}

// Mensagem renderizada no log da história.
export interface LogEntry {
  id: number;
  text: string;
  role: "player" | "narrator";
  type: MessageType;
  streaming?: boolean;  // true enquanto texto está sendo revelado (typewriter)
}
