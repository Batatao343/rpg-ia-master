"""
api.py
Interface REST API para o RPG Engine.
Atualizado para suportar Memória Híbrida (Game ID e Resumo).
Fase 10: game_id validado (UUID) na borda, CORS por env, rate limit mínimo,
log JSON por turno.
"""
import contextvars
import json
import logging
import queue
import sys
import os
import threading
import time
import uvicorn
import uuid # <--- Necessário para gerar IDs de sessão
from collections import Counter, defaultdict, deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Dict, Iterator, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
from main import app as game_graph
from persistence import save_game_state, load_game_state, save_path, _serialize_messages
from character_creator import create_player_character
from gamedata import ABILITIES, CLASSES, load_json_data, seed_factions
from llm_setup import is_simulated, set_llm_telemetry_hook
from playtest import pricing as llm_pricing
import progression
from services import quest_log
from services import state_views as sv
from services.chronicle import default_chapter_title
from services.discovery import player_codex
from services.prologue import StartScenarioIn, build_start_scenario, scenario_to_state_seed
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


# spec streaming-turno-sse (R5): telemetria de LLM em PRODUÇÃO — o hook do
# roteamento acumula os invokes do turno corrente num ContextVar (cada request
# síncrono roda numa thread com contexto próprio; zero vazamento entre turnos).
# Dev-only: os campos vão no log `rpg.turn`, NUNCA no GameResponse.
_llm_turn_events: contextvars.ContextVar = contextvars.ContextVar(
    "rpg_llm_turn_events", default=None)


def _telemetry_hook(provider: str, model: str, tier, latency_ms: int,
                    fell_back: bool) -> None:
    acc = _llm_turn_events.get()
    if acc is not None:
        acc.append({"provider": provider, "model": model,
                    "tier": getattr(tier, "value", str(tier)),
                    "latency_ms": int(latency_ms), "fell_back": bool(fell_back)})


set_llm_telemetry_hook(_telemetry_hook)


def _llm_log_fields(events: Optional[List[dict]]) -> Dict[str, Any]:
    events = events or []
    return {
        "llm_calls": len(events),
        "llm_providers": dict(Counter(e.get("provider") or "?" for e in events)),
        "fell_back": any(e.get("fell_back") for e in events),
        "cost_usd_est": round(llm_pricing.turn_cost(events), 6),
    }


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


def _reject_archived(state: dict) -> None:
    """spec conflito-01 R10: save anterior à migração de Virtudes/Vitalidade é
    ÓRFÃO. Somente-leitura — nenhuma ação o toca (409, nunca 500)."""
    if state.get("archived"):
        raise HTTPException(
            status_code=409,
            detail=state.get("archived_reason")
            or "Personagem arquivado por migração de sistema — comece uma nova jornada.")


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
    if limit > 0 and (request.url.path in ("/game/action", "/game/action/stream",
                                           "/game/new", "/game/equip", "/game/levelup",
                                           # spec inicio-personalizado (R11): 1 SMART por chamada
                                           "/game/prologue")
                      # spec polish-sessao (R2): DELETE de save também é mutação
                      or (request.method == "DELETE"
                          and request.url.path.startswith("/game/save/"))):
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
    # spec inicio-personalizado (R4): cenário aprovado no passo de prólogo.
    # StartScenarioIn re-valida na borda (limites de campo, beats ≤ 5, npcs ≤ 2
    # → excedente = 422). None = fluxo clássico, byte a byte o atual (R6).
    scenario: Optional[StartScenarioIn] = None

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
    """Fase 4.1 + spec conflito-01: consome UMA pending_choice. kind=ability ->
    ability_id; kind=virtude -> virtude (mente/agilidade/forca/carisma/corpo;
    `attr` segue aceito como alias legado)."""
    choice_id: str
    ability_id: Optional[str] = None
    virtude: Optional[str] = None
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
    death_pending: bool = False # spec checkpoints-morte: queda letal — abre a tela de morte no cliente

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
            # spec refatoracao-sistema-classes (R11): Entropia (barra) + Carga do
            # Abismo (chip por patamar). Médico é oculto (abyss.hidden) → label vago.
            "entropy": state["player"].get("entropy", 0),
            "max_entropy": state["player"].get("max_entropy", 0),
            "abyss_charge": state["player"].get("abyss_charge", 0),
            "abyss_tier": _abyss_tier_view(state["player"]),
            "defense": state["player"].get("defense", 0),
            "gold": state["player"].get("gold", 0),
            "level": state["player"].get("level", 1),
            "xp": state["player"].get("xp", 0),
            # Fase 4.1: ids canônicos + nome exibível (frontend não mostra id cru)
            # spec arvores-habilidade-classes (R10): kind distingue passiva/utilitária
            "abilities": [
                {"id": aid, "name": ABILITIES.get(aid, {}).get("name", aid),
                 "branch": ABILITIES.get(aid, {}).get("branch"),
                 "kind": ABILITIES.get(aid, {}).get("ability_kind", "active")}
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
                          state.get("event_log", []) or [], state.get("player", {}) or {}),
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
        death_pending=bool(state.get("death_pending", False)),
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


