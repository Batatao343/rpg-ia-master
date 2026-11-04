"""SPEC-381: rotas de play (movidas de api.py, sem mudanca)."""

from contextlib import nullcontext
from typing import Any
from collections.abc import Callable
from fastapi import APIRouter, HTTPException
import progression
from services.error_codes import api_error
import api_core
from api_core import (
    _begin_state_mutation,
    _bind_corr,
    _commit_state_mutation,
    _fail_operation,
    _reject_archived,
    _reject_memorial,
)
from api_models import (
    EquipRequest,
    EspolioRequest,
    ForjaRequest,
    LevelUpRequest,
    LojaCartasRequest,
    PrepareCardsRequest,
)
from api_presenters import (
    _card_reward_blocks,
    _cards_block,
    _inventory_block,
    _levelup_block,
    _prepared_slots,
)

router = APIRouter()


@router.post("/game/equip")
def game_equip(req: EquipRequest):
    """Fase 4.3: equipar/desequipar — validação 100% Python (inventory.equip)."""
    import inventory as inv_mod

    _bind_corr(req.game_id, req.action_id)
    lock = api_core._game_lock(req.game_id) if not api_core._database_profile() else nullcontext()
    with lock:
        _, state = api_core._load_or_404(req.game_id)
        claim, request_hash, receipt = _begin_state_mutation(
            state,
            action_id=req.action_id,
            kind="equip",
            payload=req.model_dump(mode="json", exclude={"action_id"}),
        )
        if receipt is not None:
            return receipt
        from infrastructure.runtime import get_runtime
        from services.turn_execution import operation_scope

        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            _reject_archived(state)
            _reject_memorial(state)
            if state.get("death_pending"):
                raise HTTPException(409, "Resolva a queda antes desta alteração.")

            if req.item_id:
                player, err = inv_mod.equip(state["player"], req.item_id)
            elif req.unequip_slot:
                player, err = inv_mod.unequip(state["player"], req.unequip_slot)
            else:
                _fail_operation(claim, "invalid_equip_request")
                raise HTTPException(status_code=400, detail="Informe item_id ou unequip_slot.")
            if err:
                _fail_operation(claim, "invalid_equip")
                raise api_error(
                    400, "equip_rejected", detail=err
                )  # err = regra de dominio, nao excecao

            state["player"] = player
            import combat_mechanics as cm_mod

            stats = cm_mod.compute_player_combat_stats(player)
            response = {
                "ok": True,
                "equipment": player.get("equipment"),
                "inventory": _inventory_block(player),
                "derived": {"ac": stats["ac"], "attack": stats["attack"]},
            }
            return _commit_state_mutation(
                state,
                response,
                claim=claim,
                request_hash=request_hash,
            )


@router.post("/game/cards/prepare")
def game_cards_prepare(req: PrepareCardsRequest):
    """SPEC-209 R4: Preparação fora de combate. A regra mora em services.cards."""
    from services import cards

    _bind_corr(req.game_id, req.action_id)
    lock = api_core._game_lock(req.game_id) if not api_core._database_profile() else nullcontext()
    with lock:
        _, state = api_core._load_or_404(req.game_id)
        claim, request_hash, receipt = _begin_state_mutation(
            state,
            action_id=req.action_id,
            kind="equip",  # reaproveita o kind (CHECK do banco); hash do payload difere
            payload=req.model_dump(mode="json", exclude={"action_id"}),
        )
        if receipt is not None:
            return receipt
        from infrastructure.runtime import get_runtime
        from services.turn_execution import operation_scope

        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            _reject_archived(state)
            _reject_memorial(state)
            if state.get("death_pending"):
                raise HTTPException(409, "Resolva a queda antes desta alteração.")
            if (state.get("combat_simulation") or {}).get("enabled"):
                _fail_operation(claim, "simulation")
                raise HTTPException(409, "O laboratório de combate não tem preparação persistente.")

            probe = cards.with_location(state)  # `_location` só na cópia transitória
            result = cards.set_prepared(probe, req.prepared)
            if not result["ok"]:
                _fail_operation(claim, "invalid_prepare")
                allowed, reason = cards.reorganize_status(state)
                status = 409 if not allowed else 400
                raise api_error(status, "prepare_rejected", detail=reason or result["error"])
            state["player"] = probe["player"]
            player = state["player"]
            response = {
                "ok": True,
                "prepared_cards": list(player.get("prepared_cards") or []),
                "cards": _cards_block(player),
                "prepared_slots": _prepared_slots(player),
            }
            return _commit_state_mutation(
                state,
                response,
                claim=claim,
                request_hash=request_hash,
            )


