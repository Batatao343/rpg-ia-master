"""
persistence.py
Gerencia o Salvamento e Carregamento do Estado do Jogo.
Salva em pasta dedicada 'saves/' e serializa novos campos de memória.
"""
import os
import json
import glob
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

# Configuração de Pastas
SAVES_DIR = "saves"
DEFAULT_SAVE_NAME = "autosave"

def _serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """Converte objetos Message do LangChain para dicionários simples (JSON)."""
    serialized = []
    for msg in messages:
        msg_type = "unknown"
        if isinstance(msg, HumanMessage): msg_type = "human"
        elif isinstance(msg, AIMessage): msg_type = "ai"
        elif isinstance(msg, SystemMessage): msg_type = "system"
        
        serialized.append({
            "type": msg_type,
            "content": msg.content
        })
    return serialized

def _deserialize_messages(data: List[Dict[str, str]]) -> List[BaseMessage]:
    """Reconstrói objetos Message do LangChain a partir de dicionários."""
    messages = []
    for item in data:
        if item["type"] == "human":
            messages.append(HumanMessage(content=item["content"]))
        elif item["type"] == "ai":
            messages.append(AIMessage(content=item["content"]))
        elif item["type"] == "system":
            messages.append(SystemMessage(content=item["content"]))
    return messages

def get_latest_save_file() -> Optional[str]:
    """Retorna o caminho do arquivo de save mais recente na pasta saves/."""
    if not os.path.exists(SAVES_DIR):
        return None
    
    # Lista todos os .json na pasta saves
    list_of_files = glob.glob(os.path.join(SAVES_DIR, "*.json"))
    if not list_of_files:
        return None
        
    # Retorna o mais recente
    return max(list_of_files, key=os.path.getctime)

def save_game_state(state: Dict[str, Any]) -> bool:
    """
    Salva o estado completo do jogo em JSON na pasta 'saves/'.
    Usa o 'game_id' como nome do arquivo.
    """
    if not state: return False

    try:
        # Garante que a pasta existe
        if not os.path.exists(SAVES_DIR):
            os.makedirs(SAVES_DIR)

        # Define nome do arquivo baseado no ID
        game_id = state.get("game_id", DEFAULT_SAVE_NAME)
        file_path = os.path.join(SAVES_DIR, f"{game_id}.json")

        # Prepara os dados serializáveis
        save_data = {
            # --- Identificação e Memória (Novos Campos) ---
            "game_id": game_id,
            "narrative_summary": state.get("narrative_summary", ""),
            "archivist_last_run": state.get("archivist_last_run", 0),
            
            # --- Dados Transicionais ---
            "combat_target": state.get("combat_target"),
            "loot_source": state.get("loot_source"),

            # --- Dados Core ---
            "player": state.get("player", {}),
            "world": state.get("world", {}),
            "party": state.get("party", []),
            "enemies": state.get("enemies", []), 
            "npcs": state.get("npcs", {}),       
            "inventory": state.get("inventory", []),
            "quests": state.get("quests", []),
            "campaign_plan": state.get("campaign_plan", {}), 
            
            # --- Histórico ---
            "message_history": _serialize_messages(state.get("messages", []))
        }

        # Escreve no disco
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
        
        return True

    except Exception as e:
        print(f"❌ Erro crítico ao salvar jogo: {e}")
        return False

def load_game_state(specific_file: str = None) -> Dict[str, Any]:
    """
    Carrega o jogo. Se specific_file não for passado, carrega o mais recente.
    """
    target_file = specific_file
    
    if not target_file:
        target_file = get_latest_save_file()
    
    if not target_file or not os.path.exists(target_file):
        return None

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # Reconstrói o Estado compatível com GameState
        state = {
            # --- Recupera Memória ---
            "game_id": raw_data.get("game_id", "recovered_session"),
            "narrative_summary": raw_data.get("narrative_summary", ""),
            "archivist_last_run": raw_data.get("archivist_last_run", 0),
            
            # --- Recupera Core ---
            "player": raw_data.get("player", {}),
            "world": raw_data.get("world", {}),
            "party": raw_data.get("party", []),
            "enemies": raw_data.get("enemies", []),
            "npcs": raw_data.get("npcs", {}),
            "inventory": raw_data.get("inventory", []),
            "quests": raw_data.get("quests", []),
            "campaign_plan": raw_data.get("campaign_plan", {}),
            
            # --- Recupera Transicionais ---
            "combat_target": raw_data.get("combat_target"),
            "loot_source": raw_data.get("loot_source"),

            # --- Recupera Mensagens ---
            "messages": _deserialize_messages(raw_data.get("message_history", [])),
            
            # Garante campos técnicos de fluxo
            "next": "storyteller", 
            "needs_replan": False
        }

        return state

    except Exception as e:
        print(f"⚠️ Erro ao carregar save '{target_file}': {e}")
        return None