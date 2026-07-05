// Espelha os DTOs da API (api.py :: GameResponse / blocos auxiliares).

// Fase 4.1: habilidade conhecida (id canônico + nome exibível)
export interface AbilityRef {
  id: string;
  name: string;
  branch: string | null;
}

export interface PendingChoice {
  id: string;
  level: number;
  kind: "ability" | "attribute";
}

export interface EligibleAbility {
  id: string;
  name: string;
  description: string;
  branch: string | null;
  branch_name: string | null;
  tier: number;
  cost: number;
  resource_type: string;
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
  current_branch?: string | null;
  branches?: Record<string, BranchInfo>;
}

export interface PlayerStats {
  name: string;
  class_name: string;
  race: string;
  hp: number;
  max_hp: number;
  mana: number;
  max_mana: number;
  stamina: number;
  max_stamina: number;
  defense: number;
  gold: number;
  level: number;
  xp: number;
  abilities: AbilityRef[];
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

export interface WorldBlock {
  location: string;
  location_id: string;
  day: number;
  period: string;
  visited: string[];
  danger: number;
  controlled: Record<string, string>; // Fase 3.4: location_id -> NOME de quem domina (era faction_id)
  danger_overrides: Record<string, number>; // location_id -> perigo elevado (ascensão)
  turn_count: number; // Fase 3.2: dispara refetch do Codex quando o turno muda
  map_overlays: MapOverlays; // Fase 3.4
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
  name: string;
  hp: number;
  max_hp: number;
  defense: number;
  conditions: Condition[];
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
  player_conditions: Condition[];
  cooldowns: Record<string, number>;
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
}

// Fase 4.5: companheiro da party (HP bar no HUD)
export interface PartyMember {
  name: string;
  hp: number;
  max_hp: number;
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
}

export interface CreateOptions {
  races: string[];
  classes: string[];
  regions: string[];
}

export interface CreatePayload {
  name: string;
  race: string;
  class_name: string;
  region: string;
  level: number;
  backstory: string;
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
