"""SPEC-381: rotas de auth (movidas de api.py, sem mudanca)."""

import logging
import os
import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from infrastructure.contracts import public_auth_code
import api_core
from api_core import _CORS_ORIGINS, _client_ip, _client_latency_enabled, _log_csrf_rejection

router = APIRouter()


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    # Login aceita senhas legadas >=8; criação/troca exigem >=10 (SPEC-220 R9).
    password: str = Field(min_length=8, max_length=256)
    captcha_token: str | None = Field(default=None, max_length=4096)


class SignupRequest(AuthRequest):
    password: str = Field(min_length=10, max_length=256)
    # SPEC-222 R9 (D-D): declaração de 18+ exigida pela API (não só pela UI); sem ela, 422
    # antes de qualquer chamada ao provedor de identidade.
    age_confirmed: Literal[True]


@router.get("/auth/config")
def auth_config(request: Request):
    required = api_core._database_profile()
    authenticated = False
    principal = None
    if required:
        try:
            from infrastructure.runtime import get_runtime
            from services.auth_sessions import ACCESS_COOKIE

            principal = get_runtime().identity_verifier.verify(
                request.cookies.get(ACCESS_COOKIE),
            )
            authenticated = bool(principal)
        except Exception:
            authenticated = False
    from services.account_security import captcha_config

    lifecycle = False
    if required:
        from infrastructure.runtime import get_runtime
        from infrastructure.supabase_identity import SupabaseIdentityProvider

        lifecycle = isinstance(get_runtime().identity_verifier, SupabaseIdentityProvider)
    return {
        "required": required,
        "authenticated": authenticated,
        "lifecycle_available": lifecycle,
        "email_confirmation_required": _email_confirmation_required(),
        "captcha": captcha_config(),
        # SPEC-200 R10: so aparece quando LIGADO (default: ausente => cliente nao envia).
        **({"client_latency_report": True} if _client_latency_enabled() else {}),
        **({"user_id": str(principal.user_id)} if principal else {}),
    }


def _android_refresh_max_age(request: Request | None) -> int | None:
    """SPEC-193: Max-Age so no refresh cookie e so p/ cliente nativo.

    O header X-RPG-Client NAO e fronteira de seguranca (qualquer cliente pode
    envia-lo); rotacao/revogacao do refresh token (SPEC-190) continua valendo.
    """
    if request is None or request.headers.get("x-rpg-client", "").lower() != "android":
        return None
    try:
        value = int(os.getenv("RPG_ANDROID_REFRESH_MAX_AGE_SECONDS", "1209600"))
    except ValueError:
        value = 1209600
    return min(max(value, 3600), 2592000)


def _set_session_cookies(
    response: Response, tokens, *, clear_deletion: bool = True, request: Request | None = None
) -> str:
    from services.auth_sessions import (
        ACCESS_COOKIE,
        CSRF_COOKIE,
        REFRESH_COOKIE,
        CsrfSigner,
        cookie_settings,
    )

    secure = os.getenv("RPG_COOKIE_SECURE", "0") == "1"
    csrf = CsrfSigner(os.getenv("RPG_SESSION_SECRET", "")).issue()
    if clear_deletion:
        response.delete_cookie("rpg_deletion", path="/account/delete")
    response.set_cookie(ACCESS_COOKIE, tokens.access_token, **cookie_settings(secure=secure))
    age = _android_refresh_max_age(request)
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        **cookie_settings(secure=secure, refresh=True),
        **({"max_age": age} if age else {}),
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
        # SPEC-193: o CSRF acompanha a vida do refresh no cliente nativo (senao /auth/refresh no boot falha).
        **({"max_age": age} if age else {}),
    )
    return csrf