def _abyss_tier_view(player: dict) -> str:
    """spec refatoracao-sistema-classes (R11): patamar da Carga do Abismo p/ o HUD.
    Classe com `abyss.hidden` (Médico — Recidiva) NÃO expõe o valor: label enigmático."""
    import combat_mechanics as _cm
    cfg = _cm.entropy_config(player)
    if (cfg.get("abyss") or {}).get("hidden"):
        return "?"
    return _cm.abyss_tier(player)


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
            # spec arvores-habilidade-classes (R10): o wizard de level up mostra
            # o tipo (ativa/passiva/utilitária) antes da escolha
            "kind": a.get("ability_kind", "active"),
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

    import combat_mechanics as cm_mod
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
        # spec polish-sessao (R4): chips 100% mecânicos derivados da ficha
        "suggestions": cm_mod.combat_suggestions(player, enemies, meta),
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


def _world_block(w: dict, projection: Optional[dict] = None, event_log: Optional[list] = None,
                 player: Optional[dict] = None) -> Dict[str, Any]:
    clock = w.get("world_clock") or {}
    turn = w.get("turn_count", 0)
    # spec itens-vivos-e-luz (R7): estado de luz p/ o HUD (precisa do player p/
    # saber se ele carrega uma fonte de luz).
    from world_utils import light_level
    light = light_level(w, player or {})
    return {
        "location": w.get("current_location", ""),
        "location_id": w.get("current_location_id", ""),
        "day": clock.get("day", 1),
        "period": clock.get("period", "Amanhecer"),
        "visited": w.get("visited", []),
        "danger": w.get("danger_level", 1),
        "weather": w.get("weather", ""),  # Fase 6.5: rótulo do clima atual
        "light": {"dark": light["dark"], "lit": light["lit"], "label": light["label"]},
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

@app.get("/data/onboarding")
def get_onboarding():
    """Spec onboarding-valoria (R4): lore curado do wizard de criação.

    Conteúdo estático de data/onboarding.json — zero LLM, zero RAG.
    """
    data = load_json_data("onboarding.json")
    if not data:
        raise HTTPException(status_code=404,
                            detail="Conteúdo de onboarding indisponível.")
    return data

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

@app.post("/game/prologue")
def game_prologue(req: CreateCharacterRequest):
    """spec inicio-personalizado (R1): gera o cenário de abertura a partir da
    ficha + descrição livre. 1 chamada SMART; guard de FallbackLLM devolve
    template determinístico — nunca 500. Stateless: o cenário vive no client
    entre preview e confirm."""
    char_input = {
        "name": req.name,
        "class_name": req.class_name,
        "race": req.race,
        "region": req.region,
        "backstory": req.backstory,
        "level": req.level,
    }
    scenario, mock = build_start_scenario(char_input)
    return {"scenario": scenario.model_dump(), "mock": mock}


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
            # spec refatoracao-sistema-classes: Entropia é o pool das 5 classes.
            "entropy": final_char.get("entropy", 0),
            "max_entropy": final_char.get("max_entropy", 0),
            "abyss_charge": final_char.get("abyss_charge", 0),
            "gold": 50 * req.level,
            "alignment": "Neutro",
            # spec conflito-01: 5 Virtudes + Vitalidade/Ferimentos (mana/stamina/attributes saíram)
            "virtudes": final_char["virtudes"],
            "vitalidade": final_char.get("vitalidade", final_char.get("max_vitalidade", final_char["max_hp"])),
            "max_vitalidade": final_char.get("max_vitalidade", final_char["max_hp"]),
            "ferimento_espacos": final_char.get("ferimento_espacos", {}),
            "ferimentos": final_char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
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

    # spec inicio-personalizado (R5): cenário aprovado semeia plano pessoal,
    # capítulo 1, NPCs da história e a cena de abertura. Sem scenario, o
    # estado acima fica intocado (R6 — fluxo clássico byte a byte).
    if req.scenario is not None:
        seed = scenario_to_state_seed(
            req.scenario,
            {**char_input, "game_id": new_game_id},
            start_loc_id=initial_state["world"].get("current_location_id", ""),
        )
        initial_state["campaign_plan"] = seed["campaign_plan"]
        initial_state["chronicle"][0]["title"] = seed["chronicle_title"]
        initial_state["npcs"] = seed["npcs"]
        initial_state["messages"][-1] = HumanMessage(content=seed["opening_message"])
        initial_state["narrative_summary"] += seed["summary_extra"]

    # 3. Roda o Grafo
    try:
        final_state = game_graph.invoke(initial_state)
        save_game_state(final_state)
        # spec checkpoints-morte (D7): checkpoint INICIAL = início da sessão. Garante
        # que a morte sempre tem para onde restaurar, mesmo antes do 1º checkpoint de cadência.
        from persistence import save_checkpoint
        save_checkpoint(final_state)
        return format_response(final_state)
    except Exception as e:
        # Auditoria A6: detalhe interno só no log do servidor, nunca na resposta.
        print(f"Erro ao criar jogo: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar o jogo.")

def _append_player_input(state: dict, input_text: str) -> None:
    """Anexa a ação do jogador ao histórico (mesma regra dos dois endpoints)."""
    state["messages"].append(HumanMessage(content=input_text))
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]


