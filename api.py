"""
api.py
Interface REST API para o RPG Engine.
Permite que frontends (React, Lovable, Mobile) se conectem ao jogo.
"""
import sys
import os
import uvicorn
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
    version="v1.0"
)

# Configuração de CORS (Permite que o frontend acesse o backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Em produção, troque "*" pela URL do seu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS (DTOs) ---
# Define o que o Frontend precisa enviar e o que vai receber

class CreateCharacterRequest(BaseModel):
    name: str
    race: str
    class_name: str
    region: str
    level: int = 1
    backstory: Optional[str] = ""

class ActionRequest(BaseModel):
    input_text: str

class GameResponse(BaseModel):
    message: str
    message_type: str = "STORY" # STORY, COMBAT, LOOT, NPC
    player_stats: Dict[str, Any]
    inventory: List[str]
    current_location: str
    last_turn_log: List[Dict[str, Any]] # Histórico recente

# --- HELPER: FORMATA RESPOSTA ---
def format_response(state: dict) -> GameResponse:
    # Pega a última mensagem
    last_msg_obj = state["messages"][-1]
    last_content = last_msg_obj.content
    
    # Define o tipo de mensagem para o frontend colorir
    # (Logica simplificada baseada no router ou conteúdo)
    msg_type = "STORY"
    next_node = state.get("next", "")
    
    if "⚔️" in last_content or next_node == "combat_agent":
        msg_type = "COMBAT"
    elif "💰" in last_content or "item" in last_content.lower():
        msg_type = "LOOT"
    elif "🗣️" in last_content or '"' in last_content:
        msg_type = "NPC"

    return GameResponse(
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
        last_turn_log=_serialize_messages(state["messages"][-5:]) # Retorna ultimas 5 para chat log
    )

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "engine": "RPG IA v8.2"}

@app.get("/data/options")
def get_creation_options():
    """Retorna listas de Raças e Classes para o Frontend popular os selects."""
    origins = load_json_data("origins.json")
    return {
        "races": [r["name"] for r in origins.get("races", [])],
        "classes": list(CLASSES.keys()),
        "regions": [r["name"] for r in origins.get("regions", [])]
    }

@app.get("/game/state")
def get_current_state():
    """Carrega o jogo salvo e retorna o estado atual."""
    state = load_game_state()
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return format_response(state)

@app.post("/game/new", response_model=GameResponse)
def new_game(req: CreateCharacterRequest):
    """Cria um novo personagem e inicia a campanha."""
    print(f"Criando personagem: {req.name}")
    
    # 1. Gera Ficha via IA (mesma lógica do game_engine)
    char_input = {
        "name": req.name,
        "class_name": req.class_name,
        "race": req.race,
        "region": req.region,
        "backstory": req.backstory,
        "level": req.level
    }
    final_char = create_player_character(char_input)

    # 2. Monta Estado Inicial
    initial_state = {
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
            "abilities": final_char["known_abilities"]
        },
        "world": {
            "current_location": final_char["region"],
            "time_of_day": "Amanhecer",
            "turn_count": 0,
            "danger_level": req.level
        },
        # Gatilho inicial para a IA narrar
        "messages": [
            SystemMessage(content=f"A jornada de {req.name} começa em {final_char['region']}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {req.level}.")
        ],
        "party": [],
        "enemies": [],
        "npcs": {},
        "quests": [],
        "campaign_plan": {},
        "next": "storyteller"
    }

    # 3. Roda o Grafo para gerar a primeira descrição
    try:
        final_state = game_graph.invoke(initial_state)
        save_game_state(final_state)
        return format_response(final_state)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/game/action", response_model=GameResponse)
def game_action(req: ActionRequest):
    """Envia uma ação do jogador e retorna a resposta da IA."""
    
    # 1. Carrega Estado
    state = load_game_state()
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado. Crie um novo jogo.")

    # 2. Adiciona Input do Usuário
    user_msg = HumanMessage(content=req.input_text)
    state["messages"].append(user_msg)
    
    # Limita histórico para economizar tokens
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]

    # 3. Executa Engine
    try:
        new_state = game_graph.invoke(state)
        
        # 4. Salva e Retorna
        save_game_state(new_state)
        return format_response(new_state)
    
    except Exception as e:
        print(f"Erro na API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Para rodar direto do arquivo (debug)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)