@router.post("/auth/login")
def auth_login(body: AuthRequest, request: Request, response: Response):
    if not api_core._database_profile():
        raise HTTPException(status_code=404, detail="auth desativada no perfil legacy")
    from infrastructure.contracts import Unauthorized
    from infrastructure.runtime import get_runtime
    from services.account_security import auth_limit, auth_success, captcha_config

    runtime = get_runtime()
    provider = runtime.identity_verifier
    captcha_mode = captcha_config()["mode"]
    if captcha_mode not in {"app", "gotrue"}:
        raise HTTPException(503, "captcha_unavailable")
    if captcha_mode == "gotrue":
        _auth_abuse(request, action="login", email=body.email, captcha_token=body.captcha_token)
    else:
        _require_allowed_origin(request)  # SPEC-220 R5: login CSRF
        auth_limit(runtime, request, action="login", email=body.email)
    try:
        if captcha_mode == "gotrue":
            tokens = provider.login(body.email, body.password, captcha_token=body.captcha_token)
        else:
            tokens = provider.login(body.email, body.password)
    except Unauthorized as exc:
        code = public_auth_code(exc)
        if code == "captcha_invalid":
            raise HTTPException(status_code=403, detail=code) from None
        if code == "credentials_invalid":
            # SPEC-220 R4: só a falha de credencial conta no bucket por e-mail.
            auth_limit(runtime, request, action="login", email=body.email, stage="failure")
        raise HTTPException(status_code=401, detail=code) from None
    auth_success(runtime, action="login", email=body.email, request=request)
    try:
        provider.verify(tokens.access_token)
    except Unauthorized as exc:
        raise HTTPException(status_code=401, detail=public_auth_code(exc)) from None
    csrf = _set_session_cookies(response, tokens, request=request)
    _set_recent_cookie(response, tokens.user_id, tokens.access_token)
    return {"authenticated": True, "csrf_token": csrf}


@router.post("/auth/signup")
def auth_signup(body: SignupRequest, request: Request, response: Response):
    if not api_core._database_profile():
        raise HTTPException(status_code=404, detail="auth desativada no perfil legacy")
    from infrastructure.contracts import Unauthorized
    from infrastructure.runtime import get_runtime
    from services.account_security import GENERIC_MESSAGE

    _auth_abuse(request, action="signup", email=body.email, captcha_token=body.captcha_token)
    try:
        from services.account_security import captcha_config

        if captcha_config()["mode"] == "gotrue":
            tokens = get_runtime().identity_verifier.signup(
                body.email, body.password, captcha_token=body.captcha_token
            )
        else:
            tokens = get_runtime().identity_verifier.signup(body.email, body.password)
        if tokens is None or _email_confirmation_required():
            if tokens:
                get_runtime().identity_verifier.logout(tokens.access_token)
            response.status_code = 202
            return {"authenticated": False, "message": GENERIC_MESSAGE}
        csrf = _set_session_cookies(response, tokens, request=request)
        return {"authenticated": True, "csrf_token": csrf}
    except Unauthorized as exc:
        if public_auth_code(exc) == "captcha_invalid":
            raise HTTPException(status_code=403, detail="captcha_invalid") from None
        if _email_confirmation_required():
            response.status_code = 202
            return {"authenticated": False, "message": GENERIC_MESSAGE}
        raise HTTPException(status_code=400, detail=public_auth_code(exc)) from None


def _email_confirmation_required() -> bool:
    return (
        os.getenv(
            "RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED",
            "1" if os.getenv("RPG_RUNTIME_PROFILE", "").startswith("hosted") else "0",
        )
        == "1"
    )


def _set_recent_cookie(response: Response, owner, access: str) -> None:
    from services.account_security import RECENT_COOKIE, proof

    response.set_cookie(
        RECENT_COOKIE,
        proof(owner, "recent", access),
        max_age=300,
        httponly=True,
        secure=os.getenv("RPG_COOKIE_SECURE", "0") == "1",
        samesite="strict",
        path="/",
    )


def _lifecycle_runtime():
    from infrastructure.runtime import get_runtime
    from infrastructure.supabase_identity import SupabaseIdentityProvider

    runtime = get_runtime()
    if not api_core._database_profile() or not isinstance(
        runtime.identity_verifier, SupabaseIdentityProvider
    ):
        raise HTTPException(404, "lifecycle_unavailable")
    return runtime


def _require_allowed_origin(request: Request) -> None:
    """SPEC-220 R5: rotas públicas de /auth só aceitam Origin da allowlist."""
    if request.headers.get("origin") not in _CORS_ORIGINS:
        _log_csrf_rejection(request, "origin_denied")
        raise HTTPException(403, "origin_denied")


def _auth_abuse(
    request: Request,
    *,
    action: str,
    email: str = "",
    captcha_token: str | None = None,
    access: str = "",
) -> None:
    from infrastructure.contracts import Unauthorized
    from infrastructure.runtime import get_runtime
    from services.account_security import auth_limit, validate_captcha

    _require_allowed_origin(request)
    runtime = get_runtime()
    auth_limit(runtime, request, action=action, email=email, access=access)
    from services.account_security import captcha_config

    captcha_mode = captcha_config()["mode"]
    if captcha_mode not in {"app", "gotrue"}:
        raise HTTPException(503, "captcha_unavailable")
    if action in {"signup", "reset", "verify"} or (
        captcha_mode == "gotrue" and action in {"login", "reauth"}
    ):
        try:
            validate_captcha(captcha_token, remote_ip=_client_ip(request), action=action)
        except ValueError:
            raise HTTPException(503, "captcha_unavailable") from None
        except Unauthorized as exc:
            raise HTTPException(403, public_auth_code(exc)) from None


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    captcha_token: str | None = Field(default=None, max_length=4096)


