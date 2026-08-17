"""playtest/runner.py — roda campanhas de playtest sobre o grafo do jogo.

`run_campaign` cria um personagem (mesmo caminho de /game/new), roda N turnos
via `game_graph.invoke` (o mesmo `app` da API) e salva a cada turno num
diretório ISOLADO (`saves_playtest/`, via monkeypatch de `persistence.SAVES_DIR`)
para nunca poluir os saves do jogador.

Princípios (spec fase-5.1):
  - Determinismo: mesmo (profile, seed, turns) com MockLLM → mesma campanha.
    O RNG global é semeado no início da campanha (MockLLM/combate reproduzíveis)
    e o perfil recebe um `random.Random(seed)` PRÓPRIO (não polui o global).
  - Resiliência: exceção de um turno NÃO derruba a campanha — registra em
    `errors` e segue com o estado anterior.
  - Telemetria: registra provider/modelo/tier/fell_back por turno via o hook
    `set_llm_telemetry_hook` do roteamento (None no MockLLM).
"""
from __future__ import annotations

import contextlib
import copy
import json
import os
import queue
import random
import threading
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Callable, Dict, List, Optional

# Diretório de saves isolado das campanhas de playtest (spec R7).
PLAYTEST_SAVES_DIR = os.getenv("RPG_PLAYTEST_SAVES_DIR", "saves_playtest")


class PlaytestTimeoutError(TimeoutError):
    """Watchdog do harness; a operação vencida permanece apenas em thread daemon."""

    def __init__(self, phase: str, timeout_seconds: float, *,
                 elapsed_seconds: Optional[float] = None):
        self.phase = str(phase)
        self.timeout_seconds = float(timeout_seconds)
        self.elapsed_seconds = float(
            elapsed_seconds
            if elapsed_seconds is not None else timeout_seconds
        )
        super().__init__(
            f"{self.phase} excedeu {self.timeout_seconds:g}s de wall-clock "
            f"(observado {self.elapsed_seconds:g}s)"
        )


def _run_with_watchdog(call: Callable[[], Any], *, timeout_seconds: float,
                       phase: str) -> Any:
    """Executa ``call`` com teto de parede sem prender a saída do processo.

    Python não consegue matar uma thread com segurança. Por isso o worker é
    daemon e, ao vencer, a campanha inteira é abortada; o CLI não inicia outro
    perfil no mesmo processo. Os próprios clientes HTTP continuam com timeout.
    """
    timeout = float(timeout_seconds or 0)
    if timeout <= 0:
        return call()
    started_monotonic = time.monotonic()
    started_wall = time.time()
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            result_queue.put((True, call()))
        except BaseException as exc:  # propaga inclusive exceções não-Exception
            result_queue.put((False, exc))

    worker = threading.Thread(
        target=_worker,
        name=f"playtest-watchdog-{phase}",
        daemon=True,
    )
    worker.start()
    try:
        ok, payload = result_queue.get(timeout=timeout)
    except queue.Empty as exc:
        elapsed = max(
            time.monotonic() - started_monotonic,
            time.time() - started_wall,
        )
        raise PlaytestTimeoutError(
            phase, timeout, elapsed_seconds=elapsed,
        ) from exc
    elapsed = max(
        time.monotonic() - started_monotonic,
        time.time() - started_wall,
    )
    # Um notebook pode suspender enquanto worker e supervisor aguardam. Nesse
    # caso ambos retomam juntos e o resultado pode já estar na fila antes que o
    # timeout da Queue seja processado. O deadline absoluto continua soberano.
    if elapsed > timeout:
        raise PlaytestTimeoutError(
            phase, timeout, elapsed_seconds=elapsed,
        )
    if ok:
        return payload
    raise payload


@dataclass
class TurnRecord:
    """Um turno da campanha. `route` é a rota do GRAFO (storyteller/combat/...),
    NÃO o tier de LLM — não confundir. provider/model/tier vêm do hook de
    telemetria do roteamento (None sob MockLLM)."""
    turn: int
    action: str
    route: str
    latency_ms: int
    game_id: str = ""
    save_path: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    tier: Optional[str] = None
    fell_back: bool = False
    # Fase 5.3: todos os invokes de LLM do turno (p/ custo agregado) e métricas
    # de estado capturadas pós-turno (alimentam a telemetria JSONL).
    llm_events: List[dict] = field(default_factory=list)
    rag_events: List[dict] = field(default_factory=list)
    nodes_executed: List[str] = field(default_factory=list)
    node_latency_ms: Dict[str, int] = field(default_factory=dict)
    combat_executed: bool = False
    combat_active_before: bool = False
    combat_round_before: int = 0
    combat_round_after: int = 0
    combat_started: bool = False
    combat_ended: bool = False
    decision: dict = field(default_factory=dict)
    resolved_action: dict = field(default_factory=dict)
    events_applied: int = 0
    events_rejected: int = 0
    error: Optional[str] = None
    location_id: str = ""
    player_hp: int = 0
    player_max_hp: int = 0
    player_vitality: int = 0
    player_max_vitality: int = 0
    player_level: int = 1
    gold: int = 0
    # spec balanceamento-early-game (R5): campos crus das métricas de balanço.
    combat_active: bool = False
    replanned: bool = False
    # spec balanceamento-classes-pos-playtest (R2): recurso das 5 Posturas por turno.
    entropy: int = 0
    max_entropy: int = 0
    abyss_charge: int = 0
    abyss_tier: str = ""
    # spec playtest-agente-curioso-entropia (R3): GASTO de Entropia no turno de
    # combate (não o snapshot) — quanto foi pago + se usou habilidade ativa.
    entropy_spent: int = 0
    used_active_ability: bool = False
    ability_id: Optional[str] = None
    class_mechanics: List[dict] = field(default_factory=list)
    # Hardening pós-smoke: snapshots mecânicos auditáveis. Reações só pertencem
    # ao turno em que o combat_agent executou; Ferimentos cobrem player e todos
    # os inimigos ainda materializados no estado pós-turno.
    reactions: List[dict] = field(default_factory=list)
    last_tactics: List[dict] = field(default_factory=list)
    player_wounds: Dict[str, list] = field(default_factory=dict)
    enemy_wounds: Dict[str, Dict[str, list]] = field(default_factory=dict)
    conflict_wounds: Dict[str, list] = field(default_factory=dict)
    # spec hardening-memoria-proveniencia: snapshot cumulativo auditável.
    memory_by_provenance: Dict[str, int] = field(default_factory=dict)
    memory_writes_by_provenance: Dict[str, int] = field(default_factory=dict)
    memory_rejections: int = 0
    memory_promotions: int = 0
    violations: List[str] = field(default_factory=list)
    violation_details: List[dict] = field(default_factory=list)
    death: Optional[dict] = None
    death_pending: bool = False
    game_over: bool = False
    # Narração que o jogador leria no turno (p/ transcript qualitativo do prompt).
    narrative: str = ""
    progression_choices: List[dict] = field(default_factory=list)
    # Remediação playtest real 100t: pedido social e conversão no mesmo turno.
    quest_requested: bool = False
    quests_before: int = 0
    quests_after: int = 0
    combat_origin: str = "unknown"
    conflict_instance_id: str = ""
    session_action_count: int = 0
    canonical_turn: int = 0
    timeline_epoch: int = 0
    memory_by_confidence: Dict[str, int] = field(default_factory=dict)
    stale_speculative_memories: int = 0


