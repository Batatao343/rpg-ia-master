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
from copy import deepcopy
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, Iterator, List, Literal, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
from main import app as game_graph
import gamedata
from persistence import save_game_state, load_game_state, save_path, _serialize_messages
from character_creator import create_player_character
from gamedata import CLASSES, load_json_data, seed_factions
from llm_setup import (
    LLMAttemptEvent,
    is_simulated,
    set_llm_attempt_telemetry_hook,
    set_llm_telemetry_hook,
)
from playtest import pricing as llm_pricing
import progression
from services import quest_log
from services import state_views as sv
from services.chronicle import default_chapter_title
from services.discovery import player_codex
from services.prologue import StartScenarioIn, build_start_scenario, scenario_to_state_seed
from services.visual_catalog import (
    creation_visuals,
    resolve_turn_visual_state,
    visual_response,
)
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
_llm_attempt_events: contextvars.ContextVar = contextvars.ContextVar(
    "rpg_llm_attempt_events", default=None)

# Hardening 2026-08-11: mutações do mesmo save são serializadas no processo.
# A Fase 10b substituirá isto por transação/lock distribuído no storage.
_game_locks: Dict[str, threading.RLock] = {}
_game_locks_guard = threading.Lock()


def _game_lock(game_id: Optional[str]) -> threading.RLock:
    key = str(game_id or "__latest__")
    with _game_locks_guard:
        return _game_locks.setdefault(key, threading.RLock())


def _telemetry_hook(provider: str, model: str, tier, latency_ms: int,
                    fell_back: bool) -> None:
    acc = _llm_turn_events.get()
    if acc is not None:
        acc.append({"provider": provider, "model": model,
                    "tier": getattr(tier, "value", str(tier)),
                    "latency_ms": int(latency_ms), "fell_back": bool(fell_back)})


set_llm_telemetry_hook(_telemetry_hook)


def _attempt_telemetry_hook(event: LLMAttemptEvent) -> None:
    acc = _llm_attempt_events.get()
    if acc is not None:
        network_attempted = event.outcome not in {"build_error", "circuit_open"}
        acc.append({
            "provider": event.provider,
            "model": event.model,
            "tier": getattr(event.tier, "value", str(event.tier)),
            "attempt_index": int(event.attempt_index),
            "latency_ms": int(event.latency_ms),
            "fell_back": bool(event.fell_back),
            "outcome": event.outcome,
            "error": event.error,
            "structured": bool(event.structured),
            "network_attempted": network_attempted,
        })


set_llm_attempt_telemetry_hook(_attempt_telemetry_hook)


def _llm_log_fields(events: Optional[List[dict]],
                    attempts: Optional[List[dict]] = None) -> Dict[str, Any]:
    events = events or []
    attempts = attempts or []
    network_attempts = [
        event for event in attempts
        if event.get("network_attempted",
                     event.get("outcome") not in {"build_error", "circuit_open"})]
    skipped = [event for event in attempts if event not in network_attempts]
    cost_events = network_attempts or events
    return {
        "llm_calls": len(events),
        "llm_requests": len(network_attempts) if attempts else len(events),
        "llm_attempts": len(attempts),
        "llm_failures": sum(
            1 for event in network_attempts if event.get("outcome") != "success"),
        "llm_skipped": len(skipped),
        "llm_attempt_outcomes": dict(Counter(
            event.get("outcome") or "?" for event in attempts)),
        "llm_providers": dict(Counter(e.get("provider") or "?" for e in events)),
        "fell_back": any(e.get("fell_back") for e in events),
        "cost_usd_est": round(llm_pricing.turn_cost(cost_events), 6),
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
                                           "/game/new", "/game/combat-simulator",
                                           "/game/equip", "/game/levelup",
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

    @field_validator("class_name")
    @classmethod
    def _canonical_class(cls, value: str) -> str:
        if value not in gamedata.CLASSES:
            raise ValueError("classe desconhecida")
        return value

    @field_validator("race")
    @classmethod
    def _canonical_race(cls, value: str) -> str:
        names = {str(row.get("name")) for row in
                 (load_json_data("origins.json") or {}).get("races", [])}
        if value not in names:
            raise ValueError("raça desconhecida")
        return value

    @field_validator("region")
    @classmethod
    def _canonical_region(cls, value: str) -> str:
        names = {str(row.get("name")) for row in
                 (load_json_data("origins.json") or {}).get("regions", [])}
        if value not in names:
            raise ValueError("região desconhecida")
        return value

class ActionRequest(BaseModel):
    # Auditoria A7: ação vira prompt — sem teto, request gigante = custo/latência.
    input_text: str = Field(max_length=2000)
    game_id: Optional[str] = None # Opcional: permite especificar qual save carregar
    action_id: Optional[str] = Field(default=None, max_length=36)
    # conflito-16: seleção tática canônica da UI; o motor revalida tudo.
    card_id: Optional[str] = Field(default=None, max_length=128)
    target_id: Optional[str] = Field(default=None, max_length=128)
    ruptura: bool = False
    reaction_card_id: Optional[str] = Field(default=None, max_length=128)
    # Laboratório/UI tática: ações fechadas evitam parse LLM de chips mecânicos.
    action_kind: Optional[Literal["attack", "maneuver", "pass", "flee"]] = None
    maneuver: Optional[Literal[
        "engajar", "desengajar", "guardar", "esconder", "procurar"
    ]] = None

    @field_validator("action_id")
    @classmethod
    def _canonical_action_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            return str(uuid.UUID(value))
        except (ValueError, TypeError):
            raise ValueError("action_id inválido (esperado UUID)")


class CombatSimulatorRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=40)
    level: Literal[1, 3, 5, 10] = 1
    enemy_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(default=1, ge=1, le=3)

    @field_validator("class_name")
    @classmethod
    def _known_class(cls, value: str) -> str:
        if value not in gamedata.CLASSES:
            raise ValueError("classe desconhecida")
        return value

    @field_validator("enemy_id")
    @classmethod
    def _known_enemy(cls, value: str) -> str:
        if value not in gamedata.BESTIARY:
            raise ValueError("inimigo desconhecido")
        return value

