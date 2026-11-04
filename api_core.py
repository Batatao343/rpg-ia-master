"""SPEC-381: helpers compartilhados da API (movidos de api.py, sem mudanca)."""

import contextvars
import hashlib
import json
import logging
import os
import threading
import uuid
from collections import Counter
from contextlib import contextmanager
from typing import Any
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import persistence as persistence_module
from persistence import load_game_state, save_game_state, save_path
from services.error_codes import api_error
from services.usage_metering import normalize_attempts, operation_cost
from api_models import CreateCharacterRequest, GameResponse


def _current_request_id() -> str | None:
    from observability.telemetry import correlation

    return correlation().get("request_id")


def _error_response(
    status: int,
    detail: Any,
    *,
    code: str | None = None,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    """SPEC-242 R1: envelope unico ``{detail, code, request_id}`` (+ extras aditivos)."""
    from services.error_codes import envelope

    rid = _current_request_id()
    body = envelope(status, detail, code=code, request_id=rid, **extra)
    hdrs = dict(headers or {})
    if rid:
        hdrs["X-Request-ID"] = rid
    return JSONResponse(body, status_code=status, headers=hdrs or None)


def _log_csrf_rejection(request: Request, code: str) -> None:
    """SPEC-245 R3: motivo fechado; a origem só aparece se estiver na allowlist."""
    from observability.auth_log import origin_host, reject
    from services.auth_sessions import CSRF_COOKIE

    reason = code
    if code == "csrf_invalid" and (
        not request.cookies.get(CSRF_COOKIE) or not request.headers.get("x-csrf-token")
    ):
        reason = "csrf_missing"
    reject(
        "csrf_rejected",
        reason,
        route=request.url.path,
        method=request.method,
        origin_host=origin_host(request.headers.get("origin"), _CORS_ORIGINS),
    )


def _database_profile() -> bool:
    return os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"


_turn_logger = logging.getLogger("rpg.turn")


# spec streaming-turno-sse (R5): telemetria de LLM em PRODUÇÃO — o hook do
# roteamento acumula os invokes do turno corrente num ContextVar (cada request
# síncrono roda numa thread com contexto próprio; zero vazamento entre turnos).
# Dev-only: os campos vão no log `rpg.turn`, NUNCA no GameResponse.
_llm_turn_events: contextvars.ContextVar = contextvars.ContextVar(
    "rpg_llm_turn_events", default=None
)


_llm_attempt_events: contextvars.ContextVar = contextvars.ContextVar(
    "rpg_llm_attempt_events", default=None
)


_embedding_attempt_events: contextvars.ContextVar = contextvars.ContextVar(
    "rpg_embedding_attempt_events", default=None
)


def _embedding_telemetry_hook(event: dict) -> None:
    captured = _embedding_attempt_events.get()
    if captured is not None:
        captured.append(event)


def _captured_usage(claim):
    if claim is None:
        return []
    events = normalize_attempts(
        _usage_attempts(_llm_turn_events.get(), _llm_attempt_events.get()),
        operation_id=claim.operation_id,
        component=f"llm:{claim.lease_token}",
    )
    events.extend(
        normalize_attempts(
            _embedding_attempt_events.get() or [],
            operation_id=claim.operation_id,
            component=f"embedding:{claim.lease_token}",
            category="embedding",
        )
    )
    return events


# Hardening 2026-08-11: mutações do mesmo save são serializadas no processo.
# A Fase 10b substituirá isto por transação/lock distribuído no storage.
_game_locks: dict[str, threading.RLock] = {}


_game_locks_guard = threading.Lock()


def _game_lock(game_id: str | None) -> threading.RLock:
    if not game_id:
        # SPEC-228 R8: sem game_id, trava pelo UUID REAL do save mais recente
        # (legacy), para serializar com requisições que trazem o UUID.
        try:
            latest = persistence_module.get_latest_save_file()
            stem = os.path.basename(latest).removesuffix(".json") if latest else ""
            game_id = stem or None
        except Exception:
            game_id = None
    key = str(game_id or "__latest__")
    with _game_locks_guard:
        return _game_locks.setdefault(key, threading.RLock())


# SPEC-319 (revisao P2-6): o hedge abandonado nao e falha nem fallback do turno.
_NOT_A_FAILURE = frozenset({"success", "hedge_lost"})


def _llm_log_fields(
    events: list[dict] | None, attempts: list[dict] | None = None
) -> dict[str, Any]:
    events = events or []
    attempts = attempts or []
    network_attempts = [
        event
        for event in attempts
        if event.get(
            "network_attempted", event.get("outcome") not in {"build_error", "circuit_open"}
        )
    ]
    skipped = [event for event in attempts if event not in network_attempts]
    cost_events = _usage_attempts(events, attempts)
    normalized = normalize_attempts(cost_events, operation_id=uuid.UUID(int=0))
    return {
        "llm_calls": len(events),
        "llm_requests": len(network_attempts) if attempts else len(events),
        "llm_attempts": len(attempts),
        "llm_failures": sum(
            1 for event in network_attempts if event.get("outcome") not in _NOT_A_FAILURE
        ),
        "llm_skipped": len(skipped),
        "llm_attempt_outcomes": dict(Counter(event.get("outcome") or "?" for event in attempts)),
        "llm_providers": dict(Counter(e.get("provider") or "?" for e in events)),
        "fell_back": any(e.get("fell_back") for e in events),
        "cost_usd_est": round(float(operation_cost(normalized)), 9),
        "cost_basis": "estimated"
        if any(not item.billing_exact for item in normalized if item.counts_as_spend)
        else "normalized",
        # SPEC-236 R2: provider failures without usage are counted apart, never as spend.
        "llm_failed_no_usage": sum(1 for item in normalized if not item.counts_as_spend),
        # SPEC-248 R4: classe de erro (top 5) e status HTTP por tentativa, sem texto de provider
        "llm_errors": dict(
            Counter(
                event.get("error_type")
                for event in attempts
                if event.get("outcome") != "success" and event.get("error_type")
            ).most_common(5)
        ),
        "llm_http_statuses": dict(
            Counter(str(event.get("http_status")) for event in attempts if event.get("http_status"))
        ),
    }


def _usage_attempts(events: list[dict] | None, attempts: list[dict] | None) -> list[dict]:
    if attempts:
        return list(attempts)
    return [{**event, "outcome": "success", "network_attempted": True} for event in (events or [])]


def _resolve_save_file(game_id: str | None) -> str | None:
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
        raise HTTPException(
            status_code=409,
            detail="Esta saga terminou. A crônica permanece como memorial — comece uma nova jornada.",
        )
    # SPEC-233 R9: laboratório encerrado não vira campanha (sem XP/RAG/viagem).
    if (state.get("combat_simulation") or {}).get("enabled") and not (
        state.get("combat") or {}
    ).get("active"):
        raise HTTPException(
            status_code=409,
            detail="simulation_finished: o laboratório de combate terminou — reinicie a simulação.",
        )


def _reject_archived(state: dict) -> None:
    """spec conflito-01 R10: save anterior à migração de Virtudes/Vitalidade é
    ÓRFÃO. Somente-leitura — nenhuma ação o toca (409, nunca 500)."""
    if state.get("archived"):
        raise api_error(
            409,
            "game_archived",
            detail=state.get("archived_reason")
            or "Personagem arquivado por migração de sistema — comece uma nova jornada.",
        )


_CLIENT_LATENCY_PATH = "/telemetry/client-latency"


_CLIENT_ERROR_PATH = "/telemetry/client-error"


def _client_ip(request: Request) -> str:
    from services.abuse_policy import client_ip  # SPEC-219 R4

    return client_ip(request)


class QuotaExceeded(HTTPException):
    """429/503 de abuso levantado dentro de um handler (corpo completo via exception_handler)."""

    def __init__(self, detail: str, scope: str, retry_after: int, status_code: int = 429) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )
        self.scope = scope
        self.retry_after_seconds = int(retry_after)