@dataclass
class CampaignResult:
    profile: str
    seed: int
    turns_completed: int
    errors: List[dict]
    history: List[TurnRecord]
    final_state: dict
    save_path: str
    # Fase 5.2: violações de invariante coletadas por turno (campanha não para).
    violations: List[dict] = field(default_factory=list)
    mock: bool = True
    aborted_reason: Optional[str] = None  # Fase 5.3: teto de requests/custo
    # spec checkpoints-morte (D6): mortes que dispararam auto-restore (turno/local/causa).
    deaths_log: List[dict] = field(default_factory=list)
    turns_requested: int = 0
    startup_llm_events: List[dict] = field(default_factory=list)
    startup_rag_events: List[dict] = field(default_factory=list)
    invariants_enabled: bool = True
    scenario: Optional[str] = None


def _resolve_profile_progression(state: dict, profile: object) -> List[dict]:
    """Simula o modal de level-up apenas para perfis que optam por isso."""
    if not getattr(profile, "resolve_progression", False):
        return []
    import gamedata
    import progression
    from services import cards

    player = dict(state.get("player") or {})
    applied: List[dict] = []
    # Uma subida pode enfileirar carta + virtude; consome ambas como a UI faria.
    for choice in list(player.get("pending_choices") or []):
        choice_id = str(choice.get("id") or "")
        kind = str(choice.get("kind") or "")
        kwargs: Dict[str, str] = {}
        selected = ""
        if kind == "virtude":
            virtues = player.get("virtudes") or {}
            eligible = [key for key in gamedata.VIRTUDES
                        if int(virtues.get(key, 0) or 0) < gamedata.VIRTUDE_MAX]
            if eligible:
                selected = min(eligible, key=lambda key: (int(virtues.get(key, 0) or 0), key))
                kwargs["virtude"] = selected
        elif kind == "carta":
            eligible_cards = sorted(progression.eligible_cards(player))
            if eligible_cards:
                selected = eligible_cards[0]
                kwargs["card_id"] = selected
            else:
                evolved = player.get("evolved_cards") or {}
                evolvable = [
                    cid for cid in (player.get("known_cards") or [])
                    if cid not in evolved and (cards.get_card(cid) or {}).get("evolucao")
                ]
                if evolvable:
                    selected = sorted(evolvable)[0]
                    kwargs.update(evolve_card_id=selected, caminho="A")
        if not selected:
            continue
        updated, error = progression.apply_choice(player, choice_id, **kwargs)
        if error:
            continue
        player = updated
        applied.append({
            "choice_id": choice_id, "kind": kind, "selection": selected,
            **({"path": "A"} if kwargs.get("caminho") else {}),
        })
    if applied:
        state["player"] = player
    return applied


# --- criação de personagem (espelha /game/new) -----------------------------

# Personagem default determinístico do playtest. Devoto do Abismo (tank, HP alto)
# cobre exploração e combate sem morrer cedo no mock; região-hub (Nova Arcádia)
# tem muitas conexões p/ o explorador. (spec refatoracao-sistema-classes)
_DEFAULT_CHAR = {
    "class_name": "Devoto do Abismo",
    "race": "Humano",
    "region": "Nova Arcádia",
    "level": 1,
    "backstory": "Um andarilho de teste, forjado pelo harness.",
}


def resolve_class_name(raw: str) -> str:
    """spec balanceamento-classes-pos-playtest (R1): aceita o nome exato OU o
    slug (`devoto_do_abismo`, sem acento, case-insensitive) e devolve a chave
    canônica de CLASSES. Inválido → KeyError com as opções."""
    import unicodedata
    from gamedata import CLASSES

    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFD", str(s).lower().replace("_", " "))
        return "".join(ch for ch in s if not unicodedata.combining(ch)).strip()

    for cname in CLASSES:
        if _norm(cname) == _norm(raw):
            return cname
    raise KeyError(f"classe desconhecida: {raw!r} (conhecidas: {sorted(CLASSES)})")