class VerifyEmailRequest(BaseModel):
    token_hash: str = Field(min_length=10, max_length=512)
    type: Literal["signup"] = "signup"


class ResetPasswordRequest(BaseModel):
    token_hash: str = Field(min_length=10, max_length=512)
    new_password: str = Field(min_length=10, max_length=256)


@router.post("/auth/reset/request", status_code=202)
@router.post("/auth/verify/request", status_code=202)
def auth_email_request(body: EmailRequest, request: Request):
    import logging

    import httpx

    from infrastructure.contracts import Unauthorized
    from infrastructure.supabase_identity import AuthEmailDeliveryError
    from observability.metrics import metrics
    from observability.telemetry import correlation, safe_json
    from services.account_security import GENERIC_MESSAGE

    runtime = _lifecycle_runtime()
    recovery = request.url.path == "/auth/reset/request"
    action = "reset" if recovery else "verify"
    _auth_abuse(request, action=action, email=body.email, captcha_token=body.captcha_token)
    try:
        from services.account_security import captcha_config

        if captcha_config()["mode"] == "gotrue":
            runtime.identity_verifier.request_email(
                body.email, recovery=recovery, captcha_token=body.captcha_token
            )
        else:
            runtime.identity_verifier.request_email(body.email, recovery=recovery)
    except Unauthorized as exc:
        # Captcha recusado pelo GoTrue não depende da conta: dizer isso não enumera.
        raise HTTPException(403, public_auth_code(exc)) from None
    except (AuthEmailDeliveryError, httpx.HTTPError) as exc:
        status_class = exc.status_class if isinstance(exc, AuthEmailDeliveryError) else "network"
        metrics.increment(
            "rpg_auth_email_delivery_failures_total",
            {"action": action, "status_class": status_class},
        )
        logging.getLogger("rpg.account").warning(
            safe_json(
                {
                    "event": "auth.email_delivery_failed",
                    "flow": action,
                    "status_class": status_class,
                    "request_id": correlation().get("request_id"),
                }
            )
        )
    return {"message": GENERIC_MESSAGE}


@router.post("/auth/verify")
def auth_verify_email(body: VerifyEmailRequest, request: Request, response: Response):
    from infrastructure.contracts import Unauthorized

    runtime = _lifecycle_runtime()
    _auth_abuse(request, action="verify_link")
    try:
        tokens = runtime.identity_verifier.verify_email(body.token_hash)
        runtime.identity_verifier.verify(tokens.access_token)
        return {
            "authenticated": True,
            "csrf_token": _set_session_cookies(response, tokens, request=request),
        }
    except Unauthorized as exc:
        raise HTTPException(400, public_auth_code(exc)) from None


def _clear_auth_cookies(response: Response, *, keep_csrf: bool = False) -> None:
    from services.account_security import RECENT_COOKIE
    from services.auth_sessions import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE

    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/auth/refresh")
    response.delete_cookie(RECENT_COOKIE, path="/")
    if not keep_csrf:
        response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/auth/reset/confirm")
def auth_reset_confirm(body: ResetPasswordRequest, request: Request, response: Response):
    from infrastructure.contracts import Unauthorized

    runtime = _lifecycle_runtime()
    _auth_abuse(request, action="reset_link")
    try:
        runtime.identity_verifier.reset_password(body.token_hash, body.new_password)
    except Unauthorized as exc:
        raise HTTPException(400, public_auth_code(exc)) from None
    _clear_auth_cookies(response)
    return {"authenticated": False, "message": "Senha atualizada. Entre novamente."}


class ReauthRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)
    captcha_token: str | None = Field(default=None, max_length=4096)


