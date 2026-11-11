"""SPEC-381: rotas de turn (movidas de api.py, sem mudanca)."""

import hashlib
import json
import logging
import os
import queue
import threading
import time
import uuid
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
from typing import Any
from collections.abc import Iterator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from observability.telemetry import log_event as _log_event
import persistence as persistence_module
import progression
from character_creator import create_player_character
from gamedata import seed_factions
from llm_setup import is_simulated
from main import app as game_graph
from persistence import save_path
from services.chronicle import default_chapter_title
from services.prologue import scenario_to_state_seed
from services.prompt_guard import origin_fragment
from services.usage_metering import normalize_attempts, operation_cost
from services.visual_catalog import resolve_turn_visual_state
from world_utils import starting_world
import api_core
from api_core import (
    QuotaExceeded,
    _NOT_A_FAILURE,
    _begin_state_mutation,
    _bind_corr,
    _captured_usage,
    _commit_state_mutation,
    _current_request_id,
    _embedding_attempt_events,
    _embedding_telemetry_hook,
    _enforce_owner_budget,
    _enqueue_turn_art,
    _error_response,
    _fail_operation,
    _llm_attempt_events,
    _llm_log_fields,
    _llm_turn_events,
    _op_rejected,
    _op_replayed,
    _prologue_owner,
    _reject_archived,
    _reject_memorial,
    _release_failed,
    _turn_logger,
    _usage_attempts,
    _validated_receipt,
)
from api_models import ActionRequest, CreateCharacterRequest, GameResponse
from api_presenters import format_response

router = APIRouter()


@router.post("/game/new", response_model=GameResponse)
def new_game(req: CreateCharacterRequest):
    from infrastructure.runtime import get_runtime
    from rag import embedding_usage_scope
    from services.turn_effects import effect_scope
    from services.turn_execution import operation_scope

    _bind_corr(None, getattr(req, "action_id", None))
    claim, request_hash, prior = api_core._begin_create_operation(req)
    if prior is not None:
        return prior
    llm_token = _llm_turn_events.set([])
    attempt_token = _llm_attempt_events.set([])
    embedding_token = _embedding_attempt_events.set([])
    try:
        _enforce_owner_budget(
            "llm_aux"
        )  # SPEC-219 R3; falha aqui encerra o claim (retry com a mesma chave)
        with (
            operation_scope(get_runtime().turn_coordinator if claim else None, claim),
            effect_scope(),
            embedding_usage_scope(_embedding_telemetry_hook),
        ):
            return _create_game(req, claim)
    except Exception as exc:
        if claim is not None:
            try:
                get_runtime().turn_coordinator.fail(
                    claim, type(exc).__name__, usage_events=_captured_usage(claim)
                )
            except Exception as fail_exc:
                _release_failed(claim, fail_exc, exc)
        raise
    finally:
        _llm_turn_events.reset(llm_token)
        _llm_attempt_events.reset(attempt_token)
        _embedding_attempt_events.reset(embedding_token)


def _reputation_ids(final_char: dict) -> tuple[str, str]:
    from services.reputation import resolve_race_id, resolve_region_id

    return resolve_race_id(final_char.get("race")), resolve_region_id(final_char.get("region"))


