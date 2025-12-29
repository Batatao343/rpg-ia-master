"""
persistence.py
Gerencia o Salvamento e Carregamento do Estado do Jogo.
Serializa objetos complexos (como mensagens do LangChain) para JSON.
"""
import os
import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

# Caminho do arquivo de save
SAVE_DIR = "data"
SAVE_FILE = os.path.join(SAVE_DIR, "savegame.json")

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
        # Ignora tipos desconhecidos para evitar quebra
    return messages

def save_game_state(state: Dict[str, Any]) -> bool:
    """
    Salva o estado completo do jogo em JSON.
    Retorna True se sucesso, False se falha.
    """
    if not state:
        return False

    try:
        # 1. Prepara os dados serializáveis
        # Extraímos apenas o que é persistente. 
        # Campos transitórios (como 'next' ou 'router_confidence') não precisam ser salvos.
        save_data = {
            "player": state.get("player", {}),
            "world": state.get("world", {}),
            "party": state.get("party", []),
            "enemies": state.get("enemies", []), # Salva estado dos monstros (HP atual, etc)
            "npcs": state.get("npcs", {}),       # Salva memória dos NPCs
            "inventory": state.get("inventory", []),
            "quests": state.get("quests", []),
            "campaign_plan": state.get("campaign_plan", {}), # VITAL para o Storyteller continuar a trama
            
            # Serializa o histórico de mensagens
            "message_history": _serialize_messages(state.get("messages", []))
        }

        # 2. Garante que a pasta existe
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

        # 3. Escreve no disco
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
        
        return True

    except Exception as e:
        print(f"❌ Erro crítico ao salvar jogo: {e}")
        return False

def load_game_state() -> Dict[str, Any]:
    """
    Carrega o jogo do disco e reconstrói o Estado.
    Retorna None se não houver save ou houver erro.
    """
    if not os.path.exists(SAVE_FILE):
        return None

    try:
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # Reconstrói o Estado compatível com GameState
        state = {
            "player": raw_data.get("player", {}),
            "world": raw_data.get("world", {}),
            "party": raw_data.get("party", []),
            "enemies": raw_data.get("enemies", []),
            "npcs": raw_data.get("npcs", {}),
            "inventory": raw_data.get("inventory", []),
            "quests": raw_data.get("quests", []),
            "campaign_plan": raw_data.get("campaign_plan", {}),
            
            # Reconstrói objetos de mensagem
            "messages": _deserialize_messages(raw_data.get("message_history", [])),
            
            # Garante campos técnicos para o grafo não quebrar ao iniciar
            "next": "storyteller", 
            "loot_source": None,
            "combat_target": None
        }

        return state

    except Exception as e:
        print(f"⚠️ Erro ao carregar save (arquivo corrompido?): {e}")
        return None