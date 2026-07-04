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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
from main import app as game_graph
from persistence import save_game_state, load_game_state, _serialize_messages
from character_creator import create_player_character
from gamedata import ABILITIES, CLASSES, load_json_data, seed_factions
import progression
from services import quest_log
from services import state_views as sv
from services.chronicle import default_chapter_title
from services.discovery import player_codex
from world_utils import starting_world

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

class LevelUpRequest(BaseModel):
    """Fase 4.1: consome UMA pending_choice. kind=ability -> ability_id;
    kind=attribute -> attr (str/dex/con/int/wis/cha ou nome longo/PT)."""
    choice_id: str
    ability_id: Optional[str] = None
    attr: Optional[str] = None
    game_id: Optional[str] = None

class GameResponse(BaseModel):
    game_id: str # <--- Novo: Frontend precisa saber o ID
    message: str
    message_type: str 
    player_stats: Dict[str, Any]
    inventory: List[str]
    current_location: str
    narrative_summary: str # <--- Novo: Frontend pode mostrar o resumo
    last_turn_log: List[Dict[str, Any]]
    simulated: bool = False # True quando rodando em modo simulado (sem API key)
    world: Dict[str, Any] = {} # location_id, day, period, visited (fog of war), danger
    quest: Dict[str, Any] = {} # objetivo atual, beats (status), clímax, progresso
    combat: Dict[str, Any] = {} # inimigos, condições, iniciativa, round, cooldowns
    npcs: List[Dict[str, Any]] = [] # NPCs conhecidos (nome, papel, local, relação, última lembrança)
    chronicle: List[Dict[str, Any]] = [] # capítulos: {title, started_turn, location, entries[{text,turn,kind,event_id?}]}
    factions: List[Dict[str, Any]] = [] # fações vivas: objetivo, progresso, postura, reputação

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
            "name": state["player"].get("name", "Herói"),
            "class_name": state["player"].get("class_name") or state["player"].get("class", ""),
            "race": state["player"].get("race", ""),
            "hp": state["player"].get("hp", 0),
            "max_hp": state["player"].get("max_hp", 0),
            "mana": state["player"].get("mana", 0),
            "max_mana": state["player"].get("max_mana", 0),
            "stamina": state["player"].get("stamina", 0),
            "max_stamina": state["player"].get("max_stamina", 0),
            "defense": state["player"].get("defense", 0),
            "gold": state["player"].get("gold", 0),
            "level": state["player"].get("level", 1),
            "xp": state["player"].get("xp", 0),
            # Fase 4.1: ids canônicos + nome exibível (frontend não mostra id cru)
            "abilities": [
                {"id": aid, "name": ABILITIES.get(aid, {}).get("name", aid),
                 "branch": ABILITIES.get(aid, {}).get("branch")}
                for aid in (state["player"].get("known_abilities", []) or [])
            ],
            "xp_next_level": progression.xp_to_next(int(state["player"].get("level", 1) or 1)),
            "pending_choices": state["player"].get("pending_choices", []) or [],
            "level_up": _levelup_block(state["player"]),
        },
        inventory=state["player"]["inventory"],
        current_location=state["world"]["current_location"],
        narrative_summary=state.get("narrative_summary", ""),
        last_turn_log=_serialize_messages(state["messages"][-5:]),
        simulated=(not os.getenv("GOOGLE_API_KEY")) and (not os.getenv("RPG_NO_MOCK")),
        world=_world_block(state.get("world", {}) or {}, state.get("world_projection", {}) or {},
                          state.get("event_log", []) or []),
        quest=_quest_block(state.get("campaign_plan") or {}, state.get("quests", []) or []),
        combat=_combat_block(state),
        npcs=_npcs_block(state.get("npcs", {}) or {}),
        chronicle=_chronicle_block(state.get("chronicle", []) or []),
        factions=_factions_block(state.get("factions", []) or [],
                                 state.get("faction_intel", {}) or {},
                                 (state.get("world", {}) or {}).get("turn_count", 0),
                                 state.get("event_log", []) or [],
                                 state.get("world_projection", {}) or {}),
    )