def _log_turn(state: dict, t0: float, eventos_antes: int, error: Optional[str],
              llm_events: Optional[List[dict]] = None) -> None:
    _turn_logger.info(json.dumps({
        "evt": "turn",
        "game_id": state.get("game_id", "?"),
        "turn": (state.get("world") or {}).get("turn_count", 0),
        "route": state.get("next", ""),
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "events_applied": (len(state.get("event_log", [])) - eventos_antes) if not error else 0,
        "events_rejected": len(state.get("pending_world_events", []) or []) if not error else 0,
        "error": error,
        **_llm_log_fields(llm_events),
    }, ensure_ascii=False))


def _run_turn(state: dict, input_text: str) -> GameResponse:
    """Miolo do turno (spec streaming-turno-sse R2): grafo + save + log.
    Compartilhado pelo POST clássico e pelo stream — carga/validações ficam
    nos endpoints. Levanta HTTPException(500) genérica em falha (A6)."""
    _append_player_input(state, input_text)
    t0 = time.monotonic()
    eventos_antes = len(state.get("event_log", []))
    acc_token = _llm_turn_events.set([])
    try:
        new_state = game_graph.invoke(state)
        save_game_state(new_state)
        # spec checkpoints-morte (D1): grava checkpoint na cadência (10 turnos /
        # zona segura). `state` = estado ANTES do turno → detecta entrada em zona segura.
        from services import checkpoints as _cp
        _cp.maybe_write(new_state, prev=state)
        _log_turn(new_state, t0, eventos_antes, None, _llm_turn_events.get())
        return format_response(new_state)
    except Exception as e:
        _log_turn(state, t0, eventos_antes, str(e)[:200], _llm_turn_events.get())
        print(f"Erro na API: {e}")
        # Auditoria A6: str(e) fica no log JSON acima; cliente recebe genérico.
        raise HTTPException(status_code=500, detail="Erro interno ao processar o turno.")
    finally:
        _llm_turn_events.reset(acc_token)


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
    # spec conflito-01: save pré-Virtudes é órfão — só leitura.
    _reject_archived(state)
    # spec checkpoints-morte: queda letal pendente — o jogador precisa resolver a
    # TELA DE MORTE (POST /game/death) antes de agir de novo.
    if state.get("death_pending"):
        raise HTTPException(status_code=409,
                            detail="Você tombou. Escolha continuar do checkpoint ou aceitar o fim.")

    return _run_turn(state, req.input_text)


