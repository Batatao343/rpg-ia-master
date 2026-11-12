"""SPEC-381: rotas de billing (movidas de api.py, sem mudanca)."""

import os
import time
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
import api_core
from api_core import QuotaExceeded, _account_reader

router = APIRouter()


@router.get("/account/balance")
def account_balance():
    from infrastructure.request_context import current_principal

    return _account_reader().balance(current_principal())


def _stripe_payments():
    if not api_core._database_profile():
        raise HTTPException(503, "stripe_disabled")
    from services.stripe_checkout import StripeError, StripeSettings, StripeTestAdapter

    try:
        settings = StripeSettings.from_env()
    except StripeError:
        # A sales kill switch keeps signed late webhooks available while the
        # empty SKU allowlist prevents a new Checkout session.
        settings = StripeSettings.for_reconciliation()
    from infrastructure.runtime import get_runtime
    from infrastructure.stripe_payments import StripePayments

    return StripePayments(
        get_runtime().game_store.pool, settings, StripeTestAdapter(settings.secret_key)
    )


class CheckoutRequest(BaseModel):
    model_config = {"extra": "forbid"}
    sku_id: str = Field(min_length=1, max_length=120)
    request_id: uuid.UUID


@router.get("/account/checkout/skus")
def checkout_skus(request: Request):
    _refuse_android_stripe(request)
    from services.stripe_checkout import StripeError

    try:
        return JSONResponse(_stripe_payments().skus(), headers={"Cache-Control": "no-store"})
    except StripeError:
        raise HTTPException(503, "stripe_catalog_unavailable") from None


def _refuse_android_stripe(request: Request) -> None:
    # SPEC-194 R8 policy (not a security boundary): the Android app never uses Stripe.
    if request.headers.get("x-rpg-client", "").lower() == "android":
        raise HTTPException(403, "stripe_unavailable_on_android")


@router.post("/account/checkout")
def checkout_create(body: CheckoutRequest, request: Request):
    _refuse_android_stripe(request)
    from infrastructure.request_context import current_principal
    from services.kill_switches import SwitchOff
    from services.shard_pricing import PricingUnavailable
    from services.stripe_checkout import OpenOrdersLimit, StripeError

    try:
        return JSONResponse(
            _stripe_payments().checkout(current_principal(), body.sku_id, body.request_id),
            headers={"Cache-Control": "no-store"},
        )
    except OpenOrdersLimit:
        raise QuotaExceeded("too_many_open_orders", "owner", 60) from None
    except SwitchOff:
        raise HTTPException(503, "new_purchases_disabled") from None
    except (StripeError, PricingUnavailable) as exc:
        from infrastructure.payment_log import checkout_failed

        checkout_failed("create", exc)
        raise HTTPException(503, "stripe_checkout_unavailable") from None


_FAKE_GOOGLE = None


def _google_play():
    if not api_core._database_profile():
        raise HTTPException(503, "google_play_disabled")
    from infrastructure.google_play_payments import GooglePlayPurchases, PostgresPurchaseStore
    from infrastructure.runtime import get_runtime
    from services.google_play import GooglePlayError, _account_key, shared_client
    from services.google_play_fake import FakeGooglePlayClient, fake_allowed, fake_requested

    global _FAKE_GOOGLE
    try:
        _account_key()  # fail closed without the HMAC key (account binding cannot be trusted)
        if fake_requested() and not fake_allowed():
            raise GooglePlayError(
                "google_play_unconfigured"
            )  # fake flag on hosted/Vercel: refuse, never fall through
        if fake_allowed():  # SPEC-194: local profile + explicit env only; never hosted
            _FAKE_GOOGLE = _FAKE_GOOGLE or FakeGooglePlayClient()
            client = _FAKE_GOOGLE
        else:
            client = shared_client()
    except GooglePlayError:
        raise HTTPException(503, "google_play_unconfigured") from None
    return GooglePlayPurchases(PostgresPurchaseStore(get_runtime().game_store.pool), client)


