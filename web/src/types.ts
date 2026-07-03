// Espelha os DTOs da API (api.py :: GameResponse / blocos auxiliares).

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
  abilities: string[];
}

export interface NpcView {
  name: string;
  role: string;
  location: string;
  relationship: number; // 0..10
  last_memory: string;
}


export interface WorldBlock {
  location: string;
  location_id: string;
  day: number;
  period: string;
  visited: string[];
  danger: number;
  controlled: Record<string, string>; // location_id -> faction_id (dominado)
  danger_overrides: Record<string, number>; // location_id -> perigo elevado (ascensão)
}

export interface Beat {
  description: string;
  status: "pending" | "done";
}

export interface QuestBlock {
  objective: string;
  climax: string;
  current_step: number;
  total: number;
  beats: Beat[];
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

export interface GameResponse {
  game_id: string;
  message: string;
  message_type: MessageType;
  player_stats: PlayerStats;
  inventory: string[];
  current_location: string;
  narrative_summary: string;
  simulated: boolean;
  world: WorldBlock;
  quest: QuestBlock;
  combat: CombatBlock;
  npcs: NpcView[];
  chronicle: ChronicleChapter[];
  factions: FactionView[];
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

// Mensagem renderizada no log da história.
export interface LogEntry {
  id: number;
  text: string;
  role: "player" | "narrator";
  type: MessageType;
  streaming?: boolean;  // true enquanto texto está sendo revelado (typewriter)
}
