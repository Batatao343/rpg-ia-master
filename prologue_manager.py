from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from llm_setup import get_llm, ModelTier
from rag import query_rag


class ProloguePlan(BaseModel):
    """Schema structured for generating consistent prologue details."""
    starting_location: str = Field(description="Name of the location from Lore or invented fitting the theme.")
    intro_narrative: str = Field(description="3 paragraphs setting a dark, mysterious scene.")
    quest_plan: List[str] = Field(min_length=3, max_length=3, description="3 short, actionable objectives.")


def generate_prologue(player_data: Dict) -> Dict:
    """
    Gera um local inicial, narrativa e plano de quest baseados no personagem.
    Retorna um dicionário pronto para dar .update() na chave 'world' do GameState.
    """

    player_name = player_data.get("name", "Viajante")
    player_class = player_data.get("class_name", "Aventureiro")
    player_race = player_data.get("race", "Humano")

    # 1. MELHORIA NO RAG: Busca focada em LOCAIS e ORIGENS, não apenas na classe
    search_query = f"Starting locations for {player_race} {player_class} in dark fantasy world. Dangerous regions, crypts, slums."
    
    try:
        lore = query_rag(search_query, index_name="lore")
    except Exception as exc:  # noqa: BLE001
        print(f"[PROLOGUE] Falha RAG: {exc}")
        lore = "O mundo é sombrio, cheio de névoa e perigos antigos."

    # 2. MELHORIA NO PROMPT: Injeção de Tom (Dark Fantasy) e Instruções Claras
    system_msg = SystemMessage(
        content=(
            "You are the Dungeon Master for a Grim Dark Fantasy RPG. "
            "Your goal is to create an immersive, atmospheric prologue for a new character.\n\n"
            "GUIDELINES:\n"
            "- Tone: Dark, mysterious, dangerous. Avoid 'happy tavern' starts.\n"
            "- Location: Use the provided LORE to pick a specific location fitting the race/class.\n"
            "- Narrative: Focus on sensory details (smell of decay, cold fog, shadows).\n"
            "- Quest Plan: Create 3 immediate steps: 1) Immediate Survival/Awareness, 2) Exploration, 3) A Plot Hook."
        )
    )
    
    human_msg = HumanMessage(
        content=(
            f"Character: {player_name}, a {player_race} {player_class}.\n"
            f"LORE CONTEXT:\n{lore}"
        )
    )

    llm = get_llm(temperature=0.7, tier=ModelTier.SMART) # Temp um pouco maior para criatividade
    
    try:
        planner = llm.with_structured_output(ProloguePlan)
        result = planner.invoke([system_msg, human_msg])
        
        # Converte para dict seguro
        data = result.model_dump() if hasattr(result, "model_dump") else dict(result)

    except Exception as exc:  # noqa: BLE001
        print(f"[PROLOGUE] Falha ao gerar prólogo via LLM: {exc}")
        # Fallback Robusto
        data = {
            "starting_location": "Estrada de Caravanas Sombria",
            "intro_narrative": (
                f"{player_name} desperta com o gosto de sangue na boca. A chuva fria cai sobre os destroços "
                "de uma caravana. Não há sobreviventes à vista, apenas o silêncio da morte e pegadas "
                "que somem na lama."
            ),
            "quest_plan": [
                "Verificar se há itens úteis nos destroços.",
                "Encontrar abrigo da chuva e do frio.",
                "Seguir as pegadas para descobrir quem atacou.",
            ],
        }

    # 3. PADRONIZAÇÃO DE RETORNO (Para o GameState)
    # Garante que temos 'current_location' (usado pelo engine) igual a 'starting_location'
    starting_loc = data.get("starting_location", "Ermos Desconhecidos")
    
    return {
        "current_location": starting_loc,
        "starting_location": starting_loc, # Mantém histórico
        "intro_narrative": data.get("intro_narrative"),
        "quest_plan": data.get("quest_plan", []),
        "quest_plan_origin": starting_loc, # Para saber onde essa quest foi gerada
        "turn_count": 0, # Reseta o relógio do mundo
        "time_of_day": "Noite", # Começar à noite é sempre mais tenso
        "weather": "Névoa Fria" # Clima padrão
    }