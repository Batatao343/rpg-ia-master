"""SPEC-381: rotas de saves (movidas de api.py, sem mudanca)."""

import hashlib
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import api_core
from api_core import (
    _fail_operation,
    _meter_auxiliary_operation,
    _op_rejected,
    _op_replayed,
    _validated_receipt,
)
from api_models import ChronicleSearchRequest

router = APIRouter()


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


@router.get("/game/saves", response_model=list[SaveSummary])
def get_saves():
    """R1: lista as campanhas salvas (mtime desc; corrompido é pulado)."""
    import persistence as persistence_mod

    return persistence_mod.list_saves()


@router.delete("/game/save/{game_id}")
def delete_save_endpoint(game_id: str, request: Request):
    """R2: exclui save + memória da sessão. Confirmação é da UI (uso local)."""
    import persistence as persistence_mod

    if api_core._database_profile():
        from infrastructure.contracts import Conflict, NotFound
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        try:
            game_uuid = uuid.UUID(game_id)
            operation_id = uuid.UUID(request.headers.get("idempotency-key", ""))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key UUID é obrigatório.",
            ) from exc
        runtime = get_runtime()
        principal = current_principal()
        receipt_fn = getattr(runtime.turn_coordinator, "receipt", None)
        digest = hashlib.sha256(f"delete:{game_uuid}".encode()).hexdigest()
        # SPEC-337 R17: recibo validado por kind+hash (o delete grava game_id=None de propósito).
        prior = (
            _validated_receipt(
                runtime.turn_coordinator,
                principal,
                operation_id,
                game_id=None,
                kind="delete",
                request_hash=digest,
            )
            if callable(receipt_fn)
            else None
        )
        if prior:
            return prior
        try:
            claim = runtime.turn_coordinator.claim(
                principal,
                operation_id,
                game_id=None,
                kind="delete",
                request_hash=digest,
                base_version=None,
            )
            return runtime.turn_coordinator.commit_delete(
                principal,
                claim,
                game_uuid,
                receipt={"ok": True},
            )
        except Conflict as exc:
            prior = (
                _validated_receipt(
                    runtime.turn_coordinator,
                    principal,
                    operation_id,
                    game_id=None,
                    kind="delete",
                    request_hash=digest,
                )
                if callable(receipt_fn)
                else None
            )
            if prior:
                _op_replayed("delete", operation_id)
                return prior
            _op_rejected("operation_in_progress", "delete", operation_id)
            raise HTTPException(status_code=409, detail="operation_in_progress") from exc
        except NotFound as exc:
            _fail_operation(claim, "not_found")
            raise HTTPException(status_code=404, detail="Save não encontrado.") from exc
    try:
        with api_core._game_lock(game_id):
            removed = persistence_mod.delete_save(game_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="game_id inválido (esperado UUID).")
    if not removed:
        raise HTTPException(status_code=404, detail="Save não encontrado.")
    return {"ok": True}


@router.post("/game/chronicle/search")
def search_chronicle_endpoint(req: ChronicleSearchRequest):
    _, state = api_core._load_or_404(req.game_id)
    from services.chronicle_search import search_chronicle

    try:
        semantic = None
        if api_core._database_profile():
            from infrastructure.pgvector_memory import PgVectorMemoryStore
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime
            from services.chronicle_repository import ChronicleRepository

            runtime = get_runtime()
            if runtime.resources and isinstance(runtime.memory_store, PgVectorMemoryStore):
                with _meter_auxiliary_operation(
                    "chronicle_search", game_id=uuid.UUID(str(state["game_id"]))
                ):
                    semantic = ChronicleRepository(
                        runtime.resources[0],
                        runtime.memory_store,
                    ).semantic_candidates(
                        current_principal(),
                        uuid.UUID(str(state["game_id"])),
                        req.query,
                        top_k=req.top_k,
                    )
        from services.faction_display import conceal_for

        return conceal_for(  # SPEC-293 R3
            state,
            search_chronicle(
                state.get("chronicle") or [],
                req.query,
                top_k=req.top_k,
                semantic=semantic,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="chronicle_query_invalid") from exc


@router.get("/game/chronicle/export")
def export_chronicle(game_id: str | None = None):
    """R5: crônica como .txt (download) com separadores por capítulo."""
    from fastapi.responses import PlainTextResponse

    _, state = api_core._load_or_404(game_id, detail="Nenhum jogo salvo encontrado.")

    player = state.get("player") or {}
    lines: list[str] = [
        f"CRÔNICA DE {player.get('name', 'HERÓI').upper()}",
        f"{player.get('class_name', '')} — {state.get('world', {}).get('current_location', '')}",
        "",
    ]
    for cap in state.get("chronicle") or []:
        if not isinstance(cap, dict):
            continue
        lines.append("=" * 60)
        lines.append(
            f"{cap.get('title', '')}  (turno {cap.get('started_turn', 0)}"
            f" — {cap.get('location', '')})"
        )
        lines.append("=" * 60)
        for e in cap.get("entries") or []:
            if isinstance(e, dict) and str(e.get("text", "")).strip():
                marker = "•" if e.get("kind") == "milestone" else "—"
                lines.append(f"{marker} [t{e.get('turn', 0)}] {e['text']}")
        lines.append("")
    from services.body_limit import safe_attachment_filename

    ascii_name, quoted = safe_attachment_filename(str(player.get("name", "")))
    disposition = (
        f"attachment; filename=\"cronica_{ascii_name}.txt\"; filename*=UTF-8''cronica_{quoted}.txt"
    )
    from services.faction_display import conceal_for

    text = conceal_for(state, "\n".join(lines))  # SPEC-293 R3
    return PlainTextResponse(text, headers={"Content-Disposition": disposition})