def _enforce_owner_budget(cls_name: str, *, minute: bool = False, daily: bool = True) -> None:
    """SPEC-219 R2/R3/R8: antes de gastar LLM. Perfis DB apenas (legacy = so IP, R11)."""
    if not _database_profile():
        return
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime
    from services import abuse_policy
    from services.daily_spend_cap import text_cap_exceeded

    principal = current_principal()
    runtime = get_runtime()

    def _reader():
        from infrastructure.finops_reader import PostgresFinopsReader

        return PostgresFinopsReader(runtime.game_store.pool)

    if text_cap_exceeded(_reader):
        cap_retry = abuse_policy.seconds_until_utc_midnight()
        abuse_policy.record_block(cls_name, "cap", owner=principal.user_id, retry_after=cap_retry)
        raise QuotaExceeded("daily_spend_cap", "cap", cap_retry, 503)
    cls = abuse_policy.ROUTE_CLASSES[cls_name]
    if minute:
        _ip, owner_limit = abuse_policy.limits_for(cls)
        if owner_limit > 0:
            decision = runtime.rate_limiter.consume(
                f"user:{principal.user_id}:{cls.name}",
                limit=owner_limit,
                window_seconds=cls.window_s,
            )
            if not decision.allowed:
                abuse_policy.record_block(
                    cls.name,
                    "owner",
                    owner=principal.user_id,
                    retry_after=decision.retry_after_seconds,
                    limit=owner_limit,
                )
                raise QuotaExceeded("rate_limited", "owner", decision.retry_after_seconds)
    limit = abuse_policy.daily_quota_limit()
    quota = getattr(runtime, "daily_quota", None)
    if not daily or limit <= 0 or quota is None:
        return
    try:
        verdict = quota.bump(principal.user_id, cls_name, limit)
    except (
        Exception
    ) as exc:  # contador indisponivel nao pode derrubar o jogo (o IP/owner/min seguem valendo)
        abuse_policy.limiter_unavailable("daily_quota", exc)
        return
    if not verdict.allowed:
        abuse_policy.record_block(
            cls_name,
            "daily",
            owner=principal.user_id,
            retry_after=verdict.retry_after_seconds,
            limit=limit,
        )
        raise QuotaExceeded("daily_quota_exceeded", "daily", verdict.retry_after_seconds)