class EquipRequest(BaseModel):
    """Fase 4.3: equipa item do inventário (slot deduzido do tipo) ou desequipa slot."""
    item_id: Optional[str] = None   # equipar este item
    unequip_slot: Optional[str] = None  # OU esvaziar este slot
    game_id: Optional[str] = None

class LevelUpRequest(BaseModel):
    """Conflito v2: consome escolha de Carta/evolução ou de Virtude."""
    choice_id: str
    card_id: Optional[str] = None
    evolve_card_id: Optional[str] = None
    caminho: Optional[str] = None
    virtude: Optional[str] = None
    attr: Optional[str] = None
    game_id: Optional[str] = None


class VisualVariantResponse(BaseModel):
    url: str
    width: int
    height: int
    bytes: int
    sha256: str


class VisualVariantsResponse(BaseModel):
    thumbnail: VisualVariantResponse
    display: VisualVariantResponse


class VisualAssetResponse(BaseModel):
    asset_id: str
    subject_type: Literal["race", "class", "location", "npc"]
    subject_id: str
    title: str
    alt: str
    placeholder_color: str
    variants: VisualVariantsResponse


class SceneVisualResponse(BaseModel):
    location_id: str
    location_name: str
    scope: Literal["exact", "regional", "placeholder"]
    asset: Optional[VisualAssetResponse] = None


class VisualCueResponse(BaseModel):
    kind: Literal["npc_first_appearance"]
    subject_id: str
    subject_name: str
    caption: str
    asset: Optional[VisualAssetResponse] = None
    fallback: bool


class VisualResponse(BaseModel):
    scene: SceneVisualResponse
    cue: Optional[VisualCueResponse] = None

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
    game_over: bool = False     # memorial/bloqueio definitivo; Vitalidade 0 não basta
    death: Dict[str, Any] = {}  # conflito-16: Última Ação/Terminal/estabilização
    combat_simulation: Dict[str, Any] = {}
    visual: VisualResponse

