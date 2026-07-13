"""
api.py
Interface REST API para o RPG Engine.
Atualizado para suportar Memória Híbrida (Game ID e Resumo).
Fase 10: game_id validado (UUID) na borda, CORS por env, rate limit mínimo,
log JSON por turno.
"""
import json
import logging
import sys
import os
import time
import uvicorn
import uuid # <--- Necessário para gerar IDs de sessão
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
from main import app as game_graph
from persistence import save_game_state, load_game_state, save_path, _serialize_messages
from character_creator import create_player_character
from gamedata import ABILITIES, CLASSES, load_json_data, seed_factions
from llm_setup import is_simulated
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

# Fase 10 (R5): CORS restrito por default; configurável via RPG_CORS_ORIGINS
# (CSV no .env; "*" só se explicitamente configurado).
_CORS_ORIGINS = [
    o.strip() for o in os.getenv(
        "RPG_CORS_ORIGINS", "http://localhost:8000,http://localhost:5173"
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fase 10 (R7): 1 linha JSON por turno no stderr (base de observabilidade).
_turn_logger = logging.getLogger("rpg.turn")
if not _turn_logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _turn_logger.addHandler(_handler)
    _turn_logger.setLevel(logging.INFO)
    _turn_logger.propagate = False


def _resolve_save_file(game_id: Optional[str]) -> Optional[str]:
    """game_id do cliente -> caminho de save validado (Fase 10, R1/R2).

    None passa (carrega o save mais recente); não-UUID -> HTTP 400 sem tocar
    no filesystem.
    """
    if not game_id:
        return None
    try:
        return save_path(game_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="game_id inválido (esperado UUID).")


def _reject_memorial(state: dict) -> None:
    """Fase 4.6 (R7) + auditoria A2: save morto é MEMORIAL — nenhum endpoint
    de mutação (action/equip/levelup) toca nele."""
    if state.get("game_over"):
        raise HTTPException(status_code=409,
                            detail="Esta saga terminou. A crônica permanece como memorial — comece uma nova jornada.")


# Fase 10 (R6): rate limit mínimo por IP (janela deslizante em memória).
# RPG_RATE_LIMIT = req/min em /game/action e /game/new; 0 desliga (suíte/smoke).
_RATE_WINDOW_S = 60.0
_rate_hits: Dict[str, deque] = defaultdict(deque)


def _rate_limit_max() -> int:
    try:
        return int(os.getenv("RPG_RATE_LIMIT", "30"))
    except ValueError:
        return 30


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    limit = _rate_limit_max()
    # Auditoria A2: equip/levelup também mutam o save — entram na janela.
    if limit > 0 and request.url.path in ("/game/action", "/game/new",
                                          "/game/equip", "/game/levelup"):
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        # Auditoria A8: teto no dict — descarta IPs com janela inteira vencida.
        if len(_rate_hits) > 1000:
            stale = [k for k, dq in _rate_hits.items()
                     if not dq or now - dq[-1] > _RATE_WINDOW_S]
            for k in stale:
                del _rate_hits[k]
        hits = _rate_hits[ip]
        while hits and now - hits[0] > _RATE_WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429,
                                content={"detail": "Muitas requisições — aguarde um instante."})
        hits.append(now)
    return await call_next(request)

# --- MODELOS DE DADOS (DTOs) ---
class CreateCharacterRequest(BaseModel):
    # Auditoria A1: level sem bound permitia ouro NEGATIVO (50×level) e ficha
    # absurda; A7: campos livres viram prompt de LLM — tamanho limitado na borda.
    name: str = Field(min_length=1, max_length=80)
    race: str = Field(max_length=40)
    class_name: str = Field(max_length=40)
    region: str = Field(max_length=60)
    level: int = Field(1, ge=1, le=20)
    backstory: Optional[str] = Field("", max_length=2000)

class ActionRequest(BaseModel):
    # Auditoria A7: ação vira prompt — sem teto, request gigante = custo/latência.
    input_text: str = Field(max_length=2000)
    game_id: Optional[str] = None # Opcional: permite especificar qual save carregar

class EquipRequest(BaseModel):
    """Fase 4.3: equipa item do inventário (slot deduzido do tipo) ou desequipa slot."""
    item_id: Optional[str] = None   # equipar este item
    unequip_slot: Optional[str] = None  # OU esvaziar este slot
    game_id: Optional[str] = None

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
    # Fase 4.3: estruturado — {id, name, qty, type, equipped, slot}
    inventory: List[Dict[str, Any]]
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
    party: List[Dict[str, Any]] = [] # Fase 4.5: companheiros {name, hp, max_hp, active, archetype, status}

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
        inventory=_inventory_block(state["player"]),
        current_location=state["world"]["current_location"],
        narrative_summary=state.get("narrative_summary", ""),
        last_turn_log=_serialize_messages(state["messages"][-5:]),
        # Auditoria A4: espelha a decisão real do get_llm (qualquer provider conta)
        simulated=is_simulated(),
        world=_world_block(state.get("world", {}) or {}, state.get("world_projection", {}) or {},
                          state.get("event_log", []) or []),
        quest=_quest_block(state.get("campaign_plan") or {}, state.get("quests", []) or []),
        combat=_combat_block(state),
        npcs=_npcs_block(state.get("npcs", {}) or {}),
        chronicle=_chronicle_block(state.get("chronicle", []) or []),
        party=[{"name": c.get("name", "?"), "hp": c.get("hp", 0),
                "max_hp": c.get("max_hp", 1), "active": bool(c.get("active")),
                "archetype": c.get("archetype", ""), "status": c.get("status", "ativo")}
               for c in (state.get("party") or []) if isinstance(c, dict)],
        factions=_factions_block(state.get("factions", []) or [],
                                 state.get("faction_intel", {}) or {},
                                 (state.get("world", {}) or {}).get("turn_count", 0),
                                 state.get("event_log", []) or [],
                                 state.get("world_projection", {}) or {}),
    )