def _levelup_block(player: dict) -> Dict[str, Any]:
    """Fase 4.1: escolhas pendentes + elegíveis da árvore (vazio se nada pendente)."""
    pending = player.get("pending_choices", []) or []
    if not pending:
        return {}
    class_name = str(player.get("class_name", ""))
    branches = (CLASSES.get(class_name) or {}).get("branches") or {}
    eligible = []
    for aid in progression.eligible_abilities(player):
        a = ABILITIES.get(aid, {})
        br = a.get("branch")
        eligible.append({
            "id": aid, "name": a.get("name", aid),
            "description": a.get("description", ""),
            "branch": br,
            "branch_name": (branches.get(br) or {}).get("name") if br else None,
            "tier": a.get("tier", 1), "cost": a.get("cost", 0),
            "resource_type": a.get("resource_type", ""),
        })
    return {
        "pending": pending,
        "eligible": eligible,
        "current_branch": progression.player_branch(player),
        "branches": branches,
    }


def _chronicle_block(chronicle: list) -> List[Dict[str, Any]]:
    """Capítulos da crônica para o HUD (Fase 3.1) — filtra entradas vazias."""
    out: List[Dict[str, Any]] = []
    for cap in chronicle:
        if not isinstance(cap, dict):
            continue
        entries = [e for e in (cap.get("entries") or [])
                   if isinstance(e, dict) and str(e.get("text", "")).strip()]
        out.append({
            "title": cap.get("title", ""),
            "started_turn": cap.get("started_turn", 0),
            "location": cap.get("location", ""),
            "entries": entries,
        })
    return out


def _factions_block(factions: list, intel: dict, turn: int = 0,
                    event_log: Optional[list] = None, projection: Optional[dict] = None) -> List[Dict[str, Any]]:
    """
    Fações para o HUD — não-onisciência: só as que o jogador CONHECE (intel.known).
    Objetivo só se aprendido; progresso é o SNAPSHOT que o jogador viu (nunca o ao vivo);
    fações eliminadas somem. Fase 3.4: history/stability_label são views derivadas do
    event_log/projection — só pra fações já filtradas por known (não vaza timeline de
    fação desconhecida).
    """
    intel = intel or {}
    out = []
    for f in factions:
        if not isinstance(f, dict):
            continue
        if f.get("defeated"):
            continue
        rec = intel.get(f.get("id", ""), {})
        if not rec.get("known"):
            continue  # jogador nunca ouviu falar desta facção
        knows_goal = bool(rec.get("knows_goal"))
        seen = rec.get("progress_seen")
        intel_turn = rec.get("intel_turn")
        stale = seen is not None and isinstance(intel_turn, int) and int(turn) > int(intel_turn)
        fid = f.get("id", "")
        out.append({
            "id": fid,
            "name": f.get("name", ""),
            "goal": f.get("goal", "") if knows_goal else "",
            "knows_goal": knows_goal,
            "region": f.get("region", ""),
            "progress": int(seen) if seen is not None else None,
            "intel_stale": bool(stale),
            "disposition": f.get("disposition", "neutro"),
            "reputation": int(f.get("reputation", 0)),
            "completed": bool(f.get("completed", False)),
            "history": sv.reputation_history(event_log or [], fid),
            "stability_label": sv.stability_label(projection or {}, fid),
        })
    return out


def _npcs_block(npcs: dict) -> List[Dict[str, Any]]:
    """NPCs conhecidos pelo jogador (o que sabemos hoje: papel, local, relação, última lembrança)."""
    out = []
    for key, n in npcs.items():
        if not isinstance(n, dict):
            continue
        mem = n.get("memory") or []
        last_mem = mem[-1] if isinstance(mem, list) and mem else ""
        out.append({
            "name": n.get("name", key),
            "role": n.get("role", ""),
            "location": n.get("location", ""),
            "relationship": n.get("relationship", 5),
            "last_memory": last_mem,
        })
    return out