class GooglePlayVerifyRequest(BaseModel):
    model_config = {"extra": "forbid"}
    product_id: str = Field(min_length=1, max_length=128)
    purchase_token: str = Field(min_length=16, max_length=2048)
    order_id: str | None = Field(default=None, max_length=128)


@router.get("/account/purchases/google/profile")
def google_play_profile():
    """Value the app must pass to setObfuscatedAccountId before launching billing."""
    from infrastructure.request_context import current_principal
    from services.google_play import GooglePlayError, obfuscated_account_id
    from services.kill_switches import SwitchOff, require_purchases

    try:  # SPEC-196 F4: client must hide buy buttons BEFORE the user pays at Google
        require_purchases("google_play")
    except SwitchOff:
        return JSONResponse(
            {"purchases_disabled": True, "reason": "new_purchases_disabled"},
            headers={"Cache-Control": "no-store"},
        )
    try:
        account_id = obfuscated_account_id(current_principal().user_id)
    except GooglePlayError:
        raise HTTPException(503, "google_play_unconfigured") from None
    return JSONResponse(
        {"obfuscated_account_id": account_id, "purchases_disabled": False},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/account/purchases/google/products")
def google_play_products():
    """Play product ids the app may query in the Store. No price: price comes from the Store only."""
    from infrastructure.google_play_payments import PostgresPurchaseStore
    from infrastructure.runtime import get_runtime

    if not api_core._database_profile():
        raise HTTPException(503, "google_play_disabled")
    items = PostgresPurchaseStore(get_runtime().game_store.pool).list_products()
    return JSONResponse({"items": items}, headers={"Cache-Control": "no-store"})


@router.post("/account/purchases/google/verify")
def google_play_verify(body: GooglePlayVerifyRequest):
    from infrastructure.request_context import current_principal
    from infrastructure.wallet import WalletConflict
    from services.google_play import GooglePlayError

    unavailable = ("google_play_unavailable", "google_play_unconfigured", "new_purchases_disabled")
    conflicts = (
        "google_play_token_conflict",
        "google_play_purchase_cancelled",
        "google_play_already_consumed",
        "google_play_test_purchase_rejected",
    )
    started = time.monotonic()
    try:
        result = _google_play().verify(
            current_principal(), body.product_id, body.purchase_token, body.order_id
        )
    except WalletConflict:
        from infrastructure.payment_log import google_verify

        google_verify("google_play_wallet_conflict", body, started, level="warning")
        raise HTTPException(409, "google_play_wallet_conflict") from None
    except GooglePlayError as exc:
        code = str(exc)
        from infrastructure.payment_log import google_verify

        google_verify(
            code,
            body,
            started,
            upstream_status=getattr(exc, "upstream_status", 0),
            level="error" if code in unavailable else "warning",
        )
        if code in unavailable:
            status = 503
        elif code in conflicts:
            status = 409
        elif code == "account_deleted":
            status = 403
        else:
            status = 422
        raise HTTPException(status, code) from None
    from infrastructure.payment_log import google_verify

    google_verify("pending" if result.get("status") == "pending" else "credited", body, started)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/account/checkout/{order_id}")
def checkout_status(order_id: uuid.UUID):
    from infrastructure.request_context import current_principal
    from services.stripe_checkout import StripeError

    try:
        result = _stripe_payments().order(current_principal(), str(order_id))
    except StripeError as exc:
        from infrastructure.payment_log import checkout_failed

        checkout_failed("order", exc)
        raise HTTPException(503, "stripe_checkout_unavailable") from None
    if result is None:
        raise HTTPException(404, "payment_order_not_found")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    """External provider route: raw signature replaces user cookie/CSRF auth."""
    import hashlib

    from infrastructure.payment_log import stripe_webhook as _wh
    from services.stripe_checkout import (
        MAX_WEBHOOK_BYTES,
        StripeError,
        StripeSettings,
        verify_event,
    )

    started = time.monotonic()
    try:
        try:
            settings = StripeSettings.from_env()
        except StripeError:
            settings = StripeSettings.for_reconciliation()
    except StripeError:
        _wh("disabled", started)
        raise HTTPException(503, "stripe_disabled") from None
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdecimal() or int(declared) > MAX_WEBHOOK_BYTES):
        _wh("too_large", started)
        from services.body_limit import log_body_too_large

        log_body_too_large(
            request.url.path,
            MAX_WEBHOOK_BYTES,
            int(declared) if declared.isdecimal() else None,
            routes=request.app.routes,
        )
        raise HTTPException(413, "stripe_body_limit")
    payload = bytearray()
    event = None
    try:
        async with __import__("asyncio").timeout(15):
            async for chunk in request.stream():
                if len(payload) + len(chunk) > MAX_WEBHOOK_BYTES:
                    _wh("too_large", started)
                    from services.body_limit import log_body_too_large

                    log_body_too_large(
                        request.url.path, MAX_WEBHOOK_BYTES, routes=request.app.routes
                    )
                    raise HTTPException(413, "stripe_body_limit")
                payload.extend(chunk)
        raw_body = bytes(payload)
        event = verify_event(
            raw_body, request.headers.get("stripe-signature", ""), settings.webhook_secret
        )
        result = await run_in_threadpool(
            _stripe_payments().accept_event, event, body_sha256=hashlib.sha256(raw_body).hexdigest()
        )
        _wh(
            "duplicate" if result.get("duplicate") else "applied",
            started,
            event=event,
            apply_result=result.get("apply_result"),
        )
        return result
    except StripeError as exc:
        code = str(exc.args[0] if exc.args else "")
        if event is None:
            _wh("signature_invalid", started, error_code=code)
        elif code == "stripe_event_replay_conflict":
            _wh("replay_conflict", started, event=event)
        else:  # evento autentico recusado pelas regras financeiras (ex.: sku_mismatch)
            _wh(
                "rejected",
                started,
                event=event,
                error_code=code,
                apply_result="sku_mismatch"
                if code == "stripe_order_sku_authority_mismatch"
                else None,
            )
        raise HTTPException(400, "stripe_event_invalid") from None
    except TimeoutError:
        _wh("timeout", started)
        raise HTTPException(408, "stripe_body_timeout") from None