def _inventory_block(player: dict) -> List[Dict[str, Any]]:
    """Fase 4.3: inventário estruturado com nome canônico (nunca title() sobre id)."""
    import inventory as inv_mod
    from gamedata import ARTIFACTS_DB
    eq = player.get("equipment") or {}
    equipped = {v: k for k, v in eq.items() if v}
    out = []
    for e in player.get("inventory") or []:
        if not isinstance(e, dict):  # tolerância a estado antigo em memória
            e = inv_mod.make_entry(str(e), 1)
        item = ARTIFACTS_DB.get(e.get("id", "")) or {}
        out.append({
            "id": e.get("id"), "name": inv_mod.item_display(e),
            "qty": int(e.get("qty", 1)),
            "type": item.get("type", "desconhecido"),
            "equipped": e.get("id") in equipped,
            "slot": equipped.get(e.get("id")) or inv_mod.slot_for(e.get("id", "")),
            "unique": bool(item.get("unique")),  # Fase 6.2: ◆ um por mundo
        })
    return out


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
    """Camada 2 (spec npcs-3-camadas): só NPCs conhecidos, com traits REVELADOS
    — hidden_traits NUNCA sai pela API (R9)."""
    from services.npc_layers import visible_npc_view
    out = visible_npc_view(npcs)
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
        "weather": w.get("weather", ""),  # Fase 6.5: rótulo do clima atual
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
        # Fase 6.1: rotas comerciais bloqueadas (WorldMap traceja a conexão)
        "blocked_routes": [
            {"a": r.get("a", ""), "b": r.get("b", "")}
            for r in (projection or {}).get("blocked_routes", []) or []
        ],
        # spec mapa-sublocais (R7): interiores do local atual ("Locais daqui")
        # + caminho de volta quando o jogador está DENTRO de um interior.
        "interiors": _interiors_block(w.get("current_location_id", "")),
    }


def _interiors_block(loc_id: str) -> Dict[str, Any]:
    from gamedata import get_location, interiors_of
    loc = get_location(loc_id) or {}
    here = [
        {"id": i["id"], "name": i["name"], "danger": i.get("danger", 0),
         "tags": i.get("tags", [])}
        for i in interiors_of(loc_id)
    ]
    exit_to = None
    if loc.get("kind") == "interior":
        parent = get_location(loc.get("parent_id", "")) or {}
        if parent:
            exit_to = {"id": parent["id"], "name": parent["name"]}
    return {"here": here, "exit_to": exit_to}

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
    """Grafo de locais (Fase 0) para o mapa com fog of war no frontend.

    spec mapa-sublocais (R7): interiores NÃO aparecem no mapa-múndi —
    são expostos como "Locais daqui" no bloco `world` de /game/state.
    """
    data = dict(load_json_data("world_map.json") or {})
    data["locations"] = [
        loc for loc in data.get("locations", [])
        if loc.get("kind") != "interior"
    ]
    return data

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
    file_to_load = _resolve_save_file(game_id)
        
    state = load_game_state(file_to_load)
    
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return format_response(state)