class DeathChoiceRequest(BaseModel):
    game_id: Optional[str] = None
    choice: str = Field(pattern="^(continue|accept)$")  # Continuar do checkpoint / Aceitar o fim


@app.post("/game/death", response_model=GameResponse)
def game_death(req: DeathChoiceRequest):
    """spec checkpoints-morte (D2): resolve a tela de morte.
    - `continue` → restaura do checkpoint (ou do início da sessão, D7); a saga segue.
    - `accept`   → memorial (game_over): a crônica encerra por escolha do jogador."""
    file_to_load = _resolve_save_file(req.game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if not state.get("death_pending"):
        raise HTTPException(status_code=409, detail="Nenhuma queda pendente para resolver.")
    from services import checkpoints as _cp
    new_state = _cp.resolve_death_choice(state, req.choice)
    save_game_state(new_state)
    return format_response(new_state)


# --- STREAMING DO TURNO (spec streaming-turno-sse) ---------------------------

_MEMORIAL_DETAIL = ("Esta saga terminou. A crônica permanece como memorial — "
                    "comece uma nova jornada.")
_SSE_PING_S = 10.0
_NARRATIVE_CHUNK = 80


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_turn(state: dict, input_text: str) -> Iterator[str]:
    """Gerador SSE do turno (R1): accepted → phase/route → narrative → state.
    Mesmo estado/save/log do POST clássico (R2/R3). Roda o grafo numa thread
    própria para intercalar keepalive `: ping` a cada 10s."""
    yield _sse("accepted", {"game_id": state.get("game_id", "?")})
    if state.get("game_over"):
        # R3: memorial — evento `error` com 409 semântico e fecha o stream.
        yield _sse("error", {"detail": _MEMORIAL_DETAIL, "code": 409})
        return
    if state.get("archived"):
        # spec conflito-01: save pré-Virtudes é órfão — só leitura.
        yield _sse("error", {"detail": state.get("archived_reason") or _MEMORIAL_DETAIL, "code": 409})
        return
    # spec checkpoints-morte: queda pendente — cliente deve chamar /game/death.
    if state.get("death_pending"):
        yield _sse("error", {"detail": "Você tombou. Resolva a tela de morte.", "code": 409})
        return

    _append_player_input(state, input_text)
    t0 = time.monotonic()
    eventos_antes = len(state.get("event_log", []))
    q: "queue.Queue" = queue.Queue()
    llm_acc: List[dict] = []

    def _worker():
        _llm_turn_events.set(llm_acc)  # contexto próprio da thread do grafo
        try:
            for chunk in game_graph.stream(state, stream_mode=["updates", "values"]):
                q.put(("chunk", chunk))
            q.put(("done", None))
        except Exception as e:  # noqa: BLE001
            q.put(("exc", e))

    threading.Thread(target=_worker, daemon=True).start()

    final_state: Optional[dict] = None
    try:
        while True:
            try:
                kind, payload = q.get(timeout=_SSE_PING_S)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            if kind == "exc":
                raise payload
            if kind == "done":
                break
            mode, data = payload
            if mode == "updates":
                for node, upd in (data or {}).items():
                    yield _sse("phase", {"node": node, "status": "done"})
                    if node == "dm_router":
                        yield _sse("route", {"route": (upd or {}).get("next", "") or ""})
            elif mode == "values":
                final_state = data

        if final_state is None:
            raise RuntimeError("stream não produziu estado final")
        save_game_state(final_state)
        from services import checkpoints as _cp
        _cp.maybe_write(final_state, prev=state)  # spec checkpoints-morte (D1)
        _log_turn(final_state, t0, eventos_antes, None, llm_acc)
        resp = format_response(final_state)
        narrative = resp.message or ""
        for i in range(0, len(narrative), _NARRATIVE_CHUNK):
            yield _sse("narrative", {"chunk": narrative[i:i + _NARRATIVE_CHUNK],
                                     "done": False})
        yield _sse("narrative", {"chunk": "", "done": True})
        yield _sse("state", json.loads(resp.model_dump_json()))
    except Exception as e:  # noqa: BLE001
        _log_turn(state, t0, eventos_antes, str(e)[:200], llm_acc)
        print(f"Erro no stream: {e}")
        # A6: detalhe fica no log; o cliente recebe genérico e cai no POST clássico.
        yield _sse("error", {"detail": "Erro interno ao processar o turno."})


@app.post("/game/action/stream")
def game_action_stream(req: ActionRequest):
    """R1: mesmo corpo do /game/action, resposta text/event-stream com fases
    reais do grafo. Guard-rails (rate limit via middleware, game_id, memorial,
    teto de input) valem aqui também (R3)."""
    file_to_load = _resolve_save_file(req.game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    return StreamingResponse(_stream_turn(state, req.input_text),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

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
        ability_id=req.ability_id, virtude=req.virtude, attr=req.attr)
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
            "virtudes": player.get("virtudes", {}),
            "abilities": [
                {"id": aid, "name": ABILITIES.get(aid, {}).get("name", aid),
                 "branch": ABILITIES.get(aid, {}).get("branch")}
                for aid in (player.get("known_abilities", []) or [])
            ],
            "pending_choices": player.get("pending_choices", []) or [],
            "level_up": _levelup_block(player),
        },
    }