def _combat_block(state: dict) -> Dict[str, Any]:
    """Expõe o estado de combate para o HUD (inimigos vivos, condições, iniciativa)."""
    meta = state.get("combat") or {}
    enemies = state.get("enemies") or []
    player = state.get("player") or {}
    alive = [e for e in enemies if e.get("status") == "ativo"]

    def _conds(entity):
        return [{"name": c.get("name", ""), "dot": c.get("dot", 0), "duration": c.get("duration", 0)}
                for c in (entity.get("active_conditions") or []) if isinstance(c, dict)]

    return {
        "active": bool(meta.get("active")) and bool(alive),
        "round": meta.get("round", 0),
        "order": [{"name": o.get("name", ""), "side": o.get("side", ""), "init": o.get("init", 0)}
                  for o in (meta.get("order") or [])],
        "enemies": [
            {"name": e.get("name", ""), "hp": e.get("hp", 0), "max_hp": e.get("max_hp", 0),
             "defense": e.get("defense", 0), "conditions": _conds(e)}
            for e in alive
        ],
        "player_conditions": _conds(player),
        "cooldowns": dict(player.get("ability_cooldowns", {}) or {}),
    }


def _quest_block(plan: dict, quests: list) -> Dict[str, Any]:
    """Fase 3.3: main (view do campaign_plan) + side quests + markers pro mapa."""
    plan = plan or {}
    beats = plan.get("beats", []) or []
    step = plan.get("current_step", 0)
    climax = plan.get("climax", "")
    if 0 <= step < len(beats):
        objective = beats[step].get("description", "")
    else:
        # Todos os beats concluídos → o clímax é o objetivo final da cena.
        objective = climax
    main = {
        "objective": objective,
        "climax": climax,
        "current_step": step,
        "total": len(beats),
        "arc_title": plan.get("arc_title", ""),
        "beats": [
            {"description": b.get("description", ""), "status": b.get("status", "pending")}
            for b in beats
        ],
    }
    quests = [q for q in (quests or []) if isinstance(q, dict)]
    active = [q for q in quests if q.get("status") == "active"]
    resolved = sorted((q for q in quests if q.get("status") != "active"),
                      key=lambda q: q.get("resolved_turn", 0), reverse=True)[:5]
    return {"main": main, "side": active + resolved, "markers": quest_log.quest_markers(quests)}


def _world_block(w: dict, projection: Optional[dict] = None, event_log: Optional[list] = None) -> Dict[str, Any]:
    clock = w.get("world_clock") or {}
    turn = w.get("turn_count", 0)
    return {
        "location": w.get("current_location", ""),
        "location_id": w.get("current_location_id", ""),
        "day": clock.get("day", 1),
        "period": clock.get("period", "Amanhecer"),
        "visited": w.get("visited", []),
        "danger": w.get("danger_level", 1),
        "turn_count": turn,  # Fase 3.2: refetch do Codex quando o turno muda
        # Fase 3.4: controlador por local visitado (verdade 2.5+/projection vence o
        # legado da Fase 2; NOME, não id — ver services/state_views.visible_controllers).
        "controlled": sv.visible_controllers(w, projection or {}),
        "danger_overrides": dict(w.get("danger_overrides") or {}),
        "map_overlays": {
            "control_changes": sv.recent_control_changes(event_log or [], w.get("visited", []), turn),
            "threats": sv.active_threats(w, turn),
            "looming_threat": w.get("looming_threat", ""),
        },
    }

# --- ENDPOINTS ---

@app.get("/health")
def health_check():
    return {"status": "online", "engine": "RPG IA v9.0 Hybrid Memory"}

@app.get("/data/options")
def get_creation_options():
    origins = load_json_data("origins.json")
    return {
        "races": [r["name"] for r in origins.get("races", [])],
        # Fase 2.5b: raças completas (desc + traits) p/ o frontend exibir na criação
        "races_full": origins.get("races", []),
        "classes": list(CLASSES.keys()),
        "regions": [r["name"] for r in origins.get("regions", [])]
    }

