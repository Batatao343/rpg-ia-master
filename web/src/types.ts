// Espelha os DTOs da API (api.py :: GameResponse / blocos auxiliares).

// Fase 4.1: habilidade conhecida (id canônico + nome exibível)
// spec arvores-habilidade-classes (R10): tipo da habilidade — passiva/utilitária
// não é ação de combate clicável; ganham selo na ficha.
export type AbilityKind = "active" | "passive" | "utility";

export interface PendingChoice {
  id: string;
  level: number;
  kind: "carta" | "virtude" | "subclass" | "virtue_mastery" | "ability" | "attribute";
}

export interface EligibleAbility {
  id: string;
  name: string;
  description: string;
  branch?: string | null;
  branch_name?: string | null;
  subclass?: string;
  tier: number | string;
  tier_label?: string;
  level_req?: number;
  apex?: boolean;
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
  subclasses?: Array<{
    id: string; name: string; identity: string; playstyle: string;
    tradeoff: string; preview_card_ids: string[];
  }>;
  virtue_cards?: Array<{
    card_id: string; virtude: string; mastery: number; effective_stage: number;
  }>;
  unlocked_tier?: number;
  prepared_slots?: number;
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
  /** SPEC-209: aditivos — ausentes em servidor antigo (UI degrada para somente leitura). */
  can_reorganize?: { allowed: boolean; reason: string };
  prepared_slots?: number;
  subclass?: string;
  scars?: ScarView[];
  virtue_cards?: Array<{ card_id: string; name: string; type: string; description: string;
    virtude: string; mastery: number; effective_stage: number }>;
  evolvable_card_ids?: string[];
}

/** Cicatriz permanente (morte rica). O dado não tem turno de origem — nunca exibido. */
export interface ScarView {
  id: string;
  origem: string;
  consequencia_negativa: string;
  habilidade_positiva_relacionada: string;
}