@app.get("/game/codex")
def get_player_codex(game_id: Optional[str] = None):
    """Codex do jogador (Fase 3.2) — locais/fações/personagens/criaturas/segredos
    já registrados no save. On-demand (fora do GameResponse) para não inchar o turno."""
    file_to_load = _resolve_save_file(game_id)
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
            # Fase 4.3: slots do creator (auto-equip) — sem isto o HUD nasce sem arma
            "equipment": final_char.get("equipment",
                                        {"weapon": None, "armor": None, "accessory": None}),
            "known_abilities": final_char["known_abilities"],
            "pending_choices": final_char.get("pending_choices", []),
            "defense": final_char["defense"],
            "attack_bonus": final_char.get("attack_bonus", 0),
            "active_conditions": [],
            # Fase 2.5b: traits raciais calculados no creator
            "racial_traits": final_char.get("racial_traits", []),
            "condition_resists": final_char.get("condition_resists", []),
            "racial_save_bonus": final_char.get("racial_save_bonus", {}),
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
        # Auditoria A6: detalhe interno só no log do servidor, nunca na resposta.
        print(f"Erro ao criar jogo: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar o jogo.")

@app.post("/game/action", response_model=GameResponse)
def game_action(req: ActionRequest):
    """Envia uma ação do jogador."""
    
    # Tenta carregar pelo ID se fornecido, ou o ultimo
    file_to_load = _resolve_save_file(req.game_id)

    state = load_game_state(file_to_load)

    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    # Fase 4.6 (R7): save morto é MEMORIAL — a crônica fica, ações não.
    _reject_memorial(state)

    # Adiciona Input
    user_msg = HumanMessage(content=req.input_text)
    state["messages"].append(user_msg)
    
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]

    # Executa Engine
    t0 = time.monotonic()
    eventos_antes = len(state.get("event_log", []))
    try:
        new_state = game_graph.invoke(state)
        save_game_state(new_state)
        _turn_logger.info(json.dumps({
            "evt": "turn",
            "game_id": new_state.get("game_id", "?"),
            "turn": (new_state.get("world") or {}).get("turn_count", 0),
            "route": new_state.get("next", ""),
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "events_applied": len(new_state.get("event_log", [])) - eventos_antes,
            "events_rejected": len(new_state.get("pending_world_events", []) or []),
            "error": None,
        }, ensure_ascii=False))
        return format_response(new_state)

    except Exception as e:
        _turn_logger.info(json.dumps({
            "evt": "turn", "game_id": state.get("game_id", "?"),
            "turn": (state.get("world") or {}).get("turn_count", 0),
            "route": state.get("next", ""),
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "events_applied": 0, "events_rejected": 0, "error": str(e)[:200],
        }, ensure_ascii=False))
        print(f"Erro na API: {e}")
        # Auditoria A6: str(e) fica no log JSON acima; cliente recebe genérico.
        raise HTTPException(status_code=500, detail="Erro interno ao processar o turno.")

@app.post("/game/equip")
def game_equip(req: EquipRequest):
    """Fase 4.3: equipar/desequipar — validação 100% Python (inventory.equip)."""
    import inventory as inv_mod
    file_to_load = _resolve_save_file(req.game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    _reject_memorial(state)

    if req.item_id:
        player, err = inv_mod.equip(state["player"], req.item_id)
    elif req.unequip_slot:
        player, err = inv_mod.unequip(state["player"], req.unequip_slot)
    else:
        raise HTTPException(status_code=400, detail="Informe item_id ou unequip_slot.")
    if err:
        raise HTTPException(status_code=400, detail=err)

    state["player"] = player
    save_game_state(state)
    import combat_mechanics as cm_mod
    stats = cm_mod.compute_player_combat_stats(player)
    return {"ok": True, "equipment": player.get("equipment"),
            "inventory": _inventory_block(player),
            "derived": {"ac": stats["ac"], "attack": stats["attack"]}}


@app.post("/game/levelup")
def game_levelup(req: LevelUpRequest):
    """Fase 4.1: aplica UMA escolha de level up (habilidade ou atributo).

    Validação 100% server-side (progression.apply_choice): escolha inexistente,
    habilidade inelegível (classe/nível/pré-requisito/ramo rival) ou atributo
    inválido → 400 e o save fica intocado."""
    file_to_load = _resolve_save_file(req.game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    _reject_memorial(state)

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
    # Auditoria A5: default local-only (API não tem auth até a Fase 10b).
    # Exponha na LAN conscientemente via RPG_HOST=0.0.0.0 no .env.
    uvicorn.run(app, host=os.getenv("RPG_HOST", "127.0.0.1"), port=8000)