def _create_game(req: CreateCharacterRequest, claim):
    _log_event("api", "character_create", level="info")

    char_input = {
        "name": req.name,
        "class_name": req.class_name,
        "race": req.race,
        "region": req.region,
        "backstory": req.backstory or "",
        "level": req.level,
        "appearance": req.appearance,
        "visual_exclusions": req.visual_exclusions,
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
        "narrative_summary": f"A jornada de {req.name} começa em {final_char['region']}. {origin_fragment(req.backstory)}".rstrip(),  # SPEC-223 R5
        "archivist_last_run": 0,
        # Fase 3.1: capítulo 1 existe desde o turno 0 (determinístico, sem LLM)
        "chronicle": [
            {
                "title": default_chapter_title(final_char["region"]),
                "started_turn": 0,
                "location": final_char["region"],
                "entries": [],
            }
        ],
        "combat_target": None,
        "loot_source": None,
        # --- Dados do Player ---
        "player": {
            "name": final_char["name"],
            "class_name": final_char["class_name"],
            "race": final_char["race"],
            # SPEC-298 R5: ids estáveis (o nome exibível não serve de chave)
            "race_id": _reputation_ids(final_char)[0],
            "origin_region_id": _reputation_ids(final_char)[1],
            "level": final_char["level"],
            "xp": final_char.get("xp", 0),
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
            "vitalidade": final_char.get(
                "vitalidade", final_char.get("max_vitalidade", final_char["max_hp"])
            ),
            "max_vitalidade": final_char.get("max_vitalidade", final_char["max_hp"]),
            "vitalidade_max_penalty": final_char.get("vitalidade_max_penalty", 0),
            "ferimento_espacos": final_char.get("ferimento_espacos", {}),
            "ferimentos": final_char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
            "inventory": final_char["inventory"],
            # Fase 4.3: slots do creator (auto-equip) — sem isto o HUD nasce sem arma
            "equipment": final_char.get(
                "equipment", {"weapon": None, "armor": None, "accessory": None}
            ),
            "known_cards": final_char.get("known_cards", []),
            "prepared_cards": final_char.get("prepared_cards", []),
            "card_usage": final_char.get("card_usage", {}),
            "virtue_cards": final_char.get("virtue_cards", []),
            "evolved_cards": final_char.get("evolved_cards", {}),
            "pending_choices": final_char.get("pending_choices", []),
            # SPEC-227 R9: nível > 1 sobe pelo pipeline de XP — carrega o rastro.
            **{
                k: final_char[k]
                for k in ("subclass", "progression_events", "progression_grants")
                if k in final_char
            },
            "defense": final_char["defense"],
            "attack_bonus": final_char.get("attack_bonus", 0),
            "active_conditions": [],
            # Fase 2.5b: traits raciais calculados no creator
            "racial_traits": final_char.get("racial_traits", []),
            "condition_resists": final_char.get("condition_resists", []),
            "racial_save_bonus": final_char.get("racial_save_bonus", {}),
            "appearance": req.appearance,
            "visual_exclusions": req.visual_exclusions,
        },
        "world": starting_world(final_char["region"], req.level),
        "messages": [
            SystemMessage(content=f"A jornada de {req.name} começa em {final_char['region']}."),
            HumanMessage(
                content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {req.level}."
            ),
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
        "continuity": {
            "session_action_count": 0,
            "timeline_epoch": 0,
            "last_checkpoint_turn": 0,
            "death_history": [],
        },
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        # --- Fase 2.5: mundo estruturado ---
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
        "art_arc_budgets": {},
        "art_generation_ledger": [],
    }
    initial_state["player"] = progression.normalize_player_progression(initial_state["player"])
    from services import world_calendar

    world_calendar.init_new_game(initial_state)  # SPEC-303 R5: calendário ancorado no dia 1

    # spec inicio-personalizado (R5): cenário aprovado semeia plano pessoal,
    # capítulo 1, NPCs da história e a cena de abertura. Sem scenario, o
    # estado acima fica intocado (R6 — fluxo clássico byte a byte).
    pool_pending = (
        None  # SPEC-351 R18: (scenario, semente verificada, region_id) p/ depois de persistir
    )
    if req.scenario is not None:
        from services import opening_threads
        from services.prologue import revalidate_scenario, verified_seed

        start_loc_id = initial_state["world"].get("current_location_id", "")
        scenario_in, menu, pool_seed = req.scenario, None, None
        if opening_threads.mode() == "on" and (
            scenario_in.thread_refs or scenario_in.plot_npc_id or scenario_in.personal_npc
        ):
            region_id = opening_threads.region_of_location(start_loc_id)
            menu = opening_threads.thread_menu(
                region_id,
                backstory=req.backstory or "",
                start_location_id=start_loc_id,
                postura=req.class_name,
                race=req.race,
            )
            scenario_in = revalidate_scenario(scenario_in, menu)
            pool_seed = verified_seed(
                scenario_in, req.scenario_token, _prologue_owner(), start_loc_id
            )
            pool_pending = (scenario_in, pool_seed, region_id)
        seed = scenario_to_state_seed(
            scenario_in,
            {**char_input, "game_id": new_game_id},
            start_loc_id=start_loc_id,
            menu=menu,
            pool_seed=pool_seed,
        )
        initial_state["campaign_plan"] = seed["campaign_plan"]
        initial_state["chronicle"][0]["title"] = seed["chronicle_title"]
        initial_state["npcs"] = seed["npcs"]
        initial_state["messages"][-1] = HumanMessage(content=seed["opening_message"])
        initial_state["narrative_summary"] += seed["summary_extra"]

    # 3. Roda o Grafo
    try:
        final_state = game_graph.invoke(initial_state)
        # A abertura posiciona a linha do tempo, mas não é ação do jogador.
        from services.continuity import mark_checkpoint

        final_state["continuity"] = mark_checkpoint(
            {**(final_state.get("continuity") or {}), "session_action_count": 0},
            canonical_turn=int((final_state.get("world") or {}).get("turn_count", 0) or 0),
        )
        visual_key = f"new:{new_game_id}"
        final_state.update(
            resolve_turn_visual_state(initial_state, final_state, action_key=visual_key)
        )
        response = format_response(final_state, cue_action_key=visual_key)
        from services.presentation_history import record_history

        record_history(final_state, response.message, include_input=False)
        if claim is not None:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            version, _receipt = get_runtime().turn_coordinator.commit_create(
                current_principal(),
                claim,
                final_state,
                receipt={"response": response.model_dump(mode="json")},
                checkpoint=True,
                usage_events=_captured_usage(claim),
            )
            final_state["_storage_version"] = version
        else:
            if not api_core.save_game_state(final_state):
                raise RuntimeError("falha ao persistir jogo novo")
            # checkpoint INICIAL: a morte sempre possui um ponto de retorno.
            from persistence import save_checkpoint

            if not save_checkpoint(final_state):
                import persistence as persistence_mod

                persistence_mod.delete_save(new_game_id)
                raise RuntimeError("falha ao persistir checkpoint inicial")
        if pool_pending is not None:  # SPEC-351 R18: só depois de persistir; nunca quebra a request
            from services.prologue import submit_personal_npc

            submit_personal_npc(
                pool_pending[0],
                pool_pending[1],
                game_id=new_game_id,
                region_id=pool_pending[2],
                char_input=char_input,
            )
        return response
    except Exception as e:
        # Auditoria A6: detalhe interno só no log do servidor, nunca na resposta.
        _log_event("api", "new_game_failed", level="error", error=type(e).__name__)
        raise HTTPException(status_code=500, detail="Erro interno ao criar o jogo.")


def _append_player_input(state: dict, input_text: str) -> None:
    """Anexa a ação do jogador ao histórico (mesma regra dos dois endpoints)."""
    state["messages"].append(HumanMessage(content=input_text))
    if len(state["messages"]) > 20:
        state["messages"] = state["messages"][-20:]


_ACTION_LEDGER_LIMIT = 64


def _mark_action_processed(state: dict, action_id: str | None) -> None:
    if not action_id:
        return
    ledger = [
        str(value)
        for value in (state.get("processed_action_ids") or [])
        if value and str(value) != action_id
    ]
    ledger.append(action_id)
    state["processed_action_ids"] = ledger[-_ACTION_LEDGER_LIMIT:]


def _prepare_checkpoint(state: dict, previous: dict) -> bool:
    """Marca o snapshot antes do commit; o adapter Postgres o grava na mesma tx."""
    if (state.get("combat_simulation") or {}).get("enabled"):
        return False
    from services import checkpoints as _cp

    if not _cp.should_checkpoint(state, previous):
        return False
    if api_core._database_profile():
        # Postgres grava turno+checkpoint na mesma tx; legacy só marca depois
        # que o arquivo existir (SPEC-228 R5).
        from services.continuity import mark_checkpoint

        state["continuity"] = mark_checkpoint(
            state.get("continuity"),
            canonical_turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
        )
    return True


def _prepare_chronicle_derivatives(state: dict) -> None:
    """Legacy recebe digest extrativo local; Postgres agenda worker após commit."""
    if api_core._database_profile():
        return
    from services.chronicle import ensure_chronicle_ids
    from services.chronicle_compression import extractive_digest, should_compress

    chapters = ensure_chronicle_ids(
        state.get("chronicle") or [],
        game_id=str(state.get("game_id", "legacy")),
    )
    for index, chapter in enumerate(chapters):
        if should_compress(chapter, closed=index < len(chapters) - 1):
            chapter["digest"] = extractive_digest(chapter)
    state["chronicle"] = chapters


def _schedule_chronicle_jobs(state: dict) -> None:
    if not api_core._database_profile():
        return
    try:
        from infrastructure.pgvector_memory import PgVectorMemoryStore
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime
        from services.chronicle_repository import ChronicleRepository

        runtime = get_runtime()
        if runtime.resources and isinstance(runtime.memory_store, PgVectorMemoryStore):
            ChronicleRepository(runtime.resources[0], runtime.memory_store).enqueue_due(
                current_principal(),
                state,
            )
    except Exception as exc:
        logging.getLogger("rpg.chronicle").warning(
            "falha ao agendar derivado da crônica: %s",
            type(exc).__name__,
        )


def _operation_hash(req: ActionRequest) -> str:
    payload = req.model_dump(mode="json", exclude={"action_id"})
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _begin_turn_operation(state: dict, req: ActionRequest):
    """Retorna ``(claim, request_hash, receipt_response)`` no perfil durável."""
    if not api_core._database_profile():
        return None, "", None
    if not req.action_id:
        raise HTTPException(status_code=400, detail="action_id é obrigatório neste perfil.")
    from infrastructure.contracts import Conflict, LeaseHeld, StaleVersion
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    runtime = get_runtime()
    principal = current_principal()
    operation_id = uuid.UUID(req.action_id)
    request_hash = _operation_hash(req)

    def receipt_fn():
        return _validated_receipt(
            runtime.turn_coordinator,
            principal,
            operation_id,
            game_id=uuid.UUID(str(state["game_id"])),
            kind="turn",
            request_hash=request_hash,
        )

    receipt = receipt_fn()
    if receipt and isinstance(receipt.get("response"), dict):
        _op_replayed("turn", operation_id)
        return None, request_hash, GameResponse.model_validate(receipt["response"])
    try:
        claim = runtime.turn_coordinator.claim(
            principal,
            operation_id,
            game_id=uuid.UUID(str(state["game_id"])),
            kind="turn",
            request_hash=request_hash,
            base_version=int(state.get("_storage_version", 0) or 0),
        )
    except Conflict as exc:
        receipt = receipt_fn()
        if receipt and isinstance(receipt.get("response"), dict):
            _op_replayed("turn", operation_id)
            return None, request_hash, GameResponse.model_validate(receipt["response"])
        code = "operation_in_progress" if isinstance(exc, LeaseHeld) else "operation_conflict"
        if isinstance(exc, StaleVersion):
            code = "stale_version"
        _op_rejected(code, "turn", operation_id)
        raise HTTPException(status_code=409, detail=code) from exc
    return claim, request_hash, None


def _commit_turn(
    state: dict,
    response: GameResponse,
    *,
    claim,
    request_hash: str,
    checkpoint: bool,
    latency_ms: int,
    llm_events: list[dict],
    llm_attempts: list[dict],
    embedding_attempts: list[dict] | None = None,
) -> None:
    from services.presentation_history import record_history

    presentation_entry_id = record_history(state, response.message)
    if claim is None:
        if checkpoint:
            # SPEC-228 R5: checkpoint ANTES do save; só marca após gravar.
            # Falha vira adiamento (warning), nunca 500 com turno já salvo.
            from services import checkpoints as _cp
            from services.continuity import mark_checkpoint, normalize

            turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
            if _cp.write_now(state):
                state["continuity"] = mark_checkpoint(state.get("continuity"), canonical_turn=turn)
            else:
                meta = normalize(state.get("continuity"), canonical_turn=turn)
                meta["checkpoint_deferred"] = True
                state["continuity"] = meta
                _log_event("api", "checkpoint_deferred", level="warning")
        api_core._require_saved(state, detail="turno")
        _schedule_chronicle_jobs(state)
        return
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    runtime = get_runtime()
    commit = getattr(runtime.turn_coordinator, "commit_game", None)
    if not callable(commit):
        raise RuntimeError("coordinator durável sem commit transacional")
    llm_usage_events = normalize_attempts(
        _usage_attempts(llm_events, llm_attempts),
        operation_id=claim.operation_id,
        component=f"llm:{claim.lease_token}",
    )
    usage_events = [
        *llm_usage_events,
        *normalize_attempts(
            embedding_attempts or [],
            operation_id=claim.operation_id,
            component=f"embedding:{claim.lease_token}",
            category="embedding",
        ),
    ]
    from observability.metrics import metrics

    db_started = time.monotonic()
    from observability.telemetry import span

    try:
        with span("db.commit_turn", operation="commit_turn"):
            version, _receipt = commit(
                current_principal(),
                claim,
                state,
                receipt={"response": response.model_dump(mode="json")},
                input_sha256=request_hash,
                latency_ms=latency_ms,
                llm_cost_usd=operation_cost(usage_events),
                usage_events=usage_events,
                checkpoint=checkpoint,
                presentation_entry_id=presentation_entry_id,
            )
    except Exception:
        metrics.increment("rpg_turn_commits_total", {"outcome": "error"})
        metrics.observe(
            "rpg_db_duration_seconds",
            {"operation": "commit_turn", "outcome": "error"},
            time.monotonic() - db_started,
        )
        raise
    metrics.increment("rpg_turn_commits_total", {"outcome": "ok"})
    metrics.observe(
        "rpg_db_duration_seconds",
        {"operation": "commit_turn", "outcome": "ok"},
        time.monotonic() - db_started,
    )
    state["_storage_version"] = version
    _schedule_chronicle_jobs(state)


def _apply_play_list(state: dict, req: ActionRequest, active_enemies: list[dict]) -> None:
    """SPEC-328 R13: `jogadas` → `TurnDeclaration.jogadas` (ordem preservada). Só com o
    baralho `on` e pilhas no conflito; o motor valida mão/Fôlego/Entropia (R15)."""
    from services import card_piles
    from services import cards as _cards_svc
    from services import combat_targeting as _targeting

    if card_piles.mode() != "on" or not isinstance((state.get("combat") or {}).get("pilhas"), dict):
        raise HTTPException(
            409,
            detail={
                "code": "deck_off",
                "message": "Este conflito não usa o Baralho de Conflito.",
            },
        )
    default_target = str(active_enemies[0].get("id")) if active_enemies else None
    steps: list[dict] = []
    for play_index, play in enumerate(req.jogadas or []):
        if (
            play.action_kind == "discard"
        ):  # SPEC-368 R6: descartar por Fôlego; sem alvo, o motor valida
            if not play.card_id:
                raise HTTPException(
                    422,
                    detail={
                        "code": "validation_failed",
                        "message": "Descartar pede a Carta (card_id).",
                    },
                )
            steps.append({"kind": "discard", "card_id": play.card_id})
            continue
        bad = _targeting.check_declared_target(
            state,
            card_id=play.card_id,
            action_kind=play.action_kind,
            maneuver=play.maneuver,
            target_id=play.target_id,
        )
        if bad:
            raise HTTPException(
                409,
                detail={
                    "code": "invalid_target",
                    "invalid_reason": bad,
                    "message": "O alvo escolhido deixou de ser válido. Escolha de novo.",
                    "play_index": play_index,  # SPEC-363 R21: só esta jogada sai da fila
                    "card_id": play.card_id,
                },
            )
        if play.card_id:
            from agents.combat import _default_card_target

            steps.append(
                {
                    "kind": "card",
                    "card_id": play.card_id,
                    "target_id": play.target_id
                    or _default_card_target(
                        _cards_svc.get_card(play.card_id) or {}, default_target
                    ),
                    "params": {
                        "ruptura": bool(play.ruptura),
                        **({"descartar": list(play.descartar)} if play.descartar else {}),
                    },
                }
            )
        elif play.action_kind == "maneuver" and play.maneuver:
            steps.append(
                {"kind": "maneuver", "maneuver": play.maneuver, "target_id": default_target}
            )
        else:
            steps.append(
                {
                    "kind": play.action_kind or "attack",
                    "target_id": play.target_id or default_target,
                }
            )
    state["player_reaction_card_id"] = req.reaction_card_id
    state["combat_declaration"] = {
        "actor_id": "player",
        "acao": steps[0],
        "jogadas": steps,
        "reaction_card_id": req.reaction_card_id,
    }


def _apply_action_options(state: dict, req: ActionRequest) -> None:
    """Traduz seleções da UI para a declaração que o motor já consome."""
    if not (state.get("combat") or {}).get("active"):
        return
    active_enemies = [
        enemy
        for enemy in (state.get("enemies") or [])
        if not enemy.get("dead")
        and enemy.get("status", "ativo") not in ("morto", "fugiu", "rendido", "incapacitado")
    ]
    if req.jogadas:
        return _apply_play_list(state, req, active_enemies)
    explicit_target = req.target_id
    if req.card_id and explicit_target:
        # SPEC-205 R10: Carta de suporte nunca mira um inimigo vindo da UI.
        from services import cards as _cards_svc

        _effect = str(
            ((_cards_svc.get_card(req.card_id) or {}).get("efeito") or {}).get("kind") or ""
        )
        from services.conflict_turn import _SUPPORT_EFFECTS as _SUPPORT

        if _effect in _SUPPORT and explicit_target in {str(e.get("id")) for e in active_enemies}:
            explicit_target = None
    # SPEC-205 R9: alvo explícito fora de `valid_targets` (estado velho) é
    # rejeitado na borda, sem tocar Entropia/frequência nem rodar turno.
    from services import combat_targeting as _targeting

    _bad = _targeting.check_declared_target(
        state,
        card_id=req.card_id,
        action_kind=req.action_kind,
        maneuver=req.maneuver,
        target_id=explicit_target,
    )
    if _bad:
        raise HTTPException(
            409,
            detail={
                "code": "invalid_target",
                "invalid_reason": _bad,
                "message": "O alvo escolhido deixou de ser válido. Escolha de novo.",
            },
        )
    state["player_reaction_card_id"] = req.reaction_card_id
    target_id = explicit_target or (str(active_enemies[0].get("id")) if active_enemies else None)
    action = None
    if req.card_id:
        card_target = explicit_target
        if not card_target:
            # SPEC-232 (ex-SPEC-199 R12): Carta benéfica sem alvo explícito mira o
            # próprio jogador — nunca herda o 1º inimigo (cura no inimigo).
            from agents.combat import _default_card_target
            from services import cards as cards_svc

            card_target = _default_card_target(
                cards_svc.get_card(req.card_id) or {},
                str(active_enemies[0].get("id")) if active_enemies else None,
            )
        action = {
            "kind": "card",
            "card_id": req.card_id,
            "target_id": card_target,
            "params": {"ruptura": bool(req.ruptura)},
        }
    elif req.action_kind == "maneuver" and req.maneuver:
        action = {
            "kind": "maneuver",
            "maneuver": req.maneuver,
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


def _latency_log_fields(
    timeline,
    llm_events: list[dict] | None,
    llm_attempts: list[dict] | None,
    *,
    action_id: str | None = None,
    input_text: str = "",
) -> dict[str, Any]:
    """SPEC-200 R5/R17: campos ADITIVOS da linha `rpg.turn`. Nunca levanta e
    nunca leva texto do jogador nem game_id cru (so contagens, ms e pseudonimos)."""
    if timeline is None:
        return {}
    try:
        from decimal import Decimal

        from observability.latency import input_size
        from observability.telemetry import pseudonym

        attempts = list(llm_attempts or [])
        network = [
            a
            for a in attempts
            if a.get("network_attempted", a.get("outcome") not in {"build_error", "circuit_open"})
        ]
        by_tier: dict[str, dict[str, Any]] = {}
        for item in network:
            row = by_tier.setdefault(
                str(item.get("tier") or "?"),
                {"attempts": 0, "failed": 0, "fallbacks": 0, "latency_ms": 0},
            )
            row["attempts"] += 1
            row["failed"] += 0 if item.get("outcome") in _NOT_A_FAILURE else 1
            row["fallbacks"] += (
                1 if item.get("fell_back") and item.get("outcome") != "hedge_lost" else 0
            )
            row["latency_ms"] += int(item.get("latency_ms") or 0)
        with_usage = [a for a in network if a.get("usage")]
        normalized = normalize_attempts(network, operation_id=uuid.UUID(int=0))
        priced = [(a, e) for a, e in zip(network, normalized) if a.get("usage")]
        for item, event in priced:
            row = by_tier[str(item.get("tier") or "?")]
            row["cost_usd"] = str(Decimal(row.get("cost_usd", "0")) + event.cost_usd)
        if not network:
            cost_usd, basis = "0", "none"
        elif not with_usage:
            cost_usd, basis = None, "unavailable"  # nunca zero fabricado
        else:
            cost_usd = str(sum((e.cost_usd for _, e in priced), Decimal("0")))
            basis = "usage" if len(with_usage) == len(network) else "partial"
        reported = [a["usage"] for a in with_usage if "cached_tokens" in a["usage"]]
        cached_total = sum(int(u.get("cached_tokens") or 0) for u in reported) if reported else None
        input_total = sum(int(u.get("input_tokens") or 0) for u in reported)
        ratio = round(cached_total / input_total, 4) if reported and input_total > 0 else None
        timeline.extra.update(
            {
                "action_ref": pseudonym(action_id) if action_id else None,
                "execution_mode": os.getenv("RPG_TURN_EXECUTION", "sequential").strip().lower(),
                "attribution": "interval",
                "llm_attempts": len(attempts),
                "llm_fallbacks": sum(
                    1 for a in network if a.get("fell_back") and a.get("outcome") != "hedge_lost"
                ),
                "llm_failed_attempts": sum(
                    1 for a in network if a.get("outcome") not in _NOT_A_FAILURE
                ),
                "providers_used": sorted({str(a.get("provider") or "?") for a in network}),
                "cost_usd": cost_usd,
                "cost_usd_basis": basis,
                "llm_by_tier": by_tier,
                "cached_tokens": cached_total,
                "cache_hit_ratio": ratio,
                "input_chars": len(input_text or ""),
                "input_size": input_size(len(input_text or "")),
                "rag_cache": "not_instrumented",
            }
        )
        timeline.extra.setdefault("lock_wait_ms", 0)
        return timeline.fields()
    except Exception:
        return {}


def _emit_turn_latency_metrics(timeline, route: str) -> None:
    """SPEC-200 R6: fases por turno (labels fechados). Falha nao quebra o turno."""
    try:
        from observability.metrics import metrics

        for phase_name, ms in timeline.phase_ms().items():
            metrics.observe(
                "rpg_turn_phase_seconds", {"route": route, "phase": phase_name}, ms / 1000
            )
    except Exception:
        pass


def _turn_route(timeline) -> str:
    return (
        "/game/action/stream" if getattr(timeline, "transport", "") == "stream" else "/game/action"
    )


def _log_turn(
    state: dict,
    t0: float,
    eventos_antes: int,
    error: str | None,
    llm_events: list[dict] | None = None,
    *,
    rejections_antes: int = 0,
    llm_attempts: list[dict] | None = None,
    latency_fields: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    fallbacks: list[str] | None = None,
) -> None:
    from observability.telemetry import correlation, pseudonym, safe_json

    _turn_logger.info(
        safe_json(
            {
                "event": "turn",
                "evt": "turn",
                "game_id_ref": pseudonym(state.get("game_id", "?")),
                **correlation(),
                "turn": (state.get("world") or {}).get("turn_count", 0),
                "route": state.get("next", ""),
                "latency_ms": (
                    latency_ms if latency_ms is not None else int((time.monotonic() - t0) * 1000)
                ),
                "events_applied": (len(state.get("event_log", [])) - eventos_antes)
                if not error
                else 0,
                "events_rejected": (
                    max(0, len(state.get("event_rejections", []) or []) - rejections_antes)
                    if not error
                    else 0
                ),
                "error": error,
                # SPEC-247 R1: fonte da decisao de rota + motivo de fallback (codigos fechados)
                "route_source": state.get("route_source"),
                "route_fallback_reason": state.get("route_fallback_reason"),
                "fallbacks": dict(Counter(fallbacks or [])),  # SPEC-250 R5: node.reason -> contagem
                "narrative_rejected": dict(
                    getattr(fallbacks, "counters", None) or {}
                ),  # SPEC-252 R2: kind -> contagem
                **_llm_log_fields(llm_events, llm_attempts),
                **(latency_fields or {}),
            }
        )
    )


def _record_audit_trace(
    new_state: dict,
    previous_state: dict,
    *,
    action_id,
    timeline,
    llm_events,
    llm_attempts,
    input_text: str,
) -> None:
    """SPEC-207 R7: trilha de auditoria por turno, dentro do commit. Nunca derruba
    o turno (falha vira trilha ausente, marcada `unavailable` no export)."""
    try:
        from services.audit_trace import record_turn_trace

        # Popula os campos SPEC-200 da timeline (idempotente; recomputado no log).
        _latency_log_fields(
            timeline, llm_events, llm_attempts, action_id=action_id, input_text=input_text
        )
        record_turn_trace(
            new_state,
            previous_state=previous_state,
            action_id=action_id,
            timeline=timeline,
            llm_attempts=llm_attempts,
        )
    except Exception as exc:
        _log_event("api", "audit_trace_not_written", level="warning", error=type(exc).__name__)


def _run_turn(
    state: dict,
    input_text: str,
    action_id: str | None = None,
    *,
    claim=None,
    request_hash: str = "",
    progress=None,
    timeline=None,
    out: dict | None = None,
    pre_drain: bool = False,
) -> GameResponse:
    from rag import embedding_usage_scope
    from services.audit_trace import collecting as _audit_collecting
    from services.turn_effects import effect_scope

    with effect_scope(), embedding_usage_scope(_embedding_telemetry_hook), _audit_collecting():
        return _run_turn_collected(
            state,
            input_text,
            action_id,
            claim=claim,
            request_hash=request_hash,
            progress=progress,
            timeline=timeline,
            out=out,
            pre_drain=pre_drain,
        )


def _early_event(early_state: dict, node: str, update: Any) -> dict | None:
    """SPEC-316: texto antecipado do no narrador `node` (ou None). Nunca derruba o turno."""
    try:
        from services.turn_delivery import early_narrative

        text = early_narrative(early_state["acc"], update, node)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("sse", "early_narrative_failed", exc)
        return None
    return {"text": text, "node": node} if text else None


def _run_turn_collected(
    state: dict,
    input_text: str,
    action_id: str | None = None,
    *,
    claim=None,
    request_hash: str = "",
    progress=None,
    timeline=None,
    out: dict | None = None,
    pre_drain: bool = False,
) -> GameResponse:
    """Miolo do turno (spec streaming-turno-sse R2): grafo + save + log.
    Compartilhado pelo POST clássico e pelo stream — carga/validações ficam
    nos endpoints. Levanta HTTPException(500) genérica em falha (A6)."""
    from observability import latency as _lat

    if timeline is None:
        timeline = _lat.TurnTimeline(transport="post")
    t0 = time.monotonic()
    acc_token = _llm_turn_events.set([])
    attempt_token = _llm_attempt_events.set([])
    embedding_token = _embedding_attempt_events.set([])
    from observability.telemetry import begin_fallbacks, end_fallbacks

    fallback_token, fallbacks = begin_fallbacks()  # SPEC-250 R5
    timeline_token = _lat.bind(timeline)
    if pre_drain:
        # SPEC-213 (perfil DB): projeção pendente drenada na cerca do turno, com o
        # uso de LLM no ledger do turno e a memória no mesmo commit; ANTES da ação
        # nova entrar no histórico (o derivado só vê o canônico já commitado).
        state = _pre_drain_in_turn(state)
    _append_player_input(state, input_text)
    eventos_antes = len(state.get("event_log", []))
    rejections_antes = len(state.get("event_rejections", []) or [])

    from services import turn_delivery as _delivery

    # SPEC-316: so o stream (progress != None) antecipa a narracao; POST nao muda.
    early_on = progress is not None and _delivery.early_mode() != "off"
    early_state = {"acc": state}

    def _timeline_progress(chunk):
        # SPEC-200 R3: atribuicao por intervalo entre updates (criterio da SPEC-116).
        early_event = None
        try:
            mode, data = chunk
            if mode == "values":
                early_state["acc"] = data  # estado ANTES da proxima update
            if mode == "updates":
                for node, update in (data or {}).items():
                    timeline.node_done(str(node))
                    if node == "dm_router" and isinstance(update, dict) and update.get("next"):
                        timeline.extra["route_next"] = str(update["next"])
                    if early_on and node in _delivery.NARRATING_NODES:
                        calc_t0 = time.monotonic()
                        early_event = _early_event(early_state, str(node), update)
                        # P2-3: custo do calculo antecipado no caminho critico (medido na §6)
                        timeline.extra["early_calc_ms"] = int(
                            timeline.extra.get("early_calc_ms", 0)
                        ) + int((time.monotonic() - calc_t0) * 1000)
        except Exception:
            pass
        if progress is not None:
            progress(chunk)
            if early_event is not None:
                progress(("early_narrative", early_event))

    # SPEC-319: tokens do narrador so no stream SSE (POST/CLI/playtest seguem no invoke).
    # `shadow` tambem streama (mede o TTFT), mas o SSE descarta os deltas.
    from services import narrative_sink as _nsink

    sink_token = None
    if progress is not None and _nsink.token_stream_mode() != "off":

        def _token_sink(kind: str, text: str) -> None:
            progress(("narrative_delta" if kind == "delta" else "narrative_reset", {"text": text}))

        sink_token = _nsink.bind(_token_sink, lambda: early_state["acc"])

    try:
        previous_state = deepcopy(state)
        from services.turn_execution import execute_graph

        new_state = execute_graph(
            game_graph,
            state,
            progress=_timeline_progress if hasattr(game_graph, "stream") else progress,
        )
        timeline.settle()
        with timeline.phase(_lat.TurnPhase.PERSISTENCE):
            visual_key = action_id or f"turn:{(new_state.get('world') or {}).get('turn_count', 0)}"
            new_state.update(
                resolve_turn_visual_state(previous_state, new_state, action_key=visual_key)
            )
            _enqueue_turn_art(previous_state, new_state, visual_key)
            _mark_action_processed(new_state, action_id)
            # SPEC-213 R4: versão canônica sobe 1 por turno commitado; derivados
            # adiados (modo A) ficam `pending` e são drenados pelo dono do lock.
            from services.projections import stamp_commit

            stamp_commit(new_state, action_id)
            checkpoint = _prepare_checkpoint(new_state, state)
            _prepare_chronicle_derivatives(new_state)
            response = format_response(new_state, cue_action_key=visual_key)
            llm_events = _llm_turn_events.get() or []
            llm_attempts = _llm_attempt_events.get() or []
            _record_audit_trace(
                new_state,
                previous_state,
                action_id=action_id,
                timeline=timeline,
                llm_events=llm_events,
                llm_attempts=llm_attempts,
                input_text=input_text,
            )
            _commit_turn(
                new_state,
                response,
                claim=claim,
                request_hash=request_hash,
                checkpoint=checkpoint,
                latency_ms=int((time.monotonic() - t0) * 1000),
                llm_events=llm_events,
                llm_attempts=llm_attempts,
                embedding_attempts=_embedding_attempt_events.get() or [],
            )
        timeline.finish()
        timeline.extra.setdefault("route_next", str(new_state.get("next", "") or ""))
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        timeline.submit_log(
            lambda: _log_turn(
                new_state,
                t0,
                eventos_antes,
                None,
                llm_events,
                rejections_antes=rejections_antes,
                llm_attempts=llm_attempts,
                fallbacks=fallbacks,
                latency_ms=elapsed_ms,
                latency_fields=_latency_log_fields(
                    timeline, llm_events, llm_attempts, action_id=action_id, input_text=input_text
                ),
            )
        )
        from observability.metrics import metrics

        route_label = _turn_route(timeline)
        metrics.observe(
            "rpg_turn_duration_seconds",
            {"route": route_label, "outcome": "ok", "simulated": str(is_simulated()).lower()},
            time.monotonic() - t0,
        )
        _emit_turn_latency_metrics(timeline, route_label)
        if out is not None:
            out["state"] = new_state
        return response
    except Exception as e:
        from observability.metrics import metrics

        metrics.observe(
            "rpg_turn_duration_seconds",
            {
                "route": _turn_route(timeline),
                "outcome": "error",
                "simulated": str(is_simulated()).lower(),
            },
            time.monotonic() - t0,
        )
        timeline.finish()
        if claim is not None:
            try:
                from infrastructure.runtime import get_runtime

                failed_usage = normalize_attempts(
                    _usage_attempts(_llm_turn_events.get(), _llm_attempt_events.get()),
                    operation_id=claim.operation_id,
                    component=f"llm:{claim.lease_token}",
                )
                failed_usage.extend(
                    normalize_attempts(
                        _embedding_attempt_events.get() or [],
                        operation_id=claim.operation_id,
                        component=f"embedding:{claim.lease_token}",
                        category="embedding",
                    )
                )
                get_runtime().turn_coordinator.fail(
                    claim, type(e).__name__, usage_events=failed_usage
                )
            except Exception as fail_exc:
                _release_failed(claim, fail_exc, e)
        _log_turn(
            state,
            t0,
            eventos_antes,
            type(e).__name__,
            _llm_turn_events.get(),
            rejections_antes=rejections_antes,
            fallbacks=fallbacks,
            llm_attempts=_llm_attempt_events.get(),
            latency_fields=_latency_log_fields(
                timeline,
                _llm_turn_events.get(),
                _llm_attempt_events.get(),
                action_id=action_id,
                input_text=input_text,
            ),
        )
        from observability.telemetry import safe_stack

        _log_event("api", "turn_failed", level="error", error=type(e).__name__, stack=safe_stack(e))
        raise HTTPException(status_code=500, detail="Erro interno ao processar o turno.")
    finally:
        if sink_token is not None:
            _nsink.unbind(sink_token)
        end_fallbacks(fallback_token)
        _lat.unbind(timeline_token)
        _llm_turn_events.reset(acc_token)
        _llm_attempt_events.reset(attempt_token)
        _embedding_attempt_events.reset(embedding_token)


def _projection_owner() -> bool:
    """SPEC-213 R9/R10: a API é dona da projeção em todos os perfis. Legacy: o
    lock de processo segura o turno até drenar (modo A). Perfis com banco: o
    commit do turno grava o job `project_archive` (outbox, modo B) e a própria
    API o executa logo após responder; worker/cron e o próximo turno (dentro da
    sua cerca) são os fallbacks duráveis."""
    return True


def _pre_drain_in_turn(state: dict) -> dict:
    """Perfil DB: projeção pendente drenada DENTRO da cerca do turno (R10/R15),
    antes da ação do jogador entrar no histórico; memória vai no mesmo commit."""
    from services.projections import has_pending, run_pending

    if not has_pending(state):
        return state
    try:
        return run_pending(state)
    except Exception as exc:
        _log_event("projection", "pre_turn_failed", level="warning", error=type(exc).__name__)
        return state


def _await_projection_db(state: dict, game_id: str | None) -> dict:
    """R10 em perfil DB: se o job da projeção pendente está RODANDO (outra
    request/worker), espera até `RPG_PROJECTION_WAIT_SECONDS` e relê o jogo, em
    vez de repetir o LLM. Fila parada/sem dono → segue; o turno drena na cerca."""
    from services import projections

    plan = projections.normalize_plan(state.get("pending_derived"))
    if plan is None or plan["canonical_version"] is None or not plan["action_id"]:
        return state
    try:
        from infrastructure.runtime import get_runtime

        status = getattr(get_runtime().job_queue, "status", None)
        if not callable(status):
            return state
        key = projections.dedupe_key(state.get("game_id"), plan["epoch"], plan["action_id"])
        deadline = time.monotonic() + projections.wait_seconds()
        waited = False
        while time.monotonic() < deadline:
            row = status(projections.JOB_KIND, key)
            if not row or row["status"] != "running" or not row["leased"]:
                break
            waited = True
            time.sleep(0.2)
        if waited:
            fresh = api_core.load_game_state(api_core._resolve_save_file(game_id))
            return fresh or state
    except Exception as exc:
        _log_event("projection", "await_failed", level="warning", error=type(exc).__name__)
    return state


def _drain_projection_db(state: dict) -> None:
    """Perfil DB, pós-resposta: arrenda o PRÓPRIO job do outbox e o executa com
    o ciclo normal de lease/fence da fila (nunca thread nova; R9). Nunca levanta."""
    from services import projections

    payload = projections.job_payload(state)
    if payload is None:
        return
    try:
        from infrastructure.runtime import get_runtime
        from workers.job_worker import JobWorker
        from workers.projection_jobs import make_handler

        runtime = get_runtime()
        lease_key = getattr(runtime.job_queue, "lease_key", None)
        if not callable(lease_key) or not runtime.resources:
            return
        job = lease_key(
            "api-post-response",
            projections.JOB_KIND,
            projections.dedupe_key(payload["game_id"], payload["epoch"], payload["action_id"]),
        )
        if job is None:
            return
        handler = make_handler(runtime.resources[0], runtime.memory_store)
        JobWorker(
            runtime.job_queue, {projections.JOB_KIND: handler}, worker_id="api-post-response"
        ).run_leased(job)
    except Exception as exc:
        _log_event(
            "projection", "post_response_db_failed", level="warning", error=type(exc).__name__
        )


def _drain_projection(state: dict, *, where: str) -> dict:
    """Executa a projeção pendente sob o lock do turno e persiste. Nunca levanta."""
    from services.projections import has_pending, run_pending

    if not has_pending(state):
        return state
    try:
        drained = run_pending(state)
        api_core._require_saved(drained, detail=f"projeção ({where})")
        return drained
    except Exception as exc:
        _log_event(
            "projection", "drain_failed", level="warning", where=where, error=type(exc).__name__
        )
        return state


def _execute_action(
    req: ActionRequest, *, progress=None, timeline=None, on_response=None
) -> GameResponse:
    from infrastructure.runtime import get_runtime
    from observability import latency as _lat
    from services.turn_execution import operation_scope

    if timeline is None:
        timeline = _lat.TurnTimeline(transport="post")
    if not req.game_id and not api_core._database_profile():
        # SPEC-228 R8: resolve o "mais recente" UMA vez; lock e load usam o UUID.
        latest = persistence_module.get_latest_save_file()
        stem = os.path.basename(latest).removesuffix(".json") if latest else ""
        try:
            if stem:
                save_path(stem)
                req = req.model_copy(update={"game_id": stem})
        except ValueError:
            pass
    _bind_corr(req.game_id, req.action_id)
    lock = api_core._game_lock(req.game_id) if not api_core._database_profile() else nullcontext()
    lock_wait_started = _lat.now()
    with lock:
        # SPEC-200 R17: a "fila" do turno = espera do lock (e, em perfis hosted, da operacao).
        timeline.extra["lock_wait_ms"] = int(round((_lat.now() - lock_wait_started) * 1000))
        _, state = api_core._load_or_404(req.game_id)
        if not api_core._database_profile():
            persistence_module.ensure_synthetic_checkpoint(state)  # SPEC-228 R4
        operation_wait_started = _lat.now()
        if api_core._database_profile():
            # SPEC-213 R10: projeção do turno anterior em execução → espera e relê.
            state = _await_projection_db(state, req.game_id)
        claim, request_hash, receipt = _begin_turn_operation(state, req)
        if api_core._database_profile():
            timeline.extra["lock_wait_ms"] += int(
                round((_lat.now() - operation_wait_started) * 1000)
            )
        if receipt is not None:
            return receipt
        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            if api_core._action_already_processed(state, req.action_id):
                return format_response(state, cue_action_key=req.action_id)
            _reject_memorial(state)
            _reject_archived(state)
            if state.get("death_pending"):
                raise HTTPException(409, "Você tombou. Resolva a tela de morte.")
            # SPEC-219 R3/R10: 1 consumo por turno (POST e SSE), depois do replay por action_id.
            _enforce_owner_budget("turn", minute=True)
            _apply_action_options(state, req)
            from services.projections import deferral_scope, projection_mode

            owner = _projection_owner()
            db = api_core._database_profile()
            if owner and not db:
                # R15: projeção pendente (crash/falha anterior) roda antes do grafo.
                state = _drain_projection(state, where="pre_turn")
            holder: dict = {}
            with deferral_scope(owner and projection_mode() == "post_response"):
                response = _run_turn(
                    state,
                    req.input_text,
                    req.action_id,
                    claim=claim,
                    request_hash=request_hash,
                    progress=progress,
                    timeline=timeline,
                    out=holder,
                    pre_drain=owner and db,
                )
        # Fora da cerca do turno (já commitado; o heartbeat do lease do turno não
        # pode falhar a request depois da entrega), mas ainda sob o lock legacy.
        if on_response is not None:
            on_response(response)  # SSE: narração sai ANTES dos derivados
        if owner and holder.get("state") is not None:
            if db:
                _drain_projection_db(holder["state"])
            else:
                _drain_projection(holder["state"], where="post_response")
        return response


def _drain_creature_gen() -> None:
    """SPEC-361 (R2-P1-2): perfil legacy roda a criatura nova agendada numa thread daemon, um job
    por vez, FORA do lock do jogo (a próxima ação não espera). Perfil DB: worker/cron."""
    # Nunca levanta nem bloqueia: roda depois de a resposta (já persistida) ir para a fila do SSE.
    try:
        if api_core._database_profile():
            return
        from services.creature_gen_jobs import drenar_em_segundo_plano, tem_pendente

        if tem_pendente():  # sem job agendado, nenhuma thread
            drenar_em_segundo_plano()
    except Exception as exc:
        _log_event(
            "bestiary", "creature_gen_drain_failed", level="warning", error=type(exc).__name__
        )


def _publish_timeline(timeline, outcome: str) -> None:
    """Entrega o registro final aos sinks (baseline). Nunca levanta."""
    try:
        from observability import latency as _lat

        if outcome != "client_gone":  # o worker ainda pode estar rodando
            timeline.finish()
        _lat.publish({**timeline.fields(), "outcome": outcome, "total_ms": timeline.total_ms()})
    except Exception:
        pass


@router.post("/game/action", response_model=GameResponse)
def game_action(req: ActionRequest):
    from observability import latency as _lat

    timeline = _lat.TurnTimeline(transport="post")
    outcome = "error"
    try:
        response = _execute_action(req, timeline=timeline)
        outcome = "ok"
        return response
    finally:
        _publish_timeline(timeline, outcome)


class DeathChoiceRequest(BaseModel):
    game_id: str | None = None
    choice: str = Field(pattern="^(continue|accept)$")  # Continuar do checkpoint / Aceitar o fim
    action_id: str | None = Field(default=None, max_length=36)


@router.post("/game/death", response_model=GameResponse)
def game_death(req: DeathChoiceRequest):
    """spec checkpoints-morte (D2): resolve a tela de morte.
    - `continue` → restaura do checkpoint (ou do início da sessão, D7); a saga segue.
    - `accept`   → memorial (game_over): a crônica encerra por escolha do jogador."""
    _bind_corr(req.game_id, req.action_id)
    lock = api_core._game_lock(req.game_id) if not api_core._database_profile() else nullcontext()
    with lock:
        _, state = api_core._load_or_404(req.game_id)
        claim, request_hash, receipt = _begin_state_mutation(
            state,
            action_id=req.action_id,
            kind="death",
            payload=req.model_dump(mode="json", exclude={"action_id"}),
        )
        if receipt is not None:
            return GameResponse.model_validate(receipt)
        from infrastructure.runtime import get_runtime
        from services.turn_execution import operation_scope

        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            _reject_archived(state)
            try:
                _reject_archived(state)
                if not state.get("death_pending"):
                    raise HTTPException(
                        status_code=409, detail="Nenhuma queda pendente para resolver."
                    )
            except Exception as exc:
                _fail_operation(claim, type(exc).__name__)
                raise
            from services import checkpoints as _cp

            try:
                new_state = _cp.resolve_death_choice(state, req.choice)
            except _cp.NoRestorePoint as exc:
                _fail_operation(claim, "no_restore_point")
                return _error_response(
                    409,
                    "Sem ponto de retorno válido; aceite o memorial ou inicie nova jornada.",
                    code="no_restore_point",
                    death_pending=True,
                )
            response = format_response(new_state)
            _commit_state_mutation(
                new_state,
                response.model_dump(mode="json"),
                claim=claim,
                request_hash=request_hash,
            )
            return response


# --- STREAMING DO TURNO (spec streaming-turno-sse) ---------------------------

_SSE_PING_S = 10.0


_NARRATIVE_CHUNK = 80


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


_STREAM_ROUTE = "/game/action/stream"


def _stream_turn(
    req: ActionRequest, accepted_game_id: str, principal=None, timeline=None
) -> Iterator[str]:
    """Envolve o gerador SSE com as marcas de latencia (SPEC-200) e publica o
    registro final mesmo se o consumidor desconectar (GeneratorExit)."""
    from observability import latency as _lat

    if timeline is None:
        timeline = _lat.TurnTimeline(transport="stream")
    outcome = {
        "value": "client_gone",
        "phase": "start",
        "gone": False,
        "worker": None,
        "_lock": threading.Lock(),
        "_t0": time.monotonic(),
    }
    timeline.hold_log()  # SPEC-212 R13: `rpg.turn` sai apos ttfmc/ttlt
    _sse_log("started", transport="stream")
    try:
        yield from _stream_turn_events(req, accepted_game_id, principal, timeline, outcome)
    finally:
        timeline.release_log()
        with outcome["_lock"]:
            gone = outcome["value"] == "client_gone"
            outcome["gone"] = gone
            worker_done = outcome["worker"]
        if gone:  # SPEC-247 R2: o cliente caiu; o worker segue e conclui o turno
            _sse_log(
                "client_disconnected",
                phase=outcome["phase"],
                elapsed_ms=int((time.monotonic() - outcome["_t0"]) * 1000),
            )
            if worker_done is not None:
                _sse_log("worker_finished_after_disconnect", outcome=worker_done)
        _log_turn_delivery(timeline, outcome["value"], outcome.get("error_type"), outcome)
        _publish_timeline(timeline, outcome["value"])


def _sse_log(event: str, *, level: str = "info", **fields: Any) -> None:
    try:
        from observability.telemetry import log_event

        log_event("sse", event, level=level, **fields)
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


def _worker_done(outcome: dict, result: str) -> None:
    with outcome["_lock"]:
        outcome["worker"] = result
        gone = outcome["gone"]
    if gone:
        _sse_log("worker_finished_after_disconnect", outcome=result)


def _record_early_delivery(
    outcome: dict, timeline, *, early_on: bool, shadow_text: str | None, final_text: str
) -> None:
    """SPEC-316 R7/R8: ganho da entrega antecipada (`state_ms - ttlt_ms`); no `shadow`
    o ganho e hipotetico (texto calculado, nao emitido) e vai ao log `sse.early_narrative_shadow`."""
    state_ms = timeline.mark_ms("state")
    if state_ms is None:
        return
    if early_on:
        ttlt_ms = timeline.mark_ms("ttlt")
        outcome["early_narrative"] = True
        outcome["early_gain_ms"] = None if ttlt_ms is None else max(0, state_ms - ttlt_ms)
    elif shadow_text is not None:
        shadow_ms = timeline.mark_ms("early_shadow")
        gain = None if shadow_ms is None else max(0, state_ms - shadow_ms)
        outcome["early_narrative"] = False
        outcome["early_gain_ms"] = gain
        _sse_log("early_narrative_shadow", gain_ms=gain, identical=shadow_text == final_text)


def _log_turn_delivery(
    timeline, outcome: str, error_type: str | None = None, early: dict | None = None
) -> None:
    """Linha `evt:"turn_delivery"`: marcas de entrega que so existem apos o worker
    ter logado `rpg.turn` (ttfmc/ttlt). Sem texto, sem game_id cru."""
    try:
        from observability.telemetry import safe_json

        _turn_logger.info(
            safe_json(
                {
                    "event": "turn_delivery",
                    "evt": "turn_delivery",
                    "action_ref": timeline.extra.get("action_ref"),
                    "transport": timeline.transport,
                    # SPEC-319 R6: com token real, TTFT != TTFMC (SPEC-200) e nao e pseudo.
                    "pseudo_streaming": not bool((early or {}).get("token_stream", False)),
                    "first_token_server_ms": timeline.mark_ms("first_token"),
                    "token_replace": bool((early or {}).get("token_replace", False)),
                    "ack_server_ms": timeline.mark_ms("accepted"),
                    "ttfmc_server_ms": timeline.mark_ms("ttfmc"),
                    "ttlt_server_ms": timeline.mark_ms("ttlt"),
                    "state_server_ms": timeline.mark_ms("state"),
                    "early_narrative": bool((early or {}).get("early_narrative", False)),
                    "early_gain_ms": (early or {}).get("early_gain_ms"),
                    "outcome": outcome,
                    **({"error_type": error_type} if outcome == "error" and error_type else {}),
                }
            )
        )
    except Exception:
        pass


def _stream_turn_events(
    req: ActionRequest, accepted_game_id: str, principal, timeline, outcome: dict
) -> Iterator[str]:
    """SSE cujo worker possui lock, execução e persistência do turno.

    Se o consumidor desconectar, a thread termina o save e o ``action_id`` torna
    seguro o fallback POST. O gerador apenas apresenta eventos já produzidos.
    """
    from observability.metrics import metrics

    outcome["phase"] = "accepted"
    yield _sse("accepted", {"game_id": accepted_game_id})
    timeline.mark("accepted")  # retomada do gerador = proxy de flush
    try:
        metrics.observe(
            "rpg_sse_ack_seconds",
            {"route": _STREAM_ROUTE},
            (timeline.mark_ms("accepted") or 0) / 1000,
        )
    except Exception:
        pass
    q: queue.Queue = queue.Queue()

    def _worker():
        result = "ok"
        try:
            from infrastructure.request_context import principal_scope

            context = principal_scope(principal) if principal is not None else nullcontext()
            with context:
                delivered = {"done": False}

                def _deliver(response):
                    delivered["done"] = True
                    q.put(("response", response))

                response = _execute_action(
                    req,
                    progress=lambda chunk: q.put(("chunk", chunk)),
                    timeline=timeline,
                    on_response=_deliver,
                )
                if not delivered["done"]:
                    q.put(("response", response))
                _drain_creature_gen()  # SPEC-361: fora do lock do jogo, narração já entregue
        except HTTPException as exc:
            from services.error_codes import code_for

            payload = {
                "detail": exc.detail,
                "code": exc.status_code,  # ``code`` numerico: compat do cliente
                "error_code": code_for(exc.status_code, exc.detail, getattr(exc, "code", None)),
                "request_id": _current_request_id(),
            }
            if isinstance(exc, QuotaExceeded):  # SPEC-219: cliente mostra "volta em HH:MM"
                payload.update(scope=exc.scope, retry_after_seconds=exc.retry_after_seconds)
            result = "error"
            outcome["error_type"] = type(exc).__name__
            _sse_log(
                "error",
                level="warning",
                code=payload["error_code"],
                status=exc.status_code,
                error_type=type(exc).__name__,
            )
            q.put(("http_error", payload))
        except Exception as exc:
            result = "error"
            outcome["error_type"] = type(exc).__name__
            from observability.telemetry import safe_stack

            _sse_log(
                "error",
                level="error",
                code="internal_turn_error",
                error_type=type(exc).__name__,
                stack=safe_stack(exc),
            )
            q.put(("exc", exc))
        finally:
            _worker_done(outcome, result)

    from observability.telemetry import contextualize

    # SPEC-240 R3: a thread do SSE herda request_id/game_ref/action_ref da requisicao.
    threading.Thread(target=contextualize(_worker), daemon=True).start()

    def _observe_delivery(mark: str, metric: str) -> None:
        try:
            ms = timeline.mark_ms(mark)
            if ms is not None:
                metrics.observe(metric, {"route": _STREAM_ROUTE, "source": "server"}, ms / 1000)
        except Exception:
            pass

    from services.turn_delivery import early_mode, narrative_chunks

    # SPEC-316: `off` ignora; `shadow` so mede; `on` emite a narracao antes do arquivista.
    delivery_mode = early_mode()
    emitted_text: str | None = None  # narracao ja entregue ao cliente (modo `on`)
    shadow_text: str | None = None

    def _emit_early(text: str) -> Iterator[str]:
        for piece in narrative_chunks(text, _NARRATIVE_CHUNK):
            if piece.strip() and timeline.mark_ms("ttfmc") is None:
                timeline.mark("ttfmc")
                _observe_delivery("ttfmc", "rpg_turn_first_content_seconds")
            yield _sse("narrative", {"chunk": piece, "done": False})
        timeline.mark("ttlt")
        _observe_delivery("ttlt", "rpg_turn_last_content_seconds")
        yield _sse("narrative", {"chunk": "", "done": True})

    # SPEC-319: tokens reais do narrador. `on` os repassa; `shadow` so mede o TTFT.
    from services.narrative_sink import replace_reason as _replace_reason
    from services.narrative_sink import token_stream_mode

    token_mode = token_stream_mode()
    tok = {"text": "", "shadow": "", "sent": False}  # texto ja entregue por deltas / medido

    def _finish_tokens(final_text: str) -> Iterator[str]:
        """Fecha a narracao entregue por deltas: extensao do que o jogador ja leu vira so o
        sufixo; qualquer divergencia (guard, recibo, regra de ouro) vira `replace` (R3)."""
        shown = tok["text"]
        if final_text.startswith(shown):
            for piece in narrative_chunks(final_text[len(shown) :], _NARRATIVE_CHUNK):
                yield _sse("narrative", {"chunk": piece, "done": False})
            timeline.mark("ttlt")
            _observe_delivery("ttlt", "rpg_turn_last_content_seconds")
            yield _sse("narrative", {"chunk": "", "done": True})
        else:
            timeline.mark("ttlt")
            _observe_delivery("ttlt", "rpg_turn_last_content_seconds")
            outcome["token_replace"] = True
            common = len(os.path.commonprefix([shown, final_text]))
            # P2-4: motivo do replace (a §6 separa formatacao/abertura de guard de conteudo)
            _sse_log(
                "token_replace",
                reason=_replace_reason(shown, final_text),
                shown_len=len(shown),
                final_len=len(final_text),
                common_prefix_len=common,
            )
            yield _sse("narrative", {"chunk": final_text, "done": True, "replace": True})
        tok["text"] = final_text

    while True:
        try:
            kind, payload = q.get(timeout=_SSE_PING_S)
        except queue.Empty:
            yield ": ping\n\n"
            continue
        if kind == "http_error":
            outcome["value"] = "error"
            if emitted_text is not None or tok["text"]:
                payload = {**payload, "narrative_shown": True}  # SPEC-316 R5
            yield _sse("error", payload)
            return
        if kind == "exc":
            outcome["value"] = "error"
            body = {
                "detail": "Erro interno ao processar o turno.",
                "code": 500,
                "error_code": "internal_turn_error",
                "request_id": _current_request_id(),
            }
            if emitted_text is not None or tok["text"]:
                body["narrative_shown"] = True  # SPEC-316 R5
            yield _sse("error", body)
            return
        if kind == "chunk":
            mode, data = payload
            if mode == "narrative_delta":
                piece = str((data or {}).get("text") or "")
                if not piece:
                    continue
                if token_mode == "on":
                    if timeline.mark_ms("first_token") is None:
                        timeline.mark("first_token")
                        _observe_delivery("first_token", "rpg_turn_first_token_seconds")
                    if piece.strip() and timeline.mark_ms("ttfmc") is None:
                        timeline.mark("ttfmc")
                        _observe_delivery("ttfmc", "rpg_turn_first_content_seconds")
                    tok["text"] += piece
                    outcome["phase"] = "narrative_tokens"
                    outcome["token_stream"] = True
                    yield _sse("narrative", {"chunk": piece, "done": False, "live": True})
                else:  # shadow: mede sem enviar
                    if timeline.mark_ms("first_token_shadow") is None:
                        timeline.mark("first_token_shadow")
                    tok["shadow"] += piece
                continue
            if mode == "narrative_reset":
                if token_mode == "on" and tok["text"]:
                    tok["text"] = ""
                    yield _sse("narrative", {"chunk": "", "done": False, "reset": True})
                tok["shadow"] = ""
                continue
            if mode == "early_narrative":
                text = str((data or {}).get("text") or "")
                if delivery_mode == "on" and emitted_text is None and text.strip():
                    emitted_text = text
                    outcome["phase"] = "narrative_early"
                    if tok["text"]:
                        yield from _finish_tokens(text)
                    else:
                        yield from _emit_early(text)
                elif delivery_mode == "shadow" and shadow_text is None and text.strip():
                    shadow_text = text
                    timeline.mark("early_shadow")
                continue
            if mode == "updates":
                for node, upd in (data or {}).items():
                    if node not in {"action_guard", "turn_prepare", "dispatch", "turn_finalizer"}:
                        outcome["phase"] = str(node)[:40]
                        yield _sse("phase", {"node": node, "status": "done"})
                    if node == "dm_router":
                        yield _sse("route", {"route": (upd or {}).get("next", "") or ""})
            continue
        if kind == "response":
            resp = payload
            outcome["phase"] = "narrative"
            narrative = resp.message or ""
            if token_mode == "shadow" and tok["shadow"]:
                _sse_log(
                    "token_stream_shadow",
                    ttft_shadow_ms=timeline.mark_ms("first_token_shadow"),
                    identical_to_final=tok["shadow"].strip() == narrative.strip(),
                    # D1 (revisao P2-5): mesma regra do `on` — so conta como replace se o final
                    # nao ESTENDE o que o jogador ja teria lido.
                    would_replace=not narrative.startswith(tok["shadow"]),
                    # follow-up D1: motivo (none|start|tail|shorter) para o staging confirmar
                    reason=_replace_reason(tok["shadow"], narrative),
                )
            if emitted_text is None and tok["text"]:
                # tokens entregues e sem entrega antecipada (316 off/shadow): fecha aqui
                yield from _finish_tokens(narrative)
                yield _sse("visual", resp.visual.model_dump(mode="json"))
            elif emitted_text is None:
                yield _sse("visual", resp.visual.model_dump(mode="json"))
                for i in range(0, len(narrative), _NARRATIVE_CHUNK):
                    piece = narrative[i : i + _NARRATIVE_CHUNK]
                    if piece.strip() and timeline.mark_ms("ttfmc") is None:
                        timeline.mark("ttfmc")  # primeiro conteudo significativo (SPEC-200)
                        _observe_delivery("ttfmc", "rpg_turn_first_content_seconds")
                    yield _sse("narrative", {"chunk": piece, "done": False})
                timeline.mark("ttlt")
                _observe_delivery("ttlt", "rpg_turn_last_content_seconds")
                yield _sse("narrative", {"chunk": "", "done": True})
            else:
                if narrative != emitted_text:  # R2: o guard/recibo mudou a prosa
                    yield _sse("narrative", {"chunk": narrative, "done": True, "replace": True})
                yield _sse("visual", resp.visual.model_dump(mode="json"))
            timeline.mark("state")
            _record_early_delivery(
                outcome,
                timeline,
                early_on=emitted_text is not None,
                shadow_text=shadow_text,
                final_text=narrative,
            )
            outcome["value"] = "ok"
            yield _sse("state", json.loads(resp.model_dump_json()))
            return


@router.post("/game/action/stream")
def game_action_stream(req: ActionRequest):
    """R1: mesmo corpo do /game/action, resposta text/event-stream com fases
    reais do grafo. Guard-rails (rate limit via middleware, game_id, memorial,
    teto de input) valem aqui também (R3)."""
    from observability import latency as _lat

    timeline = _lat.TurnTimeline(transport="stream")  # t0 = entrada do handler (ACK servidor)
    _, state = api_core._load_or_404(req.game_id, locked_read=True)
    if not req.game_id and not api_core._database_profile() and state.get("game_id"):
        # SPEC-228 R8: resolve "mais recente" UMA vez; aceite e worker usam o UUID.
        req = req.model_copy(update={"game_id": str(state["game_id"])})
    principal = None
    if api_core._database_profile():
        from infrastructure.request_context import current_principal

        principal = current_principal()
    return StreamingResponse(
        _stream_turn(
            req,
            str(state.get("game_id", "?")),
            principal,
            timeline,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