export interface NpcView {
  name: string;
  role: string;
  location: string;
  attitude_label: "hostil" | "desconfiado" | "neutro" | "amistoso" | "leal"; // SPEC-298: só rótulo
  recent_changes?: RecentChange[];
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

// SPEC-296: rumor percebido pelo herói ("Ouvi dizer").
export interface NewsItem {
  day: number;
  period: string;
  location_id: string;
  location_name: string;
  text: string;
  source: string;
  turn: number;
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
  news?: NewsItem[]; // SPEC-296: "Ouvi dizer" (últimas 12, da mais antiga para a mais nova)
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
  base_cost?: number;
  frequency: string;
  spent: boolean;
  ready: boolean;
  has_rupture: boolean;
  rupture_ready: boolean;
  trigger: string;
  evolved: string | null;
  /** SPEC-205: alvos válidos (ids) calculados no servidor; ausente em servidor antigo. */
  valid_targets?: string[];
  invalid_reason?: InvalidReason | null;
}

export type InvalidReason = "not_prepared" | "spent_frequency" | "no_entropy" | "cooldown" |
  "no_valid_target" | "target_dead" | "target_hidden" | "out_of_zone" | "not_your_turn" | "combat_inactive";

export interface BasicActionView {
  kind: "attack" | "maneuver" | "pass" | "flee";
  maneuver?: "engajar" | "desengajar" | "guardar" | "esconder" | "procurar";
  valid_targets: string[];
  invalid_reason: InvalidReason | null;
  cost: number;
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
  basic_actions?: BasicActionView[];
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
  // SPEC-203: state machine e elenco congelado do encontro (somente leitura).
  phase?: EncounterPhase;
  outcome?: EncounterOutcome | null;
  encounter_id?: string | null;
  encounter_view?: EncounterView | Record<string, never>;
}

export type EncounterPhase = "entering" | "active" | "resolving" | "ended";
export type EncounterOutcome =
  "victory" | "fled" | "surrendered_enemy" | "defeat" | "death" | "expired";

export interface EncounterView {
  encounter_id: string;
  origin: string;
  participants: Array<{
    participant_id: string; species_label: string; categoria: string;
    role: "hostile" | "ally" | "neutral" | "hazard";
    presence: "present" | "arrived" | "departed";
    status: "ativo" | "morto" | "fugiu" | "rendido" | "capturado" | "ausente";
  }>;
}

/** SPEC-203 R7: desfecho mecânico; XP vem só de `turn_outcome` (xp_event_ref). */
export interface CombatResultView {
  encounter_id: string;
  outcome: EncounterOutcome;
  participants: Array<{ participant_id: string; species_label: string; final_status: string }>;
  xp_event_ref: string | null;
  loot_ref: string | null;
  ended_round: number;
  result_event_id: string;
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
  will_restore_turn: number | null;
  will_lose_turns: number | null;
  retained: string[];
  reverted: string[];
}

export interface ContinuityView {
  session_action_count: number;
  canonical_turn: number;
  timeline_epoch: number;
  last_checkpoint_turn: number | null;
  death_history: Array<Record<string, unknown>>;
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

export interface RecentChange {
  turn: number;
  text: string;
}

export interface ReputationNotice {
  kind: string;
  subject_id: string;
  text: string;
}

export interface FactionView {
  id: string;
  name: string;
  goal: string; // "" se o jogador ainda não souber o plano
  knows_goal: boolean;
  region: string;
  progress: number | null; // SNAPSHOT visto pelo jogador (null = desconhecido); nunca o ao vivo
  intel_stale: boolean; // true se o snapshot pode estar defasado
  standing_label: "hostil" | "desconfiado" | "neutro" | "amistoso" | "aliado"; // SPEC-298: sem número
  recent_changes: RecentChange[];
  completed: boolean;
  stability_label: "estável" | "instável" | "em colapso"; // Fase 3.4: nunca o número interno
  membership?: FactionMembershipView; // SPEC-301: só se o jogador tem/teve vínculo
}

// SPEC-301 R22: vínculo do jogador com a fação — só rótulos e texto (sem mérito/influência).
export interface FactionMembershipView {
  status: string;
  rank_name: string;
  standing_label: string;
  perks: string[];
  active_mission_id: string;
}

export interface ChronicleEntry {
  entry_id?: string;
  text: string;
  turn: number;
  kind: "milestone" | "prose"; // milestone = determinístico (event_log); prose = menestrel LLM
  event_id?: string; // só milestones — auditoria
}

export interface ChronicleChapter {
  chapter_id?: string;
  title: string;
  started_turn: number;
  location: string;
  entries: ChronicleEntry[];
  digest?: {
    status: string;
    short_title?: string;
    summary: string;
    covered_entry_count: number;
    from_turn?: number;
    to_turn?: number;
  };
}

export interface ChronicleSearchHit {
  chapter_id: string;
  chapter_title: string;
  snippet: string;
  source_kind: "entry" | "digest";
  from_turn: number;
  to_turn: number;
  entry_ids: string[];
  event_ids: string[];
  match_kind: "semantic" | "lexical" | "hybrid";
}

export interface ChronicleSearchResponse {
  mode: "hybrid" | "semantic" | "lexical_fallback";
  index_current: boolean;
  hits: ChronicleSearchHit[];
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
  approval_label?: string; // SPEC-300: rótulo vago (hostil/desconfiado/neutro/amistoso/leal), nunca número
  bond_label?: string; // SPEC-300: "vínculo" | "compromisso" (só a partir do vínculo)
}

export interface TurnOutcome {
  receipt_id: string; turn: number;
  xp_delta: number; level_delta: number; level_after?: number;
  gold_delta: number;
  items_gained: { id: string; name: string; qty: number }[];
  quests_completed: { id: string; title: string }[];
  source: "combat" | "loot" | "story" | "quest" | "exploration" | "mixed" | "none";
}

// SPEC-202: quem respondeu o turno (indicador PASSIVO; não há seletor).
export interface Speaker {
  kind: "narrator" | "npc" | "system";
  id: string;
  name: string;
  reason?: string;
}

export interface GameResponse {
  reputation_notices?: ReputationNotice[]; // SPEC-298 R26: avisos do turno (texto fixo, sem números)
  companion_feedback?: string[]; // SPEC-300 R29: "Brunna não gostou disso." (sem números)
  timeline_epoch?: number;
  art_offers?: { offer_id: string; type: "npc" | "scene" }[];
  art_generations?: { generation_id: string; type: "player" | "npc" | "scene"; subject_id: string }[];
  portrait_generation_id?: string | null;
  game_id: string;
  message: string;
  message_type: MessageType;
  speaker?: Speaker;
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
  continuity?: ContinuityView;
  combat_simulation: CombatSimulationMeta;
  turn_outcome?: Partial<TurnOutcome>;  // {} quando não há ganho
  combat_result?: CombatResultView | Record<string, never>;  // SPEC-203: {} fora do turno de término
  projections?: ProjectionsView | Record<string, never>;  // SPEC-213 R13: só status
  visual: VisualResponse;
}

/** SPEC-213 R13: status das projeções derivadas (resumo/memória/crônica). */
export type ProjectionStatus = "pending" | "completed" | "failed" | "stale";
export interface ProjectionsView {
  canonical_version: number;
  summary: { status: ProjectionStatus; projected_version: number };
  memory: { status: ProjectionStatus; projected_version: number };
  chronicle: { status: ProjectionStatus; projected_version: number };
}

export interface VisualVariant {
  url: string;
  width: number;
  height: number;
  bytes: number;
  sha256: string;
}

export interface VisualAsset {
  asset_id: string;
  subject_type: "race" | "class" | "location" | "npc";
  subject_id: string;
  title: string;
  alt: string;
  placeholder_color: string;
  variants: { thumbnail: VisualVariant; display: VisualVariant };
}

export interface SceneVisual {
  location_id: string;
  location_name: string;
  scope: "exact" | "regional" | "placeholder";
  asset: VisualAsset | null;
}

export interface VisualCue {
  kind: "npc_first_appearance";
  subject_id: string;
  subject_name: string;
  caption: string;
  asset: VisualAsset | null;
  fallback: boolean;
}

export interface VisualResponse {
  scene: SceneVisual;
  cue: VisualCue | null;
}

export interface CreateOptions {
  races: string[];
  classes: string[];
  regions: string[];
  // Fase 2.5b: raças completas (desc + traits) p/ os cards do wizard
  races_full?: RaceFull[];
  visuals?: {
    races: Record<string, VisualAsset | null>;
    classes: Record<string, VisualAsset | null>;
  };
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
  appearance?: string;
  visual_exclusions?: string;
  generate_portrait?: boolean;
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
// SPEC-206: vocabulário compartilhado de conhecimento (ids em inglês; rótulo pt-BR em `label`).
export type KnowledgeKind = "fact" | "report" | "rumor" | "suspicion" | "perception";
export type KnowledgeCertainty = "confirmed" | "reported" | "speculative";

export interface KnowledgeStamp {
  knowledge_kind: KnowledgeKind;
  certainty: KnowledgeCertainty;
  source_kind: string;
  source_ref: string;
  label: string;
  first_seen_turn: number | null;
  last_updated_turn: number | null;
  stale: boolean;
}

export interface KnowledgeNote extends KnowledgeStamp {
  memory_id: string;
  text: string;
}

// Campos aditivos da SPEC-206 — opcionais p/ compatibilidade com API antiga.
export interface CodexKnowledgeFields {
  knowledge?: KnowledgeStamp;
  notes?: KnowledgeNote[];
}

export interface CodexLocation extends CodexKnowledgeFields {
  id: string;
  name: string;
  body: string; // "" se doc hidden/secret ou não achado
}

export interface CodexFaction extends CodexKnowledgeFields {
  id: string;
  name: string;
  goal: string; // "" se knows_goal for false (não-onisciência)
  knows_goal: boolean;
  body: string;
}

export interface CodexCharacter extends CodexKnowledgeFields {
  name: string;
  role: string;
  location: string;
  body: string;
  // spec npcs-3-camadas (R8): fonte do conhecimento + traits revelados
  knowledge_source?: "met" | "mentioned" | "lore";
  revealed_traits?: Array<{ id: string; name: string; description: string }>;
}

export interface CodexCreature extends CodexKnowledgeFields {
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

export interface CodexSecret extends CodexKnowledgeFields {
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
  meta?: {
    taxonomy_version: number;
    counts: Partial<Record<"locations" | "factions" | "characters" | "creatures" | "secrets", number>>;
    redactions: number;
  };
}

// Mensagem renderizada no log da história.
export interface LogEntry {
  id: number;
  historyId?: string;
  costMilli?: string | null;
  technicalCostUsd?: string | null;
  technicalCostExact?: boolean;
  text: string;
  role: "player" | "narrator";
  type: MessageType;
  speaker?: Speaker | null;  // SPEC-202: quem respondeu (rótulo passivo)
  streaming?: boolean;  // true enquanto texto está sendo revelado (typewriter)
  visual?: VisualCue | null;
  onTypewriterDone?: () => void;  // fim real da animação (SPEC-235 R7)
}

// --- SPEC-211: dossiês vivos (GET /game/codex/dossiers) ---
export interface DossierArt {
  asset_id: string;
  alt: string;
  placeholder_color?: string | null;
  variants?: VisualAsset["variants"] | null;
}

export interface DossierClaim {
  text: string;
  knowledge: KnowledgeStamp;
}

export interface DossierEncounter {
  turn: number;
  location_id: string;
  outcome: string;
  encounter_id?: string | null;
}

export interface DossierBase {
  id: string;
  kind: "npc" | "location" | "faction" | "secret" | "creature";
  title: string;
  last_updated_turn: number;
  version: number;
  art: DossierArt | null;
  knowledge: KnowledgeStamp;
  notes: KnowledgeNote[];
}

export interface NpcDossier extends DossierBase {
  kind: "npc";
  role: string;
  location: string;
  status: string;
  attitude_label: string;
  recent_changes?: RecentChange[];
  knowledge_source: string;
  revealed_traits: Array<{ id: string; name: string; description?: string }>;
  claims: DossierClaim[];
  appears_to_know: DossierClaim[];
  encounters: DossierEncounter[];
  last_seen_turn: number | null;
  body: string;
}

export interface LocationDossier extends DossierBase {
  kind: "location";
  body: string;
  region: string;
  npcs: string[];
  creatures: string[];
  events: DossierEncounter[];
}

export interface FactionDossier extends DossierBase {
  kind: "faction";
  body: string;
  goal: string;
  knows_goal: boolean;
  region: string;
  standing_label: string;
  recent_changes?: RecentChange[];
  progress: number | null;
  intel_stale: boolean;
  stale_label: string;
}

export interface SecretDossier extends DossierBase {
  kind: "secret";
  fact: string;
  entity_id: string;
  turn: number;
}

export interface CreatureDossier extends DossierBase {
  kind: "creature";
  tier: number;
  tier_name: string;
  regions: string[];
  rarity_note?: string | null;
  first_seen_turn: number | null;
  // Ausentes do JSON quando acima do tier (R6): sempre opcionais.
  description?: string;
  type?: string;
  max_hp?: number | null;
  defense?: number | null;
  attacks?: Array<string | { name: string }>;
  behavior?: Record<string, unknown>;
  loot?: string[];
  revealed_cards?: Array<{ id: string; name: string }>;
  revealed_resistances?: string[];
}

export interface ChronicleIndexEntry {
  chapter_id: string;
  arc_title: string;
  started_turn: number;
  location: string;
  entry_count: number;
  entity_ids: string[];
}

export interface DossiersPayload {
  version: number;
  generated_at_turn: number;
  sections: {
    npcs: NpcDossier[];
    locations: LocationDossier[];
    factions: FactionDossier[];
    secrets: SecretDossier[];
    chronicle_index: ChronicleIndexEntry[];
  };
  bestiary: CreatureDossier[];
}

// SPEC-210: mapa do jogo com fog server-side (GET /game/map?game_id=).
export type MapNodeState = "atual" | "visitado" | "adjacente" | "bloqueado";

export interface MapNodeView {
  id: string;
  state: MapNodeState;
  name: string;
  coords: { x: number; y: number };
  reachable?: boolean;
  reason?: string;
  // Só em locais visitados (adjacentes chegam apenas com id/coords/name):
  region_id?: string;
  danger?: number;
  lore_seed?: string;
  art?: { location_id: string; scope: "exact" | "regional" | "placeholder"; asset: VisualAsset | null };
  ruler?: string;
  quest_target?: boolean;
  threatened?: boolean;
  threat_hint?: string;
  contested?: boolean;
}

export interface MapTravelOption {
  location_id: string;
  name: string;
  periods: number;
  reachable: boolean;
  blocked: boolean;
  reason: string;
}

export interface MapView {
  game_id: string;
  turn_count: number;
  map_version: string;
  current_id: string;
  anchor_id: string;
  nodes: MapNodeView[];
  edges: Array<{ a: string; b: string; blocked: boolean }>;
  interiors: { here: Array<{ id: string; name: string; danger: number; tags: string[] }>; exit_to: { id: string; name: string } | null };
  travel_options: MapTravelOption[];
  travel_gate: { blocked: boolean; reason: string };
  looming_threat: string;
}