def _client_latency_enabled() -> bool:
    return os.getenv("RPG_CLIENT_LATENCY_REPORT", "0").strip() == "1"


def _metrics_authorized(request: Request) -> bool:
    """SPEC-221 R1: Bearer RPG_METRICS_TOKEN (>=32 chars). Perfil DB sem token valido = fechado."""
    import hmac

    token = os.getenv("RPG_METRICS_TOKEN", "")
    if not token:
        return not _database_profile()  # legacy/local sem env: scrape local aberto
    if len(token) < 32:
        return False
    header = request.headers.get("authorization", "")
    scheme, _, supplied = header.partition(" ")
    if scheme.lower() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(supplied.strip().encode(), token.encode())


def _account_reader():
    if not _database_profile():
        raise HTTPException(404, "Conta indisponível neste perfil.")
    from infrastructure.account_read_model import PostgresAccountReader
    from infrastructure.runtime import get_runtime

    return PostgresAccountReader(get_runtime().game_store.pool)


def _prologue_owner() -> str:
    """Dono do selo do prólogo: usuário autenticado, ou "legacy" (perfil sem login)."""
    try:
        from infrastructure.request_context import current_principal

        principal = current_principal(required=False)
    except Exception:  # silent-ok: sem principal = perfil legacy/CLI
        principal = None
    return str(getattr(principal, "user_id", None) or "legacy")


