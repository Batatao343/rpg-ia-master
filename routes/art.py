"""SPEC-381: rotas de art (movidas de api.py, sem mudanca)."""

import os
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from gamedata import load_json_data
from infrastructure.db_roles import admin_connection
from services.prologue import build_start_scenario_ctx
import api_core
import api_presenters
from api_core import (
    _begin_state_mutation,
    _commit_state_mutation,
    _enforce_owner_budget,
    _fail_operation,
    _meter_auxiliary_operation,
    _prologue_owner,
    _reject_archived,
    _reject_memorial,
)
from api_models import (
    ArtBriefRequest,
    ArtConfirmRequest,
    ArtQualityRequest,
    ArtQuoteRequest,
    CreateCharacterRequest,
)
from api_presenters import _portrait_manifest_ctx, _public_art_refs

router = APIRouter()


@router.post("/game/prologue")
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
        "backstory": req.backstory or "",
        "level": req.level,
    }
    _enforce_owner_budget("llm_aux")  # SPEC-219 R3 (minuto/owner ja aplicado na fronteira)
    with _meter_auxiliary_operation("prologue"):
        scenario, mock, ctx = build_start_scenario_ctx(char_input)
    from services.prologue import sign_for_client

    body = {"scenario": scenario.model_dump(), "mock": mock}
    token = sign_for_client(scenario, ctx, _prologue_owner())
    if token:
        body["scenario_token"] = token
    return body


@router.post("/game/art/brief")
def preview_player_art_brief(req: ArtBriefRequest):
    from services.art_brief import build_player_art_brief, render_image_prompt

    brief = build_player_art_brief(req.model_dump())
    return {"brief": brief, "rendered_prompt": render_image_prompt(brief), "provider_called": False}


def _guard_image_effect() -> None:
    """SPEC-196: kill switch + stale rate card refuse NEW image quotes/generation only."""
    from services.finops_alerts import require_paid_effect
    from services.kill_switches import IMAGE, SwitchOff, get_switches
    from services.shard_pricing import PricingUnavailable

    try:
        get_switches().require(IMAGE)
        require_paid_effect("image")
    except SwitchOff:
        raise HTTPException(503, "image_generation_disabled") from None
    except PricingUnavailable:
        raise HTTPException(503, "image_pricing_unavailable") from None


def _image_finance(*, guard: bool = True):
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime
    from services.image_quotes import ImageQuoteRepository

    if not api_core._database_profile() or os.getenv(
        "RPG_DYNAMIC_ART_ENABLED", "0"
    ).lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise HTTPException(503, "image_quotes_unavailable")
    if guard:
        _guard_image_effect()
    runtime = get_runtime()
    return runtime, current_principal(), ImageQuoteRepository(runtime.resources[0])


def _validate_image_request(state: dict, reformulation: bool, image_type: str) -> None:
    _reject_memorial(state)
    _reject_archived(state)
    if state.get("death_pending"):
        raise HTTPException(409, "Resolva a queda antes de encomendar arte.")
    if image_type == "player":
        rows = [
            row
            for row in state.get("art_generation_ledger", [])
            if row.get("trigger_kind") == "player_portrait"
        ]
        if (reformulation and len(rows) != 1) or (not reformulation and rows):
            raise HTTPException(409, "Retrato ou reformulação indisponível.")


def _offer_brief_for_quote(state: dict, image_type: str, trigger, brief: dict, profile: dict):
    """SPEC-326 R2/D7: oferta de profile antigo é reconstruída do estado, nunca cotada como está."""
    if brief.get("profile_version") == profile.get("profile_version"):
        return brief
    from services.art_brief import build_epic_art_brief, build_npc_art_brief

    if image_type == "npc":
        return build_npc_art_brief(state, trigger.subject_id)
    return build_epic_art_brief(state, {})


