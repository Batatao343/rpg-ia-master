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

    lore = query_rag(f"{player_class} {player_race}", index_name="lore")

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
        result_data = (
            result.model_dump() if hasattr(result, "model_dump") else dict(result)
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

    quest_plan = result_data.get("quest_plan", [])
    return {
        "current_location": result_data.get("starting_location", "Local Desconhecido"),
        "intro_narrative": result_data.get("intro_narrative", "A jornada começa..."),
        "quest_plan": quest_plan,
        "quest_plan_origin": result_data.get("starting_location", ""),
    }