@contextmanager
def _meter_auxiliary_operation(kind: str, *, game_id: uuid.UUID | None = None):
    """Own stateless provider calls without persisting their input or output."""
    from rag import embedding_usage_scope

    claim = None
    coordinator = None
    if _database_profile():
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        coordinator = get_runtime().turn_coordinator
        operation_id = uuid.uuid4()
        claim = coordinator.claim(
            current_principal(),
            operation_id,
            game_id=game_id,
            kind=kind,
            request_hash=hashlib.sha256(operation_id.bytes).hexdigest(),
            base_version=None,
            exclusive=False,
        )
    llm_token = _llm_turn_events.set([])
    attempt_token = _llm_attempt_events.set([])
    embedding_token = _embedding_attempt_events.set([])
    try:
        with embedding_usage_scope(_embedding_telemetry_hook):
            yield
        if claim is not None:
            coordinator.complete(
                claim,
                committed_version=None,
                receipt={"status": "completed"},
                usage_events=_captured_usage(claim),
            )
    except Exception as exc:
        if claim is not None:
            try:
                coordinator.fail(claim, type(exc).__name__, usage_events=_captured_usage(claim))
            except Exception as fail_exc:
                _release_failed(claim, fail_exc, exc)
        raise
    finally:
        _llm_turn_events.reset(llm_token)
        _llm_attempt_events.reset(attempt_token)
        _embedding_attempt_events.reset(embedding_token)


def _enqueue_art_generation(state: dict, trigger, brief: dict) -> dict:
    """Automatic triggers publish offers; no reservation or job is created."""
    from dataclasses import asdict

    offer_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"art-offer:{state['game_id']}:{trigger.trigger_kind}:{trigger.trigger_instance_id}:{trigger.arc_instance_id}",
        )
    )
    offers = list(state.get("art_offers") or [])
    if not any(row.get("offer_id") == offer_id for row in offers):
        offers.append(
            {
                "offer_id": offer_id,
                "type": trigger.subject_type,
                "trigger": asdict(trigger),
                "brief": brief,
            }
        )
    state["art_offers"] = offers[-32:]
    return {"status": "offered", "offer_id": offer_id, "placeholder": True}


def _enqueue_turn_art(state_before: dict, state_after: dict, action_key: str) -> None:
    if os.getenv("RPG_DYNAMIC_ART_ENABLED", "0").strip().lower() not in {"1", "true", "yes"}:
        return
    from services.art_brief import build_epic_art_brief, build_npc_art_brief
    from services.art_triggers import resolve_art_triggers

    for trigger in resolve_art_triggers(state_before, state_after, action_key=action_key):
        brief = (
            build_npc_art_brief(state_after, trigger.subject_id)
            if trigger.subject_type == "npc"
            else build_epic_art_brief(state_after, {})  # SPEC-326 R8: chefe/local vêm do estado
        )
        _enqueue_art_generation(state_after, trigger, brief)


def _action_already_processed(state: dict, action_id: str | None) -> bool:
    return bool(action_id and action_id in (state.get("processed_action_ids") or []))


def _require_saved(state: dict, *, detail: str = "estado") -> None:
    if not save_game_state(state):
        raise RuntimeError(f"falha ao persistir {detail}")


