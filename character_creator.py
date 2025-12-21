from typing import Dict, List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from llm_setup import get_llm, ModelTier
from state import Attributes


class PlayerStatsSchema(BaseModel):
    name: str
    class_name: str
    race: str
    hp: int = Field(ge=10, le=60)
    max_hp: int = Field(ge=10, le=60)
    mana: int = Field(ge=0, le=40)
    max_mana: int = Field(ge=0, le=40)
    stamina: int = Field(ge=5, le=40)
    max_stamina: int = Field(ge=5, le=40)
    gold: int = Field(ge=0, le=500)
    level: int = Field(ge=1, le=5)
    xp: int = Field(ge=0, le=500)
    alignment: str
    attributes: Attributes
    inventory: List[str] = Field(default_factory=list)
    known_abilities: List[str] = Field(default_factory=list)
    defense: int = Field(ge=8, le=20)
    attack_bonus: int = Field(ge=-2, le=8)
    active_conditions: List[str] = Field(default_factory=list)


def create_player_character(manual_args: Dict | None = None) -> Dict:
    """Solicita detalhes básicos e gera um personagem equilibrado via LLM.

    ``manual_args`` permite testes automatizados sem depender de ``input()``.
    """

    manual_args = manual_args or {}
    print("🧙 Criação de Personagem")
    if manual_args:
        name = manual_args.get("name", "Herói Sem Nome")
        class_name = manual_args.get("class_name", "Aventureiro")
        race = manual_args.get("race", "Humano")
    else:
        name = input("Nome do Herói: ").strip() or "Herói Sem Nome"
        class_name = input("Classe (ex: Necromancer): ").strip() or "Aventureiro"
        race = input("Raça (ex: Undead): ").strip() or "Humano"

    system_msg = SystemMessage(
        content=(
            "You are a character builder for a dark fantasy RPG. "
            "Generate balanced, level-1 stats with modest gear."
        )
    )

    human_msg = HumanMessage(
        content=(
            f"Name: {name}\nClass: {class_name}\nRace: {race}. "
            "Return concise JSON stats for this hero."
        )
    )

    llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
    try:
        builder = llm.with_structured_output(PlayerStatsSchema)
        stats = builder.invoke([system_msg, human_msg])
    except Exception as exc:  # noqa: BLE001
        print(f"[CHARACTER CREATOR] Falha ao gerar stats: {exc}")
        stats = PlayerStatsSchema(
            name=name,
            class_name=class_name,
            race=race,
            hp=30,
            max_hp=30,
            mana=10,
            max_mana=10,
            stamina=20,
            max_stamina=20,
            gold=25,
            level=1,
            xp=0,
            alignment="Neutral",
            attributes={
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            inventory=["Rusty Sword", "Traveler's Cloak"],
            known_abilities=[],
            defense=12,
            attack_bonus=1,
            active_conditions=[],
        )

    return {
        "name": stats.name,
        "class_name": stats.class_name,
        "race": stats.race,
        "hp": stats.hp,
        "max_hp": stats.max_hp,
        "mana": stats.mana,
        "max_mana": stats.max_mana,
        "stamina": stats.stamina,
        "max_stamina": stats.max_stamina,
        "gold": stats.gold,
        "xp": stats.xp,
        "level": stats.level,
        "alignment": stats.alignment,
        "attributes": stats.attributes,
        "inventory": stats.inventory,
        "known_abilities": stats.known_abilities,
        "defense": stats.defense,
        "attack_bonus": stats.attack_bonus,
        "active_conditions": stats.active_conditions,
    }