@router.post("/account/transcriptions")
async def account_transcription(request: Request):
    """Raw audio upload, separate from game actions. No multipart spool or recording store."""
    from infrastructure.contracts import Conflict
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime
    from infrastructure.wallet import InsufficientShards, WalletConflict
    from services.shard_pricing import PricingUnavailable
    from services.speech_to_text import (
        MAX_AUDIO_BYTES,
        SpeechError,
        canonical_mime,
        transcribe_audio,
    )

    if not api_core._database_profile() or os.getenv("RPG_SPEECH_ENABLED", "0") != "1":
        raise HTTPException(503, "speech_disabled")
    principal = current_principal()
    runtime = get_runtime()
    decision = await run_in_threadpool(
        runtime.rate_limiter.consume,
        f"speech:{principal.user_id}",
        limit=5,
        window_seconds=60,
    )
    if not decision.allowed:
        from services.abuse_policy import record_block

        record_block(
            "stt",
            "owner",
            owner=principal.user_id,
            retry_after=decision.retry_after_seconds,
            limit=5,
        )
        raise HTTPException(
            429, "speech_rate_limit", headers={"Retry-After": str(decision.retry_after_seconds)}
        )
    try:
        operation_id = uuid.UUID(request.headers.get("x-operation-id", ""))
        mime = canonical_mime(request.headers.get("content-type", ""))
        declared = request.headers.get("content-length")
        if declared is not None and (
            not declared.isdecimal() or not 0 < int(declared) <= MAX_AUDIO_BYTES
        ):
            from services.body_limit import log_body_too_large

            log_body_too_large(
                request.url.path,
                MAX_AUDIO_BYTES,
                int(declared) if declared.isdecimal() else None,
                routes=request.app.routes,
            )
            raise SpeechError("audio_bytes", 413)
        payload = bytearray()
        async with __import__("asyncio").timeout(15):
            async for chunk in request.stream():
                if len(payload) + len(chunk) > MAX_AUDIO_BYTES:
                    from services.body_limit import log_body_too_large

                    log_body_too_large(request.url.path, MAX_AUDIO_BYTES, routes=request.app.routes)
                    raise SpeechError("audio_bytes", 413)
                payload.extend(chunk)
        from infrastructure.speech_finance import PostgresSpeechFinance

        result = await transcribe_audio(
            bytes(payload), mime, operation_id, PostgresSpeechFinance(runtime, principal)
        )
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except SpeechError as exc:
        raise HTTPException(exc.status, exc.code) from None
    except InsufficientShards:
        raise HTTPException(402, "speech_insufficient_balance") from None
    except (Conflict, WalletConflict):
        # Transcript is ephemeral. A consumed key never retranscribes its audio.
        raise HTTPException(409, "speech_operation_unavailable") from None
    except PricingUnavailable:
        raise HTTPException(503, "speech_pricing_unavailable") from None
    except (ValueError, TimeoutError):
        raise HTTPException(422, "speech_request_invalid") from None
    except Exception as exc:
        from observability.telemetry import log_event, safe_stack

        log_event(
            "stt",
            "internal_error",
            level="error",
            code="speech_internal_error",
            error_type=type(exc).__name__,
            stack=safe_stack(exc),
        )
        raise HTTPException(503, "speech_internal_error") from None