def _build_initial_state(profile: str, seed: int,
                         class_name: Optional[str] = None) -> dict:
    """Monta o estado inicial da campanha — MESMO shape de api.new_game."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from character_creator import create_player_character
    from gamedata import seed_factions
    from services.chronicle import default_chapter_title
    from world_utils import starting_world

    char_input = dict(_DEFAULT_CHAR)
    if class_name:
        char_input["class_name"] = resolve_class_name(class_name)
    char_input["name"] = f"Playtest-{profile}"
    final_char = create_player_character(char_input)
    level = int(char_input["level"])

    game_id = str(uuid.uuid4())
    region = final_char["region"]
    return {
        "game_id": game_id,
        "narrative_summary": f"A jornada de {final_char['name']} começa em {region}.",
        "archivist_last_run": 0,
        "chronicle": [{"title": default_chapter_title(region),
                       "started_turn": 0, "location": region, "entries": []}],
        "combat_target": None,
        "loot_source": None,
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
            "gold": 50 * level,
            "alignment": "Neutro",
            # spec conflito-01: Virtudes + Vitalidade/Ferimentos (mana/stamina/attributes saíram)
            "virtudes": final_char["virtudes"],
            "vitalidade": final_char.get("vitalidade", final_char.get("max_vitalidade", final_char["max_hp"])),
            "max_vitalidade": final_char.get("max_vitalidade", final_char["max_hp"]),
            "ferimento_espacos": final_char.get("ferimento_espacos", {}),
            "ferimentos": final_char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
            "inventory": final_char["inventory"],
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
            "racial_traits": final_char.get("racial_traits", []),
            "condition_resists": final_char.get("condition_resists", []),
            "racial_save_bonus": final_char.get("racial_save_bonus", {}),
        },
        "world": starting_world(region, level),
        "messages": [
            SystemMessage(content=f"A jornada de {final_char['name']} começa em {region}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {level}."),
        ],
        "party": [],
        "enemies": [],
        "factions": seed_factions(),
        "faction_intel": {},
        "bestiary_knowledge": {},
        "quests": [],
        "archive_due": False,
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "continuity": {"session_action_count": 0, "timeline_epoch": 0,
                       "last_checkpoint_turn": 0, "death_history": []},
    }


# --- helpers de ambiente ----------------------------------------------------

@contextlib.contextmanager
def _isolated_saves():
    """Aponta persistence.SAVES_DIR p/ o diretório de playtest e restaura ao fim."""
    import persistence
    original = persistence.SAVES_DIR
    persistence.SAVES_DIR = PLAYTEST_SAVES_DIR
    os.makedirs(PLAYTEST_SAVES_DIR, exist_ok=True)
    try:
        yield
    finally:
        persistence.SAVES_DIR = original


@contextlib.contextmanager
def _isolated_runtime_cache():
    """spec isolar-cache-runtime (R6): caches gerados (bestiário/NPC/artefatos)
    vão p/ dentro do diretório de playtest — run mock ou --real nunca suja data/."""
    prev = os.environ.get("RPG_RUNTIME_CACHE_DIR")
    os.environ["RPG_RUNTIME_CACHE_DIR"] = os.path.join(PLAYTEST_SAVES_DIR, "runtime")
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("RPG_RUNTIME_CACHE_DIR", None)
        else:
            os.environ["RPG_RUNTIME_CACHE_DIR"] = prev


@contextlib.contextmanager
def _force_mock(active: bool):
    """Garante RPG_FORCE_MOCK ligado (offline) ou desligado (--real), restaurando."""
    prev = os.environ.get("RPG_FORCE_MOCK")
    if active:
        os.environ["RPG_FORCE_MOCK"] = "1"
    else:
        os.environ.pop("RPG_FORCE_MOCK", None)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("RPG_FORCE_MOCK", None)
        else:
            os.environ["RPG_FORCE_MOCK"] = prev


@contextlib.contextmanager
def _offline_embeddings(active: bool):
    """Backend RAG efêmero do modo MOCK.

    Leituras continuam sem embeddings/rede. Escritas válidas, porém, precisam
    preservar a semântica de commit do jogo: são aceitas num store em memória e
    emitem ``RAGOperationEvent(success=True)``. Simplesmente devolver embeddings
    ``None`` fazia archivist/NPC tratarem todo turno offline como falha durável,
    retendo ConflictSummary e produzindo milhares de falsos positivos.

    Alguns agentes importam os writers diretamente (aliases de módulo), então
    todos são trocados/restaurados junto com ``rag``. Cada entrada no contexto
    cria um store novo; campanhas sequenciais no mesmo processo não vazam fatos.
    Em ``--real`` o contexto é um no-op.
    """
    if not active:
        yield
        return
    import rag
    import persistence
    from agents import archivist as archivist_module
    from agents import npc as npc_module
    from agents import world_simulator as world_module

    session_store: Dict[str, List[str]] = {}
    npc_store: Dict[tuple[str, str], List[str]] = {}

    def _capture_offline_memory(game_id: str) -> Optional[Dict[str, bytes]]:
        payload = {
            "session": list(session_store.get(str(game_id), [])),
            "npcs": {
                npc_id: list(values)
                for (gid, npc_id), values in npc_store.items()
                if gid == str(game_id)
            },
        }
        if not payload["session"] and not payload["npcs"]:
            return None
        return {"__offline_store__.json": json.dumps(
            payload, ensure_ascii=False, sort_keys=True).encode("utf-8")}

    def _restore_offline_memory(game_id: str,
                                captured: Optional[Dict[str, bytes]]) -> None:
        gid = str(game_id)
        session_store.pop(gid, None)
        for key in [key for key in npc_store if key[0] == gid]:
            npc_store.pop(key, None)
        raw = (captured or {}).get("__offline_store__.json")
        if not raw:
            return
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("session"):
            session_store[gid] = list(payload["session"])
        for npc_id, values in (payload.get("npcs") or {}).items():
            npc_store[(gid, str(npc_id))] = list(values)

    def _offline_path(game_id: str, npc_id: Optional[str] = None) -> str:
        session = rag._safe_storage_component(game_id, "session")
        if npc_id is None:
            return f"memory://playtest/{session}/session"
        npc = rag._safe_storage_component(npc_id, "npc")
        return f"memory://playtest/{session}/{npc}"

    def _write_session(
        game_id: str, texts: List[str], *, metadatas: Optional[List[Dict]] = None,
    ) -> bool:
        valid = bool(game_id and isinstance(texts, list) and texts)
        path = _offline_path(str(game_id)) if game_id else ""
        if valid:
            session_store.setdefault(str(game_id), []).extend(
                str(text) for text in texts
            )
        return rag._rag_operation_result(
            "add_session_memory",
            valid,
            game_id=str(game_id or ""),
            npc_id=None,
            path=path,
            facts_count=len(texts) if isinstance(texts, list) else 0,
            provider="offline-simulated" if valid else None,
            error=None if valid else "invalid_input",
            metadatas=metadatas,
        )

    def _write_npc(
        game_id: str,
        npc_id: str,
        texts: List[str],
        *,
        metadatas: Optional[List[Dict]] = None,
    ) -> bool:
        valid = bool(game_id and npc_id and isinstance(texts, list) and texts)
        path = (
            _offline_path(str(game_id), str(npc_id))
            if game_id and npc_id else ""
        )
        if valid:
            npc_store.setdefault((str(game_id), str(npc_id)), []).extend(
                str(text) for text in texts
            )
        return rag._rag_operation_result(
            "add_npc_memory",
            valid,
            game_id=str(game_id or ""),
            npc_id=str(npc_id) if npc_id else None,
            path=path,
            facts_count=len(texts) if isinstance(texts, list) else 0,
            provider="offline-simulated" if valid else None,
            error=None if valid else "invalid_input",
            metadatas=metadatas,
        )

    replacements = [
        (rag, "get_embeddings", lambda: None),
        (rag, "_embeddings_for_index", lambda _path: None),
        (rag, "add_memory_to_session", _write_session),
        (rag, "add_npc_memory", _write_npc),
        (archivist_module, "add_memory_to_session", _write_session),
        (archivist_module, "add_npc_memory", _write_npc),
        (npc_module, "add_npc_memory", _write_npc),
        (world_module, "add_memory_to_session", _write_session),
        (persistence, "capture_session_memory", _capture_offline_memory),
        (persistence, "restore_captured_session_memory", _restore_offline_memory),
    ]
    originals = [
        (module, attribute, getattr(module, attribute))
        for module, attribute, _replacement in replacements
    ]
    for module, attribute, replacement in replacements:
        setattr(module, attribute, replacement)
    try:
        yield
    finally:
        for module, attribute, original in reversed(originals):
            setattr(module, attribute, original)


def _clear_caches() -> None:
    """Zera caches globais de dados/grafo entre campanhas (spec §7). npc_database
    é cache legítimo de dedupe global — não é limpo aqui."""
    with contextlib.suppress(Exception):
        from services.graph_resolver import clear_cache
        clear_cache()
    with contextlib.suppress(Exception):
        from services.codex_loader import clear_codex_index_cache
        clear_codex_index_cache()


def _last_ai_text(state: dict) -> str:
    """Última mensagem de narração visível (o que um jogador leria na tela)."""
    for msg in reversed(state.get("messages", []) or []):
        content = getattr(msg, "content", "")
        if content and getattr(msg, "type", "") != "human":
            return str(content)
    return ""


# Rotas válidas do router (a DECISÃO em `next`); "loot" é a chave da aresta.
_ROUTER_ROUTES = {"storyteller", "combat_agent", "npc_actor", "loot"}


def _safe_event_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if is_dataclass(raw):
        return asdict(raw)
    if hasattr(raw, "model_dump"):
        return dict(raw.model_dump())
    data = getattr(raw, "__dict__", None)
    return dict(data) if isinstance(data, dict) else {}


def _normalize_llm_event(*args, **kwargs) -> dict:
    """Aceita o hook legado de 5 argumentos ou o evento de tentativa novo."""
    if len(args) == 1 and not kwargs:
        data = _safe_event_dict(args[0])
    elif len(args) >= 5:
        provider, model, tier, latency_ms, fell_back = args[:5]
        data = {
            "provider": provider,
            "model": model,
            "tier": tier,
            "latency_ms": latency_ms,
            "fell_back": fell_back,
            "outcome": "success",
        }
    else:
        data = dict(kwargs)
    outcome = str(data.get("outcome") or data.get("status") or "success")
    error = str(data.get("error") or "")
    no_network = outcome in {"build_error", "circuit_open"}
    # Não persiste payloads/respostas/prompts. Somente campos permitidos.
    return {
        "provider": str(data.get("provider") or "?"),
        "model": str(data.get("model") or "?"),
        "tier": getattr(data.get("tier"), "value", str(data.get("tier") or "?")),
        "latency_ms": max(0, int(data.get("latency_ms", 0) or 0)),
        "fell_back": bool(data.get("fell_back")),
        "status": outcome,
        "network_attempted": (
            False if no_network else bool(data.get("network_attempted", True))
        ),
        "attempt_index": data.get("attempt_index"),
        "structured": bool(data.get("structured", False)),
        "error": error[:240] or None,
    }


def _normalize_rag_event(raw: Any) -> dict:
    data = _safe_event_dict(raw)
    return {
        "operation": str(data.get("operation") or "?"),
        "success": bool(data.get("success", False)),
        "provider": str(data.get("provider") or "?"),
        "game_id": data.get("game_id"),
        "npc_id": data.get("npc_id"),
        "path": str(data.get("path") or "")[-240:] or None,
        "facts_count": int(data.get("facts_count", 0) or 0),
        "provenance_counts": {
            str(key): int(value or 0)
            for key, value in dict(data.get("provenance_counts") or {}).items()
        },
        "error": str(data.get("error") or "")[:240] or None,
    }


def _rag_memory_counts(events: List[dict]) -> Dict[str, int]:
    counts: Counter = Counter()
    for event in events:
        if not event.get("success"):
            continue
        counts.update({
            str(key): int(value or 0)
            for key, value in dict(event.get("provenance_counts") or {}).items()
        })
    return dict(counts)


def _network_events(events: List[dict]) -> List[dict]:
    return [event for event in events if event.get("network_attempted", True)]


def _count_new_rejections(before: List[dict], after: List[dict]) -> int:
    """Conta conteúdo novo mesmo quando o buffer circular continua em 100 itens."""
    def identity(item: object) -> str:
        try:
            return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(item)

    old = Counter(identity(item) for item in before)
    new = Counter(identity(item) for item in after)
    return sum(max(0, count - old.get(key, 0)) for key, count in new.items())


def _run_turn(game_graph, state: dict, *,
              nodes_executed: Optional[List[str]] = None,
              node_observations: Optional[dict] = None,
              node_latency_ms: Optional[dict] = None) -> tuple[dict, str]:
    """Invoca o grafo capturando a DECISÃO do `dm_router` (spec R3): a rota fiel
    é o `next` que o router escolheu, não o `next` do estado final (combate/loot
    sobrescrevem). Se o combate está ATIVO na entrada do turno, a rota é
    `combat_agent` (lock de combate). Devolve (estado_final, rota).

    Usa streaming multi-modo: `updates` expõe o dict parcial de cada nó (lê o
    `next` do dm_router na primeira aparição); `values` dá o estado completo
    (o último = resultado equivalente ao `.invoke`)."""
    combat_on_entry = bool((state.get("combat") or {}).get("active"))
    nodes = nodes_executed if nodes_executed is not None else []
    timings = node_latency_ms if node_latency_ms is not None else {}
    node_started = time.perf_counter()
    stream = getattr(game_graph, "stream", None)
    if stream is None:
        # Grafo sem streaming (ex.: wrapper de teste que só implementa invoke):
        # cai pro invoke; rota vem do estado final (best-effort, como antes).
        new_state = game_graph.invoke(state)
        route = "combat_agent" if combat_on_entry else (new_state.get("next") or "")
        if route:
            nodes.append(route)
            timings[route] = timings.get(route, 0) + int(
                (time.perf_counter() - node_started) * 1000
            )
        return new_state, route
    router_next = ""
    final = state
    for mode, chunk in stream(state, stream_mode=["updates", "values"]):
        if mode == "updates" and isinstance(chunk, dict):
            names = list(chunk)
            elapsed = int((time.perf_counter() - node_started) * 1000)
            for index, node_name in enumerate(names):
                if node_name not in nodes:
                    nodes.append(node_name)
                timings[node_name] = timings.get(node_name, 0) + (elapsed if index == 0 else 0)
            node_started = time.perf_counter()
            upd = chunk.get("dm_router")
            if isinstance(upd, dict) and not router_next:
                router_next = upd.get("next") or ""
            combat_update = chunk.get("combat_agent")
            if (
                node_observations is not None
                and isinstance(combat_update, dict)
            ):
                # O archivist pode consumir o ConflictSummary no mesmo invoke.
                # Preserva somente a janela mecânica intermediária necessária
                # à auditoria, sem duplicar mensagens/prompts no JSONL.
                node_observations["combat_agent"] = copy.deepcopy({
                    key: combat_update.get(key)
                    for key in (
                        "combat", "player", "enemies", "conflict_summary",
                        "tactics",
                    )
                    if key in combat_update
                })
        elif mode == "values":
            final = chunk
    route = "combat_agent" if combat_on_entry else router_next
    return final, route


def _observed_resolved_action(node_observations: Optional[dict]) -> dict:
    """Resultado mecânico emitido pelo combat node neste invoke, ou vazio.

    ``combat.last_player_action`` é estado persistente do jogo e não pode ser
    usado diretamente como uma métrica por turno: faria uma fuga reaparecer em
    todos os turnos narrativos seguintes.
    """
    combat_update = (node_observations or {}).get("combat_agent") or {}
    observed_combat = combat_update.get("combat") or {}
    return dict(observed_combat.get("last_player_action") or {})


def _is_explicit_quest_request(action: str) -> bool:
    """Pedido diegético de tarefa; usado somente como métrica do harness."""
    import re
    return bool(re.search(
        r"\b(?:tarefa|miss[aã]o|trabalho|favor)\s+concret[oa]\b",
        str(action or ""),
        flags=re.IGNORECASE,
    ))


def _campaign_experience_violations(
    profile: str,
    history: List[TurnRecord],
    final_state: dict,
) -> List[dict]:
    """Oráculos agregados: alertam validade/viés sem fingir bug por turno."""
    if profile != "normal" or not history:
        return []
    out: List[dict] = []
    total = len(history)
    combat_turns = len([
        record for record in history
        if record.combat_executed or record.route == "combat_agent"
    ])
    combat_pct = round(100.0 * combat_turns / total, 1)
    if total >= 50 and combat_pct > 35.0:
        out.append({
            "check_id": "profile.combat_share",
            "severity": "warning",
            "turn": history[-1].turn,
            "message": f"perfil normal passou {combat_pct:.1f}% dos turnos em combate",
            "details": {
                "combat_turns": combat_turns,
                "turns": total,
                "combat_turn_pct": combat_pct,
                "warning_pct": 35.0,
            },
        })
    from playtest.metrics import quest_request_conversion_count
    requests = len([record for record in history if record.quest_requested])
    conversions = quest_request_conversion_count(history, window=3)
    if total >= 50 and requests >= 2 and conversions == 0:
        out.append({
            "check_id": "profile.quest_conversion_empty",
            "severity": "warning",
            "turn": history[-1].turn,
            "message": f"{requests} pedidos concretos não criaram nenhuma quest",
            "details": {
                "quest_requests": requests,
                "quest_request_conversions": conversions,
                "final_quests": len(final_state.get("quests", []) or []),
            },
        })
    return out


# --- runner -----------------------------------------------------------------

def run_campaign(profile: str, turns: int = 50, seed: int = 0,
                 use_real_llm: bool = False,
                 on_turn_end: Optional[Callable[[dict, int], None]] = None,
                 invariants: bool = True,
                 max_requests: int = 0,
                 max_cost: float = 0.0,
                 class_name: Optional[str] = None,
                 turn_timeout_seconds: Optional[float] = None,
                 scenario: Optional[str] = None) -> CampaignResult:
    """Joga `turns` turnos com o perfil `profile` e devolve o CampaignResult.

    - `on_turn_end(state, turn)` roda após cada turno; exceção conta como erro.
    - `invariants=True` (default) audita cada turno com playtest.invariants
      (se disponível); violações vão p/ `result.violations` sem parar a campanha.
    - `max_requests`/`max_cost` (só fazem sentido com `use_real_llm`) abortam a
      campanha educadamente ao atingir o teto (spec 5.3 R6). 0 = desligado.
    - `turn_timeout_seconds` limita startup e cada turno. `None` usa 120s em
      run real e desliga no mock; valor explícito também serve em testes offline.
    """
    from playtest.profiles import PROFILES
    scenario_module = None
    if scenario:
        from playtest import scenarios as scenario_module
        expected_profile = scenario_module.profile_for(scenario)
        if profile != expected_profile:
            raise ValueError(
                f"cenário {scenario!r} exige perfil {expected_profile!r}, "
                f"recebeu {profile!r}"
            )
    if profile not in PROFILES:
        raise KeyError(f"perfil desconhecido: {profile!r} (conhecidos: {sorted(PROFILES)})")
    prof = PROFILES[profile]
    prof.reset()  # spec fix-explorador-loop: perfis são singleton — zera memória por campanha
    prof_rng = random.Random(seed)

    errors: List[dict] = []
    history: List[TurnRecord] = []
    violations: List[dict] = []
    aborted_reason: Optional[str] = None
    llm_calls = {"count": 0, "cost": 0.0}
    deaths_log: List[dict] = []  # spec checkpoints-morte (D6)
    startup_llm_events: List[dict] = []
    startup_rag_events: List[dict] = []
    llm_sink: List[dict] = startup_llm_events
    rag_sink: List[dict] = startup_rag_events
    state: dict = {}
    game_id = ""
    final_path = ""
    no_progress_streak = 0
    from services import checkpoints as _cp

    if turn_timeout_seconds is None:
        turn_timeout_seconds = (
            float(os.getenv("RPG_PLAYTEST_TURN_TIMEOUT_SECONDS", "120"))
            if use_real_llm else 0.0
        )
    turn_timeout_seconds = max(0.0, float(turn_timeout_seconds or 0.0))

    import llm_setup
    reset_circuits = getattr(llm_setup, "reset_llm_circuit_breakers", None)
    if reset_circuits is not None:
        reset_circuits()
    attempt_setter = getattr(llm_setup, "set_llm_attempt_telemetry_hook", None)
    # O hook por tentativa é o contrato de runs reais. Em mock mantemos o hook
    # legado: wrappers de teste e callers antigos ainda o emitem manualmente.
    llm_setter = (
        attempt_setter
        if use_real_llm and attempt_setter is not None
        else llm_setup.set_llm_telemetry_hook
    )

    def _llm_hook(*args, **kwargs):
        event = _normalize_llm_event(*args, **kwargs)
        if event.get("attempt_index") is None:
            event["attempt_index"] = len(llm_sink)
        llm_sink.append(event)

    rag_setter = None
    try:
        import rag as _rag
        rag_setter = getattr(_rag, "set_rag_operation_hook", None)
    except Exception:
        pass

    def _rag_hook(event):
        rag_sink.append(_normalize_rag_event(event))

    with _force_mock(active=not use_real_llm), \
            _offline_embeddings(active=not use_real_llm), _isolated_saves(), \
            _isolated_runtime_cache():
        _clear_caches()
        random.seed(seed)  # reproduz MockLLM + combate da campanha inteira
        from main import app as game_graph
        from persistence import save_game_state, save_path
        from langchain_core.messages import HumanMessage

        llm_setter(_llm_hook)
        if rag_setter:
            rag_setter(_rag_hook)
        try:
            state = _build_initial_state(profile, seed, class_name=class_name)
            if scenario_module is not None:
                # O startup (campaign_manager/storyteller) já deve enxergar a
                # cena dirigida; reaplicamos depois para garantir que a própria
                # abertura não consumiu/alterou a pré-condição do oráculo.
                state = scenario_module.prepare(str(scenario), state)
            game_id = state["game_id"]
            state = _run_with_watchdog(
                lambda: game_graph.invoke(state),
                timeout_seconds=turn_timeout_seconds,
                phase="startup",
            )
            # Startup é prólogo, não decisão do perfil.
            from services.continuity import mark_checkpoint
            state["continuity"] = mark_checkpoint(
                {**(state.get("continuity") or {}), "session_action_count": 0},
                canonical_turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
            )
            if scenario_module is not None:
                state = scenario_module.prepare(str(scenario), state)
            save_game_state(state)
            _bump_llm_events_budget(llm_calls, startup_llm_events)
            prev_state = state
            # spec checkpoints-morte (D6): snapshots in-memory p/ auto-restore.
            initial_snap = _cp.snapshot(state)
            checkpoint_snap = None

            startup_abort = _budget_abort_reason(
                llm_calls,
                max_requests=max_requests,
                max_cost=max_cost,
                phase="startup",
            )
            if startup_abort:
                aborted_reason = startup_abort

            for turn in range(1, turns + 1) if not aborted_reason else []:
                progression_choices = _resolve_profile_progression(state, prof)
                directed = (
                    scenario_module.decision_for(str(scenario), turn, state)
                    if scenario_module is not None else None
                )
                decision = directed or prof.decide(state, prof_rng)
                action = decision.text
                state["messages"].append(HumanMessage(content=action))
                if len(state["messages"]) > 20:
                    state["messages"] = state["messages"][-20:]
                state["combat_declaration"] = (
                    decision.declaration if decision.mode == "declaration" else None
                )
                state["combat_flee_attempt"] = decision.mode == "flee"
                state["combat_flee_destination"] = (
                    decision.flee_destination_id if decision.mode == "flee" else None
                )

                turn_events: List[dict] = []
                turn_rag_events: List[dict] = []
                llm_sink = turn_events
                rag_sink = turn_rag_events
                t0 = time.monotonic()
                events_before = len(state.get("event_log", []) or [])
                quests_before = len(state.get("quests", []) or [])
                rejected_before = list(state.get("event_rejections", []) or [])
                plan_before = (state.get("campaign_plan") or {}).get("last_planned_turn")
                combat_before = state.get("combat") or {}
                combat_on_entry = bool(combat_before.get("active"))
                combat_round_before = int(combat_before.get("round", 0) or 0)
                try:
                    from playtest import invariants as _inv
                    progress_before = _inv.combat_progress_fingerprint(state)
                except Exception:
                    _inv = None
                    progress_before = None
                nodes: List[str] = []
                node_timings: Dict[str, int] = {}
                node_observations: dict = {}
                decision_record = decision.to_record()
                rec = TurnRecord(
                    turn=turn,
                    action=action,
                    route="",
                    latency_ms=0,
                    game_id=game_id,
                    save_path=os.path.abspath(save_path(game_id)),
                    decision=decision_record,
                    combat_active_before=combat_on_entry,
                    combat_round_before=combat_round_before,
                    progression_choices=progression_choices,
                    quest_requested=_is_explicit_quest_request(action),
                    quests_before=quests_before,
                    quests_after=quests_before,
                )
                turn_input_state = state
                try:
                    new_state, rec.route = _run_with_watchdog(
                        lambda: _run_turn(
                            game_graph,
                            state,
                            nodes_executed=nodes,
                            node_observations=node_observations,
                            node_latency_ms=node_timings,
                        ),
                        timeout_seconds=turn_timeout_seconds,
                        phase=f"turno {turn}",
                    )
                    save_game_state(new_state)
                    rec.latency_ms = int((time.monotonic() - t0) * 1000)
                    rec.nodes_executed = nodes
                    rec.node_latency_ms = node_timings
                    rec.combat_executed = "combat_agent" in nodes
                    combat_after = new_state.get("combat") or {}
                    rec.combat_round_after = int(
                        combat_after.get("round", combat_round_before) or 0
                    )
                    active_after = bool(combat_after.get("active"))
                    rec.combat_started = rec.combat_executed and not combat_on_entry
                    rec.combat_ended = rec.combat_executed and not active_after
                    rec.resolved_action = _observed_resolved_action(
                        node_observations,
                    )
                    rec.replanned = ((new_state.get("campaign_plan") or {})
                                     .get("last_planned_turn") != plan_before)
                    rec.events_applied = max(
                        0, len(new_state.get("event_log", []) or []) - events_before,
                    )
                    rec.events_rejected = _count_new_rejections(
                        rejected_before,
                        list(new_state.get("event_rejections", []) or []),
                    )
                    rec.quests_after = len(new_state.get("quests", []) or [])
                    rec.narrative = _last_ai_text(new_state)
                    _fill_state_metrics(
                        rec,
                        new_state,
                        combat_observation=node_observations.get("combat_agent"),
                    )
                    _attach_telemetry(rec, list(turn_events))
                    rec.rag_events = list(turn_rag_events)
                    rec.memory_writes_by_provenance = _rag_memory_counts(
                        rec.rag_events
                    )
                    _bump_llm_events_budget(llm_calls, rec.llm_events)

                    try:
                        progress_after = (
                            _inv.combat_progress_fingerprint(new_state)
                            if _inv is not None else None
                        )
                    except Exception:
                        progress_after = None
                    if rec.combat_executed and combat_on_entry and active_after \
                            and progress_before is not None \
                            and progress_before == progress_after:
                        no_progress_streak += 1
                    else:
                        no_progress_streak = 0

                    # Invariantes (5.2) — não param a campanha.
                    audit_context = {
                        "profile": profile,
                        "action": action,
                        "decision": decision_record,
                        "resolved_action": rec.resolved_action,
                        "combat_executed": rec.combat_executed,
                        "combat_ended": rec.combat_ended,
                        "combat_no_progress_streak": no_progress_streak,
                        "rag_events": rec.rag_events,
                        "latency_ms": rec.latency_ms,
                        "real_llm": bool(use_real_llm),
                    }
                    turn_viol = (
                        _run_invariants(
                            new_state, turn_input_state, turn,
                            context=audit_context,
                        )
                        if invariants else []
                    )
                    # spec polish-prosa (§7): MockLLM tem narração FIXA → o check de
                    # abertura repetida dispararia sempre; irrelevante em mock.
                    if not use_real_llm:
                        turn_viol = [v for v in turn_viol
                                     if v.get("check_id") != "narrative.repeated_opening"]
                    rec.violations = [v["check_id"] for v in turn_viol]
                    rec.violation_details = turn_viol
                    violations.extend(turn_viol)

                    prev_state = state
                    state = new_state

                    if on_turn_end is not None:
                        try:
                            on_turn_end(state, turn)
                        except Exception as e:  # violação de invariante externa = erro
                            errors.append({"turn": turn, "action": action, "exc": repr(e)})
                            rec.error = repr(e)
                except Exception as e:
                    rec.latency_ms = int((time.monotonic() - t0) * 1000)
                    rec.error = repr(e)
                    # Timeout é uma saída própria; os nós já observados continuam
                    # auditáveis sem atribuir o custo a uma rota inconclusa.
                    rec.route = (
                        "timeout" if isinstance(e, PlaytestTimeoutError)
                        else ("combat_agent" if combat_on_entry
                              else (state.get("next", "") or ""))
                    )
                    rec.nodes_executed = list(nodes)
                    rec.node_latency_ms = dict(node_timings)
                    rec.combat_executed = "combat_agent" in nodes or combat_on_entry
                    _fill_state_metrics(rec, state)
                    _attach_telemetry(rec, list(turn_events))
                    rec.rag_events = list(turn_rag_events)
                    rec.memory_writes_by_provenance = _rag_memory_counts(
                        rec.rag_events
                    )
                    _bump_llm_events_budget(llm_calls, rec.llm_events)
                    errors.append({"turn": turn, "action": action, "exc": repr(e)})
                    if isinstance(e, PlaytestTimeoutError):
                        aborted_reason = (
                            f"timeout: {e.phase} excedeu "
                            f"{e.timeout_seconds:g}s"
                        )
                    # mantém o estado anterior; próximo turno continua

                history.append(rec)

                # Uma operação vencida pode continuar apenas no worker daemon.
                # Não inicia outro turno nem toca checkpoints com estado parcial.
                if aborted_reason and aborted_reason.startswith("timeout:"):
                    break

                # spec checkpoints-morte (D1/D6): grava snapshot na cadência; a
                # morte (death_pending) NÃO encerra — o runner sempre "Continua"
                # (auto-restore do checkpoint, ou do início se ainda não houver) e
                # conta a morte. game_over só viria da via voluntária "Aceitar",
                # que o harness nunca escolhe.
                if _cp.should_checkpoint(state, prev_state):
                    checkpoint_snap = _cp.snapshot(state)
                if state.get("death_pending"):
                    _dev = next((e for e in reversed(state.get("event_log") or [])
                                 if isinstance(e, dict) and e.get("type") == "player_downed"), {})
                    _pay = (_dev or {}).get("payload", {}) or {}
                    _continuity = state.get("continuity") or {}
                    death = {
                        "turn": turn,
                        "session_action": int(
                            _continuity.get("session_action_count", turn) or turn
                        ),
                        "canonical_turn": int(
                            (state.get("world") or {}).get("turn_count", 0) or 0
                        ),
                        "timeline_epoch": int(
                            _continuity.get("timeline_epoch", 0) or 0
                        ),
                        "location": _pay.get("location"),
                        "cause": _pay.get("killer"),
                    }
                    deaths_log.append(death)
                    rec.death = death
                    state = _cp.resolve_death_choice(
                        state, "continue", checkpoint=checkpoint_snap, initial_state=initial_snap)
                    save_game_state(state)
                    prev_state = state

                # spec playtest-stop-gameover: game_over (memorial voluntário) ainda
                # encerra — no harness nunca ocorre, mas o gate segue defensivo.
                if state.get("game_over"):
                    aborted_reason = f"player_death (turno {turn})"
                    break

                # Teto de orçamento (5.3 R6) — checado após contabilizar o turno.
                budget_abort = _budget_abort_reason(
                    llm_calls,
                    max_requests=max_requests,
                    max_cost=max_cost,
                    phase=f"turno {turn}",
                )
                if budget_abort:
                    aborted_reason = budget_abort
                    break
        except Exception as exc:
            # Eventos de startup coletados antes da exceção continuam contando:
            # não se perde request/custo só porque a abertura falhou.
            if llm_calls["count"] == 0 and startup_llm_events:
                _bump_llm_events_budget(llm_calls, startup_llm_events)
            errors.append({
                "turn": 0,
                "action": "<startup>",
                "exc": repr(exc),
                "phase": "startup",
            })
            aborted_reason = (
                f"timeout: {exc.phase} excedeu {exc.timeout_seconds:g}s"
                if isinstance(exc, PlaytestTimeoutError)
                else f"startup_error: {type(exc).__name__}"
            )
        finally:
            llm_setter(None)
            if rag_setter:
                rag_setter(None)

        if game_id:
            final_path = os.path.abspath(save_path(game_id))

    result = CampaignResult(
        profile=profile, seed=seed, turns_completed=len(history),
        errors=errors, history=history, final_state=state, save_path=final_path,
        violations=violations, mock=not use_real_llm, aborted_reason=aborted_reason,
        deaths_log=deaths_log, turns_requested=turns,
        startup_llm_events=startup_llm_events,
        startup_rag_events=startup_rag_events,
        invariants_enabled=invariants,
        scenario=scenario,
    )
    campaign_violations = _campaign_experience_violations(
        profile, history, state,
    )
    if campaign_violations:
        violations.extend(campaign_violations)
        if history:
            history[-1].violations.extend(
                item["check_id"] for item in campaign_violations
            )
            history[-1].violation_details.extend(campaign_violations)
    if scenario_module is not None and not (
        aborted_reason and aborted_reason.startswith("timeout:")
    ):
        scenario_violations = scenario_module.oracle_violations(
            str(scenario), result,
        )
        if scenario_violations:
            violations.extend(scenario_violations)
            if history:
                history[-1].violations.extend(
                    item["check_id"] for item in scenario_violations
                )
                history[-1].violation_details.extend(scenario_violations)
    return result


def _fill_state_metrics(
    rec: TurnRecord,
    state: dict,
    *,
    combat_observation: Optional[dict] = None,
) -> None:
    observed = combat_observation or {}
    player = observed.get("player") or state.get("player", {}) or {}
    world = state.get("world", {}) or {}
    rec.location_id = world.get("current_location_id", "") or ""
    rec.player_hp = int(player.get("hp", 0) or 0)
    rec.player_max_hp = int(player.get("max_hp", 0) or 0)
    rec.player_vitality = int(
        player.get("vitalidade", player.get("hp", 0)) or 0
    )
    rec.player_max_vitality = int(
        player.get("max_vitalidade", player.get("max_hp", 0)) or 0
    )
    rec.player_level = int(player.get("level", 1) or 1)
    rec.gold = int(player.get("gold", 0) or 0)
    rec.combat_active = bool((state.get("combat") or {}).get("active"))
    rec.death_pending = bool(state.get("death_pending"))
    rec.game_over = bool(state.get("game_over"))
    # spec balanceamento-classes-pos-playtest (R2): Entropia/Carga por turno.
    rec.entropy = int(player.get("entropy", 0) or 0)
    rec.max_entropy = int(player.get("max_entropy", 0) or 0)
    rec.abyss_charge = int(player.get("abyss_charge", 0) or 0)
    try:
        from combat_mechanics import abyss_tier
        rec.abyss_tier = abyss_tier(player)
    except Exception:
        rec.abyss_tier = ""
    # spec playtest-agente-curioso-entropia (R3): só turno de combate carrega
    # gasto fiel. `combat_executed` inclui o primeiro round disparado dentro do
    # storyteller, que a rota isolada não enxerga.
    if rec.combat_executed:
        rec.entropy_spent = int(player.get("_last_entropy_spent", 0) or 0)
        rec.used_active_ability = bool(player.get("_last_used_active"))
        rec.ability_id = player.get("_last_ability_id")
        rec.class_mechanics = copy.deepcopy(list(
            player.get("_last_class_mechanics") or []
        ))
        combat = observed.get("combat") or state.get("combat") or {}
        rec.reactions = copy.deepcopy(list(combat.get("last_reactions") or []))
        rec.last_tactics = copy.deepcopy(list(
            observed.get("tactics") or combat.get("last_tactics") or []
        ))
    else:
        rec.entropy_spent = 0
        rec.used_active_ability = False
        rec.ability_id = None
        rec.class_mechanics = []
        rec.reactions = []
        rec.last_tactics = []
    rec.player_wounds = copy.deepcopy(dict(player.get("ferimentos") or {}))
    observed_enemies = (
        observed.get("enemies")
        if isinstance(observed.get("enemies"), list)
        else state.get("enemies")
    ) or []
    rec.enemy_wounds = {
        str(enemy.get("id") or enemy.get("name") or f"enemy-{index}"):
            copy.deepcopy(dict(enemy.get("ferimentos") or {}))
        for index, enemy in enumerate(observed_enemies)
        if isinstance(enemy, dict)
    }
    conflict_summary = (
        observed.get("conflict_summary")
        or state.get("conflict_summary")
        or {}
    )
    rec.conflict_wounds = copy.deepcopy(
        dict(conflict_summary.get("ferimentos") or {})
    )
    try:
        from services.memory_provenance import normalize_memory_facts
        memory_records = normalize_memory_facts(state.get("memory_facts"))
    except Exception:
        memory_records = []
    rec.memory_by_provenance = dict(Counter(
        str(record.get("provenance") or "legacy_unverified")
        for record in memory_records
    ))
    rec.memory_by_confidence = dict(Counter(
        str(record.get("confidence") or "speculative") for record in memory_records
    ))
    canonical_turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    rec.stale_speculative_memories = len([
        record for record in memory_records
        if record.get("confidence") == "speculative"
        and record.get("source_turn") is not None
        and canonical_turn - int(record.get("source_turn") or 0) >= 20
    ])
    rec.combat_origin = str((state.get("combat") or {}).get("origin") or "unknown")
    rec.conflict_instance_id = str(
        (state.get("combat") or {}).get("instance_id") or ""
    )
    continuity = state.get("continuity") or {}
    rec.session_action_count = int(continuity.get("session_action_count", canonical_turn) or 0)
    rec.canonical_turn = canonical_turn
    rec.timeline_epoch = int(continuity.get("timeline_epoch", 0) or 0)
    rec.memory_rejections = len([
        row for row in (state.get("memory_rejections") or [])
        if isinstance(row, dict)
    ])
    rec.memory_promotions = sum(
        max(1, int(row.get("count", 1) or 1))
        for row in (state.get("memory_promotions") or [])
        if isinstance(row, dict)
    )
    player_refs = {
        str(player.get("id") or "").strip(),
        str(player.get("name") or "").strip(),
        "player",
    }
    for actor_id, wounds in rec.conflict_wounds.items():
        normalized_id = str(actor_id or "").strip()
        if not normalized_id or normalized_id in player_refs:
            continue
        if isinstance(wounds, dict):
            normalized_wounds = copy.deepcopy(wounds)
        elif isinstance(wounds, list):
            normalized_wounds = {"leve": [], "grave": [], "critico": []}
            for wound in wounds:
                if not isinstance(wound, dict):
                    continue
                category = str(wound.get("categoria") or "").casefold()
                if category in normalized_wounds:
                    normalized_wounds[category].append(copy.deepcopy(wound))
        else:
            continue
        rec.enemy_wounds.setdefault(normalized_id, normalized_wounds)


def _attach_telemetry(rec: TurnRecord, events: List[dict]) -> None:
    """Escolhe o evento representativo do turno (o que casa a rota; senão o
    último) e guarda TODOS os invokes p/ custo agregado (5.3)."""
    rec.llm_events = events
    if not events:
        return
    tier_of_route = {
        "combat_agent": "fast", "storyteller": "fast", "npc_actor": "fast",
        "loot": "fast",
    }.get(rec.route)
    successes = [e for e in events if e.get("status", "success") == "success"]
    candidates = successes or events
    chosen = next(
        (e for e in candidates if e.get("tier") == tier_of_route),
        candidates[-1],
    )
    rec.provider = chosen.get("provider")
    rec.model = chosen.get("model")
    rec.tier = chosen.get("tier")
    rec.fell_back = any(e.get("fell_back") for e in events)


def _bump_llm_events_budget(budget: dict, events: List[dict]) -> None:
    """Conta tentativas de rede, inclusive falhas; build_error não é request."""
    from playtest import pricing
    network = _network_events(events)
    budget["count"] += len(network)
    # Lower bound conservador: uma tentativa que chegou ao provider pode ter
    # consumido tokens mesmo se terminou em erro.
    budget["cost"] += pricing.turn_cost(network)


def _budget_abort_reason(
    budget: dict, *, max_requests: int, max_cost: float, phase: str,
) -> Optional[str]:
    if max_requests and budget["count"] >= max_requests:
        return (
            f"max_requests atingido ({budget['count']}/{max_requests}, {phase})"
        )
    if max_cost and budget["cost"] >= max_cost:
        return f"max_cost atingido ({budget['cost']:.4f}/{max_cost}, {phase})"
    return None


def _run_invariants(
    state: dict,
    prev_state: Optional[dict],
    turn: int,
    *,
    context: Optional[dict] = None,
) -> List[dict]:
    """Chama playtest.invariants.check_all se o módulo existir (Fase 5.2)."""
    try:
        from playtest import invariants as inv
    except Exception as exc:
        return [{
            "check_id": "invariant.runner_crash",
            "severity": "error",
            "turn": turn,
            "message": f"falha ao importar invariantes: {type(exc).__name__}",
            "details": {
                "phase": "import",
                "exception_type": type(exc).__name__,
                "error": str(exc)[:180],
            },
        }]
    try:
        return [v.__dict__ if hasattr(v, "__dict__") else dict(v)
                for v in inv.check_all(
                    state, prev_state, turn, context=context,
                )]
    except Exception as exc:
        return [{
            "check_id": "invariant.runner_crash",
            "severity": "error",
            "turn": turn,
            "message": f"runner de invariantes falhou: {type(exc).__name__}",
            "details": {
                "phase": "check_all",
                "exception_type": type(exc).__name__,
                "error": str(exc)[:180],
            },
        }]
