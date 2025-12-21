import operator
from typing import Annotated, List, TypedDict, Optional, Dict, Any
from langchain_core.messages import BaseMessage

class Attributes(TypedDict):
    strength: int; dexterity: int; constitution: int
    intelligence: int; wisdom: int; charisma: int

class PlayerStats(TypedDict):
    name: str; class_name: str
    hp: int; max_hp: int
    mana: int; max_mana: int
    stamina: int; max_stamina: int
    gold: int; level: int; xp: int; alignment: str
    attributes: Attributes
    inventory: List[str]; known_abilities: List[str]
    defense: int; attack_bonus: int
    active_conditions: List[str] 

class EnemyStats(TypedDict):
    id: str; name: str
    hp: int; max_hp: int
    stamina: int; mana: int
    defense: int; attack_mod: int
    attributes: Attributes; abilities: List[str]
    status: str # "ativo", "morto"
    active_conditions: List[str]

class CompanionState(TypedDict):
    name: str; hp: int; max_hp: int; active: bool; stats: Dict

class WorldState(TypedDict):
    current_location: str; time_of_day: str; turn_count: int; weather: str
    quest_plan: List[str]; quest_plan_origin: Optional[str]

class GameState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next: Optional[str]
    player: PlayerStats
    world: WorldState
    enemies: List[EnemyStats] 
    party: List[CompanionState]
    npcs: Dict[str, Dict]
    active_npc_name: Optional[str]