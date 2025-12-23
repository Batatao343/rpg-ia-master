from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from llm_setup import get_llm, ModelTier
from rag import query_rag


class ProloguePlan(BaseModel):
    """Schema structured for generating consistent prologue details."""

    starting_location: str
    intro_narrative: str
    quest_plan: list[str] = Field(min_length=3, max_length=3)


def generate_prologue(player_data: Dict) -> Dict:
    """Gera um local inicial, narrativa e plano de quest baseados no personagem."""

    player_class = player_data.get("class_name", "Adventurer")
    player_race = player_data.get("race", "Human")

    try:
        lore = query_rag(f"{player_class} {player_race}", index_name="lore")
    except Exception as exc:  # noqa: BLE001
        print(f"[PROLOGUE] Falha RAG: {exc}")
        lore = ""

    system_msg = SystemMessage(
        content=(
            "You are the campaign prologue generator."
            " Use retrieved lore to craft a specific starting location,"
            " an evocative intro paragraph, and a 3-step objective list."
        )
    )
    human_msg = HumanMessage(
        content=(
            f"Class: {player_class}\nRace: {player_race}\n"
            f"Name: {player_data.get('name', 'Hero')}"
        )
    )

    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)
    try:
        planner = llm.with_structured_output(ProloguePlan)
        result = planner.invoke(
            [system_msg, human_msg, HumanMessage(content=f"Lore Context:\n{lore}")]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[PROLOGUE] Falha ao gerar prólogo: {exc}")
        result_data = {
            "starting_location": "Estrada de Caravanas Sombria",
            "intro_narrative": (
                "Você desperta em uma carroça de mercadores abandonada, com chuva fina"
                " caindo e marcas de batalha recentes ao redor."
            ),
            "quest_plan": [
                "Avalie seus pertences e ferimentos.",
                "Encontre abrigo seguro na noite chuvosa.",
                "Investigue quem atacou a caravana.",
            ],
        }
    else:
        result_data = (
            result.model_dump() if hasattr(result, "model_dump") else dict(result)
        )

    quest_plan = result_data.get("quest_plan", [])
    # Fallback garantido para campos obrigatórios
    starting_location = result_data.get("starting_location") or result_data.get("current_location") or "Local Desconhecido"
    intro = result_data.get("intro_narrative") or "A jornada começa..."
    if not quest_plan:
        quest_plan = [
            "Avalie seus pertences e ferimentos.",
            "Encontre abrigo seguro na noite chuvosa.",
            "Investigue quem atacou a caravana.",
        ]
    return {
        "current_location": starting_location,
        "starting_location": starting_location,
        "intro_narrative": intro,
        "quest_plan": quest_plan,
        "quest_plan_origin": starting_location,
    }
