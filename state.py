"""Typed structures describing the shared game state for the LangGraph workflow."""

import operator
from typing import Annotated, Dict, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage


class Attributes(TypedDict):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


class Condition(TypedDict, total=False):
    name: str
    dot: int        # dano por turno (0 = buff/debuff sem dano direto)
    duration: int   # turnos restantes
    source: str     # quem/que habilidade aplicou
    # --- Fase 4.2: modificadores tipados (lidos por combat_mechanics.condition_modifiers)
    stat: Optional[str]     # "damage" | "ac" | "attack" | "save"
    delta: int              # soma no stat enquanto durar
    control: Optional[str]  # "stun" (perde turno) | "root" (não foge) | "fear" (-2 acerto)


class PlayerStats(TypedDict, total=False):
    name: str
    class_name: str
    race: str
    hp: int
    max_hp: int
    mana: int
    max_mana: int
    stamina: int
    max_stamina: int
    gold: int
    level: int
    xp: int
    alignment: str
    attributes: Attributes
    # Fase 4.3: inventário estruturado — {"id": str, "qty": int, "display_name"?: str}
    # (id resolve no ARTIFACTS_DB; item_desconhecido preserva nome de save antigo)
    inventory: List[Dict]
    # Fase 4.3: slots de equipamento — {"weapon"|"armor"|"accessory": item_id|None}
    # combate lê SÓ os slots (inventory.equip/unequip; backfill auto-equipa 1x)
    equipment: Dict[str, Optional[str]]
    known_abilities: List[str]  # Fase 4.1: ids canônicos de player_abilities.json
    # Fase 4.1: escolhas de level up pendentes — {"id", "level", "kind": ability|attribute}
    pending_choices: List[Dict]
    defense: int
    attack_bonus: int
    active_conditions: List[Condition]
    ability_cooldowns: Dict[str, int]  # ability_id -> turnos restantes
    # --- Fase 2.5b: traits raciais (aplicados na criação; ver data/origins.json) ---
    racial_traits: List[str]           # nomes dos traits (narração/HUD)
    condition_resists: List[str]       # substrings de condições que a raça ignora
    racial_save_bonus: Dict[str, int]  # attr curto -> bônus em saving throws


class EnemyStats(TypedDict):
    id: str
    name: str
    hp: int
    max_hp: int
    stamina: int
    mana: int
    defense: int
    attack_mod: int
    attributes: Attributes
    abilities: List[str]
    status: str  # "ativo", "morto", "fugiu"
    active_conditions: List["Condition"]
    attacks: Optional[List[Dict]]
    # --- Fase 2.5b: comportamento de combate (ver data/bestiary.json) ---
    # {"profile": "tatico"|"feroz"|"covarde"|"implacavel", "flee_below": float, "pack_morale": bool}
    behavior: Optional[Dict]


class CompanionState(TypedDict):
    name: str
    hp: int
    max_hp: int
    active: bool
    stats: Dict


class WorldClock(TypedDict):
    day: int
    period: str  # "Amanhecer" | "Manhã" | "Tarde" | "Anoitecer" | "Noite"


class WorldState(TypedDict, total=False):
    current_location: str
    current_location_id: str        # id no grafo data/world_map.json
    visited: List[str]              # ids de locais já revelados (fog of war)
    world_clock: WorldClock         # dia + período (relógio do mundo)
    time_of_day: str
    turn_count: int
    weather: str
    quest_plan: List[str]
    quest_plan_origin: Optional[str]
    danger_level: int
    # --- Fase 4.4: economia — estoque persistente por mercador + último restock ---
    merchant_stocks: Dict[str, Dict[str, int]]   # merchant_id -> {item_id: qty}
    merchant_restock_day: Dict[str, int]         # merchant_id -> dia do último restock
    # --- Fase 2 / Etapa B: mundo que evolui (escrito por resolve_faction_completions) ---
    controlled: Dict[str, str]       # location_id -> faction_id (local dominado por fação)
    danger_overrides: Dict[str, int] # location_id -> perigo elevado por ascensão (teto 4)
    looming_threat: str              # ameaça invocada (entidade) pairando sobre o mundo
    last_encounter_turn: int         # turno do último encontro automático (cooldown)
    threat_alerts: List[Dict]        # Fase 2.5b: fugas viram alerta regional (ver world_utils.register_flee_alert)


class Faction(TypedDict, total=False):
    id: str
    name: str
    goal: str                 # objetivo de longo prazo da facção
    region: str               # região-base no grafo do mundo
    progress: int             # 0-100 rumo ao objetivo (avança em ticks de descanso/viagem)
    pace: int                 # quanto progride por período de tempo (determinístico)
    disposition: str          # "hostil" | "neutro" | "aliado" — postura geral no mundo
    reputation: int           # reputação do jogador com a facção (-100..100)
    completed: bool           # objetivo concluído (dispara evento de mundo)
    defeated: bool            # eliminada por outra facção (Fase 2 — sai de jogo)


class FactionIntel(TypedDict, total=False):
    """O que o JOGADOR sabe sobre uma facção (não-onisciência). Chave = faction_id."""
    known: bool               # existência revelada (só por NPC que sabe)
    knows_goal: bool          # objetivo/plano revelado
    progress_seen: int        # SNAPSHOT do progresso no momento em que soube (fica defasado)
    intel_turn: int           # turno em que o snapshot foi obtido (p/ marcar defasagem)


