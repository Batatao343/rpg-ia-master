"""
game_engine.py
Fachada principal. Conecta UI -> Lógica.
"""
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage

from character_creator import create_player_character
from prologue_manager import generate_prologue
from main import app as dm_graph
from test_runner import create_base_state
from memory_utils import sanitize_history
from persistence import load_game, save_game, list_saves

def create_new_game(name: str, class_name: str, race: str, backstory: str = "", level: int = 1) -> Dict[str, Any]:
    """Cria o estado inicial do jogo."""
    
    # 1. Cria Ficha (IA processa backstory e nível)
    player_data = create_player_character({
        "name": name, 
        "class_name": class_name, 
        "race": race,
        "backstory": backstory,
        "level": level
    })
    
    # 2. Gera Prólogo
    prologue = generate_prologue(player_data)
    
    # 3. Monta Estado
    state = create_base_state()
    state["player"] = player_data
    state["world"].update({
        "current_location": prologue.get("current_location", "Desconhecido"),
        "quest_plan": prologue.get("quest_plan", []),
        "quest_plan_origin": prologue.get("quest_plan_origin"),
        "time_of_day": prologue.get("time_of_day", "Noite"),
        "weather": prologue.get("weather", "Nebuloso")
    })
    
    state["messages"] = [AIMessage(content=prologue.get("intro_narrative", "Início..."))]
    return state

def process_turn(state: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Processa um turno."""
    state["messages"].append(HumanMessage(content=user_input))
    new_state = dm_graph.invoke(state)
    new_state["messages"] = sanitize_history(new_state.get("messages", []))
    return new_state

def get_last_ai_message(state: Dict[str, Any]) -> str:
    msgs = state.get("messages", [])
    if msgs and isinstance(msgs[-1], AIMessage):
        return msgs[-1].content
    return "..."

# Exports
save_game_state = save_game
load_game_state = load_game
list_saved_games = list_saves