@app.get("/data/map")
def get_world_map():
    """Grafo de locais (Fase 0) para o mapa com fog of war no frontend."""
    return load_json_data("world_map.json")

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

@app.get("/game/codex")
def get_player_codex(game_id: Optional[str] = None):
    """Codex do jogador (Fase 3.2) — locais/fações/personagens/criaturas/segredos
    já registrados no save. On-demand (fora do GameResponse) para não inchar o turno."""
    file_to_load = f"saves/{game_id}.json" if game_id else None
    state = load_game_state(file_to_load)

    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return player_codex(state)

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
        # Fase 3.1: capítulo 1 existe desde o turno 0 (determinístico, sem LLM)
        "chronicle": [{"title": default_chapter_title(final_char["region"]),
                       "started_turn": 0, "location": final_char["region"], "entries": []}],
        "combat_target": None,
        "loot_source": None,

        # --- Dados do Player ---
        "player": {
            "name": final_char["name"],
            "class_name": final_char["class_name"],
            "race": final_char["race"],
            "level": final_char["level"],
            "xp": 0,
            "hp": final_char["hp"],
            "max_hp": final_char["max_hp"],
            "mana": final_char["mana"],
            "max_mana": final_char["max_mana"],
            "stamina": final_char["stamina"],
            "max_stamina": final_char["max_stamina"],
            "gold": 50 * req.level,
            "alignment": "Neutro",
            "attributes": final_char["attributes"],
            "inventory": final_char["inventory"],
            "known_abilities": final_char["known_abilities"],
            "defense": final_char["defense"],
            "attack_bonus": final_char.get("attack_bonus", 0),
            "active_conditions": []
        },
        "world": starting_world(final_char["region"], req.level),
        "messages": [
            SystemMessage(content=f"A jornada de {req.name} começa em {final_char['region']}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {req.level}.")
        ],
        "party": [],
        "enemies": [],
        "factions": seed_factions(),
        "faction_intel": {},  # não-onisciência: jogador começa sem saber de nenhuma facção
        "bestiary_knowledge": {},
        "quests": [],
        "archive_due": False,
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        # --- Fase 2.5: mundo estruturado ---
        "event_log": [],
        "world_projection": {},
        "pending_world_events": []
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

@app.post("/game/levelup")
def game_levelup(req: LevelUpRequest):
    """Fase 4.1: aplica UMA escolha de level up (habilidade ou atributo).

    Validação 100% server-side (progression.apply_choice): escolha inexistente,
    habilidade inelegível (classe/nível/pré-requisito/ramo rival) ou atributo
    inválido → 400 e o save fica intocado."""
    file_to_load = f"saves/{req.game_id}.json" if req.game_id else None
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    player, err = progression.apply_choice(
        state["player"], req.choice_id,
        ability_id=req.ability_id, attr=req.attr)
    if err:
        raise HTTPException(status_code=400, detail=err)

    state["player"] = player
    save_game_state(state)
    return {
        "ok": True,
        "player_stats": {
            "level": player.get("level", 1),
            "xp": player.get("xp", 0),
            "xp_next_level": progression.xp_to_next(int(player.get("level", 1) or 1)),
            "attributes": player.get("attributes", {}),
            "abilities": [
                {"id": aid, "name": ABILITIES.get(aid, {}).get("name", aid),
                 "branch": ABILITIES.get(aid, {}).get("branch")}
                for aid in (player.get("known_abilities", []) or [])
            ],
            "pending_choices": player.get("pending_choices", []) or [],
            "level_up": _levelup_block(player),
        },
    }


# --- FRONTEND ESTÁTICO ---
# Servido na raiz "/". As rotas de API acima têm precedência sobre o mount.
# Prefere a build do app React (web/dist); cai para o frontend vanilla se não houver build.
_ROOT = os.path.dirname(os.path.abspath(__file__))
_WEB_DIST = os.path.join(_ROOT, "web", "dist")
_FRONTEND_DIR = _WEB_DIST if os.path.isdir(_WEB_DIST) else os.path.join(_ROOT, "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)