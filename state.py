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


class PlayerStats(TypedDict):
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
    inventory: List[str]
    known_abilities: List[str]
    defense: int
    attack_bonus: int
    active_conditions: List[str]


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
    status: str  # "ativo", "morto"
    active_conditions: List[str]
    attacks: Optional[List[Dict]]


class CompanionState(TypedDict):
    name: str
    hp: int
    max_hp: int
    active: bool
    stats: Dict


class WorldState(TypedDict):
    current_location: str
    time_of_day: str
    turn_count: int
    weather: str
    quest_plan: List[str]
    quest_plan_origin: Optional[str]
    danger_level: int


class CampaignBeat(TypedDict):
    description: str
    status: Literal["pending", "done"]


class CampaignPlan(TypedDict, total=False):
    location: str
    beats: List[CampaignBeat]
    climax: str
    current_step: int
    last_planned_turn: int


class GameState(TypedDict):
    # --- Identificação e Memória (NOVO) ---
    game_id: str  # ID único da sessão para isolar o RAG
    narrative_summary: str # Resumo de curto prazo (contexto comprimido)
    archivist_last_run: int # Controle de frequência do arquivista

    messages: Annotated[List[BaseMessage], operator.add]
    next: Optional[str]
    player: PlayerStats
    world: WorldState
    campaign_plan: Optional[CampaignPlan]
    needs_replan: bool
    enemies: List[EnemyStats]
    party: List[CompanionState]
    npcs: Dict[str, Dict]
    active_npc_name: Optional[str]
    active_plan_step: Optional[str]
    router_confidence: Optional[float]
    last_routed_intent: Optional[str]
    
    # --- Campos de Transição ---
    combat_target: Optional[str]
    loot_source: Optional[str]