class BestiaryKnowledge(TypedDict, total=False):
    """O que o JOGADOR sabe sobre uma criatura do bestiário. Chave = id de data/bestiary.json."""
    seen: int               # avistada/citada em alerta ou hint de encontro (rumor)
    fought: int              # combates iniciados contra ela
    defeated: int             # instâncias mortas pelo player
    first_seen_turn: int
    last_update_turn: int


class CampaignBeat(TypedDict):
    description: str
    status: Literal["pending", "done"]


class CampaignPlan(TypedDict, total=False):
    location: str
    beats: List[CampaignBeat]
    climax: str
    current_step: int
    last_planned_turn: int
    arc_title: str         # Fase 3.1: título do arco atual — muda → capítulo novo na crônica


# --- Fase 3.3: quest log — side quests persistentes (main quest = view do CampaignPlan) ---

class Quest(TypedDict, total=False):
    id: str                  # uuid4 hex
    title: str
    description: str
    status: str              # "active" | "completed" | "failed"
    origin_name: str         # quem/o que originou (nome exibível)
    origin_entity_id: str    # id canônico se houver (habilita falha sistêmica); "" senão
    location_id: str         # alvo no mapa ("" se não aplicável)
    created_turn: int
    resolved_turn: int
    reward_hint: str         # texto livre ("o ferreiro prometeu 50 moedas")


# --- Fase 3.1: crônica por capítulos (milestones determinísticos + prosa) ---

class ChronicleEntry(TypedDict, total=False):
    text: str
    turn: int
    kind: str        # "milestone" (determinístico, do event_log) | "prose" (menestrel LLM)
    event_id: str    # só milestones — auditoria (aponta para GameEvent.event_id)


class ChronicleChapter(TypedDict, total=False):
    title: str
    started_turn: int
    location: str            # current_location no momento da abertura
    entries: List[ChronicleEntry]


# --- Fase 2.5: eventos estruturados + estado projetado do mundo ---
# Lore base (Codex/data/graph) é imutável; o que MUDA no mundo vive aqui.

class GameEvent(TypedDict, total=False):
    event_id: str      # uuid4 hex
    turn: int          # world.turn_count no momento do evento
    type: str          # "npc_killed" | "secret_revealed" | "location_control_changed" | ...
    actor_id: str      # quem causou ("player", npc id, faction id, "system")
    target_id: str     # entidade afetada (id canônico de data/graph/entities.json)
    payload: Dict      # dados específicos do tipo
    source: str        # "combat" | "storyteller" | "rule_engine" | "system" | "test"


class EntityState(TypedDict, total=False):
    alive: bool
    location_id: str
    stability: int         # fações: -100..100
    extra: Dict            # estado adicional por componente


class DynamicEdge(TypedDict, total=False):
    id: str
    source: str
    type: str
    target: str
    created_by_event: str  # event_id de origem (auditoria)


class DisabledEdge(TypedDict, total=False):
    edge_id: str           # id da edge base desativada
    disabled_by_event: str


class RevealedFact(TypedDict, total=False):
    entity_id: str
    fact: str
    revealed_at_turn: int
    revealed_by_event: str


class WorldProjection(TypedDict, total=False):
    entities: Dict[str, EntityState]
    dynamic_edges: List[DynamicEdge]
    disabled_edges: List[DisabledEdge]
    revealed_facts: Dict[str, RevealedFact]     # chave = event_id revelador
    location_summaries: Dict[str, str]          # loc_id -> resumo dinâmico curto


class GameState(TypedDict):
    # --- Identificação e Memória (NOVO) ---
    game_id: str  # ID único da sessão para isolar o RAG
    narrative_summary: str # Resumo de curto prazo (contexto comprimido)
    archivist_last_run: int # Controle de frequência do arquivista
    archive_due: bool       # flag transitória: evento relevante pede arquivamento (cadência)
    game_over: bool         # Fase 4.6: player morreu — save vira memorial (sem chave no
                            # GameState o LangGraph DESCARTA o update; achado do smoke real)
    chronicle: List[ChronicleChapter]  # Crônica por capítulos: milestones (event_log) + prosa de menestrel

    messages: Annotated[List[BaseMessage], operator.add]
    next: Optional[str]
    player: PlayerStats
    world: WorldState
    campaign_plan: Optional[CampaignPlan]
    needs_replan: bool
    enemies: List[EnemyStats]
    party: List[CompanionState]
    factions: List[Faction]  # Fase 2: fações com objetivos próprios (mundo vivo)
    faction_intel: Dict[str, Dict]  # Fase 2: o que o jogador SABE de cada facção (não-onisciência)
    bestiary_knowledge: Dict[str, BestiaryKnowledge]  # Fase 3.2: contadores por criatura (chave = id do bestiário)
    quests: List[Quest]  # Fase 3.3: side quests persistentes (main quest deriva de campaign_plan)
    npcs: Dict[str, Dict]
    active_npc_name: Optional[str]
    active_plan_step: Optional[str]
    router_confidence: Optional[float]
    last_routed_intent: Optional[str]
    
    # --- Campos de Transição ---
    combat_target: Optional[str]
    loot_source: Optional[str]

    # --- Combate determinístico ---
    # {"round": int, "active": bool, "order": [{"id","name","side","init"}]}
    combat: Optional[Dict]

    # --- Fase 2.5: mundo estruturado (LLM propõe, motor aplica) ---
    event_log: List[GameEvent]            # append-only; auditoria do que mudou
    world_projection: WorldProjection     # estado calculado a partir do event_log
    pending_world_events: List[Dict]      # propostas ainda não validadas (Fase 2.6)