def _monster_quote_inputs(state: dict, req: ArtQuoteRequest, runtime) -> tuple[Any, dict]:
    """SPEC-352 R5: (gatilho, brief) de um retrato de inimigo. A chave é recalculada AQUI, no servidor."""
    from services import creature_art as _art
    from services.art_brief import build_creature_art_brief
    from services.art_triggers import ArtGenerationRequest

    meta = state.get("combat") or {}
    enemy = next(
        (
            e
            for e in (state.get("enemies") or [])
            if isinstance(e, dict)
            and str(e.get("id") or e.get("name")) == req.enemy_id
            and not e.get("dead")
            and e.get("status", "ativo") not in ("morto", "fugiu", "rendido", "incapacitado")
        ),
        None,
    )
    if enemy is None or not meta.get("active"):
        raise HTTPException(422, "enemy_not_in_conflict")
    if _art.is_fallback_enemy(enemy):  # SPEC-367 R11: criatura de fallback não tem retrato pago
        raise HTTPException(409, "creature_portrait_not_offered")
    game_id = str(state.get("game_id") or "")
    manifest, npc_entity_id = _portrait_manifest_ctx(state, meta)
    key = _art.portrait_key(enemy, manifest, game_id=game_id, npc_entity_id=npc_entity_id)
    if _art.curated_covers_key(enemy, key):
        raise HTTPException(409, "creature_portrait_curated")  # D-352-6: a curada vence
    existing = api_presenters._portrait_store(runtime).get_many(
        [key], game_id=game_id, npc_known=[key]
    )
    if key in existing:
        raise HTTPException(409, "creature_portrait_exists")
    important, _why = _art.is_important(enemy, manifest)
    npc = None
    if key.startswith("npc:"):
        ref = str((manifest or {}).get("target_ref") or "")
        npc = (state.get("npcs") or {}).get(ref[4:])
    request_key = str(uuid.uuid4())
    # `trigger_instance_id` leva a tentativa: a unicidade por jogo (326) não bloqueia refazer depois de
    # uma falha. O árbitro da cobrança única é `creature_portraits` (PK), não o ledger.
    trigger = ArtGenerationRequest(
        "creature_portrait", f"{key}|{request_key}", "monster", key, None, request_key
    )
    return trigger, dict(build_creature_art_brief(enemy, important=important, npc=npc))


@router.post("/game/{game_id}/art/quote")
def create_image_quote(game_id: str, req: ArtQuoteRequest):
    from infrastructure.contracts import Conflict
    from services.art_brief import build_player_art_brief
    from services.art_triggers import ArtGenerationRequest
    from services.image_quotes import public_quote
    from services.shard_pricing import PricingUnavailable

    if req.image_type == "monster":
        from services import creature_art as _art

        if _art.mode() != "on":
            raise HTTPException(404, "creature_art_disabled")
        if req.offer_id or req.reformulation or not req.enemy_id:
            raise HTTPException(422, "monster_quote_invalid")
    elif req.enemy_id is not None:
        raise HTTPException(422, "enemy_id_only_monster")
    runtime, principal, repository = _image_finance()
    _, state = api_core._load_or_404(game_id)
    _validate_image_request(state, req.reformulation, req.image_type)
    if req.image_type == "monster":
        trigger, brief = _monster_quote_inputs(state, req, runtime)
    elif req.image_type == "player":
        if req.offer_id:
            raise HTTPException(422, "player_offer_not_required")
        if req.reformulation:
            with admin_connection(runtime.resources[0]) as connection:  # SPEC-224: le wallet
                blocked = connection.execute(
                    """select 1 from app.art_generations g join app.wallet_reservations w
                    on w.reservation_id=g.wallet_reservation_id where g.game_id=%s and g.owner_id=%s
                    and g.subject_type='player' and w.status not in ('settled','released')""",
                    (uuid.UUID(game_id), principal.user_id),
                ).fetchone()
            if blocked:
                raise HTTPException(409, "Confira a geração anterior antes de reformular.")
        request_key = str(uuid.uuid4())
        trigger = ArtGenerationRequest(
            "player_portrait", request_key, "player", "player", None, request_key
        )
        brief = build_player_art_brief(state.get("player") or {}, reformulation=req.reformulation)
    else:
        if req.reformulation:
            raise HTTPException(422, "reformulation_only_player")
        offer = next(
            (
                row
                for row in state.get("art_offers", [])
                if row["offer_id"] == str(req.offer_id) and row["type"] == req.image_type
            ),
            None,
        )
        if not offer:
            raise HTTPException(404, "Oferta não encontrada.")
        trigger = ArtGenerationRequest(**offer["trigger"])
        brief = offer["brief"]
    profile = load_json_data("dynamic_art_profiles.json") or {}
    if req.image_type not in ("player", "monster"):
        brief = _offer_brief_for_quote(state, req.image_type, trigger, brief, profile)
    try:
        quote = repository.issue(
            principal,
            uuid.UUID(game_id),
            request=trigger,
            brief=brief,
            model=str(profile.get("model")),
            profile_version=str(profile.get("profile_version")),
            reformulation=req.reformulation,
        )
    except PricingUnavailable:
        raise HTTPException(503, "image_pricing_unavailable") from None
    except Conflict:
        raise HTTPException(409, "image_quote_conflict") from None
    return public_quote(quote)