def _card_reward_mutation(
    game_id: str | None,
    action_id: str | None,
    payload: dict,
    apply: Callable[[dict], dict],
    reject_code: str,
) -> Any:
    """SPEC-333: esqueleto das mutações do espólio/forja (mesmo contrato de idempotência de
    `/game/cards/prepare`; reaproveita o kind `equip` — CHECK do banco). A regra mora em
    `services.card_rewards`; aqui só o transporte."""
    from services import card_rewards

    _bind_corr(game_id, action_id)
    lock = api_core._game_lock(game_id) if not api_core._database_profile() else nullcontext()
    with lock:
        _, state = api_core._load_or_404(game_id)
        claim, request_hash, receipt = _begin_state_mutation(
            state, action_id=action_id, kind="equip", payload=payload
        )
        if receipt is not None:
            return receipt
        from infrastructure.runtime import get_runtime
        from services.turn_execution import operation_scope

        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            _reject_archived(state)
            _reject_memorial(state)
            if state.get("death_pending"):
                raise HTTPException(409, "Resolva a queda antes desta alteração.")
            if (state.get("combat_simulation") or {}).get("enabled"):
                _fail_operation(claim, "simulation")
                raise HTTPException(409, "O laboratório de combate não tem preparação persistente.")
            if card_rewards.mode() != "on":
                _fail_operation(claim, "card_rewards_off")
                raise api_error(409, "card_rewards_off")
            result = apply(state)
            if not result["ok"]:
                _fail_operation(claim, reject_code)
                raise api_error(
                    409 if result.get("conflito") else 400, reject_code, detail=result["error"]
                )
            player = state["player"]
            response = {
                "ok": True,
                "log": result.get("log", ""),
                "player_stats": {
                    "gold": int(player.get("gold", 0) or 0),
                    "cards": _cards_block(player),
                    "prepared_slots": _prepared_slots(player),
                    **_card_reward_blocks(state),
                },
                "espolio_pendente": _card_reward_blocks(state).get("espolio_pendente"),
            }
            return _commit_state_mutation(state, response, claim=claim, request_hash=request_hash)


@router.post("/game/espolio")
def game_espolio(req: EspolioRequest):
    """SPEC-333 R1/R3: escolhe 1 das 3 Cartas do espólio (ou recusa por 15 de ouro)."""
    from services import card_rewards

    return _card_reward_mutation(
        req.game_id,
        req.action_id,
        req.model_dump(mode="json", exclude={"action_id"}),
        lambda state: card_rewards.accept(state, req.card_id or None),
        "espolio_rejected",
    )


@router.post("/game/loja-cartas")
def game_loja_cartas(req: LojaCartasRequest):
    """SPEC-357 R7/R9: compra uma Carta neutra do mercador (preço e prateleira em Python)."""
    from services import card_shop

    return _card_reward_mutation(
        req.game_id,
        req.action_id,
        req.model_dump(mode="json", exclude={"action_id"}),
        lambda state: card_shop.buy(state, req.card_id),
        "loja_cartas_rejected",
    )


@router.post("/game/forja")
def game_forja(req: ForjaRequest):
    """SPEC-333 R4/R5/R8: esquecer / afiar / purgar Cicatriz, fora de combate."""
    from services import card_rewards

    def apply(state: dict) -> dict:
        if req.acao == "esquecer":
            return card_rewards.forget(state, req.card_id or "", req.via or "")
        if req.acao == "afiar":
            return card_rewards.sharpen(state, req.card_id or "")
        return card_rewards.purge_curse(state, req.scar_id or "", req.via or "")

    return _card_reward_mutation(
        req.game_id,
        req.action_id,
        req.model_dump(mode="json", exclude={"action_id"}),
        apply,
        "forja_rejected",
    )


@router.post("/game/levelup")
def game_levelup(req: LevelUpRequest):
    """Fase 4.1: aplica UMA escolha de level up (habilidade ou atributo).

    Validação 100% server-side (progression.apply_choice): escolha inexistente,
    habilidade inelegível (classe/nível/pré-requisito/ramo rival) ou atributo
    inválido → 400 e o save fica intocado."""
    _bind_corr(req.game_id, getattr(req, "action_id", None))
    lock = api_core._game_lock(req.game_id) if not api_core._database_profile() else nullcontext()
    with lock:
        _, state = api_core._load_or_404(req.game_id)
        claim, request_hash, receipt = _begin_state_mutation(
            state,
            action_id=req.action_id,
            kind="levelup",
            payload=req.model_dump(mode="json", exclude={"action_id"}),
        )
        if receipt is not None:
            return receipt
        from infrastructure.runtime import get_runtime
        from services.turn_execution import operation_scope

        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            _reject_archived(state)
            _reject_memorial(state)
            if state.get("death_pending"):
                raise HTTPException(409, "Resolva a queda antes desta alteração.")

            player, err = progression.apply_choice(
                state["player"],
                req.choice_id,
                card_id=req.card_id,
                evolve_card_id=req.evolve_card_id,
                caminho=req.caminho,
                virtude=req.virtude,
                attr=req.attr,
                subclass_id=req.subclass_id,
                virtue_card_id=req.virtue_card_id,
            )
            if err:
                _fail_operation(claim, "invalid_choice")
                raise api_error(400, "levelup_rejected", detail=err)

            progression_events = list(player.pop("progression_events", []) or [])
            state["player"] = player
            for progress_event in progression_events:
                if progress_event.get("type") == "subclass_chosen":
                    from uuid import uuid4

                    from services.chronicle import append_entry

                    subclass_id = str(progress_event.get("subclass_id", ""))
                    option = next(
                        (
                            row
                            for row in progression.eligible_subclasses(player)
                            if row["id"] == subclass_id
                        ),
                        {"name": subclass_id},
                    )
                    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
                    event_id = uuid4().hex
                    state["event_log"] = list(state.get("event_log") or []) + [
                        {
                            "event_id": event_id,
                            "turn": turn,
                            "type": "subclass_chosen",
                            "actor_id": "player",
                            "target_id": subclass_id,
                            "payload": {"subclass_id": subclass_id, "name": option["name"]},
                            "source": "progression",
                        }
                    ]
                    state["chronicle"] = append_entry(
                        state.get("chronicle") or [],
                        text=f"A subclasse {option['name']} foi escolhida.",
                        turn=turn,
                        kind="milestone",
                        event_id=event_id,
                    )
            response = {
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
            return _commit_state_mutation(
                state,
                response,
                claim=claim,
                request_hash=request_hash,
            )