@router.get("/account/purchases")
def account_purchases(cursor: str | None = None, limit: int = 20):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().purchases(current_principal(), cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@router.get("/account/usage")
def account_usage(cursor: str | None = None, limit: int = 20):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().usage(current_principal(), cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@router.get("/account/series")
def account_series(period: str = "7d"):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().series(current_principal(), period)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@router.get("/game/{game_id}/operations/{operation_id}/cost")
def turn_cost(game_id: str, operation_id: str):
    _, state = api_core._load_or_404(game_id)
    if not api_core._database_profile():
        return {
            "history_id": None,
            "cost_milli": None,
            "technical_cost_usd": None,
            "technical_cost_basis": None,
            "technical_cost_exact": False,
        }
    from infrastructure.request_context import current_principal

    try:
        cost = _account_reader().operation_cost(
            current_principal(), uuid.UUID(game_id), uuid.UUID(operation_id)
        )
    except ValueError as exc:
        raise HTTPException(400, "ID inválido.") from exc
    if cost is None:
        raise HTTPException(404, "Turno não encontrado.")
    return cost


@router.get("/game/{game_id}/operations/{operation_id}")
def operation_status(game_id: str, operation_id: str):
    _, state = api_core._load_or_404(game_id)  # ownership before lookup
    try:
        op, gid = uuid.UUID(operation_id), uuid.UUID(str(state["game_id"]))
    except ValueError as exc:
        raise HTTPException(400, "ID inválido.") from exc
    if not api_core._database_profile():
        return {
            "status": "completed"
            if api_core._action_already_processed(state, operation_id)
            else "unknown",
            "response": None,
            "legacy": True,
        }
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime

    runtime = get_runtime()
    with runtime.resources[0].connection() as connection:
        row = connection.execute(
            "select status,receipt,request_sha256 from app.operations where id=%s and game_id=%s and owner_id=%s",
            (op, gid, current_principal().user_id),
        ).fetchone()
    if not row:
        return {"status": "unknown", "response": None}
    return {
        "status": row["status"],
        "response": (row["receipt"] or {}).get("response"),
        "request_hash": row["request_sha256"],
    }