@router.post("/game/{game_id}/art/player/confirm")
@router.post("/game/{game_id}/art/confirm")
def confirm_player_art(game_id: str, req: ArtConfirmRequest):
    from infrastructure.contracts import Conflict
    from infrastructure.wallet import InsufficientShards, WalletConflict
    from services.art_triggers import ArtGenerationRequest, reserve_request
    from services.creature_portraits import CreaturePortraitTaken
    from services.shard_pricing import PricingUnavailable
    from services.turn_effects import effect_scope
    from services.turn_execution import operation_scope

    # SPEC-196: replay of an existing generation must keep working with the switch off;
    # only a NEW confirm is refused (guard runs after the `prior` lookup below).
    runtime, principal, repository = _image_finance(guard=False)
    claim = None
    _, state = api_core._load_or_404(game_id)
    try:
        quote = repository.get(principal, uuid.UUID(game_id), req.quote_id)
        with runtime.resources[0].connection() as connection:
            prior = connection.execute(
                "select generation_id,status from app.art_generations where image_quote_id=%s and owner_id=%s",
                (req.quote_id, principal.user_id),
            ).fetchone()
        if prior:
            return {
                "status": prior["status"],
                "generation_id": str(prior["generation_id"]),
                "type": quote["image_type"],
                "placeholder": prior["status"] != "ready",
                **_public_art_refs(state),
            }
        _guard_image_effect()
        _validate_image_request(state, quote["reformulation"], quote["image_type"])
        if quote["image_type"] == "monster":
            # SPEC-352 R6: checagem rápida ANTES de qualquer reserva. O árbitro final é o `claim`
            # dentro da transação de confirmação (PK de creature_portraits).

            portrait_key = str(quote["trigger"]["subject_id"])
            taken = api_presenters._portrait_store(runtime).get_many(
                [portrait_key], game_id=game_id, npc_known=[portrait_key]
            )
            if portrait_key in taken:
                raise HTTPException(409, "creature_portrait_in_progress")
        claim, request_hash, receipt = _begin_state_mutation(
            state,
            action_id=req.action_id,
            kind="art",
            payload={"game_id": game_id, **req.model_dump(mode="json", exclude={"action_id"})},
        )
        if receipt is not None:
            return receipt
        with (
            operation_scope(runtime.turn_coordinator if claim else None, claim),
            effect_scope() as effects,
        ):
            trigger = ArtGenerationRequest(**quote["trigger"])
            reserved = reserve_request(state, trigger)
            if not reserved:
                raise HTTPException(409, "Orçamento visual indisponível.")
            generation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"image-quote:{req.quote_id}"))
            reserved["art_generation_ledger"][-1]["generation_id"] = generation_id
            reserved["art_generation_ledger"][-1]["image_quote_id"] = str(req.quote_id)
            state.update(
                {key: reserved[key] for key in ("art_arc_budgets", "art_generation_ledger")}
            )
            state["art_offers"] = [
                row for row in state.get("art_offers", []) if row.get("trigger") != quote["trigger"]
            ]
            effects.defer(
                lambda connection, epoch, version: repository.confirm(
                    principal,
                    uuid.UUID(game_id),
                    req.quote_id,
                    connection=connection,
                    epoch=epoch,
                    version=version,
                    queue=runtime.job_queue,
                )
            )
            return _commit_state_mutation(
                state,
                {
                    "status": "pending",
                    "generation_id": generation_id,
                    "type": quote["image_type"],
                    "placeholder": True,
                    **_public_art_refs(state),
                },
                claim=claim,
                request_hash=request_hash,
            )
    except InsufficientShards:
        raise HTTPException(402, "image_insufficient_shards") from None
    except PricingUnavailable:
        raise HTTPException(503, "image_pricing_unavailable") from None
    except CreaturePortraitTaken:
        _fail_operation(claim, "creature_portrait_in_progress")
        raise HTTPException(409, "creature_portrait_in_progress") from None
    except (Conflict, WalletConflict):
        _fail_operation(claim, "image_quote_conflict")
        raise HTTPException(409, "image_quote_conflict") from None
    except Exception:
        _fail_operation(claim, "image_confirmation_failed")
        raise