def _op_rejected(reason: str, kind: str, operation_id=None) -> None:
    """SPEC-247 R3: todo 409 de operacao deixa linha com motivo fechado (nunca o id cru)."""
    try:
        from observability.telemetry import log_event, pseudonym

        log_event(
            "operation",
            "rejected",
            level="warning",
            reason=reason,
            op_kind=kind,
            op_ref=pseudonym(operation_id) if operation_id else None,
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


def _op_replayed(kind: str, operation_id=None) -> None:
    """SPEC-247 R3: resposta servida do recibo (idempotencia), sem reexecutar."""
    try:
        from observability.telemetry import log_event, pseudonym

        log_event(
            "operation",
            "replayed",
            op_kind=kind,
            op_ref=pseudonym(operation_id) if operation_id else None,
        )
    except Exception:  # silent-ok: o log nunca derruba o turno
        pass


def _validated_receipt(coordinator, principal, operation_id, *, game_id, kind, request_hash):
    from infrastructure.contracts import Conflict

    try:
        return coordinator.receipt(
            principal,
            operation_id,
            game_id=game_id,
            kind=kind,
            request_hash=request_hash,
        )
    except Conflict as exc:
        _op_rejected("request_mismatch", kind, operation_id)
        raise HTTPException(status_code=409, detail="operation_request_mismatch") from exc


def _failed_pending_operation(state: dict) -> str | None:
    """SPEC-235 R3: id da operação ``turn`` falha ainda não superada (perfil durável).

    Uma falha é "superada" quando uma operação posterior do mesmo jogo concluiu.
    ``death`` fica fora do gate de propósito: com ``death_pending`` o turno é
    rejeitado, então bloquear a morte criaria um deadlock."""
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    gid = uuid.UUID(str(state["game_id"]))
    with get_runtime().resources[0].connection() as connection:
        row = connection.execute(
            """
            select f.id from app.operations f
            where f.game_id=%s and f.owner_id=%s and f.kind='turn' and f.status='failed'
              and f.started_at > coalesce((select max(c.finished_at) from app.operations c
                    where c.game_id=f.game_id and c.status='completed'), '-infinity'::timestamptz)
            order by f.started_at desc limit 1
            """,
            (gid, current_principal().user_id),
        ).fetchone()
    return str(row["id"]) if row else None


def _begin_state_mutation(
    state: dict, *, action_id: str | None, kind: str, payload: dict[str, Any]
):
    if not _database_profile():
        return None, "", None
    if not action_id:
        raise HTTPException(status_code=400, detail="action_id é obrigatório neste perfil.")
    try:
        operation_id = uuid.UUID(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="action_id inválido.") from exc
    from infrastructure.contracts import Conflict
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    request_hash = hashlib.sha256(encoded).hexdigest()
    runtime = get_runtime()
    principal = current_principal()

    def receipt_fn():
        return _validated_receipt(
            runtime.turn_coordinator,
            principal,
            operation_id,
            game_id=uuid.UUID(str(state["game_id"])),
            kind=kind,
            request_hash=request_hash,
        )

    receipt = receipt_fn()
    if receipt and "response" in receipt:
        _op_replayed(kind, operation_id)
        return None, request_hash, receipt["response"]
    if kind in ("equip", "levelup"):
        pending_op = _failed_pending_operation(state)
        if pending_op:
            _op_rejected("pending_operation", kind, operation_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "pending_operation",
                    "operation_id": pending_op,
                    "message": (
                        "Há uma ação que falhou e ainda não foi superada. Retome-a ou conclua "
                        "uma nova ação antes desta alteração."
                    ),
                    "discardable": True,
                },
            )
    try:
        claim = runtime.turn_coordinator.claim(
            principal,
            operation_id,
            game_id=uuid.UUID(str(state["game_id"])),
            kind=kind,
            request_hash=request_hash,
            base_version=int(state.get("_storage_version", 0) or 0),
        )
    except Conflict as exc:
        receipt = receipt_fn()
        if receipt and "response" in receipt:
            _op_replayed(kind, operation_id)
            return None, request_hash, receipt["response"]
        _op_rejected("operation_in_progress", kind, operation_id)
        raise HTTPException(status_code=409, detail="operation_in_progress") from exc
    return claim, request_hash, None