# --- HELPER: FORMATA RESPOSTA ---
def format_response(state: dict, *, cue_action_key: Optional[str] = None) -> GameResponse:
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

    player = state["player"]
    vitality = int(player.get("vitalidade", 0) or 0)
    max_vitality = int(player.get("max_vitalidade", vitality) or vitality)
    simulation = dict(state.get("combat_simulation") or {})
    if simulation.get("enabled"):
        active = bool((state.get("combat") or {}).get("active"))
        simulation["finished"] = not active
        simulation["outcome"] = (
            "defeat" if state.get("death_pending") else
            "victory" if not active else None
        )
    return GameResponse(
        game_id=state.get("game_id", "unknown"),
        message=last_content,
        message_type=msg_type,
        player_stats={
            "name": player.get("name", "Herói"),
            "class_name": player.get("class_name") or player.get("class", ""),
            "race": player.get("race", ""),
            "vitalidade": vitality,
            "max_vitalidade": max_vitality,
            "ferimentos": player.get("ferimentos", {}),
            "dead": bool(player.get("dead")),
            "estado_terminal": bool(player.get("estado_terminal")),
            # aliases públicos derivados — nunca lidos de volta como mecânica
            "hp": vitality,
            "max_hp": max_vitality,
            "mana": player.get("mana", 0),
            "max_mana": player.get("max_mana", 0),
            "stamina": player.get("stamina", 0),
            "max_stamina": player.get("max_stamina", 0),
            # spec refatoracao-sistema-classes (R11): Entropia (barra) + Carga do
            # Abismo (chip por patamar). Médico é oculto (abyss.hidden) → label vago.
            "entropy": player.get("entropy", 0),
            "max_entropy": player.get("max_entropy", 0),
            "abyss_charge": player.get("abyss_charge", 0),
            "abyss_tier": _abyss_tier_view(player),
            "defense": player.get("defense", 0),
            "gold": player.get("gold", 0),
            "level": player.get("level", 1),
            "xp": player.get("xp", 0),
            "cards": _cards_block(player),
            "virtudes": dict(player.get("virtudes") or {}),
            "xp_next_level": progression.xp_to_next(int(player.get("level", 1) or 1)),
            "pending_choices": player.get("pending_choices", []) or [],
            "level_up": _levelup_block(player),
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
        party=[{"name": c.get("name", "?"),
                "vitalidade": int(c.get("vitalidade", 0) or 0),
                "max_vitalidade": int(c.get("max_vitalidade", 1) or 1),
                "hp": int(c.get("vitalidade", 0) or 0),
                "max_hp": int(c.get("max_vitalidade", 1) or 1),
                "active": bool(c.get("active")),
                "archetype": c.get("archetype", ""), "status": c.get("status", "ativo")}
               for c in (state.get("party") or []) if isinstance(c, dict)],
        factions=_factions_block(state.get("factions", []) or [],
                                 state.get("faction_intel", {}) or {},
                                 (state.get("world", {}) or {}).get("turn_count", 0),
                                 state.get("event_log", []) or [],
                                 state.get("world_projection", {}) or {}),
        death_pending=bool(state.get("death_pending", False)),
        game_over=bool(state.get("game_over", False)),
        death=_death_block(state),
        combat_simulation=simulation,
        visual=visual_response(state, cue_action_key=cue_action_key),
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


def _cards_block(player: dict, *, prepared_only: bool = False) -> List[Dict[str, Any]]:
    """View autoral + disponibilidade mecânica das Cartas.

    O frontend nunca tenta reproduzir frequência/custo por conta própria: recebe
    o contador já interpretado, mas o motor ainda revalida no uso.
    """
    from services import cards
    import combat_mechanics as cm
    prepared = set(player.get("prepared_cards") or [])
    evolved = player.get("evolved_cards") or {}
    entropy = int(player.get("entropy", 0) or 0)
    out = []
    for cid in player.get("known_cards") or []:
        card = cards.get_card(cid) or {}
        is_prepared = cid in prepared
        if prepared_only and not is_prepared:
            continue
        frequency = str(card.get("frequencia", "livre"))
        counter = cards.FREQ_COUNTER.get(frequency)
        usage = ((player.get("card_usage") or {}).get(cid) or {})
        spent = bool(counter and int(usage.get(counter, 0) or 0) >= 1)
        base_cost = int(card.get("custo_entropia", 0) or 0)
        cost = cm.dependencia_cost(player, base_cost)
        kind = str(card.get("tipo", ""))
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        friendly = effect_kind in {
            "cura", "estabilizar", "protecao", "reposicionar", "esconder",
            "purga_condicao", "vantagem", "buff_defesa", "buff_acerto",
            "buff_dano", "reduzir_carga_aliado",
        }
        ready = bool(
            is_prepared and kind in ("ativa", "reacao") and not spent
            and cost <= entropy
        )
        out.append({
            "id": cid, "name": card.get("name", cid), "type": kind,
            "description": card.get("descricao", ""),
            "effect_kind": effect_kind,
            "target_kind": "self" if friendly else "enemy",
            "subclass": card.get("subclasse", ""), "prepared": is_prepared,
            "cost": cost,
            "base_cost": base_cost,
            "frequency": frequency,
            "spent": spent,
            "ready": ready,
            "has_rupture": bool(card.get("ruptura")),
            "rupture_ready": bool(ready and kind == "ativa" and card.get("ruptura")),
            "trigger": card.get("gatilho", ""),
            "evolved": evolved.get(cid),
        })
    return out


def _death_block(state: dict) -> Dict[str, Any]:
    player = state.get("player") or {}
    combat = state.get("combat") or {}
    context = combat.get("death_context") or {}
    last_action = context.get("last_action") or combat.get("last_player_action")
    last_action_label = ""
    if isinstance(last_action, dict) and last_action.get("kind") == "card":
        from services import cards
        card = cards.get_card(str(last_action.get("card_id") or "")) or {}
        last_action_label = str(card.get("name") or last_action.get("card_id") or "")
    return {
        "pending": bool(state.get("death_pending")),
        "last_action": last_action,
        "last_action_label": last_action_label,
        "entered_terminal": bool(
            context.get("entered_terminal") or player.get("estado_terminal")
        ),
        "stabilization": context.get("stabilization", ""),
        "stabilization_attempts": int(
            context.get("stabilization_attempts",
                        player.get("stabilization_attempts", 0)) or 0
        ),
        "killer": context.get("killer", ""),
    }


def _levelup_block(player: dict) -> Dict[str, Any]:
    """Escolhas pendentes + Cartas elegíveis/evoluções."""
    pending = player.get("pending_choices", []) or []
    if not pending:
        return {}
    from services import cards
    eligible = []
    for cid in progression.eligible_cards(player):
        card = cards.get_card(cid) or {}
        eligible.append({
            "id": cid, "name": card.get("name", cid),
            "description": card.get("descricao", ""),
            "subclass": card.get("subclasse", ""), "tier": card.get("patamar", ""),
            "cost": int(card.get("custo_entropia", 0) or 0),
            "frequency": card.get("frequencia", "livre"),
            "kind": card.get("tipo", "ativa"),
        })
    evolvable = [
        {"id": cid, "name": (cards.get_card(cid) or {}).get("name", cid)}
        for cid in player.get("known_cards") or []
        if (cards.get_card(cid) or {}).get("evolucao")
        and cid not in (player.get("evolved_cards") or {})
        and int(player.get("level", 1) or 1) >= 4
    ]
    return {
        "pending": pending,
        "eligible": eligible,
        "evolvable": evolvable,
        "current_branch": progression.player_branch(player),
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
    """View tática pública do conflito, sem vazar ficha secreta de inimigo."""
    meta = state.get("combat") or {}
    enemies = state.get("enemies") or []
    player = state.get("player") or {}
    alive = [e for e in enemies if not e.get("dead")
             and e.get("status", "ativo") not in ("morto", "fugiu", "rendido")]

    def _conds(entity):
        return [{"name": c.get("name", ""), "dot": c.get("dot", 0), "duration": c.get("duration", 0)}
                for c in (entity.get("active_conditions") or []) if isinstance(c, dict)]

    from services import bestiary_knowledge as knowledge
    from services import cards
    initiative = list(meta.get("initiative") or [])
    scene = meta.get("scene") or {}
    participant_names = {"player": player.get("name", "Protagonista")}
    for entity in list(enemies) + list(state.get("party") or []) + list(meta.get("scene_allies") or []):
        if isinstance(entity, dict):
            participant_names[str(entity.get("id") or entity.get("name"))] = entity.get("name", "?")

    scene_view = {"zones": [], "positions": []}
    scene_view["zones"] = [
        {"id": z.get("id", ""), "name": z.get("name", ""),
         "connections": list(z.get("connections") or [])}
        for z in (scene.get("zones") or []) if isinstance(z, dict)
    ]
    for participant_id, pos in (scene.get("positions") or {}).items():
        if not isinstance(pos, dict):
            continue
        posture = pos.get("postura") or {}
        engaged = [str(value) for value in (pos.get("engaged_with") or [])]
        scene_view["positions"].append({
            "participant_id": str(participant_id),
            "participant_name": participant_names.get(str(participant_id), str(participant_id)),
            "zone_id": pos.get("zone_id", ""),
            "distance": pos.get("distance_state", "proximo"),
            "posture": posture.get("state", "neutro") if isinstance(posture, dict) else str(posture),
            "concealment": pos.get("ocultacao", "visivel"),
            "engaged_with": engaged,
            "engaged_names": [participant_names.get(value, value) for value in engaged],
        })

    enemy_views = []
    for enemy in alive:
        public = knowledge.public_panel(enemy)
        revealed_cards = []
        for card_id in enemy.get("revealed_cards") or []:
            card = cards.get_card(str(card_id)) or {}
            if card:
                revealed_cards.append({"id": str(card_id), "name": card.get("name", card_id)})
        vitality = int(public.get("vitalidade", enemy.get("vitalidade", 0)) or 0)
        max_vitality = int(public.get("max_vitalidade", enemy.get("max_vitalidade", 0)) or 0)
        enemy_views.append({
            "id": str(enemy.get("id") or enemy.get("name", "")),
            "name": enemy.get("name", ""),
            "vitalidade": vitality, "max_vitalidade": max_vitality,
            "hp": vitality, "max_hp": max_vitality,
            "esquiva": public.get("esquiva"), "protecao": public.get("protecao"),
            "integridade_atual": public.get("integridade_atual"),
            "integridade_max": public.get("integridade_max"),
            "recursos_visiveis": public.get("recursos_visiveis") or {},
            "conditions": _conds(enemy),
            "revealed_cards": revealed_cards,
            "revealed_resistances": list(enemy.get("revealed_resistances") or []),
        })

    chase = meta.get("chase") or {}
    chase_view = ({
        "track": chase.get("trilha", "pressionado"),
        "steps": ["pressionado", "afastado", "quase_livre", "escapou"],
        "escaped": bool(chase.get("escapou")), "caught": bool(chase.get("alcancado")),
        "pursuers": list(chase.get("perseguidores") or []),
        "last_roll": dict(chase.get("_last") or {}),
    } if chase else {})
    wounds = player.get("ferimentos") or {}
    return {
        "active": bool(meta.get("active")) and bool(alive),
        "round": meta.get("round", 0),
        # Compat temporária do HUD atual: iniciativa agora é POR LADO.
        "order": [{"name": "Heróis" if side == "heroes" else "Inimigos",
                   "side": "hero" if side == "heroes" else "enemy", "init": 0}
                  for side in initiative],
        "initiative": initiative,
        "enemies": enemy_views,
        "cards": _cards_block(player, prepared_only=True),
        "scene": scene_view,
        "wounds": {
            "vitality": int(player.get("vitalidade", 0) or 0),
            "max_vitality": int(player.get("max_vitalidade", 0) or 0),
            "slots": dict(player.get("ferimento_espacos") or {}),
            "by_severity": {
                severity: list(wounds.get(severity) or [])
                for severity in ("leve", "grave", "critico")
            },
        },
        "chase": chase_view,
        "player_conditions": _conds(player),
        "cooldowns": {},
        # Ponte até conflito-16: chips agora vêm das Cartas, não de habilidades d20.
        "suggestions": cards.combat_card_suggestions(player, enemies, meta),
        "last_player_action": meta.get("last_player_action"),
        "reactions": meta.get("last_reactions", []),
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
    from world_utils import light_level, weather_effects
    light = light_level(w, player or {})
    effective_weather = weather_effects(w)
    return {
        "location": w.get("current_location", ""),
        "location_id": w.get("current_location_id", ""),
        "day": clock.get("day", 1),
        "period": clock.get("period", "Amanhecer"),
        "visited": w.get("visited", []),
        "danger": w.get("danger_level", 1),
        "weather": effective_weather.get("label") or w.get("weather", ""),
        "weather_global": dict(w.get("weather_global") or {}),
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


def combat_simulator_options() -> Dict[str, Any]:
    """Catálogo público mínimo do laboratório, derivado dos dados canônicos."""
    allowed = {"lacaio", "padrao", "elite", "chefe", "nomeado"}
    enemies = []
    for enemy_id, raw in gamedata.BESTIARY.items():
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("categoria") or "padrao").strip().lower()
        if category not in allowed:
            continue
        enemies.append({
            "id": str(enemy_id),
            "name": str(raw.get("name") or enemy_id),
            "category": category,
            "regions": [str(region) for region in (raw.get("regions") or [])],
        })
    enemies.sort(key=lambda enemy: (
        {"lacaio": 0, "padrao": 1, "elite": 2, "nomeado": 3, "chefe": 4}[
            enemy["category"]
        ],
        enemy["name"].casefold(),
    ))
    return {
        "classes": list(gamedata.CLASSES),
        "levels": [1, 3, 5, 10],
        "quantities": [1, 2, 3],
        "enemies": enemies,
    }


def _build_combat_simulator_state(req: CombatSimulatorRequest) -> dict:
    """Cria arena isolada com fichas de produção e zero acesso a LLM/RAG."""
    from services import conflict_orchestrator as orchestrator
    from services import conflict_scene

    player = create_player_character({
        "name": "Combatente de Teste",
        "class_name": req.class_name,
        "race": "Humano",
        "region": "Nova Arcádia",
        "backstory": "Laboratório mecânico de combate.",
        "level": req.level,
    }, use_llm_flavor=False)
    player.update({
        "gold": 0,
        "alignment": "Neutro",
        "active_conditions": [],
        "dead": False,
        "estado_terminal": False,
        "last_stand_pending": False,
        "last_stand_resolved": False,
    })
    orchestrator.ensure_combat_sheet(player, is_player=True)

    template = gamedata.BESTIARY[req.enemy_id]
    enemies = []
    for index in range(1, req.quantity + 1):
        enemy = deepcopy(template)
        enemy["archetype_id"] = req.enemy_id
        enemy["id"] = f"{req.enemy_id}__sim_{index}"
        if req.quantity > 1:
            enemy["name"] = f"{template.get('name', req.enemy_id)} {index}"
        enemy.update({
            "status": "ativo", "dead": False, "fled": False,
            "surrendered": False, "conscious": True,
            "active_conditions": [],
            "ferimentos": {"leve": [], "grave": [], "critico": []},
        })
        enemy["vitalidade"] = int(enemy.get("max_vitalidade") or enemy.get("vitalidade") or 1)
        enemies.append(orchestrator.ensure_combat_sheet(enemy))

    scene = conflict_scene.new_scene([
        {"id": "arena", "name": "Arena do Véu", "connections": []},
    ])
    conflict_scene.place(scene, "player", zone_id="arena", distance_state="proximo")
    for enemy in enemies:
        conflict_scene.place(
            scene, enemy["id"], zone_id="arena", distance_state="proximo"
        )
    conflict_scene.freeze(scene)

    world = starting_world("Nova Arcádia", req.level)
    world["current_location"] = "Arena do Véu"
    category = str(template.get("categoria") or "padrao").lower()
    world["danger_level"] = {
        "lacaio": 1, "padrao": 2, "elite": 4, "nomeado": 5, "chefe": 6,
    }.get(category, 2)
    game_id = str(uuid.uuid4())
    enemy_label = str(template.get("name") or req.enemy_id)
    return {
        "game_id": game_id,
        "processed_action_ids": [],
        "visual_seen_entity_ids": [],
        "visual_cue_ledger": [],
        "narrative_summary": "Laboratório isolado de combate.",
        "archivist_last_run": 0,
        "archive_due": False,
        "chronicle": [],
        "combat_simulation": {
            "enabled": True,
            "enemy_id": req.enemy_id,
            "quantity": req.quantity,
        },
        "player": player,
        "world": world,
        "messages": [AIMessage(content=(
            f"⚔️ Laboratório iniciado: {req.class_name} nível {req.level} contra "
            f"{req.quantity}× {enemy_label}. Escolha uma Carta ou manobra."
        ))],
        "party": [],
        "enemies": enemies,
        "factions": [],
        "faction_intel": {},
        "bestiary_knowledge": {},
        "quests": [],
        "npcs": {},
        "campaign_plan": {
            "location": "Arena do Véu",
            "beats": [{"description": "Concluir o teste de combate.", "status": "pending"}],
            "climax": "Resultado do laboratório",
            "current_step": 0,
            "last_planned_turn": 0,
            "arc_title": "Laboratório de Combate",
        },
        "needs_replan": False,
        "next": "combat_agent",
        "combat_target": enemy_label,
        "loot_source": None,
        "combat": {
            "round": 0,
            "active": True,
            "scene": scene,
            "idle_turns": 0,
            "encounter_level": world["danger_level"],
        },
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
        "consumed_conflict_ids": [],
        "memory_facts": [],
        "pending_memory_facts": [],
        "memory_rejections": [],
        "memory_promotions": [],
        "pending_npc_memory": [],
        "narrative_rejections": [],
        "game_over": False,
        "death_pending": False,
    }


@app.get("/data/combat-simulator")
def get_combat_simulator_options():
    return combat_simulator_options()


@app.post("/game/combat-simulator", response_model=GameResponse)
def new_combat_simulator(req: CombatSimulatorRequest):
    state = _build_combat_simulator_state(req)
    if not save_game_state(state):
        raise HTTPException(status_code=500, detail="Não foi possível criar o laboratório.")
    return format_response(state)

@app.get("/data/options")
def get_creation_options():
    origins = load_json_data("origins.json")
    return {
        "races": [r["name"] for r in origins.get("races", [])],
        # Fase 2.5b: raças completas (desc + traits) p/ o frontend exibir na criação
        "races_full": origins.get("races", []),
        "classes": list(CLASSES.keys()),
        "regions": [r["name"] for r in origins.get("regions", [])],
        "visuals": creation_visuals(),
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
    import gamedata
    gamedata.sync_vitality(final_char)

    # Gera ID único
    new_game_id = str(uuid.uuid4())

    # 2. Monta Estado Inicial (COMPATÍVEL COM HYBRID MEMORY)
    initial_state = {
        # --- Campos Novos ---
        "game_id": new_game_id,
        "processed_action_ids": [],
        "visual_seen_entity_ids": [],
        "visual_cue_ledger": [],
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
            "vitalidade_max_penalty": final_char.get("vitalidade_max_penalty", 0),
            "ferimento_espacos": final_char.get("ferimento_espacos", {}),
            "ferimentos": final_char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
            "inventory": final_char["inventory"],
            # Fase 4.3: slots do creator (auto-equip) — sem isto o HUD nasce sem arma
            "equipment": final_char.get("equipment",
                                        {"weapon": None, "armor": None, "accessory": None}),
            "known_cards": final_char.get("known_cards", []),
            "prepared_cards": final_char.get("prepared_cards", []),
            "card_usage": final_char.get("card_usage", {}),
            "virtue_cards": final_char.get("virtue_cards", []),
            "evolved_cards": final_char.get("evolved_cards", {}),
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
        "game_over": False,
        "death_pending": False,
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        # --- Fase 2.5: mundo estruturado ---
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
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
        visual_key = f"new:{new_game_id}"
        final_state.update(resolve_turn_visual_state(initial_state, final_state,
                                                     action_key=visual_key))
        if not save_game_state(final_state):
            raise RuntimeError("falha ao persistir jogo novo")
        # spec checkpoints-morte (D7): checkpoint INICIAL = início da sessão. Garante
        # que a morte sempre tem para onde restaurar, mesmo antes do 1º checkpoint de cadência.
        from persistence import save_checkpoint
        if not save_checkpoint(final_state):
            import persistence as persistence_mod
            persistence_mod.delete_save(new_game_id)
            raise RuntimeError("falha ao persistir checkpoint inicial")
        return format_response(final_state, cue_action_key=visual_key)
    except Exception as e:
        # Auditoria A6: detalhe interno só no log do servidor, nunca na resposta.
        print(f"Erro ao criar jogo: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar o jogo.")

def _append_player_input(state: dict, input_text: str) -> None:
    """Anexa a ação do jogador ao histórico (mesma regra dos dois endpoints)."""
    state["messages"].append(HumanMessage(content=input_text))
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]


_ACTION_LEDGER_LIMIT = 64


def _action_already_processed(state: dict, action_id: Optional[str]) -> bool:
    return bool(action_id and action_id in (state.get("processed_action_ids") or []))


def _mark_action_processed(state: dict, action_id: Optional[str]) -> None:
    if not action_id:
        return
    ledger = [str(value) for value in (state.get("processed_action_ids") or [])
              if value and str(value) != action_id]
    ledger.append(action_id)
    state["processed_action_ids"] = ledger[-_ACTION_LEDGER_LIMIT:]


def _require_saved(state: dict, *, detail: str = "estado") -> None:
    if not save_game_state(state):
        raise RuntimeError(f"falha ao persistir {detail}")


def _write_checkpoint_if_due(state: dict, prev: dict) -> None:
    if (state.get("combat_simulation") or {}).get("enabled"):
        return
    from services import checkpoints as _cp
    if _cp.should_checkpoint(state, prev) and not _cp.maybe_write(state, prev=prev):
        raise RuntimeError("falha ao persistir checkpoint")


def _apply_action_options(state: dict, req: ActionRequest) -> None:
    """Traduz seleções da UI para a declaração que o motor já consome."""
    if not (state.get("combat") or {}).get("active"):
        return
    state["player_reaction_card_id"] = req.reaction_card_id
    active_enemies = [
        enemy for enemy in (state.get("enemies") or [])
        if not enemy.get("dead")
        and enemy.get("status", "ativo") not in ("morto", "fugiu", "rendido")
    ]
    target_id = req.target_id or (
        str(active_enemies[0].get("id")) if active_enemies else None
    )
    action = None
    if req.card_id:
        action = {
            "kind": "card", "card_id": req.card_id,
            "target_id": target_id,
            "params": {"ruptura": bool(req.ruptura)},
        }
    elif req.action_kind == "maneuver" and req.maneuver:
        action = {
            "kind": "maneuver", "maneuver": req.maneuver,
            "target_id": target_id,
        }
    elif req.action_kind in ("attack", "pass", "flee"):
        action = {"kind": req.action_kind, "target_id": target_id}
    elif (state.get("combat_simulation") or {}).get("enabled"):
        # Texto livre no laboratório nunca abre um provider: fallback fechado.
        action = {"kind": "attack", "target_id": target_id}
    if action is not None:
        state["combat_declaration"] = {
            "actor_id": "player",
            "acao": action,
            "reaction_card_id": req.reaction_card_id,
        }


def _log_turn(state: dict, t0: float, eventos_antes: int, error: Optional[str],
              llm_events: Optional[List[dict]] = None, *,
              rejections_antes: int = 0,
              llm_attempts: Optional[List[dict]] = None) -> None:
    _turn_logger.info(json.dumps({
        "evt": "turn",
        "game_id": state.get("game_id", "?"),
        "turn": (state.get("world") or {}).get("turn_count", 0),
        "route": state.get("next", ""),
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "events_applied": (len(state.get("event_log", [])) - eventos_antes) if not error else 0,
        "events_rejected": (
            max(0, len(state.get("event_rejections", []) or []) - rejections_antes)
            if not error else 0),
        "error": error,
        **_llm_log_fields(llm_events, llm_attempts),
    }, ensure_ascii=False))


def _run_turn(state: dict, input_text: str,
              action_id: Optional[str] = None) -> GameResponse:
    """Miolo do turno (spec streaming-turno-sse R2): grafo + save + log.
    Compartilhado pelo POST clássico e pelo stream — carga/validações ficam
    nos endpoints. Levanta HTTPException(500) genérica em falha (A6)."""
    _append_player_input(state, input_text)
    t0 = time.monotonic()
    eventos_antes = len(state.get("event_log", []))
    rejections_antes = len(state.get("event_rejections", []) or [])
    acc_token = _llm_turn_events.set([])
    attempt_token = _llm_attempt_events.set([])
    try:
        previous_state = deepcopy(state)
        new_state = game_graph.invoke(state)
        visual_key = action_id or f"turn:{(new_state.get('world') or {}).get('turn_count', 0)}"
        new_state.update(resolve_turn_visual_state(previous_state, new_state,
                                                   action_key=visual_key))
        _mark_action_processed(new_state, action_id)
        _require_saved(new_state, detail="turno")
        # spec checkpoints-morte (D1): grava checkpoint na cadência (10 turnos /
        # zona segura). `state` = estado ANTES do turno → detecta entrada em zona segura.
        _write_checkpoint_if_due(new_state, state)
        _log_turn(
            new_state, t0, eventos_antes, None, _llm_turn_events.get(),
            rejections_antes=rejections_antes,
            llm_attempts=_llm_attempt_events.get())
        return format_response(new_state, cue_action_key=visual_key)
    except Exception as e:
        _log_turn(
            state, t0, eventos_antes, str(e)[:200], _llm_turn_events.get(),
            rejections_antes=rejections_antes,
            llm_attempts=_llm_attempt_events.get())
        print(f"Erro na API: {e}")
        # Auditoria A6: str(e) fica no log JSON acima; cliente recebe genérico.
        raise HTTPException(status_code=500, detail="Erro interno ao processar o turno.")
    finally:
        _llm_turn_events.reset(acc_token)
        _llm_attempt_events.reset(attempt_token)


@app.post("/game/action", response_model=GameResponse)
def game_action(req: ActionRequest):
    """Envia uma ação do jogador."""

    with _game_lock(req.game_id):
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        if _action_already_processed(state, req.action_id):
            return format_response(state, cue_action_key=req.action_id)

        _reject_memorial(state)
        _reject_archived(state)
        if state.get("death_pending"):
            raise HTTPException(status_code=409,
                                detail="Você tombou. Escolha continuar do checkpoint ou aceitar o fim.")

        _apply_action_options(state, req)
        return _run_turn(state, req.input_text, req.action_id)


class DeathChoiceRequest(BaseModel):
    game_id: Optional[str] = None
    choice: str = Field(pattern="^(continue|accept)$")  # Continuar do checkpoint / Aceitar o fim


@app.post("/game/death", response_model=GameResponse)
def game_death(req: DeathChoiceRequest):
    """spec checkpoints-morte (D2): resolve a tela de morte.
    - `continue` → restaura do checkpoint (ou do início da sessão, D7); a saga segue.
    - `accept`   → memorial (game_over): a crônica encerra por escolha do jogador."""
    with _game_lock(req.game_id):
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        if not state.get("death_pending"):
            raise HTTPException(status_code=409, detail="Nenhuma queda pendente para resolver.")
        from services import checkpoints as _cp
        new_state = _cp.resolve_death_choice(state, req.choice)
        if not save_game_state(new_state):
            raise HTTPException(status_code=500, detail="Não foi possível salvar a escolha.")
        return format_response(new_state)


# --- STREAMING DO TURNO (spec streaming-turno-sse) ---------------------------

_MEMORIAL_DETAIL = ("Esta saga terminou. A crônica permanece como memorial — "
                    "comece uma nova jornada.")
_SSE_PING_S = 10.0
_NARRATIVE_CHUNK = 80


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_turn(req: ActionRequest, accepted_game_id: str) -> Iterator[str]:
    """SSE cujo worker possui lock, execução e persistência do turno.

    Se o consumidor desconectar, a thread termina o save e o ``action_id`` torna
    seguro o fallback POST. O gerador apenas apresenta eventos já produzidos.
    """
    yield _sse("accepted", {"game_id": accepted_game_id})
    q: "queue.Queue" = queue.Queue()
    llm_acc: List[dict] = []
    llm_attempt_acc: List[dict] = []

    def _worker():
        acc_token = _llm_turn_events.set(llm_acc)
        attempt_token = _llm_attempt_events.set(llm_attempt_acc)
        state: Optional[dict] = None
        t0 = time.monotonic()
        eventos_antes = 0
        rejections_antes = 0
        try:
            with _game_lock(req.game_id):
                state = load_game_state(_resolve_save_file(req.game_id))
                if not state:
                    raise HTTPException(status_code=404, detail="Jogo não encontrado.")
                if _action_already_processed(state, req.action_id):
                    q.put(("final", (state, req.action_id)))
                    return
                _reject_memorial(state)
                _reject_archived(state)
                if state.get("death_pending"):
                    raise HTTPException(
                        status_code=409,
                        detail="Você tombou. Resolva a tela de morte.",
                    )
                _apply_action_options(state, req)
                _append_player_input(state, req.input_text)
                eventos_antes = len(state.get("event_log", []))
                rejections_antes = len(state.get("event_rejections", []) or [])
                visual_previous = deepcopy(state)
                final_state: Optional[dict] = None
                for chunk in game_graph.stream(state, stream_mode=["updates", "values"]):
                    q.put(("chunk", chunk))
                    mode, data = chunk
                    if mode == "values":
                        final_state = data
                if final_state is None:
                    raise RuntimeError("stream não produziu estado final")
                visual_key = req.action_id or f"turn:{(final_state.get('world') or {}).get('turn_count', 0)}"
                final_state.update(resolve_turn_visual_state(
                    visual_previous, final_state, action_key=visual_key,
                ))
                _mark_action_processed(final_state, req.action_id)
                _require_saved(final_state, detail="turno SSE")
                _write_checkpoint_if_due(final_state, state)
                _log_turn(
                    final_state, t0, eventos_antes, None, llm_acc,
                    rejections_antes=rejections_antes,
                    llm_attempts=llm_attempt_acc,
                )
                q.put(("final", (final_state, visual_key)))
        except HTTPException as exc:
            q.put(("http_error", {"detail": exc.detail, "code": exc.status_code}))
        except Exception as e:  # noqa: BLE001
            if state is not None:
                _log_turn(
                    state, t0, eventos_antes, str(e)[:200], llm_acc,
                    rejections_antes=rejections_antes,
                    llm_attempts=llm_attempt_acc,
                )
            print(f"Erro no stream: {e}")
            q.put(("exc", e))
        finally:
            _llm_turn_events.reset(acc_token)
            _llm_attempt_events.reset(attempt_token)

    threading.Thread(target=_worker, daemon=True).start()

    while True:
        try:
            kind, payload = q.get(timeout=_SSE_PING_S)
        except queue.Empty:
            yield ": ping\n\n"
            continue
        if kind == "http_error":
            yield _sse("error", payload)
            return
        if kind == "exc":
            yield _sse("error", {"detail": "Erro interno ao processar o turno."})
            return
        if kind == "chunk":
            mode, data = payload
            if mode == "updates":
                for node, upd in (data or {}).items():
                    yield _sse("phase", {"node": node, "status": "done"})
                    if node == "dm_router":
                        yield _sse("route", {"route": (upd or {}).get("next", "") or ""})
            continue
        if kind == "final":
            final_state, visual_key = payload
            resp = format_response(final_state, cue_action_key=visual_key)
            yield _sse("visual", resp.visual.model_dump(mode="json"))
            narrative = resp.message or ""
            for i in range(0, len(narrative), _NARRATIVE_CHUNK):
                yield _sse("narrative", {
                    "chunk": narrative[i:i + _NARRATIVE_CHUNK], "done": False,
                })
            yield _sse("narrative", {"chunk": "", "done": True})
            yield _sse("state", json.loads(resp.model_dump_json()))
            return


@app.post("/game/action/stream")
def game_action_stream(req: ActionRequest):
    """R1: mesmo corpo do /game/action, resposta text/event-stream com fases
    reais do grafo. Guard-rails (rate limit via middleware, game_id, memorial,
    teto de input) valem aqui também (R3)."""
    file_to_load = _resolve_save_file(req.game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    return StreamingResponse(_stream_turn(req, str(state.get("game_id", "?"))),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

@app.post("/game/equip")
def game_equip(req: EquipRequest):
    """Fase 4.3: equipar/desequipar — validação 100% Python (inventory.equip)."""
    import inventory as inv_mod
    with _game_lock(req.game_id):
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
        if not save_game_state(state):
            raise HTTPException(status_code=500, detail="Não foi possível salvar o equipamento.")
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
    with _game_lock(req.game_id):
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        _reject_memorial(state)

        player, err = progression.apply_choice(
            state["player"], req.choice_id,
            card_id=req.card_id, evolve_card_id=req.evolve_card_id,
            caminho=req.caminho, virtude=req.virtude, attr=req.attr)
        if err:
            raise HTTPException(status_code=400, detail=err)

        state["player"] = player
        if not save_game_state(state):
            raise HTTPException(status_code=500, detail="Não foi possível salvar a progressão.")
        return {
        "ok": True,
        "player_stats": {
            "level": player.get("level", 1),
            "xp": player.get("xp", 0),
            "vitalidade": int(player.get("vitalidade", 0) or 0),
            "max_vitalidade": int(player.get("max_vitalidade", 0) or 0),
            "hp": int(player.get("vitalidade", 0) or 0),
            "max_hp": int(player.get("max_vitalidade", 0) or 0),
            "xp_next_level": progression.xp_to_next(int(player.get("level", 1) or 1)),
            "virtudes": player.get("virtudes", {}),
            "cards": _cards_block(player),
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
    combat_simulation: bool = False
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
        with _game_lock(game_id):
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