@router.get("/game/{game_id}/art/{generation_id}")
def dynamic_art_status(game_id: str, generation_id: str):
    _, state = api_core._load_or_404(game_id)
    if api_core._database_profile():
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime
        from services.dynamic_art import DynamicArtRepository

        runtime = get_runtime()
        principal = current_principal()
        try:
            generation_uuid = uuid.UUID(generation_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="generation_id inválido.") from exc
        profile = load_json_data("dynamic_art_profiles.json") or {}
        repository = DynamicArtRepository(
            runtime.resources[0],
            model=str(profile.get("model") or "gpt-image-2-2026-04-21"),
            profile_version=str(profile.get("profile_version") or "valoria-dynamic-v1"),
        )
        generation = repository.get(principal, generation_uuid)
        if not generation or str(generation["game_id"]) != str(state["game_id"]):
            raise HTTPException(status_code=404, detail="Geração não encontrada.")
        assets = []
        if generation["status"] == "ready":
            for asset in repository.assets(principal, generation_uuid):
                assets.append(
                    {
                        "asset_id": str(asset["id"]),
                        "variant": asset["variant"],
                        "url": runtime.blob_store.signed_url(asset["object_key"], 300),
                        "mime_type": asset["mime_type"],
                        "bytes": int(asset["bytes"]),
                        "width": int(asset["width"]),
                        "height": int(asset["height"]),
                        "sha256": asset["sha256"],
                    }
                )
        public_error = None
        public_status = generation["status"]
        if generation.get("error_code") == "external_result_uncertain" or (
            public_status == "generating" and generation.get("worker_inactive")
        ):
            public_status = "reconcile_required"
            public_error = (
                "O resultado da geração precisa ser conferido; não haverá nova geração automática."
            )
        if str(generation["status"]).startswith("failed"):
            public_error = (
                public_error or "A arte não pôde ser gerada; o jogo continua com placeholder."
            )
        return {
            "generation_id": generation_id,
            "status": public_status,
            "placeholder": generation["status"] != "ready",
            "assets": assets,
            "financial_status": generation.get("financial_status"),
            "credits_held": generation.get("financial_status")
            in {"reserved", "effect_started", "uncertain"},
            "error": public_error,
        }
    row = next(
        (
            item
            for item in state.get("art_generation_ledger") or []
            if item.get("generation_id") == generation_id
        ),
        None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")
    return {
        "generation_id": generation_id,
        "status": row.get("status", "pending"),
        "placeholder": row.get("status") != "ready",
    }


@router.post("/game/{game_id}/art/{generation_id}/quality")
def dynamic_art_quality(game_id: str, generation_id: str, req: ArtQualityRequest):
    _, state = api_core._load_or_404(game_id)
    if api_core._database_profile():
        from infrastructure.contracts import Conflict
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime
        from services.dynamic_art import DynamicArtRepository

        profile = load_json_data("dynamic_art_profiles.json") or {}
        runtime = get_runtime()
        repository = DynamicArtRepository(
            runtime.resources[0],
            model=str(profile.get("model")),
            profile_version=str(profile.get("profile_version")),
        )
        try:
            repository.set_quality(
                current_principal(),
                uuid.UUID(generation_id),
                game_id=uuid.UUID(str(state["game_id"])),
                approved=req.approved,
            )
        except (ValueError, Conflict) as exc:
            if (
                str(exc) == "quality_not_applicable"
            ):  # SPEC-352 R15: retrato compartilhado é do operador
                raise HTTPException(422, "quality_not_applicable") from exc
            raise HTTPException(
                status_code=409, detail="Arte não disponível para avaliação."
            ) from exc
        return {"ok": True, "status": "ready" if req.approved else "rejected_quality"}
    ledger = list(state.get("art_generation_ledger") or [])
    row = next((item for item in ledger if item.get("generation_id") == generation_id), None)
    if not row or row.get("status") != "ready":
        raise HTTPException(status_code=409, detail="Arte não disponível para avaliação.")
    row["status"] = "ready" if req.approved else "rejected_quality"
    if not api_core.save_game_state(state):
        raise HTTPException(status_code=500, detail="Não foi possível salvar a avaliação.")
    return {"ok": True, "status": row["status"]}