def _begin_create_operation(req: CreateCharacterRequest):
    if not _database_profile():
        return None, "", None
    if not req.action_id:
        raise HTTPException(status_code=400, detail="action_id é obrigatório neste perfil.")
    try:
        operation_id = uuid.UUID(req.action_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="action_id inválido.") from exc
    from infrastructure.contracts import Conflict
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    payload = req.model_dump(mode="json", exclude={"action_id"})
    request_hash = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    runtime = get_runtime()
    principal = current_principal()

    def receipt_fn():
        return _validated_receipt(
            runtime.turn_coordinator,
            principal,
            operation_id,
            game_id=None,
            kind="new_game",
            request_hash=request_hash,
        )

    receipt = receipt_fn()
    if receipt and isinstance(receipt.get("response"), dict):
        _op_replayed("new_game", operation_id)
        return None, request_hash, GameResponse.model_validate(receipt["response"])
    try:
        claim = runtime.turn_coordinator.claim(
            principal,
            operation_id,
            game_id=None,
            kind="new_game",
            request_hash=request_hash,
            base_version=None,
        )
    except Conflict as exc:
        receipt = receipt_fn()
        if receipt and isinstance(receipt.get("response"), dict):
            _op_replayed("new_game", operation_id)
            return None, request_hash, GameResponse.model_validate(receipt["response"])
        _op_rejected("operation_in_progress", "new_game", operation_id)
        raise HTTPException(status_code=409, detail="operation_in_progress") from exc
    return claim, request_hash, None


def _commit_state_mutation(
    state: dict, response: dict[str, Any], *, claim, request_hash: str
) -> dict[str, Any]:
    if claim is None:
        _require_saved(state)
        return response
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    try:
        version, receipt = get_runtime().turn_coordinator.commit_game(
            current_principal(),
            claim,
            state,
            receipt={"response": response},
            input_sha256=request_hash,
            latency_ms=0,
            llm_cost_usd=0.0,
            checkpoint=False,
            record_turn=False,
        )
    except Exception as exc:
        try:
            get_runtime().turn_coordinator.fail(claim, type(exc).__name__)
        except Exception as fail_exc:
            _release_failed(claim, fail_exc, exc)
        raise
    state["_storage_version"] = version
    return dict(receipt["response"])


def _release_failed(claim, fail_exc: BaseException, cause: BaseException | None = None) -> None:
    """SPEC-250 R3: ``turn_coordinator.fail`` falhou => lease possivelmente nao liberado. Nunca levanta."""
    try:
        from observability.telemetry import log_event, pseudonym

        log_event(
            "operation",
            "release_failed",
            level="error",
            op_ref=pseudonym(getattr(claim, "operation_id", "")),
            error_type=type(fail_exc).__name__,
            cause_type=type(cause).__name__ if cause is not None else None,
        )
    except Exception:  # silent-ok: o log nunca mascara a falha original
        pass


def _fail_operation(claim, code: str) -> None:
    if claim is None:
        return
    try:
        from infrastructure.runtime import get_runtime

        get_runtime().turn_coordinator.fail(claim, code)
    except Exception as fail_exc:
        _release_failed(claim, fail_exc)


def _load_unlocked_or_locked(file_to_load, game_id: str | None):
    """Leitura sem lock (caminho comum); se falhar no perfil legacy, relê sob o
    lock do jogo. SPEC-213: com a projeção pós-resposta o save é regravado logo
    após a entrega, e no Windows uma leitura concorrente ao `os.replace` pode
    falhar transitoriamente — sob o lock não há escritor concorrente."""
    state = load_game_state(file_to_load)
    if not state and game_id and not _database_profile():
        with _game_lock(game_id):
            state = load_game_state(file_to_load)
    return state


def _bind_corr(game_id=None, action_id=None) -> None:
    """SPEC-240 R2: game_ref/action_ref no contexto de log do handler (nunca o id cru)."""
    try:
        from observability.telemetry import bind_correlation

        bind_correlation(game_id=game_id, action_id=action_id)
    except Exception:
        pass


# SPEC-381: a lista e preenchida no lugar por api.py (mesma posicao de import, reload-safe)
_CORS_ORIGINS: list[str] = []


def _load_or_404(
    game_id: str | None, *, detail: str = "Jogo não encontrado.", locked_read: bool = False
) -> tuple[str | None, dict]:
    """SPEC-381 R18: resolve o save, carrega e responde 404 se vazio.
    Resolve os loaders na hora da chamada (patches de teste continuam valendo)."""
    file_to_load = _resolve_save_file(game_id)
    if locked_read:
        state = _load_unlocked_or_locked(file_to_load, game_id)
    else:
        state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail=detail)
    return file_to_load, state
