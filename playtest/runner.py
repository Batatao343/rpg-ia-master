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
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Diretório de saves isolado das campanhas de playtest (spec R7).
PLAYTEST_SAVES_DIR = os.getenv("RPG_PLAYTEST_SAVES_DIR", "saves_playtest")


@dataclass
class TurnRecord:
    """Um turno da campanha. `route` é a rota do GRAFO (storyteller/combat/...),
    NÃO o tier de LLM — não confundir. provider/model/tier vêm do hook de
    telemetria do roteamento (None sob MockLLM)."""
    turn: int
    action: str
    route: str
    latency_ms: int
    provider: Optional[str] = None
    model: Optional[str] = None
    tier: Optional[str] = None
    fell_back: bool = False
    # Fase 5.3: todos os invokes de LLM do turno (p/ custo agregado) e métricas
    # de estado capturadas pós-turno (alimentam a telemetria JSONL).
    llm_events: List[dict] = field(default_factory=list)
    events_applied: int = 0
    events_rejected: int = 0
    error: Optional[str] = None
    location_id: str = ""
    player_hp: int = 0
    player_max_hp: int = 0
    player_level: int = 1
    gold: int = 0
    # spec balanceamento-early-game (R5): campos crus das métricas de balanço.
    combat_active: bool = False
    replanned: bool = False
    violations: List[str] = field(default_factory=list)
    # Narração que o jogador leria no turno (p/ transcript qualitativo do prompt).
    narrative: str = ""


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


