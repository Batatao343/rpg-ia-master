import json
import os
from typing import List
from langchain_core.messages import messages_to_dict, messages_from_dict
from state import GameState

SAVE_DIR = "saves"

def ensure_save_dir():
    """Garante que a pasta de saves existe."""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

def save_game(state: GameState, filename: str = "quicksave"):
    """
    Salva o estado atual em um arquivo JSON.
    Inclui Player, Mundo, Inimigos, Party, NPCs e Histórico de Chat.
    """
    ensure_save_dir()
    
    if not filename.endswith(".json"):
        filename += ".json"
        
    filepath = os.path.join(SAVE_DIR, filename)
    
    # Serialização
    data_to_save = {
        "player": state["player"],
        "world": state["world"],
        "enemies": state.get("enemies", []),
        "party": state.get("party", []),
        "npcs": state.get("npcs", {}),
        "active_npc_name": state.get("active_npc_name"),
        "next": state.get("next"),
        "messages": messages_to_dict(state["messages"]) 
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        return f"Jogo salvo com sucesso em: {filepath}"
    except Exception as e:
        return f"Erro ao salvar o jogo: {e}"

def load_game(filename: str) -> GameState:
    """
    Carrega um save e reconstrói o GameState.
    """
    if not filename.endswith(".json"):
        filename += ".json"
        
    filepath = os.path.join(SAVE_DIR, filename)
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Save não encontrado: {filename}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Deserialização
    restored_messages = messages_from_dict(data["messages"])
    
    # Reconstrói GameState com defaults seguros para saves antigos
    restored_state: GameState = {
        "messages": restored_messages,
        "player": data["player"],
        "world": data["world"],
        "enemies": data.get("enemies", []),
        "party": data.get("party", []),
        "npcs": data.get("npcs", {}),
        "active_npc_name": data.get("active_npc_name"),
        "next": data.get("next")
    }
    
    return restored_state

def list_saves() -> List[str]:
    """Lista arquivos .json na pasta saves."""
    ensure_save_dir()
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".json")]
    return files