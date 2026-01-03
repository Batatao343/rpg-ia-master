"""
api.py
Interface REST API para o RPG Engine.
Atualizado para suportar Memória Híbrida (Game ID e Resumo).
"""
import sys
import os
import uvicorn
import uuid # <--- Necessário para gerar IDs de sessão
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
from main import app as game_graph
from persistence import save_game_state, load_game_state, _serialize_messages
from character_creator import create_player_character
from gamedata import CLASSES, load_json_data

# --- CONFIGURAÇÃO DA API ---
app = FastAPI(
    title="RPG IA Engine API",
    description="Backend para RPG de Texto com IA, Crafting e NPCs.",
    version="v2.0 Hybrid Memory"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS (DTOs) ---
class CreateCharacterRequest(BaseModel):
    name: str
    race: str
    class_name: str
    region: str
    level: int = 1
    backstory: Optional[str] = ""

class ActionRequest(BaseModel):
    input_text: str
    game_id: Optional[str] = None # Opcional: permite especificar qual save carregar

class GameResponse(BaseModel):
    game_id: str # <--- Novo: Frontend precisa saber o ID
    message: str
    message_type: str 
    player_stats: Dict[str, Any]
    inventory: List[str]
    current_location: str
    narrative_summary: str # <--- Novo: Frontend pode mostrar o resumo
    last_turn_log: List[Dict[str, Any]]

# --- HELPER: FORMATA RESPOSTA ---
def format_response(state: dict) -> GameResponse:
    # Pega a última mensagem
    last_msg_obj = state["messages"][-1]
    last_content = last_msg_obj.content
    
    # Define o tipo de mensagem
    msg_type = "STORY"
    next_node = state.get("next", "")
    
    if "⚔️" in last_content or next_node == "combat_agent":
        msg_type = "COMBAT"
    elif "💰" in last_content or "item" in last_content.lower():
        msg_type = "LOOT"
    elif "🗣️" in last_content or '"' in last_content:
        msg_type = "NPC"

    return GameResponse(
        game_id=state.get("game_id", "unknown"),
        message=last_content,
        message_type=msg_type,
        player_stats={
            "hp": state["player"]["hp"],
            "max_hp": state["player"]["max_hp"],
            "gold": state["player"]["gold"],
            "level": state["player"]["level"],
            "xp": state["player"]["xp"]
        },
        inventory=state["player"]["inventory"],
        current_location=state["world"]["current_location"],
        narrative_summary=state.get("narrative_summary", ""),
        last_turn_log=_serialize_messages(state["messages"][-5:]) 
    )

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "engine": "RPG IA v9.0 Hybrid Memory"}

@app.get("/data/options")
def get_creation_options():
    origins = load_json_data("origins.json")
    return {
        "races": [r["name"] for r in origins.get("races", [])],
        "classes": list(CLASSES.keys()),
        "regions": [r["name"] for r in origins.get("regions", [])]
    }

@app.get("/game/state")
def get_current_state(game_id: Optional[str] = None):
    """
    Carrega o jogo. Se game_id for passado, carrega aquele especifico.
    Caso contrario, carrega o ultimo modificado.
    """
    # A lógica de carregar arquivo especifico deve ser implementada no persistence futuramente
    # Por enquanto, load_game_state carrega o mais recente se não passarmos nada
    # Se você implementou o load_game_state(specific_file), usaria aqui
    
    file_to_load = None
    if game_id:
        file_to_load = f"saves/{game_id}.json"
        
    state = load_game_state(file_to_load)
    
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return format_response(state)

@app.post("/game/new", response_model=GameResponse)
def new_game(req: CreateCharacterRequest):
    """Cria um novo personagem e inicia a campanha com ID único."""
    print(f"Criando personagem: {req.name}")
    
    char_input = {
        "name": req.name,
        "class_name": req.class_name,
        "race": req.race,
        "region": req.region,
        "backstory": req.backstory,
        "level": req.level
    }
    final_char = create_player_character(char_input)
    
    # Gera ID único
    new_game_id = str(uuid.uuid4())

    # 2. Monta Estado Inicial (COMPATÍVEL COM HYBRID MEMORY)
    initial_state = {
        # --- Campos Novos ---
        "game_id": new_game_id,
        "narrative_summary": f"A jornada de {req.name} começa em {final_char['region']}. {req.backstory}",
        "archivist_last_run": 0,
        "combat_target": None,
        "loot_source": None,

        # --- Dados do Player ---
        "player": {
            "name": final_char["name"],
            "class": final_char["class_name"],
            "race": final_char["race"],
            "level": final_char["level"],
            "xp": 0,
            "hp": final_char["hp"],
            "max_hp": final_char["max_hp"],
            "gold": 50 * req.level,
            "attributes": final_char["attributes"],
            "inventory": final_char["inventory"],
            "equipment": {},
            "abilities": final_char["known_abilities"],
            "defense": final_char["defense"],
            "attack_bonus": 0,
            "active_conditions": []
        },
        "world": {
            "current_location": final_char["region"],
            "time_of_day": "Amanhecer",
            "turn_count": 0,
            "danger_level": req.level,
            "quest_plan": [],
            "quest_plan_origin": None
        },
        "messages": [
            SystemMessage(content=f"A jornada de {req.name} começa em {final_char['region']}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {req.level}.")
        ],
        "party": [],
        "enemies": [],
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller"
    }

    # 3. Roda o Grafo
    try:
        final_state = game_graph.invoke(initial_state)
        save_game_state(final_state)
        return format_response(final_state)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/game/action", response_model=GameResponse)
def game_action(req: ActionRequest):
    """Envia uma ação do jogador."""
    
    # Tenta carregar pelo ID se fornecido, ou o ultimo
    file_to_load = None
    if req.game_id:
        file_to_load = f"saves/{req.game_id}.json"

    state = load_game_state(file_to_load)
    
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    # Adiciona Input
    user_msg = HumanMessage(content=req.input_text)
    state["messages"].append(user_msg)
    
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]

    # Executa Engine
    try:
        new_state = game_graph.invoke(state)
        save_game_state(new_state)
        return format_response(new_state)
    
    except Exception as e:
        print(f"Erro na API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)