def _build_initial_state(profile: str, seed: int) -> dict:
    """Monta o estado inicial da campanha — MESMO shape de api.new_game."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from character_creator import create_player_character
    from gamedata import seed_factions
    from services.chronicle import default_chapter_title
    from world_utils import starting_world

    char_input = dict(_DEFAULT_CHAR)
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
            "mana": final_char["mana"],
            "max_mana": final_char["max_mana"],
            "stamina": final_char["stamina"],
            "max_stamina": final_char["max_stamina"],
            # spec refatoracao-sistema-classes: Entropia é o pool das 5 classes.
            "entropy": final_char.get("entropy", 0),
            "max_entropy": final_char.get("max_entropy", 0),
            "abyss_charge": final_char.get("abyss_charge", 0),
            "gold": 50 * level,
            "alignment": "Neutro",
            "attributes": final_char["attributes"],
            "inventory": final_char["inventory"],
            "equipment": final_char.get("equipment",
                                        {"weapon": None, "armor": None, "accessory": None}),
            "known_abilities": final_char["known_abilities"],
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
    """Em modo MOCK, desliga embeddings REAIS (RAG). Desde a spec
    embeddings-provider há provider vivo (Jina) no `.env`: sem isto, o archivist
    de cada turno bateria na API real durante um playtest offline — rede, custo,
    rate limit (100k tokens/min → lentidão/timeout) e não-determinismo. Em
    `--real` os embeddings reais seguem ativos (fazem parte do teste)."""
    if not active:
        yield
        return
    import rag
    orig_get, orig_for = rag.get_embeddings, rag._embeddings_for_index
    rag.get_embeddings = lambda: None
    rag._embeddings_for_index = lambda _p: None
    try:
        yield
    finally:
        rag.get_embeddings = orig_get
        rag._embeddings_for_index = orig_for


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


def _run_turn(game_graph, state: dict) -> tuple[dict, str]:
    """Invoca o grafo capturando a DECISÃO do `dm_router` (spec R3): a rota fiel
    é o `next` que o router escolheu, não o `next` do estado final (combate/loot
    sobrescrevem). Se o combate está ATIVO na entrada do turno, a rota é
    `combat_agent` (lock de combate). Devolve (estado_final, rota).

    Usa streaming multi-modo: `updates` expõe o dict parcial de cada nó (lê o
    `next` do dm_router na primeira aparição); `values` dá o estado completo
    (o último = resultado equivalente ao `.invoke`)."""
    combat_on_entry = bool((state.get("combat") or {}).get("active"))
    stream = getattr(game_graph, "stream", None)
    if stream is None:
        # Grafo sem streaming (ex.: wrapper de teste que só implementa invoke):
        # cai pro invoke; rota vem do estado final (best-effort, como antes).
        new_state = game_graph.invoke(state)
        route = "combat_agent" if combat_on_entry else (new_state.get("next") or "")
        return new_state, route
    router_next = ""
    final = state
    for mode, chunk in stream(state, stream_mode=["updates", "values"]):
        if mode == "updates" and isinstance(chunk, dict):
            upd = chunk.get("dm_router")
            if isinstance(upd, dict) and not router_next:
                router_next = upd.get("next") or ""
        elif mode == "values":
            final = chunk
    route = "combat_agent" if combat_on_entry else router_next
    return final, route


# --- runner -----------------------------------------------------------------

def run_campaign(profile: str, turns: int = 50, seed: int = 0,
                 use_real_llm: bool = False,
                 on_turn_end: Optional[Callable[[dict, int], None]] = None,
                 invariants: bool = True,
                 max_requests: int = 0,
                 max_cost: float = 0.0) -> CampaignResult:
    """Joga `turns` turnos com o perfil `profile` e devolve o CampaignResult.

    - `on_turn_end(state, turn)` roda após cada turno; exceção conta como erro.
    - `invariants=True` (default) audita cada turno com playtest.invariants
      (se disponível); violações vão p/ `result.violations` sem parar a campanha.
    - `max_requests`/`max_cost` (só fazem sentido com `use_real_llm`) abortam a
      campanha educadamente ao atingir o teto (spec 5.3 R6). 0 = desligado.
    """
    from playtest.profiles import PROFILES
    if profile not in PROFILES:
        raise KeyError(f"perfil desconhecido: {profile!r} (conhecidos: {sorted(PROFILES)})")
    prof = PROFILES[profile]
    prof_rng = random.Random(seed)

    errors: List[dict] = []
    history: List[TurnRecord] = []
    violations: List[dict] = []
    aborted_reason: Optional[str] = None
    llm_calls = {"count": 0, "cost": 0.0}

    # Telemetria do roteamento: hook coleta os invokes do turno corrente.
    from llm_setup import set_llm_telemetry_hook
    turn_events: List[dict] = []

    def _hook(provider, model, tier, latency_ms, fell_back):
        turn_events.append({
            "provider": provider, "model": model,
            "tier": getattr(tier, "value", str(tier)),
            "latency_ms": int(latency_ms), "fell_back": bool(fell_back),
        })

    with _force_mock(active=not use_real_llm), \
            _offline_embeddings(active=not use_real_llm), _isolated_saves():
        _clear_caches()
        random.seed(seed)  # reproduz MockLLM + combate da campanha inteira
        from main import app as game_graph
        from persistence import save_game_state, save_path
        from langchain_core.messages import HumanMessage

        set_llm_telemetry_hook(_hook)
        try:
            state = _build_initial_state(profile, seed)
            game_id = state["game_id"]
            turn_events.clear()
            state = game_graph.invoke(state)
            save_game_state(state)
            prev_state = state

            for turn in range(1, turns + 1):
                action = prof.next_action(state, prof_rng)
                state["messages"].append(HumanMessage(content=action))
                if len(state["messages"]) > 20:
                    state["messages"] = state["messages"][-20:]

                turn_events.clear()
                t0 = time.monotonic()
                events_before = len(state.get("event_log", []) or [])
                plan_before = (state.get("campaign_plan") or {}).get("last_planned_turn")
                combat_on_entry = bool((state.get("combat") or {}).get("active"))
                rec = TurnRecord(turn=turn, action=action, route="", latency_ms=0)
                try:
                    new_state, rec.route = _run_turn(game_graph, state)
                    save_game_state(new_state)
                    rec.latency_ms = int((time.monotonic() - t0) * 1000)
                    rec.replanned = ((new_state.get("campaign_plan") or {})
                                     .get("last_planned_turn") != plan_before)
                    rec.events_applied = len(new_state.get("event_log", []) or []) - events_before
                    rec.events_rejected = len(new_state.get("pending_world_events", []) or [])
                    rec.narrative = _last_ai_text(new_state)
                    _fill_state_metrics(rec, new_state)
                    _attach_telemetry(rec, list(turn_events))
                    _bump_llm_budget(llm_calls, rec)

                    # Invariantes (5.2) — não param a campanha.
                    turn_viol = _run_invariants(new_state, prev_state, turn) if invariants else []
                    # spec polish-prosa (§7): MockLLM tem narração FIXA → o check de
                    # abertura repetida dispararia sempre; irrelevante em mock.
                    if not use_real_llm:
                        turn_viol = [v for v in turn_viol
                                     if v.get("check_id") != "narrative.repeated_opening"]
                    rec.violations = [v["check_id"] for v in turn_viol]
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
                    # rota fiel mesmo no erro: combate na entrada = combat_agent
                    rec.route = "combat_agent" if combat_on_entry else (state.get("next", "") or "")
                    _fill_state_metrics(rec, state)
                    _attach_telemetry(rec, list(turn_events))
                    errors.append({"turn": turn, "action": action, "exc": repr(e)})
                    # mantém o estado anterior; próximo turno continua

                history.append(rec)

                # spec playtest-stop-gameover (R1/R2/R5): morte encerra a campanha
                # no MESMO turno — o grafo vira memorial (main.py:54), turnos
                # seguintes só repetiriam o memorial e poluiriam as métricas.
                if state.get("game_over"):
                    aborted_reason = f"player_death (turno {turn})"
                    break

                # Teto de orçamento (5.3 R6) — checado após contabilizar o turno.
                if max_requests and llm_calls["count"] >= max_requests:
                    aborted_reason = f"max_requests atingido ({llm_calls['count']}/{max_requests})"
                    break
                if max_cost and llm_calls["cost"] >= max_cost:
                    aborted_reason = f"max_cost atingido ({llm_calls['cost']:.4f}/{max_cost})"
                    break
        finally:
            set_llm_telemetry_hook(None)

        final_path = os.path.abspath(save_path(game_id))

    return CampaignResult(
        profile=profile, seed=seed, turns_completed=len(history),
        errors=errors, history=history, final_state=state, save_path=final_path,
        violations=violations, mock=not use_real_llm, aborted_reason=aborted_reason,
    )


def _fill_state_metrics(rec: TurnRecord, state: dict) -> None:
    player = state.get("player", {}) or {}
    world = state.get("world", {}) or {}
    rec.location_id = world.get("current_location_id", "") or ""
    rec.player_hp = int(player.get("hp", 0) or 0)
    rec.player_max_hp = int(player.get("max_hp", 0) or 0)
    rec.player_level = int(player.get("level", 1) or 1)
    rec.gold = int(player.get("gold", 0) or 0)
    rec.combat_active = bool((state.get("combat") or {}).get("active"))


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
    chosen = next((e for e in events if e.get("tier") == tier_of_route), events[-1])
    rec.provider = chosen.get("provider")
    rec.model = chosen.get("model")
    rec.tier = chosen.get("tier")
    rec.fell_back = any(e.get("fell_back") for e in events)


def _bump_llm_budget(budget: dict, rec: TurnRecord) -> None:
    """Contabiliza requests e custo estimado (5.3) do turno no orçamento."""
    from playtest import pricing
    for e in rec.llm_events:
        budget["count"] += 1
    budget["cost"] += pricing.turn_cost(rec.llm_events)


def _run_invariants(state: dict, prev_state: Optional[dict], turn: int) -> List[dict]:
    """Chama playtest.invariants.check_all se o módulo existir (Fase 5.2)."""
    try:
        from playtest import invariants as inv
    except Exception:
        return []
    try:
        return [v.__dict__ if hasattr(v, "__dict__") else dict(v)
                for v in inv.check_all(state, prev_state, turn)]
    except Exception:
        return []