# --- SAVES E CRÔNICA (spec polish-sessao) ------------------------------------

class SaveSummary(BaseModel):
    game_id: str
    name: str
    class_name: str
    level: int
    location: str
    day: int
    game_over: bool
    updated_at: float  # epoch (mtime)


@app.get("/game/saves", response_model=List[SaveSummary])
def get_saves():
    """R1: lista as campanhas salvas (mtime desc; corrompido é pulado)."""
    import persistence as persistence_mod
    return persistence_mod.list_saves()


@app.delete("/game/save/{game_id}")
def delete_save_endpoint(game_id: str):
    """R2: exclui save + memória da sessão. Confirmação é da UI (uso local)."""
    import persistence as persistence_mod
    try:
        removed = persistence_mod.delete_save(game_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="game_id inválido (esperado UUID).")
    if not removed:
        raise HTTPException(status_code=404, detail="Save não encontrado.")
    return {"ok": True}


@app.get("/game/chronicle/export")
def export_chronicle(game_id: Optional[str] = None):
    """R5: crônica como .txt (download) com separadores por capítulo."""
    from fastapi.responses import PlainTextResponse
    file_to_load = _resolve_save_file(game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")

    player = state.get("player") or {}
    lines: List[str] = [f"CRÔNICA DE {player.get('name', 'HERÓI').upper()}",
                        f"{player.get('class_name', '')} — {state.get('world', {}).get('current_location', '')}",
                        ""]
    for cap in state.get("chronicle") or []:
        if not isinstance(cap, dict):
            continue
        lines.append("=" * 60)
        lines.append(f"{cap.get('title', '')}  (turno {cap.get('started_turn', 0)}"
                     f" — {cap.get('location', '')})")
        lines.append("=" * 60)
        for e in cap.get("entries") or []:
            if isinstance(e, dict) and str(e.get("text", "")).strip():
                marker = "•" if e.get("kind") == "milestone" else "—"
                lines.append(f"{marker} [t{e.get('turn', 0)}] {e['text']}")
        lines.append("")
    hero = "".join(c for c in player.get("name", "cronica") if c.isalnum()) or "cronica"
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": f'attachment; filename="cronica_{hero}.txt"'})


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