@router.post("/auth/reauth")
def auth_reauthenticate(body: ReauthRequest, request: Request, response: Response):
    from infrastructure.contracts import Unauthorized
    from services.auth_sessions import ACCESS_COOKIE

    runtime = _lifecycle_runtime()
    access = request.cookies.get(ACCESS_COOKIE) or ""
    _auth_abuse(request, action="reauth", captcha_token=body.captcha_token, access=access)
    try:
        _validate_auth_csrf(request)
        from services.account_security import auth_limit, auth_success, captcha_config

        if not access:
            raise Unauthorized("invalid_token")
        try:
            if captcha_config()["mode"] == "gotrue":
                owner = runtime.identity_verifier.reauthenticate(
                    access, body.password, captcha_token=body.captcha_token
                )
            else:
                owner = runtime.identity_verifier.reauthenticate(access, body.password)
        except Unauthorized:
            auth_limit(runtime, request, action="reauth", stage="failure", access=access)
            raise
        auth_success(runtime, action="reauth", email="", request=request, access=access)
        _set_recent_cookie(response, owner, access)
        return {"recent": True}
    except Unauthorized as exc:
        raise HTTPException(401, public_auth_code(exc)) from None


def _require_recent(request: Request, owner) -> None:
    from infrastructure.contracts import Unauthorized
    from services.account_security import RECENT_COOKIE, proof_owner
    from services.auth_sessions import ACCESS_COOKIE

    try:
        if (
            proof_owner(
                request.cookies.get(RECENT_COOKIE),
                "recent",
                request.cookies.get(ACCESS_COOKIE) or "",
            )
            != owner
        ):
            raise Unauthorized("recent_session_required")
    except Unauthorized:
        raise HTTPException(403, "recent_session_required") from None


@router.get("/account/export")
def account_export(request: Request):
    from fastapi.encoders import jsonable_encoder

    from infrastructure.account_lifecycle import PostgresAccountLifecycle
    from infrastructure.request_context import current_principal

    runtime = _lifecycle_runtime()
    principal = current_principal()
    _require_recent(request, principal.user_id)
    data = PostgresAccountLifecycle(
        runtime.game_store.pool, runtime.identity_verifier, runtime.blob_store
    ).export(principal)
    return JSONResponse(
        jsonable_encoder(data),
        headers={
            "Content-Disposition": 'attachment; filename="valoria-account.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/game/{game_id}/audit-export")
def game_audit_export(game_id: str, request: Request):
    """SPEC-207: pacote ZIP de auditoria, owner-only, prova recente, zero LLM.

    Gerado em memória e devolvido como download; nada é retido no servidor."""
    if not api_core._database_profile():
        raise HTTPException(404, "audit_export_unavailable_in_legacy")
    from infrastructure.audit_source import AccountDeleted, PostgresAuditSource
    from infrastructure.request_context import current_principal
    from infrastructure.runtime import get_runtime
    from observability.telemetry import pseudonym
    from services.audit_export import bundle_zip
    from services.audit_redaction import AuditRedactionError

    principal = current_principal()
    _require_recent(request, principal.user_id)
    try:
        game_uuid = uuid.UUID(game_id)
    except ValueError:
        raise HTTPException(404, "game_not_found") from None
    runtime = get_runtime()
    decision = runtime.rate_limiter.consume(
        f"audit-export:{pseudonym(principal.user_id)}", limit=3, window_seconds=600
    )
    if not decision.allowed:
        from services.abuse_policy import record_block

        record_block(
            "audit_export",
            "owner",
            owner=principal.user_id,
            retry_after=decision.retry_after_seconds,
            limit=3,
        )
        raise HTTPException(
            429,
            "audit_export_rate_limit",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    try:
        source = PostgresAuditSource(runtime.game_store.pool, runtime.game_store, principal).load(
            game_uuid
        )
    except AccountDeleted:
        raise HTTPException(401, "account_deleted") from None
    if source is None:
        raise HTTPException(404, "game_not_found")
    build_sha = os.getenv("GIT_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA") or "unknown"
    try:
        data = bundle_zip(source, build_sha=build_sha)
    except AuditRedactionError:
        raise HTTPException(500, "audit_export_redaction_failed") from None
    filename = f"valoria-auditoria-{pseudonym(game_uuid)}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


class DeleteAccountRequest(BaseModel):
    confirmation: Literal["EXCLUIR"]


@router.post("/account/delete")
def account_delete(body: DeleteAccountRequest, request: Request):
    from infrastructure.account_lifecycle import PostgresAccountLifecycle
    from infrastructure.request_context import current_principal
    from services.account_security import DELETE_COOKIE, proof

    runtime = _lifecycle_runtime()
    principal = current_principal()
    if principal.issuer != "deletion-retry":
        _require_recent(request, principal.user_id)
    lifecycle = PostgresAccountLifecycle(
        runtime.game_store.pool,
        runtime.identity_verifier,
        runtime.blob_store,
    )
    lifecycle.shared_blobs = getattr(runtime, "shared_blob_store", None)  # SPEC-352
    if principal.issuer != "deletion-retry":
        lifecycle.begin(principal.user_id)
    try:
        status = lifecycle.finish(principal.user_id)
    except Exception as exc:
        import logging

        from observability.telemetry import correlation, pseudonym, safe_json

        logging.getLogger("rpg.account").warning(
            safe_json(
                {
                    "event": "account.delete.finish_failed",
                    "owner_ref": pseudonym(principal.user_id),
                    "request_id": correlation().get("request_id"),
                    "error_type": type(exc).__name__,
                }
            )
        )
        status = "deleting"  # Durable denial remains; receipt enables a safe retry.
    response = JSONResponse(
        {"status": status},
        status_code=200 if status == "deleted" else 202,
        headers={"Cache-Control": "no-store"},
    )
    _clear_auth_cookies(response, keep_csrf=True)
    response.set_cookie(
        DELETE_COOKIE,
        proof(principal.user_id, "delete"),
        max_age=604800,
        httponly=True,
        secure=os.getenv("RPG_COOKIE_SECURE", "0") == "1",
        samesite="strict",
        path="/account/delete",
    )
    return response


def _validate_auth_csrf(request: Request) -> None:
    from services.auth_sessions import (
        CSRF_COOKIE,
        CsrfSigner,
        validate_mutation_request,
    )

    validate_mutation_request(
        cookie_token=request.cookies.get(CSRF_COOKIE),
        header_token=request.headers.get("x-csrf-token"),
        origin=request.headers.get("origin"),
        allowed_origins=set(_CORS_ORIGINS),
        signer=CsrfSigner(os.getenv("RPG_SESSION_SECRET", "")),
    )


@router.post("/auth/refresh")
def auth_refresh(request: Request, response: Response):
    from infrastructure.contracts import Unauthorized
    from infrastructure.runtime import get_runtime
    from services.auth_sessions import REFRESH_COOKIE

    try:
        _validate_auth_csrf(request)
        token = request.cookies.get(REFRESH_COOKIE)
        if not token:
            raise Unauthorized("session_missing")
        tokens = get_runtime().identity_verifier.refresh(token)
        get_runtime().identity_verifier.verify(tokens.access_token)
        csrf = _set_session_cookies(response, tokens, clear_deletion=False, request=request)
        return {"authenticated": True, "csrf_token": csrf}
    except Unauthorized as exc:
        raise HTTPException(status_code=401, detail=public_auth_code(exc)) from None


@router.post("/auth/logout", status_code=204)
# SPEC-220 R1: o cookie de refresh tem path /auth/refresh; só este alias o recebe.
@router.post("/auth/refresh/logout", status_code=204)
def auth_logout(request: Request, response: Response):
    from infrastructure.runtime import get_runtime
    from services.auth_sessions import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE

    _validate_auth_csrf(request)  # CsrfError => 403 (handler), nunca 500
    _revoke_session(
        get_runtime().identity_verifier,
        request.cookies.get(ACCESS_COOKIE),
        request.cookies.get(REFRESH_COOKIE),
    )
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/auth/refresh")
    response.delete_cookie("rpg_recent", path="/")
    response.delete_cookie("rpg_deletion", path="/account/delete")


def _revoke_session(identity, access: str | None, refresh: str | None) -> None:
    """SPEC-220 R1/R2: "Sair" encerra a sessão server-side, refresh incluído.

    Access válido => logout global; access ausente/vencido => troca o refresh e
    revoga com o access novo; owner conhecido => ``revoke_all`` (D-A). Idempotente:
    refresh já inválido ou upstream fora do ar nunca vira 500 (cookies saem igual).
    """
    from infrastructure.contracts import Unauthorized
    from observability.telemetry import correlation, safe_json

    owner = None
    stage = "verify"
    try:
        if access:
            try:
                owner = identity.verify(access).user_id
            except Unauthorized:
                owner = None
            if owner is not None:
                stage = "logout"
                identity.logout(access)
        if owner is None and refresh:
            stage = "refresh"
            tokens = identity.refresh(refresh)
            owner = tokens.user_id
            stage = "logout"
            identity.logout(tokens.access_token)
        if owner is not None and hasattr(identity, "revoke_all"):
            stage = "revoke_all"
            identity.revoke_all(owner)
    except Unauthorized:
        return  # refresh já rotacionado/revogado: nada a revogar
    except Exception as exc:  # upstream/DB fora do ar: cookies ainda são limpos
        logging.getLogger("rpg.account").warning(
            safe_json(
                {
                    "event": "auth.logout.revoke_failed",
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "request_id": correlation().get("request_id"),
                }
            )
        )
