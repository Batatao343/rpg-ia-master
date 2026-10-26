"""
api.py
Interface REST API para o RPG Engine.
Atualizado para suportar Memória Híbrida (Game ID e Resumo).
Fase 10: game_id validado (UUID) na borda, CORS por env, rate limit mínimo,
log JSON por turno.
"""

import contextvars
import hashlib
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import uuid  # <--- Necessário para gerar IDs de sessão
from collections import Counter, defaultdict, deque
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from typing import Annotated, Any, Dict, List, Literal, Optional
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from observability.telemetry import log_event as _log_event

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
import gamedata
import persistence as persistence_module
import progression
from character_creator import create_player_character
from gamedata import CLASSES, load_json_data, seed_factions
from infrastructure.contracts import (
    AuthUnavailable,
    CsrfError,
    SessionSecretError,
    public_auth_code,
)
from infrastructure.contracts import (
    Unauthorized as _Unauthorized,
)
from infrastructure.db_roles import admin_connection

# --- CONFIGURAÇÃO DA API ---
# SPEC-218: boot fail-closed. Processo exposto (plataforma/bind) nunca sobe em
# `legacy`; perfis DB validam a config de segurança já no import, não no 1º request.
from infrastructure.runtime import assert_boot_policy, docs_enabled, is_hardened
from llm_setup import (
    LLMAttemptEvent,
    is_simulated,
    set_llm_attempt_telemetry_hook,
    set_llm_telemetry_hook,
)
from main import app as game_graph
from persistence import (
    IncompatibleSaveError,
    _serialize_messages,
    load_game_state,
    save_game_state,
    save_path,
)
from services import combat_flags
from services import npc_world as _npc_world
from services import quest_log
from services import state_views as sv
from services.chronicle import default_chapter_title
from services.discovery import player_codex
from services.error_codes import api_error
from services.prologue import StartScenarioIn, build_start_scenario, scenario_to_state_seed
from services.prompt_guard import origin_fragment
from services.usage_metering import normalize_attempts, operation_cost
from services.visual_catalog import (
    creation_visuals,
    resolve_turn_visual_state,
    visual_response,
)
from services.reputation import faction_tier
from world_utils import starting_world

assert_boot_policy(os.environ)
_DOCS_ON = docs_enabled(os.environ)

app = FastAPI(
    title="RPG IA Engine API",
    description="Backend para RPG de Texto com IA, Crafting e NPCs.",
    version="v2.0 Hybrid Memory",
    docs_url="/docs" if _DOCS_ON else None,
    redoc_url="/redoc" if _DOCS_ON else None,
    openapi_url="/openapi.json" if _DOCS_ON else None,
)


def _current_request_id() -> str | None:
    from observability.telemetry import correlation

    return correlation().get("request_id")


_CODE_RE = None


def _error_code_of(detail: Any) -> str | None:
    """Codigo curto/fechado quando o detail JA e um codigo (nunca prosa)."""
    global _CODE_RE
    import re

    _CODE_RE = _CODE_RE or re.compile(r"^[a-z][a-z0-9_.]{1,63}$")
    return detail if isinstance(detail, str) and _CODE_RE.match(detail) else None


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


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """SPEC-241 R3 + SPEC-242: corpo atual preservado + ``code`` + request_id (corpo e header)."""
    from services.error_codes import code_for

    code = code_for(exc.status_code, exc.detail, getattr(exc, "code", None))
    request.state.error_code = code
    return _error_response(
        exc.status_code, exc.detail, code=code, headers=exc.headers, **getattr(exc, "extra", {})
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """SPEC-241 R3: 422 com o corpo padrao + request_id; o log leva so os ``loc`` (sem valores)."""
    from fastapi.encoders import jsonable_encoder

    request.state.error_code = "validation_failed"
    errors = exc.errors()
    _log_event(
        "http",
        "validation_failed",
        level="warning",
        method=request.method,
        locs=[".".join(str(p) for p in e.get("loc", ())) for e in errors][:20],
        error_count=len(errors),
    )
    rid = _current_request_id()
    body: dict[str, Any] = {"detail": jsonable_encoder(errors), "code": "validation_failed"}
    if rid:
        body["request_id"] = rid
    return JSONResponse(body, status_code=422, headers={"X-Request-ID": rid} if rid else None)


@app.exception_handler(IncompatibleSaveError)
async def _incompatible_save_handler(_request, _exc):
    """SPEC-228 R9: save de schema mais novo é recusado, nunca regravado."""
    return _error_response(
        409,
        "Este save foi criado por uma versão mais nova do jogo; "
        "atualize o servidor antes de continuar.",
        code="save_schema_newer",
    )


@app.exception_handler(_Unauthorized)
async def _unauthorized_handler(request, exc):
    """SPEC-220 R3: 401 com código fechado; a mensagem interna fica só no servidor
    (SPEC-245 R2: ...mas agora vai para o log, como motivo fechado)."""
    from observability.auth_log import reject, session_reason

    code = public_auth_code(exc)
    request.state.error_code = code
    reject(
        "session_rejected",
        session_reason(exc),
        route=request.url.path,
        public_code=code,
        source="handler",
    )
    return _error_response(401, code)


@app.exception_handler(AuthUnavailable)
async def _auth_unavailable_handler(request, _exc):
    """SPEC-245 R1: GoTrue/JWKS fora do ar ou lento => 503 fechado, nunca 500."""
    request.state.error_code = "auth_unavailable"
    return _error_response(503, "auth_unavailable", headers={"Retry-After": "5"})


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


@app.exception_handler(CsrfError)
async def _csrf_handler(request, exc):
    """SPEC-220 R10: Origin/CSRF => 403, para o cliente não disparar refresh/logout."""
    request.state.error_code = exc.code
    _log_csrf_rejection(request, exc.code)
    return _error_response(403, exc.code)


@app.exception_handler(SessionSecretError)
async def _session_secret_handler(_request, _exc):
    return _error_response(503, "server_misconfigured")


# Fase 10 (R5): CORS restrito por default; configurável via RPG_CORS_ORIGINS
# (CSV no .env; "*" só se explicitamente configurado).
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("RPG_CORS_ORIGINS", "http://localhost:8000,http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "content-type",
        "x-csrf-token",
        "x-request-id",
        "x-rpg-client",
        "x-operation-id",
        "idempotency-key",
        "x-rpg-build",
        "x-rpg-app-version",
    ],
)


from services.body_limit import BodyLimitMiddleware  # SPEC-221 R6

app.add_middleware(
    BodyLimitMiddleware,
    default_limit=256 * 1024,
    per_path={
        "/account/transcriptions": 8 * 1024 * 1024 + 64 * 1024,
        # > MAX_WEBHOOK_BYTES: o handler (stream cru) responde o proprio 413 antes do corte do middleware.
        "/payments/stripe/webhook": 256 * 1024 + 64 * 1024,
        "/game/new": 64 * 1024,
        "/game/prologue": 64 * 1024,
        "/telemetry/client-error": 4 * 1024,  # SPEC-244 R3
    },
)

from services.cron_internal import router as _cron_router

app.include_router(
    _cron_router, include_in_schema=False
)  # SPEC-192: bearer-secret auth, no cookies/CSRF flow


def _database_profile() -> bool:
    return os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"


def _session_scoped_path(path: str, query) -> bool:
    """Rotas com dado POR JOGO/conta: exigem sessão nos perfis com banco.
    SPEC-210 (revisão Sol): `/data/map?game_id=` é a view filtrada de UM save —
    sem a fronteira não haveria principal (404 sempre no perfil DB) nem no-store."""
    if path == _CLIENT_ERROR_PATH:
        return False  # SPEC-244: erro na tela de login (sem sessao) tambem precisa chegar
    if path.startswith(("/game", "/account", "/telemetry")):
        return True
    return path == "/data/map" and bool(query.get("game_id"))


@app.middleware("http")
async def _session_boundary(request: Request, call_next):
    """Auth/CSRF só nos perfis Postgres; legacy loopback permanece intacto."""
    if not _database_profile() or not _session_scoped_path(request.url.path, request.query_params):
        return await call_next(request)
    from infrastructure.contracts import Unauthorized
    from infrastructure.request_context import reset_current_principal, set_current_principal
    from services.auth_sessions import CSRF_COOKIE, CsrfSigner, validate_mutation_request

    # SPEC-220 R8: o ``try`` cobre só identidade + CSRF; ``call_next`` fica fora,
    # então um ValueError do handler volta a ser 500 genérico (nunca 401).
    blocked = _authfail_blocked(request)  # SPEC-219 R6: sem chamar o verificador
    if blocked is not None:
        return blocked
    try:
        principal = _boundary_principal(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            secret = os.getenv("RPG_SESSION_SECRET", "")
            signer = CsrfSigner(secret)
            validate_mutation_request(
                cookie_token=request.cookies.get(CSRF_COOKIE),
                header_token=request.headers.get("x-csrf-token"),
                origin=request.headers.get("origin"),
                allowed_origins=set(_CORS_ORIGINS),
                signer=signer,
            )
    except CsrfError as exc:
        request.state.error_code = exc.code
        _log_csrf_rejection(request, exc.code)
        return _error_response(403, exc.code)
    except AuthUnavailable:
        from observability.auth_log import reject

        request.state.error_code = "auth_unavailable"
        reject(
            "session_rejected",
            "upstream_unavailable",
            route=request.url.path,
            public_code="auth_unavailable",
            source="boundary",
        )
        return _error_response(503, "auth_unavailable", headers={"Retry-After": "5"})
    except Unauthorized as exc:
        # Sem cookie nao ha verificacao a amplificar: visitante deslogado (bootstrap da SPA) nao
        # consome o balde, so quem apresenta credencial invalida (SPEC-219 R6, revisao Sol).
        from observability.auth_log import reject, session_reason

        code = public_auth_code(exc)
        request.state.error_code = code
        reject(
            "session_rejected",
            session_reason(exc),
            level=("warning" if request.cookies.get("rpg_access") else "debug"),
            route=request.url.path,
            public_code=code,
            source="boundary",
        )
        throttled = _record_authfail(request) if request.cookies.get("rpg_access") else None
        if throttled is not None:
            return throttled
        return _error_response(401, code)
    except ValueError:  # segredo de sessão curto/ausente (CsrfSigner/proof)
        from observability.auth_log import reject

        request.state.error_code = "server_misconfigured"
        reject(
            "session_rejected",
            "server_misconfigured",
            route=request.url.path,
            public_code="server_misconfigured",
            source="boundary",
            level="error",
        )
        return _error_response(503, "server_misconfigured")
    token = set_current_principal(principal)
    try:
        over = _owner_rate_limit(request, principal)  # SPEC-219 R2
        if over is not None:
            return over
        from observability.telemetry import correlation_scope

        with correlation_scope(owner_id=principal.user_id) as _corr:
            request.state.owner_ref = _corr.get("owner_ref")  # SPEC-241: access log
            return await call_next(request)
    finally:
        reset_current_principal(token)


AUTHFAIL_LIMIT = (60, 900)  # SPEC-219 R6: falhas de sessao por IP / 15 min
_authfail_until: dict[str, float] = {}  # chave -> monotonic ate quando o IP segue bloqueado


def _authfail_key(request: Request) -> str:
    from observability.telemetry import pseudonym

    return f"authfail:{pseudonym(_client_ip(request))}"


def _authfail_blocked(request: Request) -> "JSONResponse | None":
    until = _authfail_until.get(_authfail_key(request))
    if until is None:
        return None
    remaining = until - time.monotonic()
    if remaining <= 0:
        _authfail_until.pop(_authfail_key(request), None)
        return None
    return _blocked_response("rate_limited", "authfail", int(remaining) + 1)


def _record_authfail(request: Request) -> "JSONResponse | None":
    """Consome o balde de falhas (compartilhado entre instancias); estourou => 429."""
    from infrastructure.runtime import get_runtime
    from services import abuse_policy

    key = _authfail_key(request)
    try:
        decision = get_runtime().rate_limiter.consume(
            key, limit=AUTHFAIL_LIMIT[0], window_seconds=AUTHFAIL_LIMIT[1]
        )
    except Exception as exc:  # fail-open (SPEC-219), visivel (SPEC-246 R4)
        abuse_policy.limiter_unavailable("authfail", exc)
        return None
    if decision.allowed:
        return None
    if len(_authfail_until) > 2000:
        _authfail_until.clear()
    _authfail_until[key] = time.monotonic() + decision.retry_after_seconds
    abuse_policy.record_block(
        "session",
        "authfail",
        ip=_client_ip(request),
        retry_after=decision.retry_after_seconds,
        limit=AUTHFAIL_LIMIT[0],
    )
    return _blocked_response("rate_limited", "authfail", decision.retry_after_seconds)


def _boundary_principal(request: Request):
    from infrastructure.contracts import Principal, Unauthorized
    from infrastructure.runtime import get_runtime
    from services.auth_sessions import ACCESS_COOKIE

    try:
        return get_runtime().identity_verifier.verify(request.cookies.get(ACCESS_COOKIE))
    except Unauthorized:
        if request.url.path != "/account/delete":
            raise
    from services.account_security import proof_owner

    receipt = request.cookies.get("rpg_deletion")
    if receipt:
        owner = proof_owner(receipt, "delete", max_age=604800)
    else:
        # Crash after DB revocation but before Set-Cookie: a recent
        # password proof bound to this SAME stale access cookie can
        # resume only an existing tombstone, never start a deletion.
        if not request.cookies.get(ACCESS_COOKIE):
            raise Unauthorized("account_delete_not_requested")
        owner = proof_owner(
            request.cookies.get("rpg_recent"), "recent", request.cookies[ACCESS_COOKIE]
        )
    with admin_connection(get_runtime().game_store.pool) as db:  # SPEC-224: sem principal ainda
        requested = db.execute(
            "select 1 from app.account_deletions where owner_id=%s", (owner,)
        ).fetchone()
    if not requested:
        raise Unauthorized("account_delete_not_requested")
    return Principal(owner, "deletion-retry", str(owner))


# SPEC-192 F6: SPA CSP. Google Fonts are linked from web/index.html (styles+fonts); Stripe checkout is a
# top-level redirect so no Stripe origin is needed; Vite emits a single external module script.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "connect-src 'self' https://*.supabase.co https://challenges.cloudflare.com; "
    "script-src 'self' https://challenges.cloudflare.com; "
    "frame-src https://challenges.cloudflare.com; "
    "img-src 'self' data: blob: https://*.supabase.co; "
    # SPEC-222 R8: fonts are self-hosted (web/public/fonts) -- no Google Fonts origin.
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'"
)
_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"} if _DOCS_ON else set()


_ACCESS_LOG_SKIP = frozenset({"/health", "/metrics"})
# GET 2xx de polling/leitura: debug (anti-ruido); mutacoes e erros seguem em info/warning/error.
_ACCESS_LOG_QUIET_GET = frozenset(
    {
        "/game/state",
        "/game/saves",
        "/game/map",
        "/game/codex",
        "/game/codex/dossiers",
        "/auth/config",
    }
)
_API_PREFIXES = ("/game", "/account", "/auth", "/payments", "/internal", "/telemetry", "/data")


def _access_log(request: Request, route: str, status: int, started: float, request_id: str) -> None:
    """SPEC-241 R1: uma linha ``http.request`` por requisicao de API. Nunca levanta."""
    try:
        path = request.url.path
        if path in _ACCESS_LOG_SKIP:
            return
        last = path.rsplit("/", 1)[-1]
        if path.startswith("/assets/") or ("." in last and status < 400):
            return  # arquivos estaticos do bundle web
        client = request.headers.get("x-rpg-client", "").strip().lower()
        client = client if client in {"web", "android"} else "unknown"
        build_fields = _client_build_fields(request)
        level = "info"
        if status >= 500:
            level = "error"
        elif status >= 400:
            level = "warning"
            if status == 404 and not path.startswith(_API_PREFIXES):
                level = "debug"
            elif status == 401 and not request.cookies.get("rpg_access"):
                level = "debug"  # bootstrap da SPA sem cookie
        elif request.method == "GET" and (
            path in _ACCESS_LOG_QUIET_GET
            or path.startswith("/data/")
            or not path.startswith(_API_PREFIXES)
        ):
            # leitura de polling e navegacao da SPA ("/", rotas client-side): debug (revisao Sol)
            level = "debug"
        _log_event(
            "http",
            "request",
            level=level,
            method=request.method,
            route=route,
            status=status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            request_id=request_id,
            owner_ref=getattr(request.state, "owner_ref", None),
            client=client,
            error_code=getattr(request.state, "error_code", None),
            **build_fields,
        )
    except Exception:
        pass


_CLIENT_BUILD_RE = re.compile(r"(?:[0-9a-f]{7}|dev)\+\d{12}")
_APP_VERSION_RE = re.compile(r"\d{1,4}(?:\.\d{1,4}){0,3}\+\d{1,9}")


def _server_git_sha() -> str:
    return (os.getenv("GIT_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA") or "").strip().lower()


def _client_build_fields(request: Request) -> dict[str, Any]:
    """SPEC-261 R2 / SPEC-259 R4: build do bundle web e versao do app Android no access log.

    Formatos fechados (header fora do formato vira ``other``); ``build_skew`` so quando o sha do
    bundle difere do sha do servidor (cliente velho em cache x API nova)."""
    fields: dict[str, Any] = {}
    raw = request.headers.get("x-rpg-build", "").strip()
    if raw:
        build = raw if _CLIENT_BUILD_RE.fullmatch(raw) else "other"
        fields["client_build"] = build
        client_sha = build.split("+", 1)[0]
        server_sha = _server_git_sha()
        if (
            client_sha not in {"dev", "other"}
            and server_sha
            and not server_sha.startswith(client_sha)
        ):
            fields["build_skew"] = True
    version = request.headers.get("x-rpg-app-version", "").strip()
    if version:
        fields["app_version"] = version if _APP_VERSION_RE.fullmatch(version) else "other"
    return fields


def _unhandled_response(
    request: Request, route: str, exc: Exception, request_id: str
) -> JSONResponse:
    """SPEC-241 R2: 500 com request_id; log com classe + frames, nunca a mensagem."""
    from observability.telemetry import safe_stack

    request.state.error_code = "internal_error"
    _log_event(
        "http",
        "unhandled_exception",
        level="error",
        route=route,
        method=request.method,
        error_type=type(exc).__name__,
        stack=safe_stack(exc),
        request_id=request_id,
    )
    return _error_response(500, "internal_error")


async def _correlation_boundary(request: Request, call_next):
    import re
    import time

    from observability.metrics import metrics
    from observability.telemetry import new_request_id, request_scope, span

    request_id = new_request_id(request.headers.get("x-request-id"))
    started = time.perf_counter()
    route = re.sub(
        r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}(?=/|$)",
        "/{id}",
        request.url.path,
    )
    with (
        request_scope(request_id),
        span(
            "http.request",
            route=route,
            method=request.method,
        ),
    ):
        try:
            response = await call_next(request)
        except Exception as exc:
            response = _unhandled_response(request, route, exc, request_id)
        except BaseException:
            metrics.increment(
                "rpg_http_requests_total",
                {"route": route, "status_class": "5xx"},
            )
            raise
        route_object = request.scope.get("route")
        route = re.sub(r"\{[^}]+\}", "{id}", getattr(route_object, "path", route))
        metrics.increment(
            "rpg_http_requests_total",
            {"route": route, "status_class": f"{response.status_code // 100}xx"},
        )
        metrics.observe(
            "rpg_http_duration_seconds",
            {"route": route},
            time.perf_counter() - started,
        )
        _access_log(request, route, response.status_code, started, request_id)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(self), geolocation=()"
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith(("/game", "/account", "/auth")) or _session_scoped_path(
            request.url.path, request.query_params
        ):
            response.headers.setdefault("Cache-Control", "no-store")  # SPEC-221 R4 / SPEC-210
        if os.getenv("RPG_COOKIE_SECURE", "0") == "1":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        if request.url.path not in _DOCS_PATHS:  # swagger UI loads CDN scripts
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response


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


@app.get("/auth/config")
def auth_config(request: Request):
    required = _database_profile()
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


@app.post("/auth/login")
def auth_login(body: AuthRequest, request: Request, response: Response):
    if not _database_profile():
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


@app.post("/auth/signup")
def auth_signup(body: SignupRequest, request: Request, response: Response):
    if not _database_profile():
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
    if not _database_profile() or not isinstance(
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
    request: Request, *, action: str, email: str = "", captcha_token: str | None = None
) -> None:
    from infrastructure.contracts import Unauthorized
    from infrastructure.runtime import get_runtime
    from services.account_security import auth_limit, validate_captcha

    _require_allowed_origin(request)
    runtime = get_runtime()
    auth_limit(runtime, request, action=action, email=email)
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


@app.post("/auth/reset/request", status_code=202)
@app.post("/auth/verify/request", status_code=202)
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


@app.post("/auth/verify")
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


@app.post("/auth/reset/confirm")
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


@app.post("/auth/reauth")
def auth_reauthenticate(body: ReauthRequest, request: Request, response: Response):
    from infrastructure.contracts import Unauthorized
    from services.auth_sessions import ACCESS_COOKIE

    runtime = _lifecycle_runtime()
    _auth_abuse(request, action="reauth", captcha_token=body.captcha_token)
    try:
        _validate_auth_csrf(request)
        access = request.cookies.get(ACCESS_COOKIE)
        from services.account_security import captcha_config

        if captcha_config()["mode"] == "gotrue":
            owner = runtime.identity_verifier.reauthenticate(
                access, body.password, captcha_token=body.captcha_token
            )
        else:
            owner = runtime.identity_verifier.reauthenticate(access, body.password)
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


@app.get("/account/export")
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


@app.post("/game/{game_id}/audit-export")
def game_audit_export(game_id: str, request: Request):
    """SPEC-207: pacote ZIP de auditoria, owner-only, prova recente, zero LLM.

    Gerado em memória e devolvido como download; nada é retido no servidor."""
    if not _database_profile():
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


@app.post("/account/delete")
def account_delete(body: DeleteAccountRequest, request: Request):
    from infrastructure.account_lifecycle import PostgresAccountLifecycle
    from infrastructure.request_context import current_principal
    from services.account_security import DELETE_COOKIE, proof

    runtime = _lifecycle_runtime()
    principal = current_principal()
    if principal.issuer != "deletion-retry":
        _require_recent(request, principal.user_id)
    lifecycle = PostgresAccountLifecycle(
        runtime.game_store.pool, runtime.identity_verifier, runtime.blob_store
    )
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


@app.post("/auth/refresh")
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


@app.post("/auth/logout", status_code=204)
# SPEC-220 R1: o cookie de refresh tem path /auth/refresh; só este alias o recebe.
@app.post("/auth/refresh/logout", status_code=204)
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


# Fase 10 (R7) + SPEC-239: 1 linha JSON por turno; handler central em stdout.
from observability.logging_setup import configure_logging

configure_logging()
from observability.boot import log_boot_once  # SPEC-249

log_boot_once()
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


def _telemetry_hook(provider: str, model: str, tier, latency_ms: int, fell_back: bool) -> None:
    from observability.telemetry import span

    with span(
        "llm.invoke",
        provider=provider,
        tier=getattr(tier, "value", str(tier)),
        latency_ms=latency_ms,
        fell_back=fell_back,
    ):
        pass
    acc = _llm_turn_events.get()
    if acc is not None:
        acc.append(
            {
                "provider": provider,
                "model": model,
                "tier": getattr(tier, "value", str(tier)),
                "latency_ms": int(latency_ms),
                "fell_back": bool(fell_back),
            }
        )


set_llm_telemetry_hook(_telemetry_hook)


def _safe_error_type(value: Any) -> str | None:
    """Classe/codigo fechado (identificador curto); qualquer texto livre vira ``other``."""
    if not value:
        return None
    text = str(value)
    return (
        text
        if len(text) <= 60 and text.replace("_", "").replace(".", "").replace(":", "").isalnum()
        else "other"
    )


def _attempt_telemetry_hook(event: LLMAttemptEvent) -> None:
    from observability.metrics import metrics

    tier = getattr(event.tier, "value", str(event.tier))
    metrics.increment(
        "rpg_llm_attempts_total",
        {"provider": event.provider, "tier": tier, "outcome": event.outcome},
    )
    metrics.observe(
        "rpg_llm_duration_seconds",
        {"provider": event.provider, "tier": tier, "outcome": event.outcome},
        max(0, int(event.latency_ms)) / 1000,
    )
    measured = normalize_attempts(
        [
            {
                "provider": event.provider,
                "model": event.model,
                "outcome": event.outcome,
                "usage": event.usage,
                "network_attempted": event.outcome not in {"build_error", "circuit_open"},
            }
        ],
        operation_id=uuid.UUID(int=0),
    )
    for item in measured:
        metrics.increment(
            "rpg_llm_cost_usd_total",
            {"provider": event.provider, "tier": tier, "basis": item.cost_basis},
            amount=float(item.cost_usd),
        )
    try:
        from observability.latency import current_timeline

        _tl = current_timeline()
        if _tl is not None and event.outcome not in {"build_error", "circuit_open"}:
            _tl.note_attempt(tier)  # SPEC-200 R17: chamadas por fase
    except Exception:
        pass
    acc = _llm_attempt_events.get()
    if acc is not None:
        network_attempted = event.outcome not in {"build_error", "circuit_open"}
        acc.append(
            {
                "provider": event.provider,
                "model": event.model,
                "tier": tier,
                "attempt_index": int(event.attempt_index),
                "latency_ms": int(event.latency_ms),
                "fell_back": bool(event.fell_back),
                "outcome": event.outcome,
                "structured": bool(event.structured),
                "network_attempted": network_attempted,
                "usage": dict(event.usage) if event.usage else None,
                "http_status": int(getattr(event, "http_status", 0) or 0),
                "error_type": _safe_error_type(getattr(event, "error_type", None) or event.error),
            }
        )


set_llm_attempt_telemetry_hook(_attempt_telemetry_hook)


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


# Fase 10 (R6): rate limit mínimo por IP (janela deslizante em memória).
# RPG_RATE_LIMIT = req/min em /game/action e /game/new; 0 desliga (suíte/smoke).
_RATE_WINDOW_S = 60.0
_rate_hits: dict[str, deque] = defaultdict(deque)
_CLIENT_LATENCY_PATH = "/telemetry/client-latency"
_CLIENT_ERROR_PATH = "/telemetry/client-error"


def _rate_limit_max() -> int:
    try:
        return int(os.getenv("RPG_RATE_LIMIT", "30"))
    except ValueError:
        return 30


_METRICS_RATE_PER_MIN = 12
_metrics_hits: dict[str, deque] = defaultdict(deque)


async def _rate_limit_metrics(request: Request, call_next):
    """SPEC-221 R3: classe propria para /metrics (12/min por IP, em memoria por processo).

    Revisao Sol: o scraper autenticado NAO conta — o stack SPEC-106 raspa a cada 5 s (12/min
    exatos) e cairia em 429 intermitente (up==0). Sondas sem token valido seguem limitadas; o
    custo de DB do scraper legitimo ja e limitado pelo cache SQL (R2)."""
    if os.getenv("RPG_METRICS_TOKEN") and _metrics_authorized(request):
        return await call_next(request)
    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    hits = _metrics_hits[ip]
    while hits and now - hits[0] > _RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= _METRICS_RATE_PER_MIN:
        from services.abuse_policy import record_block

        record_block("metrics", "ip", ip=ip, retry_after=60, limit=_METRICS_RATE_PER_MIN)
        return _error_response(429, "rate_limited", headers={"Retry-After": "60"})
    hits.append(now)
    return await call_next(request)


def _client_ip(request: Request) -> str:
    from services.abuse_policy import client_ip  # SPEC-219 R4

    return client_ip(request)


def _blocked_response(
    detail: str, scope: str, retry_after: int, *, status: int = 429
) -> JSONResponse:
    from services.abuse_policy import rate_limited_body

    body = rate_limited_body(detail, scope, retry_after)
    return _error_response(
        status, body.pop("detail"), headers={"Retry-After": str(max(1, int(retry_after)))}, **body
    )


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    """SPEC-219 R1/R2: limite POR IP da classe da rota (o limite por owner vive em
    ``_session_boundary``, que conhece o principal; turnos tem o dele em ``_enforce_owner_budget``)."""
    if _rate_limit_max() > 0 and request.url.path == "/metrics":
        return await _rate_limit_metrics(request, call_next)
    from services import abuse_policy

    cls = abuse_policy.classify(request.method, request.url.path)
    if cls is None:
        return await call_next(request)
    ip_limit, _owner = abuse_policy.limits_for(cls)
    if ip_limit <= 0:
        return await call_next(request)
    ip = _client_ip(request)
    if _database_profile():
        from infrastructure.runtime import get_runtime
        from observability.telemetry import pseudonym

        decision = get_runtime().rate_limiter.consume(
            f"ip:{pseudonym(ip)}:{cls.name}", limit=ip_limit, window_seconds=cls.window_s
        )
        if not decision.allowed:
            abuse_policy.record_block(
                cls.name, "ip", ip=ip, retry_after=decision.retry_after_seconds, limit=ip_limit
            )
            return _blocked_response("rate_limited", "ip", decision.retry_after_seconds)
        return await call_next(request)
    # legacy: janela deslizante em memoria (R11), mesma lista de classes.
    now = time.monotonic()
    # Auditoria A8: teto no dict -- descarta chaves com janela inteira vencida.
    if len(_rate_hits) > 1000:
        stale = [k for k, dq in _rate_hits.items() if not dq or now - dq[-1] > _RATE_WINDOW_S]
        for k in stale:
            del _rate_hits[k]
    hits = _rate_hits[f"{ip}#{cls.name}"]
    while hits and now - hits[0] > cls.window_s:
        hits.popleft()
    if len(hits) >= ip_limit:
        retry_after = int(cls.window_s - (now - hits[0])) + 1
        abuse_policy.record_block(cls.name, "ip", ip=ip, retry_after=retry_after, limit=ip_limit)
        return _blocked_response("rate_limited", "ip", retry_after)
    hits.append(now)
    return await call_next(request)


# SPEC-241 R4: registrado por ULTIMO => middleware mais externo; todo retorno (inclusive 401/403/
# 413/429 vindos dos middlewares internos) recebe X-Request-ID e entra no access log.
app.middleware("http")(_correlation_boundary)


def _owner_rate_limit(request: Request, principal) -> "JSONResponse | None":
    """SPEC-219 R2: limite por owner da classe (perfis DB). Falha do limitador NAO derruba a rota."""
    from services import abuse_policy

    cls = abuse_policy.classify(request.method, request.url.path)
    if cls is None or request.url.path in _TURN_BUDGET_PATHS:
        return None
    _ip, owner_limit = abuse_policy.limits_for(cls)
    if owner_limit <= 0:
        return None
    try:
        from infrastructure.runtime import get_runtime

        decision = get_runtime().rate_limiter.consume(
            f"user:{principal.user_id}:{cls.name}", limit=owner_limit, window_seconds=cls.window_s
        )
    except Exception as exc:  # fail-open (SPEC-219), visivel (SPEC-246 R4)
        abuse_policy.limiter_unavailable("owner_minute", exc)
        return None
    if decision.allowed:
        return None
    abuse_policy.record_block(
        cls.name,
        "owner",
        owner=principal.user_id,
        retry_after=decision.retry_after_seconds,
        limit=owner_limit,
    )
    return _blocked_response("rate_limited", "owner", decision.retry_after_seconds)


# Turnos fazem a checagem por owner DEPOIS do replay por action_id (replay nao consome).
_TURN_BUDGET_PATHS = frozenset({"/game/action", "/game/action/stream"})


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


@app.exception_handler(QuotaExceeded)
async def _quota_exceeded_handler(_request, exc: QuotaExceeded):
    return _blocked_response(exc.detail, exc.scope, exc.retry_after_seconds, status=exc.status_code)


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


# --- MODELOS DE DADOS (DTOs) ---
class CreateCharacterRequest(BaseModel):
    # Auditoria A1: level sem bound permitia ouro NEGATIVO (50×level) e ficha
    # absurda; A7: campos livres viram prompt de LLM — tamanho limitado na borda.
    name: str = Field(min_length=1, max_length=80)
    race: str = Field(max_length=40)
    class_name: str = Field(max_length=40)
    region: str = Field(max_length=60)
    level: int = Field(1, ge=1, le=20)
    backstory: str | None = Field("", max_length=2000)  # null -> "" (SPEC-235 R9)
    appearance: str = Field("", max_length=1000)
    visual_exclusions: str = Field("", max_length=500)
    # spec inicio-personalizado (R4): cenário aprovado no passo de prólogo.
    # StartScenarioIn re-valida na borda (limites de campo, beats ≤ 5, npcs ≤ 2
    # → excedente = 422). None = fluxo clássico, byte a byte o atual (R6).
    scenario: StartScenarioIn | None = None
    action_id: str | None = Field(default=None, max_length=36)

    @field_validator("class_name")
    @classmethod
    def _canonical_class(cls, value: str) -> str:
        if value not in gamedata.CLASSES:
            raise ValueError("classe desconhecida")
        return value

    @field_validator("race")
    @classmethod
    def _canonical_race(cls, value: str) -> str:
        names = {
            str(row.get("name")) for row in (load_json_data("origins.json") or {}).get("races", [])
        }
        if value not in names:
            raise ValueError("raça desconhecida")
        return value

    @field_validator("region")
    @classmethod
    def _canonical_region(cls, value: str) -> str:
        names = {
            str(row.get("name"))
            for row in (load_json_data("origins.json") or {}).get("regions", [])
        }
        if value not in names:
            raise ValueError("região desconhecida")
        return value


class ActionRequest(BaseModel):
    # Auditoria A7: ação vira prompt — sem teto, request gigante = custo/latência.
    input_text: str = Field(max_length=2000)
    game_id: str | None = None  # Opcional: permite especificar qual save carregar
    action_id: str | None = Field(default=None, max_length=36)
    # conflito-16: seleção tática canônica da UI; o motor revalida tudo.
    card_id: str | None = Field(default=None, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    ruptura: bool = False
    reaction_card_id: str | None = Field(default=None, max_length=128)
    # Laboratório/UI tática: ações fechadas evitam parse LLM de chips mecânicos.
    action_kind: Literal["attack", "maneuver", "pass", "flee"] | None = None
    maneuver: Literal["engajar", "desengajar", "guardar", "esconder", "procurar"] | None = None

    @field_validator("action_id")
    @classmethod
    def _canonical_action_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(uuid.UUID(value))
        except (ValueError, TypeError):
            raise ValueError("action_id inválido (esperado UUID)")


class ArtBriefRequest(BaseModel):
    name: str = Field(default="Herói", max_length=80)
    race: str = Field(max_length=40)
    class_name: str = Field(max_length=40)
    region: str = Field(default="", max_length=60)
    appearance: str = Field(default="", max_length=1000)
    visual_exclusions: str = Field(default="", max_length=500)


class ArtConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action_id: str
    quote_id: uuid.UUID
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("confirmed must be the boolean true")
        return value


class ArtQuoteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    image_type: Literal["player", "npc", "scene"] = "player"
    offer_id: uuid.UUID | None = None
    reformulation: bool = False


class ArtQualityRequest(BaseModel):
    approved: bool


class CombatSimulatorRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=40)
    level: Literal[1, 3, 5, 10] = 1
    enemy_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(default=1, ge=1, le=3)
    action_id: str | None = Field(default=None, max_length=36)

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

    item_id: str | None = None  # equipar este item
    unequip_slot: str | None = None  # OU esvaziar este slot
    game_id: str | None = None
    action_id: str | None = Field(default=None, max_length=36)


class PrepareCardsRequest(BaseModel):
    """SPEC-209 R4: prepara/troca Cartas fora de combate (validação 100% Python)."""

    game_id: str | None = None
    prepared: list[str] = Field(default_factory=list, max_length=64)
    action_id: str | None = Field(default=None, max_length=36)


class LevelUpRequest(BaseModel):
    """Conflito v2: consome escolha de Carta/evolução ou de Virtude."""

    choice_id: str
    card_id: str | None = None
    evolve_card_id: str | None = None
    caminho: str | None = None
    virtude: str | None = None
    attr: str | None = None
    subclass_id: str | None = None
    virtue_card_id: str | None = None
    game_id: str | None = None
    action_id: str | None = Field(default=None, max_length=36)


class ChronicleSearchRequest(BaseModel):
    game_id: str
    query: str = Field(min_length=2, max_length=300)
    top_k: int = Field(default=5, ge=1, le=10)


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
    asset: VisualAssetResponse | None = None


class VisualCueResponse(BaseModel):
    kind: Literal["npc_first_appearance"]
    subject_id: str
    subject_name: str
    caption: str
    asset: VisualAssetResponse | None = None
    fallback: bool


class VisualResponse(BaseModel):
    scene: SceneVisualResponse
    cue: VisualCueResponse | None = None


class GameResponse(BaseModel):
    timeline_epoch: int = 0
    portrait_generation_id: str | None = None
    game_id: str  # <--- Novo: Frontend precisa saber o ID
    message: str
    message_type: str
    # SPEC-202 R9: quem respondeu — {kind: narrator|npc|system, id, name, reason}.
    speaker: dict[str, str] = {}
    player_stats: dict[str, Any]
    # Fase 4.3: estruturado — {id, name, qty, type, equipped, slot}
    inventory: list[dict[str, Any]]
    current_location: str
    narrative_summary: str  # <--- Novo: Frontend pode mostrar o resumo
    last_turn_log: list[dict[str, Any]]
    simulated: bool = False  # True quando rodando em modo simulado (sem API key)
    world: dict[str, Any] = {}  # location_id, day, period, visited (fog of war), danger
    quest: dict[str, Any] = {}  # objetivo atual, beats (status), clímax, progresso
    combat: dict[str, Any] = {}  # inimigos, condições, iniciativa, round, cooldowns
    npcs: list[
        dict[str, Any]
    ] = []  # NPCs conhecidos (nome, papel, local, relação, última lembrança)
    art_offers: list[dict[str, str]] = []
    art_generations: list[dict[str, str]] = []
    chronicle: list[
        dict[str, Any]
    ] = []  # capítulos: {title, started_turn, location, entries[{text,turn,kind,event_id?}]}
    factions: list[dict[str, Any]] = []  # fações vivas: objetivo, progresso, rótulo de standing
    reputation_notices: list[dict[str, str]] = []  # SPEC-298 R26: avisos do turno (sem números)
    companion_feedback: list[str] = []  # SPEC-300 R29: frases do turno (sem números)
    party: list[
        dict[str, Any]
    ] = []  # Fase 4.5: companheiros {name, hp, max_hp, active, archetype, status}
    death_pending: bool = (
        False  # spec checkpoints-morte: queda letal — abre a tela de morte no cliente
    )
    game_over: bool = False  # memorial/bloqueio definitivo; Vitalidade 0 não basta
    death: dict[str, Any] = {}  # conflito-16: Última Ação/Terminal/estabilização
    continuity: dict[str, Any] = {}
    combat_simulation: dict[str, Any] = {}
    turn_outcome: dict[str, Any] = {}  # SPEC-199: ganhos do turno (XP/ouro/itens/missões)
    combat_result: dict[str, Any] = {}  # SPEC-203: desfecho do encontro (turno de término)
    # SPEC-213 R13: só status/versões das projeções derivadas (nunca conteúdo).
    projections: dict[str, Any] = {}
    visual: VisualResponse


# --- HELPER: FORMATA RESPOSTA ---
def _public_art_refs(state: dict) -> dict:
    """Public references from the owner-scoped save; private quotes never enter UI."""
    generations = []
    for row in state.get("art_generation_ledger") or []:
        image_type = row.get("subject_type") or (
            "player" if row.get("trigger_kind") == "player_portrait" else None
        )
        if row.get("generation_id") and image_type in {"player", "npc", "scene"}:
            generations.append(
                {
                    "generation_id": str(row["generation_id"]),
                    "type": image_type,
                    "subject_id": str(row.get("subject_id") or "player"),
                }
            )
    return {
        "art_generations": generations,
        "art_offers": [
            {"offer_id": row["offer_id"], "type": row["type"]}
            for row in state.get("art_offers") or []
        ],
    }


def _response_speaker(state: dict) -> dict[str, str]:
    from services.interlocutor import response_speaker

    return response_speaker(state)


def format_response(state: dict, *, cue_action_key: str | None = None) -> GameResponse:
    """SPEC-293 R3: toda resposta de turno/estado passa pelo rótulo de exibição por
    observador (combatente de fação desconhecida aparece só pelo papel)."""
    from services.faction_display import conceal_payload, concealed_name_map

    response = _format_response_raw(state, cue_action_key=cue_action_key)
    mapping = concealed_name_map(state)
    if not mapping:
        return response
    return GameResponse.model_validate(conceal_payload(response.model_dump(), mapping))


def _format_response_raw(state: dict, *, cue_action_key: str | None = None) -> GameResponse:
    # Pega a última mensagem
    from services.turn_outcome import player_facing_message

    last_content = player_facing_message(state)

    from services.presentation_history import message_kind

    msg_type = message_kind(state)

    player = state["player"]
    vitality = int(player.get("vitalidade", 0) or 0)
    max_vitality = int(player.get("max_vitalidade", vitality) or vitality)
    simulation = dict(state.get("combat_simulation") or {})
    if simulation.get("enabled"):
        active = bool((state.get("combat") or {}).get("active"))
        simulation["finished"] = not active
        simulation["outcome"] = (
            "defeat" if state.get("death_pending") else "victory" if not active else None
        )
    from services.turn_outcome import public_outcome

    turn_outcome = (
        {} if simulation.get("enabled") else public_outcome(state.get("last_turn_outcome"))
    )
    from services.projections import projection_status_view

    return GameResponse(
        projections=projection_status_view(state),
        turn_outcome=turn_outcome,
        combat_result={} if simulation.get("enabled") else _combat_result(state),
        timeline_epoch=int((state.get("continuity") or {}).get("timeline_epoch", 0)),
        portrait_generation_id=next(
            (
                str(row["generation_id"])
                for row in reversed(state.get("art_generation_ledger") or [])
                if row.get("trigger_kind") == "player_portrait" and row.get("generation_id")
            ),
            None,
        ),
        game_id=state.get("game_id", "unknown"),
        message=last_content,
        message_type=msg_type,
        speaker=_response_speaker(state),
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
            # SPEC-209 R5/R9: aditivos — servidor decide se pode reorganizar; cicatrizes
            # são a projeção pública do que já está no save (sem inventar turno).
            "can_reorganize": _can_reorganize_view(state),
            "prepared_slots": _prepared_slots(player),
            "scars": _scars_view(player),
            "subclass": str(player.get("subclass") or ""),
            "virtue_cards": _virtue_cards_view(player),
            "evolvable_card_ids": _evolvable_card_ids(player),
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
        world=_world_block(
            state.get("world", {}) or {},
            state.get("world_projection", {}) or {},
            state.get("event_log", []) or [],
            state.get("player", {}) or {},
            state.get("world_sim"),
            state=state,
        ),
        quest=_quest_block(
            state.get("campaign_plan") or {},
            _npc_world.public_quests(state),  # SPEC-304: missao de destino nao percebido
            state.get("world") or {},
        ),
        combat=_combat_block(state),
        npcs=_npcs_block(state.get("npcs", {}) or {}, state),
        **_public_art_refs(state),
        chronicle=_chronicle_block(state.get("chronicle", []) or []),
        party=[
            {
                "name": c.get("name", "?"),
                "vitalidade": int(c.get("vitalidade", 0) or 0),
                "max_vitalidade": int(c.get("max_vitalidade", 1) or 1),
                "hp": int(c.get("vitalidade", 0) or 0),
                "max_hp": int(c.get("max_vitalidade", 1) or 1),
                "active": bool(c.get("active")),
                "archetype": c.get("archetype", ""),
                "status": c.get("status", "ativo"),
                **_companion_labels(state, c),
            }
            for c in _npc_world.public_party(state)  # SPEC-304 P1-2: o que o jogador viu
        ],
        companion_feedback=_companion_feedback(state),
        reputation_notices=_reputation_notices(state),
        factions=_factions_block(
            state.get("factions", []) or [],
            state.get("faction_intel", {}) or {},
            (state.get("world", {}) or {}).get("turn_count", 0),
            state.get("event_log", []) or [],
            state.get("world_projection", {}) or {},
            state=state,
        ),
        death_pending=bool(state.get("death_pending", False)),
        game_over=bool(state.get("game_over", False)),
        death=_death_block(state),
        continuity=_continuity_block(state),
        combat_simulation=simulation,
        visual=visual_response(state, cue_action_key=cue_action_key),
    )


def _companion_labels(state: dict, comp: dict) -> dict[str, str]:
    """SPEC-300 R29: rótulos vagos do companheiro. NUNCA o número de aprovação nem os valores."""
    from services import companion_soul as cs

    if cs.mode() != "on":
        return {}
    soul = (state.get("companion_souls") or {}).get(cs.comp_id(comp)) or {}
    if not isinstance(soul, dict) or "approval" not in soul:
        return {}
    out = {"approval_label": cs.approval_label(soul.get("approval", 50))}
    if soul.get("romance") == "vinculo":
        out["bond_label"] = "vínculo"
    elif soul.get("romance") == "compromisso":
        out["bond_label"] = "compromisso"
    return out


def _companion_feedback(state: dict) -> list[str]:
    from services import companion_soul as cs

    if cs.mode() != "on":
        return []
    return [str(t) for t in (state.get("companion_feedback") or []) if isinstance(t, str)]


def _reputation_notices(state: dict) -> list[dict[str, str]]:
    """SPEC-298 R26: avisos do turno corrente, textos fixos, passados pela projeção SPEC-293."""
    from services.faction_display import conceal_for

    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    rows = [
        {
            "kind": str(n.get("kind", "")),
            "subject_id": str(n.get("subject_id", "")),
            "text": str(n.get("text", "")),
        }
        for n in (state.get("reputation_notices") or [])
        if isinstance(n, dict) and int(n.get("turn", -1) or 0) == turn
    ]
    return conceal_for(state, rows)


def _inventory_block(player: dict) -> list[dict[str, Any]]:
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
        out.append(
            {
                "id": e.get("id"),
                "name": inv_mod.item_display(e),
                "qty": int(e.get("qty", 1)),
                "type": item.get("type", "desconhecido"),
                "equipped": e.get("id") in equipped,
                "slot": equipped.get(e.get("id")) or inv_mod.slot_for(e.get("id", "")),
                "unique": bool(item.get("unique")),  # Fase 6.2: ◆ um por mundo
            }
        )
    return out


def _abyss_tier_view(player: dict) -> str:
    """spec refatoracao-sistema-classes (R11): patamar da Carga do Abismo p/ o HUD.
    Classe com `abyss.hidden` (Médico — Recidiva) NÃO expõe o valor: label enigmático."""
    import combat_mechanics as _cm

    cfg = _cm.entropy_config(player)
    if (cfg.get("abyss") or {}).get("hidden"):
        # SPEC-235 R8: sem Carga não há o que ocultar — chip some até acumular.
        return "?" if int(player.get("abyss_charge", 0) or 0) > 0 else "nenhum"
    return _cm.abyss_tier(player)


def _can_reorganize_view(state: dict) -> dict[str, Any]:
    from services import cards

    allowed, reason = cards.reorganize_status(state)
    return {"allowed": bool(allowed), "reason": reason}


def _prepared_slots(player: dict) -> int:
    from services import cards

    return int(cards.prepare_slots_for_level(player.get("level", 1)))


def _virtue_cards_view(player: dict) -> list[dict[str, Any]]:
    from services import cards

    out = []
    for row in player.get("virtue_cards") or []:
        cid = str(row.get("card_id") or "")
        card = cards.get_card(cid) or {}
        out.append(
            {
                "card_id": cid,
                "name": card.get("name", cid),
                "type": str(card.get("tipo", "")),
                "description": card.get("descricao", ""),
                "virtude": str(row.get("virtude") or ""),
                "mastery": int(row.get("mastery", 0) or 0),
                "effective_stage": int(row.get("effective_stage", 0) or 0),
            }
        )
    return out


def _evolvable_card_ids(player: dict) -> list[str]:
    from services import cards

    if int(player.get("level", 1) or 1) < 4:
        return []
    done = player.get("evolved_cards") or {}
    return [
        cid
        for cid in player.get("known_cards") or []
        if (cards.get_card(cid) or {}).get("evolucao") and cid not in done
    ]


def _scars_view(player: dict) -> list[dict[str, str]]:
    out = []
    for scar in player.get("scars") or []:
        if not isinstance(scar, dict):
            continue
        out.append(
            {
                k: str(scar.get(k) or "")
                for k in (
                    "id",
                    "origem",
                    "consequencia_negativa",
                    "habilidade_positiva_relacionada",
                )
            }
        )
    return out


def _cards_block(player: dict, *, prepared_only: bool = False) -> list[dict[str, Any]]:
    """View autoral + disponibilidade mecânica das Cartas.

    O frontend nunca tenta reproduzir frequência/custo por conta própria: recebe
    o contador já interpretado, mas o motor ainda revalida no uso.
    """
    import combat_mechanics as cm
    from services import cards

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
        usage = (player.get("card_usage") or {}).get(cid) or {}
        spent = bool(counter and int(usage.get(counter, 0) or 0) >= 1)
        base_cost = int(card.get("custo_entropia", 0) or 0)
        cost = cm.dependencia_cost(player, base_cost)
        kind = str(card.get("tipo", ""))
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        friendly = effect_kind in {
            "cura",
            "estabilizar",
            "protecao",
            "reposicionar",
            "esconder",
            "purga_condicao",
            "vantagem",
            "buff_defesa",
            "buff_acerto",
            "buff_dano",
            "reduzir_carga_aliado",
        }
        ready = bool(is_prepared and kind in ("ativa", "reacao") and not spent and cost <= entropy)
        out.append(
            {
                "id": cid,
                "name": card.get("name", cid),
                "type": kind,
                "description": card.get("descricao", ""),
                "effect_kind": effect_kind,
                "target_kind": "self" if friendly else "enemy",
                "subclass": card.get("subclasse", ""),
                "prepared": is_prepared,
                "cost": cost,
                "base_cost": base_cost,
                "frequency": frequency,
                "spent": spent,
                "ready": ready,
                "has_rupture": bool(card.get("ruptura")),
                "rupture_ready": bool(ready and kind == "ativa" and card.get("ruptura")),
                "trigger": card.get("gatilho", ""),
                "evolved": evolved.get(cid),
            }
        )
    return out


def _death_block(state: dict) -> dict[str, Any]:
    player = state.get("player") or {}
    combat = state.get("combat") or {}
    context = combat.get("death_context") or {}
    last_action = context.get("last_action") or combat.get("last_player_action")
    last_action_label = ""
    if isinstance(last_action, dict) and last_action.get("kind") == "card":
        from services import cards

        card = cards.get_card(str(last_action.get("card_id") or "")) or {}
        last_action_label = str(card.get("name") or last_action.get("card_id") or "")
    continuity = _continuity_block(state)
    canonical = int(continuity.get("canonical_turn", 0) or 0)
    # SPEC-228 R6/R10: o turno de retorno vem do checkpoint REAL em disco.
    checkpoint: int | None = None
    if state.get("game_id"):
        try:
            checkpoint = persistence_module.checkpoint_turn(str(state["game_id"]))
        except Exception:
            checkpoint = None
    return {
        "pending": bool(state.get("death_pending")),
        "last_action": last_action,
        "last_action_label": last_action_label,
        "entered_terminal": bool(context.get("entered_terminal") or player.get("estado_terminal")),
        "stabilization": context.get("stabilization", ""),
        "stabilization_attempts": int(
            context.get("stabilization_attempts", player.get("stabilization_attempts", 0)) or 0
        ),
        "killer": context.get("killer", ""),
        "will_restore_turn": checkpoint,
        "will_lose_turns": (max(0, canonical - checkpoint) if checkpoint is not None else None),
        "retained": ["histórico de mortes", "contagem de ações da sessão"],
        "reverted": ["mundo", "inventário", "posição e memória após o checkpoint"],
    }


def _continuity_block(state: dict) -> dict[str, Any]:
    from services.continuity import normalize

    canonical = int((state.get("world") or {}).get("turn_count", 0) or 0)
    meta = normalize(state.get("continuity"), canonical_turn=canonical)
    return {**meta, "canonical_turn": canonical}


def _levelup_block(player: dict) -> dict[str, Any]:
    """Escolhas pendentes + Cartas elegíveis/evoluções."""
    pending = player.get("pending_choices", []) or []
    if not pending:
        return {}
    from services import cards

    eligible = []
    for cid in progression.eligible_cards(player):
        card = cards.get_card(cid) or {}
        eligible.append(
            {
                "id": cid,
                "name": card.get("name", cid),
                "description": card.get("descricao", ""),
                "subclass": card.get("subclasse", ""),
                "tier": int(card.get("tier", 1) or 1),
                "tier_label": gamedata.TIER_LABELS.get(int(card.get("tier", 1) or 1), ""),
                "level_req": int(card.get("level_req", 1) or 1),
                "apex": bool(card.get("apex")),
                "cost": int(card.get("custo_entropia", 0) or 0),
                "frequency": card.get("frequencia", "livre"),
                "kind": card.get("tipo", "ativa"),
            }
        )
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
        "subclasses": progression.eligible_subclasses(player)
        if any(row.get("kind") == "subclass" for row in pending)
        else [],
        "virtue_cards": [
            {
                "card_id": row.get("card_id"),
                "virtude": row.get("virtude"),
                "mastery": int(row.get("mastery", 0) or 0),
                "effective_stage": progression.effective_virtue_card_stage(row),
            }
            for row in player.get("virtue_cards") or []
        ],
        "unlocked_tier": gamedata.card_tier_for_level(int(player.get("level", 1) or 1)),
        "prepared_slots": gamedata.prepared_slots_for_level(player.get("level", 1)),
    }


def _chronicle_block(chronicle: list) -> list[dict[str, Any]]:
    """Capítulos da crônica para o HUD (Fase 3.1) — filtra entradas vazias."""
    out: list[dict[str, Any]] = []
    for cap in chronicle:
        if not isinstance(cap, dict):
            continue
        entries = [
            e
            for e in (cap.get("entries") or [])
            if isinstance(e, dict) and str(e.get("text", "")).strip()
        ]
        out.append(
            {
                "chapter_id": cap.get("chapter_id", ""),
                "title": cap.get("title", ""),
                "started_turn": cap.get("started_turn", 0),
                "location": cap.get("location", ""),
                "entries": entries,
                "digest": cap.get("digest"),
                "entry_count": len(entries),
            }
        )
    return out


def _recent_changes(row: dict) -> list[dict[str, Any]]:
    """Até 3 mudanças recentes {turn, text} (avisos já emitidos; sem número)."""
    return [
        {"turn": int(r.get("turn", 0) or 0), "text": str(r.get("text", ""))}
        for r in (row.get("recent_changes") or [])
        if isinstance(r, dict)
    ][-3:]


def _factions_block(
    factions: list,
    intel: dict,
    turn: int = 0,
    event_log: list | None = None,
    projection: dict | None = None,
    state: dict | None = None,
) -> list[dict[str, Any]]:
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
        # SPEC-301 R22: vínculo só como rótulos/texto (nunca mérito, influência ou awareness).
        membership = None
        if state is not None and state.get("faction_membership"):
            from services.faction_membership import membership_view

            membership = membership_view(state, fid)
        out.append(
            {
                "id": fid,
                "name": f.get("name", ""),
                "goal": f.get("goal", "") if knows_goal else "",
                "knows_goal": knows_goal,
                "region": f.get("region", ""),
                "progress": int(seen) if seen is not None else None,
                "intel_stale": bool(stale),
                # SPEC-298 R27: só rótulo + mudanças recentes (sem número de reputação).
                # D8: `standing_label` (faixa da fação) != `disposition` interna (hostil/neutro/aliado).
                "standing_label": faction_tier(f.get("reputation", 0)),
                "recent_changes": _recent_changes(f),
                "completed": bool(f.get("completed", False)),
                "stability_label": sv.stability_label(projection or {}, fid),
                **({"membership": membership} if membership else {}),
            }
        )
    return out


def _npcs_block(npcs: dict, state: dict | None = None) -> list[dict[str, Any]]:
    """Camada 2 (spec npcs-3-camadas): só NPCs conhecidos, com traits REVELADOS
    — hidden_traits NUNCA sai pela API (R9). SPEC-211: com `state`, NPC de entidade
    `hidden`/`secret` sem reveal aceito (regra fail-closed da SPEC-206) também some."""
    from services.npc_layers import visible_npc_view

    if state is not None:
        from services.entity_identity import resolve_npc_entity_id
        from services.player_knowledge import entity_is_player_visible

        npcs = {
            key: npc
            for key, npc in (npcs or {}).items()
            if not isinstance(npc, dict)
            or entity_is_player_visible(
                resolve_npc_entity_id(npc, str(npc.get("name", key))), state
            )
        }
    out = visible_npc_view(npcs, state)  # SPEC-304 R23: crenca do jogador, nao a verdade
    return out


def _simulation_manifest(enemies: list, game_id: str, scene: dict) -> dict:
    from services import encounter_manifest as em

    return em.build_manifest(
        enemies, source="simulation", origin="unknown", encounter_id=f"{game_id}:sim", scene=scene
    )


def _combat_result(state: dict) -> dict[str, Any]:
    """SPEC-203 R7: desfecho do turno de término, derivado de estado persistido."""
    from services import encounter_manifest as em
    from services.turn_outcome import public_outcome

    return em.result_view(state.get("combat"), public_outcome(state.get("last_turn_outcome")))


def _targeting_cards(state: dict, cards_view: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SPEC-205 R7: `valid_targets`/`invalid_reason` por Carta, calculados em Python."""
    from services import combat_targeting as targeting

    for row in cards_view:
        row.update(targeting.card_targeting(state, str(row.get("id"))))
    return cards_view


def _chase_live_for_api(chase: object) -> bool:
    return (
        isinstance(chase, dict)
        and chase.get("eligible") is not False
        and not chase.get("alcancado")
        and not chase.get("escapou")
    )


def _combat_block(state: dict) -> dict[str, Any]:
    """View tática pública do conflito, sem vazar ficha secreta de inimigo."""
    meta = state.get("combat") or {}
    enemies = state.get("enemies") or []
    player = state.get("player") or {}
    alive = [
        e
        for e in enemies
        if not e.get("dead")
        and e.get("status", "ativo") not in ("morto", "fugiu", "rendido", "incapacitado")
    ]

    def _conds(entity):
        return [
            {"name": c.get("name", ""), "dot": c.get("dot", 0), "duration": c.get("duration", 0)}
            for c in (entity.get("active_conditions") or [])
            if isinstance(c, dict)
        ]

    from services import bestiary_knowledge as knowledge
    from services import cards
    from services import combat_targeting as _targeting

    initiative = list(meta.get("initiative") or [])
    scene = meta.get("scene") or {}
    participant_names = {"player": player.get("name", "Protagonista")}
    for entity in (
        list(enemies) + list(state.get("party") or []) + list(meta.get("scene_allies") or [])
    ):
        if isinstance(entity, dict):
            participant_names[str(entity.get("id") or entity.get("name"))] = entity.get("name", "?")

    scene_view = {"zones": [], "positions": []}
    scene_view["zones"] = [
        {
            "id": z.get("id", ""),
            "name": z.get("name", ""),
            "connections": list(z.get("connections") or []),
        }
        for z in (scene.get("zones") or [])
        if isinstance(z, dict)
    ]
    for participant_id, pos in (scene.get("positions") or {}).items():
        if not isinstance(pos, dict):
            continue
        posture = pos.get("postura") or {}
        engaged = [str(value) for value in (pos.get("engaged_with") or [])]
        scene_view["positions"].append(
            {
                "participant_id": str(participant_id),
                "participant_name": participant_names.get(str(participant_id), str(participant_id)),
                "zone_id": pos.get("zone_id", ""),
                "distance": pos.get("distance_state", "proximo"),
                "posture": posture.get("state", "neutro")
                if isinstance(posture, dict)
                else str(posture),
                "concealment": pos.get("ocultacao", "visivel"),
                "engaged_with": engaged,
                "engaged_names": [participant_names.get(value, value) for value in engaged],
            }
        )

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
        enemy_views.append(
            {
                "id": str(enemy.get("id") or enemy.get("name", "")),
                "name": enemy.get("name", ""),
                "vitalidade": vitality,
                "max_vitalidade": max_vitality,
                "hp": vitality,
                "max_hp": max_vitality,
                "esquiva": public.get("esquiva"),
                "protecao": public.get("protecao"),
                "integridade_atual": public.get("integridade_atual"),
                "integridade_max": public.get("integridade_max"),
                "recursos_visiveis": public.get("recursos_visiveis") or {},
                "conditions": _conds(enemy),
                "revealed_cards": revealed_cards,
                "revealed_resistances": [
                    combat_flags.resistance_label(r)
                    for r in enemy.get("revealed_resistances") or []
                ],
            }
        )

    chase = meta.get("chase") or {}
    chase_view = (
        {
            "track": chase.get("trilha", "pressionado"),
            "steps": ["pressionado", "afastado", "quase_livre", "escapou"],
            "escaped": bool(chase.get("escapou")),
            "caught": bool(chase.get("alcancado")),
            "pursuers": list(chase.get("perseguidores") or []),
            "last_roll": dict(chase.get("_last") or {}),
        }
        if chase
        else {}
    )
    if chase_view and _chase_live_for_api(chase):
        # SPEC-325 D8: só com a flag `on`; nunca o `pending_fate` (regra de ouro).
        if combat_flags.active("chase_approach") and chase.get("approach"):
            chase_view["approach"] = str(chase["approach"])
        if combat_flags.abandon_mode() == "on":
            from services import chase as _chase_mod

            party_rows = [p for p in (state.get("party") or []) if isinstance(p, dict)]
            chase_view["abandon_candidates"] = [
                {"id": cid, "name": name}
                for cid, name in _chase_mod.abandon_candidates(chase, party_rows).items()
            ]
            offer = str(chase.get("sacrifice_offer") or "")
            offered = next(
                (p for p in party_rows if _chase_mod._ally_key(p) == offer and offer), None
            )
            if offered is not None:
                chase_view["sacrifice_offer"] = {
                    "id": offer,
                    "name": str(offered.get("name") or ""),
                }
    wounds = player.get("ferimentos") or {}
    from services import encounter_manifest as em

    manifest = meta.get("encounter") if em.is_valid_manifest(meta.get("encounter")) else None
    view: dict[str, Any] = {
        "active": bool(meta.get("active")) and bool(alive),
        "round": meta.get("round", 0),
        # SPEC-203: fase/elenco congelado (somente leitura no cliente).
        "phase": meta.get("phase") or ("active" if meta.get("active") else "ended"),
        "outcome": meta.get("outcome"),
        "encounter_id": (manifest or {}).get("encounter_id") or meta.get("instance_id"),
        "encounter_view": em.public_view(manifest, meta.get("scene")) if manifest else {},
        # Compat temporária do HUD atual: iniciativa agora é POR LADO.
        "order": [
            {
                "name": "Heróis" if side == "heroes" else "Inimigos",
                "side": "hero" if side == "heroes" else "enemy",
                "init": 0,
            }
            for side in initiative
        ],
        "initiative": initiative,
        "enemies": enemy_views,
        "cards": _targeting_cards(state, _cards_block(player, prepared_only=True)),
        "basic_actions": _targeting.basic_actions(state),
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
    if combat_flags.active("nonlethal"):
        view["nonlethal_available"] = True  # SPEC-325 D8: chip "Sem matar" so com a flag `on`
    if combat_flags.active("objects"):
        # SPEC-325 R14/D8: so rotulo/custo/usos (nunca `effect`); secreto so depois de descoberto.
        from services import conflict_scene as _cs

        scene_view["objects"] = _cs.visible_objects(scene)
    if combat_flags.active("companion_orders"):
        view["companion_orders"] = [  # SPEC-325 R15/D8: chips "<aliado>, <verbo>"
            {"id": str(p.get("id") or p.get("name")), "name": str(p.get("name") or "")}
            for p in (state.get("party") or [])
            if isinstance(p, dict) and p.get("active") and not p.get("pending_fate")
        ]
    return view


def _quest_block(plan: dict, quests: list, world: dict | None = None) -> dict[str, Any]:
    """Fase 3.3: main (view do campaign_plan) + side quests + markers pro mapa."""
    plan = plan or {}
    beats = plan.get("beats", []) or []
    step = plan.get("current_step", 0)
    climax = plan.get("climax", "")
    from services.objectives import public_objective

    public = public_objective(plan, quests, world or {})
    main = {
        "objective": public["objective"],
        "objective_source": public["source"],
        "objective_quest_id": public["quest_id"],
        "climax": "",
        "current_step": step,
        "total": len(beats),
        "arc_title": plan.get("arc_title", ""),
        "beats": [
            {"description": f"Etapa {index + 1}", "status": b.get("status", "pending")}
            for index, b in enumerate(beats)
        ],
    }
    quests = [q for q in (quests or []) if isinstance(q, dict)]
    active = [q for q in quests if q.get("status") == "active"]
    resolved = sorted(
        (q for q in quests if q.get("status") != "active"),
        key=lambda q: q.get("resolved_turn", 0),
        reverse=True,
    )[:5]
    # SPEC-305 R20: lista branca — prazo exato, fonte, canal e motivo de falha nunca saem.
    day = int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)
    side = [quest_log.public_quest_view(q, day) for q in active + resolved]
    return {"main": main, "side": side, "markers": quest_log.quest_markers(quests)}


def _world_block(
    w: dict,
    projection: dict | None = None,
    event_log: list | None = None,
    player: dict | None = None,
    world_sim: dict | None = None,
    state: dict | None = None,
) -> dict[str, Any]:
    # SPEC-308 R7/P1-3: o mapa mostra o que o heroi SABE (eventos do motor so apos percebidos)
    from services.world_perception import perceived_projection

    pstate = state or {
        "world": w,
        "world_sim": world_sim,
        "event_log": event_log or [],
        "world_projection": projection or {},
    }
    projection = perceived_projection(pstate, projection or {})
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
            "control_changes": sv.recent_control_changes(
                event_log or [], w.get("visited", []), turn, state=pstate
            ),
            "threats": sv.active_threats(w, turn),
            "looming_threat": w.get("looming_threat", ""),
        },
        # Fase 6.1: rotas comerciais bloqueadas (WorldMap traceja a conexão)
        # SPEC-302 (revisão P2-2): só rotas com ponta num local que o herói conhece.
        "blocked_routes": [
            {"a": r.get("a", ""), "b": r.get("b", "")}
            for r in (projection or {}).get("blocked_routes", []) or []
            if {r.get("a"), r.get("b")} & {*(w.get("visited") or []), w.get("current_location_id")}
        ],
        # spec mapa-sublocais (R7): interiores do local atual ("Locais daqui")
        # + caminho de volta quando o jogador está DENTRO de um interior.
        "interiors": _interiors_block(w.get("current_location_id", "")),
        # SPEC-296 R8 + SPEC-302 R31: só o rótulo vago do local ATUAL e as notícias
        # percebidas (lista branca de campos); pressões/world_sim/relações nunca saem.
        "location_state": _location_state_label(w.get("current_location_id", ""), projection),
        # SPEC-303 R22: estação com rótulo regional do local atual (só id+label; passos,
        # festas e parâmetros do calendário nunca saem)
        "season": _season_view(w),
        # SPEC-307 R16: data de Valoria derivada (pura) de world_sim.calendar; nunca sai
        # epoch_offset/year_offset/catalogo de festas.
        "date": _date_block(w, world_sim),
        "news": [
            {
                **{k: n.get(k, "") for k in ("day", "period", "location_name", "text", "turn")},
                "date_label": _news_date_label(n, world_sim),
                # SPEC-312 R17: unico campo derivado de rumor (nunca truth/rumor_id/expires_day)
                "kind": _rumors_public_kind(n),
            }
            for n in (w.get("news") or [])[-12:]
            if isinstance(n, dict) and not _rumor_news_expired(n, w)
        ],
    }


def _rumors_public_kind(entry: dict) -> str:
    from services import rumors

    return rumors.public_kind(entry)


def _rumor_news_expired(entry: dict, world: dict) -> bool:
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    return entry.get("kind") == "rumor" and int(entry.get("expires_day", 0) or 0) < day


def _date_block(w: dict, world_sim: dict | None) -> dict[str, Any] | None:
    from services import world_calendar

    if world_calendar.mode() != "on":
        return None
    day = int((w.get("world_clock") or {}).get("day", 1) or 1)
    cal = world_calendar.calendar_for_read(world_sim, day)
    if not cal:
        return None
    v = world_calendar.date_view(cal, day)
    out = {
        k: v[k]
        for k in ("label", "day_of_month", "month", "month_id", "weekday", "year", "climate")
    }
    # D8: chip de estacao so onde a regiao tem rotulo proprio (Skallgard, Zhur)
    from services.world_pressures import region_of

    sid = world_calendar.active_season(w)
    region = region_of(str(w.get("current_location_id") or ""))
    out["season_chip"] = (
        world_calendar.label_for(sid, region)
        if sid and world_calendar.has_regional_label(sid, region)
        else ""
    )
    return out


def _news_date_label(item: dict, world_sim: dict | None) -> str:
    from services import world_calendar

    if world_calendar.mode() != "on":
        return ""
    try:
        day = int(item.get("day") or 0)
    except (TypeError, ValueError):
        return ""
    cal = world_calendar.calendar_for_read(world_sim, day) if day > 0 else None
    return world_calendar.date_label(cal, day) if cal else ""


def _season_view(w: dict) -> dict[str, str] | None:
    from services import world_calendar
    from services.world_pressures import region_of

    sid = world_calendar.active_season(w)
    if not sid:
        return None
    return {
        "id": sid,
        "label": world_calendar.label_for(sid, region_of(str(w.get("current_location_id") or ""))),
    }


def _location_state_label(loc_id: str, projection: dict | None) -> str:
    from services.location_states import location_state, public_label
    from services.world_engine import mode

    if mode() != "on":
        return ""
    return public_label(location_state({"world_projection": projection or {}}, loc_id))


def _interiors_block(loc_id: str) -> dict[str, Any]:
    from services.map_view import interiors_block

    return interiors_block(loc_id)


# --- ENDPOINTS ---


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "engine": "RPG IA v9.0 Hybrid Memory",
        "git_sha": os.getenv("GIT_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA") or "",
        "profile": os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() or "legacy",
        "hardened": is_hardened(os.environ),
    }


def _client_latency_enabled() -> bool:
    return os.getenv("RPG_CLIENT_LATENCY_REPORT", "0").strip() == "1"


_LATENCY_CLAMP_MAX = 600_000


class ClientLatencyReport(BaseModel):
    """SPEC-200 R10: corpo FECHADO — sem game_id, sem texto livre."""

    model_config = ConfigDict(extra="forbid")
    action_id: uuid.UUID
    transport: Literal["stream", "post"]
    ack_ms: int | None = None
    first_phase_ms: int | None = None
    ttfmc_ms: int | None = None
    ttlt_ms: int | None = None
    state_ms: int | None = None
    outcome: Literal["ok", "error", "aborted"] = "ok"

    @field_validator("ack_ms", "first_phase_ms", "ttfmc_ms", "ttlt_ms", "state_ms", mode="before")
    @classmethod
    def _clamp(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("inteiro esperado")
        return max(0, min(_LATENCY_CLAMP_MAX, int(value)))


@app.post(_CLIENT_LATENCY_PATH, status_code=204, include_in_schema=False)
def client_latency(report: ClientLatencyReport):
    """Beacon opcional (desligado por default): so loga e observa metricas
    `source=client`. Sem efeito em estado, saves ou saldo."""
    if not _client_latency_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        from observability.metrics import metrics
        from observability.telemetry import pseudonym, safe_json

        route = "/game/action/stream" if report.transport == "stream" else "/game/action"
        if report.ttfmc_ms is not None:
            metrics.observe(
                "rpg_turn_first_content_seconds",
                {"route": route, "source": "client"},
                report.ttfmc_ms / 1000,
            )
        if report.ttlt_ms is not None:
            metrics.observe(
                "rpg_turn_last_content_seconds",
                {"route": route, "source": "client"},
                report.ttlt_ms / 1000,
            )
        _turn_logger.info(
            safe_json(
                {
                    "event": "client_latency",
                    "evt": "client_latency",
                    "action_ref": pseudonym(report.action_id),
                    "transport": report.transport,
                    "ack_ms": report.ack_ms,
                    "first_phase_ms": report.first_phase_ms,
                    "ttfmc_ms": report.ttfmc_ms,
                    "ttlt_ms": report.ttlt_ms,
                    "state_ms": report.state_ms,
                    "outcome": report.outcome,
                }
            )
        )
    except Exception:
        pass
    return Response(status_code=204)


def _client_error_enabled() -> bool:
    """SPEC-244 R3: ligado por default; ``RPG_CLIENT_ERROR_REPORT=0`` e o kill switch."""
    return os.getenv("RPG_CLIENT_ERROR_REPORT", "1").strip() != "0"


_STACK_FRAME = r"^[A-Za-z0-9_./-]{1,120}:\d{1,7}(?::\d{1,7})?$"


class ClientErrorReport(BaseModel):
    """SPEC-244 R2: corpo FECHADO. Nada de mensagem de erro, texto do jogador, URL com query ou e-mail:
    todo campo tem enum/regex estreito e campo extra e 422."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["render", "unhandled", "network", "sse", "native"]
    error_name: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$.]{0,59}$")
    code: str | None = Field(default=None, pattern=r"^[a-z0-9_.:-]{1,64}$")
    route: str | None = Field(default=None, pattern=r"^/[A-Za-z0-9_/{}.-]{0,120}$")
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:-]{8,64}$")
    build: str | None = Field(default=None, pattern=r"^(?:[0-9a-f]{7}|dev)\+\d{12}$")
    client: Literal["web", "android"] = "web"
    stack: list[Annotated[str, Field(pattern=_STACK_FRAME)]] = Field(
        default_factory=list, max_length=20
    )
    ts: int | None = Field(default=None, ge=0, le=10**14)

    @field_validator("route")
    @classmethod
    def _route_as_template(cls, value: str | None) -> str | None:
        """Revisao P2/P3: o servidor nao confia no ``routeTemplate`` do cliente -- segmento com cara
        de id (hex/uuid >= 16, so digitos) vira ``{id}`` (nunca ``game_id`` em claro no log)."""
        if value is None:
            return None
        return "/".join("{id}" if _ID_SEGMENT.fullmatch(seg) else seg for seg in value.split("/"))


_ID_SEGMENT = re.compile(r"[0-9a-fA-F-]{16,}|\d+")
# Revisao P2/P3: sob abuso (IPs distribuidos), ``client.error`` sai 1x/min por assinatura; a metrica conta tudo.
_CLIENT_ERROR_LOG_INTERVAL_S = 60.0
_client_error_last: dict[tuple, float] = {}
_CLIENT_ERROR_LOG_MAX_PER_MIN = 600
_client_error_window: list[float] = [0.0, 0]  # [inicio da janela, linhas emitidas]


@app.post(_CLIENT_ERROR_PATH, status_code=204, include_in_schema=False)
def client_error(report: ClientErrorReport, request: Request):
    """SPEC-244 R3: beacon de erro do cliente -> ``client.error`` (warning) + metrica por ``kind``.

    Publico (fora da fronteira de sessao) mas: corpo <= 4 KiB, classe de rate limit ``telemetry``
    por IP, Origin cruzada recusada e nenhum campo livre."""
    if not _client_error_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {o.rstrip("/") for o in _CORS_ORIGINS}:
        raise HTTPException(status_code=403, detail="origin_denied")
    from observability.metrics import metrics
    from observability.telemetry import correlation, pseudonym

    metrics.increment("rpg_client_errors_total", {"kind": report.kind})
    beacon_id = correlation().get("request_id")
    fields = {k: v for k, v in report.model_dump().items() if v not in (None, [])}
    if report.request_id:  # o id da requisicao que falhou vence (busca pelo codigo de suporte)
        fields["beacon_request_id"] = beacon_id
    # Repeticao identica (mesmo IP+assinatura+request_id) sai 1x/min; teto GLOBAL de linhas/min contra
    # IPs distribuidos. O request_id entra na assinatura para nao esconder o codigo de suporte de outra falha.
    signature = (
        pseudonym(_client_ip(request)),
        report.kind,
        report.code,
        report.error_name,
        report.route,
        report.request_id,
    )
    now = time.monotonic()
    last = _client_error_last.get(signature)
    if last is not None and now - last < _CLIENT_ERROR_LOG_INTERVAL_S:
        return Response(status_code=204)
    window = _client_error_window
    if now - window[0] >= _CLIENT_ERROR_LOG_INTERVAL_S:
        window[0], window[1] = now, 0
    if window[1] >= _CLIENT_ERROR_LOG_MAX_PER_MIN:
        return Response(status_code=204)
    window[1] += 1
    if len(_client_error_last) > 5000:
        _client_error_last.clear()
    _client_error_last[signature] = now
    _log_event("client", "error", level="warning", **fields)
    return Response(status_code=204)


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


class _MetricsSqlCache:
    """SPEC-221 R2: o bloco SQL do /metrics roda no maximo 1x por ttl por processo."""

    def __init__(self) -> None:
        self._at = 0.0
        self._lock = threading.Lock()

    def ttl_s(self) -> float:
        try:
            return float(os.getenv("RPG_METRICS_SQL_CACHE_S", "15"))
        except ValueError:
            return 15.0

    def refresh(self, loader) -> None:
        with self._lock:
            now = time.monotonic()
            if self._at and now - self._at < self.ttl_s():
                return
            self._at = now
        loader()

    def reset(self) -> None:
        self._at = 0.0


_metrics_sql_cache = _MetricsSqlCache()


def _load_metrics_sql() -> None:
    from observability.metrics import metrics

    try:
        from infrastructure.runtime import get_runtime

        runtime = get_runtime()
        pool = getattr(runtime.job_queue, "pool", None)
        if pool is not None:
            with admin_connection(pool) as connection:  # SPEC-224: agregado cross-owner
                rows = connection.execute(
                    """
                    select kind,status,count(*)::int as count,
                      coalesce(extract(epoch from now()-min(created_at)),0) as oldest
                    from app.jobs group by kind,status
                    """
                ).fetchall()
                operations = connection.execute(
                    """
                    select kind,coalesce(max(extract(epoch from now()-started_at)),0) as age
                    from app.operations where status='running' group by kind
                    """
                ).fetchall()
                embedding = connection.execute(
                    """
                    select embedding_status,count(*)::int as count
                    from app.memory_documents where discarded_at is null
                    group by embedding_status
                    """
                ).fetchall()
            kinds: set[str] = set()
            for row in rows:
                kind, status = str(row["kind"]), str(row["status"])
                kinds.add(kind)
                metrics.set_gauge("rpg_jobs", {"kind": kind, "status": status}, row["count"])
            for kind in kinds:
                ages = [
                    float(row["oldest"] or 0)
                    for row in rows
                    if str(row["kind"]) == kind
                    and str(row["status"]) in {"queued", "retry", "running"}
                ]
                metrics.set_gauge(
                    "rpg_job_oldest_age_seconds", {"kind": kind}, max(ages, default=0.0)
                )
            for row in operations:
                metrics.set_gauge(
                    "rpg_operation_lease_age_seconds",
                    {"kind": str(row["kind"])},
                    float(row["age"] or 0),
                )
            for row in embedding:
                metrics.set_gauge(
                    "rpg_memory_embedding_backlog",
                    {"status": str(row["embedding_status"])},
                    row["count"],
                )
            stats = getattr(getattr(pool, "_pool", None), "get_stats", lambda: {})()
            for source, label in (
                ("pool_available", "available"),
                ("pool_size", "size"),
                ("requests_waiting", "waiting"),
            ):
                metrics.set_gauge("rpg_db_pool", {"state": label}, stats.get(source, 0))
        metrics.set_gauge("rpg_metrics_db_error", {}, 0)
    except Exception:
        metrics.set_gauge("rpg_metrics_db_error", {}, 1)  # mantem ultimos valores


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(request: Request):
    from observability.metrics import metrics

    if not _metrics_authorized(request):
        return Response(status_code=404)
    if _database_profile():
        _metrics_sql_cache.refresh(_load_metrics_sql)
    try:
        from pathlib import Path

        manifests = list(
            Path(os.getenv("RPG_BACKUP_ROOT", "readiness_artifacts")).glob("backup-*/manifest.json")
        )
        if manifests:
            newest = max(item.stat().st_mtime for item in manifests)
            metrics.set_gauge(
                "rpg_backup_age_seconds",
                {"component": "complete"},
                max(0.0, time.time() - newest),
            )
    except OSError:
        pass
    from services.finops_alerts import publish_evaluation_age  # SPEC-196: grows if cron stops

    publish_evaluation_age()
    return Response(
        metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def combat_simulator_options() -> dict[str, Any]:
    """Catálogo público mínimo do laboratório, derivado dos dados canônicos."""
    allowed = {"lacaio", "padrao", "elite", "chefe", "nomeado"}
    enemies = []
    for enemy_id, raw in gamedata.BESTIARY.items():
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("categoria") or "padrao").strip().lower()
        if category not in allowed:
            continue
        enemies.append(
            {
                "id": str(enemy_id),
                "name": str(raw.get("name") or enemy_id),
                "category": category,
                "regions": [str(region) for region in (raw.get("regions") or [])],
            }
        )
    enemies.sort(
        key=lambda enemy: (
            {"lacaio": 0, "padrao": 1, "elite": 2, "nomeado": 3, "chefe": 4}[enemy["category"]],
            enemy["name"].casefold(),
        )
    )
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

    player = create_player_character(
        {
            "name": "Combatente de Teste",
            "class_name": req.class_name,
            "race": "Humano",
            "region": "Nova Arcádia",
            "backstory": "Laboratório mecânico de combate.",
            "level": req.level,
        },
        use_llm_flavor=False,
    )
    player.update(
        {
            "gold": 0,
            "alignment": "Neutro",
            "active_conditions": [],
            "dead": False,
            "estado_terminal": False,
            "last_stand_pending": False,
            "last_stand_resolved": False,
        }
    )
    orchestrator.ensure_combat_sheet(player, is_player=True)

    template = gamedata.BESTIARY[req.enemy_id]
    category = str(template.get("categoria") or "padrao").lower()
    danger = {
        "lacaio": 1,
        "padrao": 2,
        "elite": 4,
        "nomeado": 5,
        "chefe": 6,
    }.get(category, 2)
    # SPEC-290: mesmo bônus de sobrevivência de Chefe/Nomeado do jogo real.
    from agents.bestiary import apply_encounter_survival
    from services.encounter_preparation import compute_encounter_level

    encounter_level = compute_encounter_level(location_danger=danger, region_danger=danger)
    enemies = []
    for index in range(1, req.quantity + 1):
        enemy = deepcopy(template)
        enemy["archetype_id"] = req.enemy_id
        enemy["id"] = f"{req.enemy_id}__sim_{index}"
        if req.quantity > 1:
            enemy["name"] = f"{template.get('name', req.enemy_id)} {index}"
        enemy.update(
            {
                "status": "ativo",
                "dead": False,
                "fled": False,
                "surrendered": False,
                "conscious": True,
                "active_conditions": [],
                "ferimentos": {"leve": [], "grave": [], "critico": []},
            }
        )
        apply_encounter_survival(enemy, encounter_level)
        enemy["vitalidade"] = int(enemy.get("max_vitalidade") or enemy.get("vitalidade") or 1)
        enemies.append(orchestrator.ensure_combat_sheet(enemy))

    scene = conflict_scene.new_scene(
        [
            {"id": "arena", "name": "Arena do Véu", "connections": []},
        ]
    )
    conflict_scene.place(scene, "player", zone_id="arena", distance_state="proximo")
    for enemy in enemies:
        conflict_scene.place(scene, enemy["id"], zone_id="arena", distance_state="proximo")
    conflict_scene.freeze(scene)

    world = starting_world("Nova Arcádia", req.level)
    world["current_location"] = "Arena do Véu"
    world["danger_level"] = danger
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
        "messages": [
            AIMessage(
                content=(
                    f"⚔️ Laboratório iniciado: {req.class_name} nível {req.level} contra "
                    f"{req.quantity}× {enemy_label}. Escolha uma Carta ou manobra."
                )
            )
        ],
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
            # SPEC-203: paridade de fase/manifesto (sem manifesto narrativo).
            "phase": "active",
            "outcome": None,
            "instance_id": f"{game_id}:sim",
            "encounter": _simulation_manifest(enemies, game_id, scene),
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
        "rejected_item_claims": [],
        "game_over": False,
        "death_pending": False,
        "continuity": {
            "session_action_count": 0,
            "timeline_epoch": 0,
            "last_checkpoint_turn": 0,
            "death_history": [],
        },
    }


@app.get("/data/combat-simulator")
def get_combat_simulator_options():
    return combat_simulator_options()


@app.post("/game/combat-simulator", response_model=GameResponse)
def new_combat_simulator(req: CombatSimulatorRequest):
    claim, _request_hash, prior = _begin_create_operation(req)
    if prior is not None:
        return prior
    try:
        state = _build_combat_simulator_state(req)
        response = format_response(state)
        if claim is not None:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            version, _receipt = get_runtime().turn_coordinator.commit_create(
                current_principal(),
                claim,
                state,
                receipt={"response": response.model_dump(mode="json")},
                checkpoint=True,
            )
            state["_storage_version"] = version
        elif not save_game_state(state):
            raise RuntimeError("falha ao persistir laboratório")
        return response
    except Exception as exc:
        _fail_operation(claim, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível criar o laboratório.",
        ) from exc


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
        raise HTTPException(status_code=404, detail="Conteúdo de onboarding indisponível.")
    return data


@app.get("/game/map")
def get_game_map(game_id: str | None = None):
    """SPEC-210: mapa do JOGO com fog server-side (só visitados + adjacentes).

    Mesmo guard de save de /game/state (UUID validado; 404 sem save; em perfis
    com banco o carregamento já é escopado ao dono). Fail-closed: nenhum nome,
    perigo, lore ou arte de local não alcançado sai daqui."""
    from services.map_view import build_map_view

    state = _load_unlocked_or_locked(_resolve_save_file(game_id), game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return build_map_view(state)


@app.get("/data/map")
def get_world_map(game_id: str | None = None):
    """Grafo de locais (Fase 0) para o mapa com fog of war no frontend.

    spec mapa-sublocais (R7): interiores NÃO aparecem no mapa-múndi —
    são expostos como "Locais daqui" no bloco `world` de /game/state.

    SPEC-210: com `game_id` devolve o mesmo formato, mas SÓ com os locais que
    o jogador descobriu (visitados + adjacentes, sem lore/perigo dos adjacentes).
    Sem `game_id` é o grafo global estático (CLI/smoke/legado).
    """
    if game_id:
        from services.map_view import legacy_filtered_map

        state = _load_unlocked_or_locked(_resolve_save_file(game_id), game_id)
        if not state:
            raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
        return legacy_filtered_map(state)
    data = dict(load_json_data("world_map.json") or {})
    data["locations"] = [loc for loc in data.get("locations", []) if loc.get("kind") != "interior"]
    return data


@app.get("/game/state")
def get_current_state(game_id: str | None = None):
    """
    Carrega o jogo. Se game_id for passado, carrega aquele especifico.
    Caso contrario, carrega o ultimo modificado.
    """
    # A lógica de carregar arquivo especifico deve ser implementada no persistence futuramente
    # Por enquanto, load_game_state carrega o mais recente se não passarmos nada
    # Se você implementou o load_game_state(specific_file), usaria aqui

    file_to_load = None
    file_to_load = _resolve_save_file(game_id)

    state = _load_unlocked_or_locked(file_to_load, game_id)

    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return format_response(state)


@app.get("/game/codex")
def get_player_codex(game_id: str | None = None):
    """Codex do jogador (Fase 3.2) — locais/fações/personagens/criaturas/segredos
    já registrados no save. On-demand (fora do GameResponse) para não inchar o turno."""
    file_to_load = _resolve_save_file(game_id)
    state = load_game_state(file_to_load)

    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return player_codex(state)


@app.get("/game/codex/dossiers")
def get_codex_dossiers(response: Response, game_id: str | None = None):
    """SPEC-211 — dossiês vivos (NPC/local/facção/segredo/crônica + bestiário).
    Projeção somente leitura sobre o save, sobre a projeção player-facing da
    SPEC-206 (fail-closed). `GET /game/codex` segue inalterado."""
    from services.dossier_visibility import DossiersResponseModel
    from services.dossiers import build_dossiers

    file_to_load = _resolve_save_file(game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    response.headers["Cache-Control"] = "private, no-store"
    # exclude_unset: chave acima do tier (R6) fica AUSENTE do JSON, nunca `null`.
    return DossiersResponseModel.model_validate(build_dossiers(state)).model_dump(
        exclude_unset=True
    )


@app.get("/game/history")
def game_history(game_id: str, cursor: str | None = None, limit: int = 50):
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
    from services.presentation_history import history_page

    try:
        page = history_page(state, cursor=cursor, limit=limit)
        # Enrichment must never mutate a presentation_history row held by the
        # loaded GameState, even transiently.
        page["entries"] = [dict(entry) for entry in page["entries"]]
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, "history_cursor_stale") from exc
    from services.faction_display import conceal_for

    page["entries"] = conceal_for(state, page["entries"])  # SPEC-293 R3
    # Financial data is an optional read projection. A failed query must never
    # hide the narrative or invent zero spend.
    if _database_profile() and page["entries"]:
        try:
            from infrastructure.account_read_model import PostgresAccountReader
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            reader = PostgresAccountReader(get_runtime().game_store.pool)
            costs = reader.history_costs(current_principal(), uuid.UUID(game_id), page["entries"])
            for entry in page["entries"]:
                if entry.get("role") == "narrator":
                    entry.update(
                        costs.get(
                            entry["id"],
                            {
                                "cost_milli": None,
                                "technical_cost_usd": None,
                                "technical_cost_basis": None,
                                "technical_cost_exact": False,
                            },
                        )
                    )
        except Exception:
            for entry in page["entries"]:
                if entry.get("role") == "narrator":
                    entry["cost_milli"] = None
                    entry["technical_cost_usd"] = None
                    entry["technical_cost_basis"] = None
                    entry["technical_cost_exact"] = False
    return page


def _account_reader():
    if not _database_profile():
        raise HTTPException(404, "Conta indisponível neste perfil.")
    from infrastructure.account_read_model import PostgresAccountReader
    from infrastructure.runtime import get_runtime

    return PostgresAccountReader(get_runtime().game_store.pool)


@app.get("/account/balance")
def account_balance():
    from infrastructure.request_context import current_principal

    return _account_reader().balance(current_principal())


def _stripe_payments():
    if not _database_profile():
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


@app.get("/account/checkout/skus")
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


@app.post("/account/checkout")
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
    if not _database_profile():
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


@app.get("/account/purchases/google/profile")
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


@app.get("/account/purchases/google/products")
def google_play_products():
    """Play product ids the app may query in the Store. No price: price comes from the Store only."""
    from infrastructure.google_play_payments import PostgresPurchaseStore
    from infrastructure.runtime import get_runtime

    if not _database_profile():
        raise HTTPException(503, "google_play_disabled")
    items = PostgresPurchaseStore(get_runtime().game_store.pool).list_products()
    return JSONResponse({"items": items}, headers={"Cache-Control": "no-store"})


@app.post("/account/purchases/google/verify")
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


@app.get("/account/checkout/{order_id}")
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


@app.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    """External provider route: raw signature replaces user cookie/CSRF auth."""
    import hashlib

    from starlette.concurrency import run_in_threadpool

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
            routes=app.routes,
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

                    log_body_too_large(request.url.path, MAX_WEBHOOK_BYTES, routes=app.routes)
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


@app.post("/account/transcriptions")
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

    if not _database_profile() or os.getenv("RPG_SPEECH_ENABLED", "0") != "1":
        raise HTTPException(503, "speech_disabled")
    principal = current_principal()
    runtime = get_runtime()
    decision = runtime.rate_limiter.consume(
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
                routes=app.routes,
            )
            raise SpeechError("audio_bytes", 413)
        payload = bytearray()
        async with __import__("asyncio").timeout(15):
            async for chunk in request.stream():
                if len(payload) + len(chunk) > MAX_AUDIO_BYTES:
                    from services.body_limit import log_body_too_large

                    log_body_too_large(request.url.path, MAX_AUDIO_BYTES, routes=app.routes)
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


@app.get("/account/purchases")
def account_purchases(cursor: str | None = None, limit: int = 20):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().purchases(current_principal(), cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@app.get("/account/usage")
def account_usage(cursor: str | None = None, limit: int = 20):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().usage(current_principal(), cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@app.get("/account/series")
def account_series(period: str = "7d"):
    from infrastructure.request_context import current_principal

    try:
        return _account_reader().series(current_principal(), period)
    except ValueError as exc:
        raise HTTPException(400, "invalid_request") from exc


@app.get("/game/{game_id}/operations/{operation_id}/cost")
def turn_cost(game_id: str, operation_id: str):
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
    if not _database_profile():
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


@app.get("/game/{game_id}/operations/{operation_id}")
def operation_status(game_id: str, operation_id: str):
    state = load_game_state(_resolve_save_file(game_id))  # ownership before lookup
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
    try:
        op, gid = uuid.UUID(operation_id), uuid.UUID(str(state["game_id"]))
    except ValueError as exc:
        raise HTTPException(400, "ID inválido.") from exc
    if not _database_profile():
        return {
            "status": "completed" if _action_already_processed(state, operation_id) else "unknown",
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
        "backstory": req.backstory or "",
        "level": req.level,
    }
    _enforce_owner_budget("llm_aux")  # SPEC-219 R3 (minuto/owner ja aplicado na fronteira)
    with _meter_auxiliary_operation("prologue"):
        scenario, mock = build_start_scenario(char_input)
    return {"scenario": scenario.model_dump(), "mock": mock}


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


@app.post("/game/art/brief")
def preview_player_art_brief(req: ArtBriefRequest):
    from services.art_brief import build_player_art_brief, render_image_prompt

    brief = build_player_art_brief(req.model_dump())
    return {"brief": brief, "rendered_prompt": render_image_prompt(brief), "provider_called": False}


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

    if not _database_profile() or os.getenv("RPG_DYNAMIC_ART_ENABLED", "0").lower() not in {
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


@app.post("/game/{game_id}/art/quote")
def create_image_quote(game_id: str, req: ArtQuoteRequest):
    from infrastructure.contracts import Conflict
    from services.art_brief import build_player_art_brief
    from services.art_triggers import ArtGenerationRequest
    from services.image_quotes import public_quote
    from services.shard_pricing import PricingUnavailable

    runtime, principal, repository = _image_finance()
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
    _validate_image_request(state, req.reformulation, req.image_type)
    if req.image_type == "player":
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
    if req.image_type != "player":
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


@app.post("/game/{game_id}/art/player/confirm")
@app.post("/game/{game_id}/art/confirm")
def confirm_player_art(game_id: str, req: ArtConfirmRequest):
    from infrastructure.contracts import Conflict
    from infrastructure.wallet import InsufficientShards, WalletConflict
    from services.art_triggers import ArtGenerationRequest, reserve_request
    from services.shard_pricing import PricingUnavailable
    from services.turn_effects import effect_scope
    from services.turn_execution import operation_scope

    # SPEC-196: replay of an existing generation must keep working with the switch off;
    # only a NEW confirm is refused (guard runs after the `prior` lookup below).
    runtime, principal, repository = _image_finance(guard=False)
    claim = None
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
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
    except (Conflict, WalletConflict):
        _fail_operation(claim, "image_quote_conflict")
        raise HTTPException(409, "image_quote_conflict") from None
    except Exception:
        _fail_operation(claim, "image_confirmation_failed")
        raise


@app.get("/game/{game_id}/art/{generation_id}")
def dynamic_art_status(game_id: str, generation_id: str):
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if _database_profile():
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


@app.post("/game/{game_id}/art/{generation_id}/quality")
def dynamic_art_quality(game_id: str, generation_id: str, req: ArtQualityRequest):
    state = load_game_state(_resolve_save_file(game_id))
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if _database_profile():
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
                approved=req.approved,
            )
        except (ValueError, Conflict) as exc:
            raise HTTPException(
                status_code=409, detail="Arte não disponível para avaliação."
            ) from exc
        return {"ok": True, "status": "ready" if req.approved else "rejected_quality"}
    ledger = list(state.get("art_generation_ledger") or [])
    row = next((item for item in ledger if item.get("generation_id") == generation_id), None)
    if not row or row.get("status") != "ready":
        raise HTTPException(status_code=409, detail="Arte não disponível para avaliação.")
    row["status"] = "ready" if req.approved else "rejected_quality"
    if not save_game_state(state):
        raise HTTPException(status_code=500, detail="Não foi possível salvar a avaliação.")
    return {"ok": True, "status": row["status"]}


@app.post("/game/new", response_model=GameResponse)
def new_game(req: CreateCharacterRequest):
    from infrastructure.runtime import get_runtime
    from rag import embedding_usage_scope
    from services.turn_effects import effect_scope
    from services.turn_execution import operation_scope

    _bind_corr(None, getattr(req, "action_id", None))
    claim, request_hash, prior = _begin_create_operation(req)
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
            if not save_game_state(final_state):
                raise RuntimeError("falha ao persistir jogo novo")
            # checkpoint INICIAL: a morte sempre possui um ponto de retorno.
            from persistence import save_checkpoint

            if not save_checkpoint(final_state):
                import persistence as persistence_mod

                persistence_mod.delete_save(new_game_id)
                raise RuntimeError("falha ao persistir checkpoint inicial")
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


def _action_already_processed(state: dict, action_id: str | None) -> bool:
    return bool(action_id and action_id in (state.get("processed_action_ids") or []))


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


def _require_saved(state: dict, *, detail: str = "estado") -> None:
    if not save_game_state(state):
        raise RuntimeError(f"falha ao persistir {detail}")


def _prepare_checkpoint(state: dict, previous: dict) -> bool:
    """Marca o snapshot antes do commit; o adapter Postgres o grava na mesma tx."""
    if (state.get("combat_simulation") or {}).get("enabled"):
        return False
    from services import checkpoints as _cp

    if not _cp.should_checkpoint(state, previous):
        return False
    if _database_profile():
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
    if _database_profile():
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
    if not _database_profile():
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


def _begin_turn_operation(state: dict, req: ActionRequest):
    """Retorna ``(claim, request_hash, receipt_response)`` no perfil durável."""
    if not _database_profile():
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
        _require_saved(state, detail="turno")
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
            fresh = load_game_state(_resolve_save_file(game_id))
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
        _require_saved(drained, detail=f"projeção ({where})")
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
    if not req.game_id and not _database_profile():
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
    lock = _game_lock(req.game_id) if not _database_profile() else nullcontext()
    lock_wait_started = _lat.now()
    with lock:
        # SPEC-200 R17: a "fila" do turno = espera do lock (e, em perfis hosted, da operacao).
        timeline.extra["lock_wait_ms"] = int(round((_lat.now() - lock_wait_started) * 1000))
        state = load_game_state(_resolve_save_file(req.game_id))
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        if not _database_profile():
            persistence_module.ensure_synthetic_checkpoint(state)  # SPEC-228 R4
        operation_wait_started = _lat.now()
        if _database_profile():
            # SPEC-213 R10: projeção do turno anterior em execução → espera e relê.
            state = _await_projection_db(state, req.game_id)
        claim, request_hash, receipt = _begin_turn_operation(state, req)
        if _database_profile():
            timeline.extra["lock_wait_ms"] += int(
                round((_lat.now() - operation_wait_started) * 1000)
            )
        if receipt is not None:
            return receipt
        with operation_scope(get_runtime().turn_coordinator if claim else None, claim):
            if _action_already_processed(state, req.action_id):
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
            db = _database_profile()
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


def _publish_timeline(timeline, outcome: str) -> None:
    """Entrega o registro final aos sinks (baseline). Nunca levanta."""
    try:
        from observability import latency as _lat

        if outcome != "client_gone":  # o worker ainda pode estar rodando
            timeline.finish()
        _lat.publish({**timeline.fields(), "outcome": outcome, "total_ms": timeline.total_ms()})
    except Exception:
        pass


def _bind_corr(game_id=None, action_id=None) -> None:
    """SPEC-240 R2: game_ref/action_ref no contexto de log do handler (nunca o id cru)."""
    try:
        from observability.telemetry import bind_correlation

        bind_correlation(game_id=game_id, action_id=action_id)
    except Exception:
        pass


@app.post("/game/action", response_model=GameResponse)
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


@app.post("/game/death", response_model=GameResponse)
def game_death(req: DeathChoiceRequest):
    """spec checkpoints-morte (D2): resolve a tela de morte.
    - `continue` → restaura do checkpoint (ou do início da sessão, D7); a saga segue.
    - `accept`   → memorial (game_over): a crônica encerra por escolha do jogador."""
    _bind_corr(req.game_id, req.action_id)
    lock = _game_lock(req.game_id) if not _database_profile() else nullcontext()
    with lock:
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
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

_MEMORIAL_DETAIL = (
    "Esta saga terminou. A crônica permanece como memorial — comece uma nova jornada."
)
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
    stream_started = time.monotonic()
    from observability.metrics import metrics

    # DEPRECATED (SPEC-200 R7): mede so o enfileiramento de `accepted`; mantida
    # para nao abrir buraco em series. A medida honesta e `rpg_sse_ack_seconds`.
    metrics.observe(
        "rpg_sse_first_event_seconds",
        {"route": _STREAM_ROUTE},
        time.monotonic() - stream_started,
    )
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
                reason="start" if common < min(len(shown), 40) else "tail",
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


@app.post("/game/action/stream")
def game_action_stream(req: ActionRequest):
    """R1: mesmo corpo do /game/action, resposta text/event-stream com fases
    reais do grafo. Guard-rails (rate limit via middleware, game_id, memorial,
    teto de input) valem aqui também (R3)."""
    from observability import latency as _lat

    timeline = _lat.TurnTimeline(transport="stream")  # t0 = entrada do handler (ACK servidor)
    file_to_load = _resolve_save_file(req.game_id)
    state = _load_unlocked_or_locked(file_to_load, req.game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    if not req.game_id and not _database_profile() and state.get("game_id"):
        # SPEC-228 R8: resolve "mais recente" UMA vez; aceite e worker usam o UUID.
        req = req.model_copy(update={"game_id": str(state["game_id"])})
    principal = None
    if _database_profile():
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


@app.post("/game/equip")
def game_equip(req: EquipRequest):
    """Fase 4.3: equipar/desequipar — validação 100% Python (inventory.equip)."""
    import inventory as inv_mod

    _bind_corr(req.game_id, req.action_id)
    lock = _game_lock(req.game_id) if not _database_profile() else nullcontext()
    with lock:
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
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


@app.post("/game/cards/prepare")
def game_cards_prepare(req: PrepareCardsRequest):
    """SPEC-209 R4: Preparação fora de combate. A regra mora em services.cards."""
    from services import cards

    _bind_corr(req.game_id, req.action_id)
    lock = _game_lock(req.game_id) if not _database_profile() else nullcontext()
    with lock:
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
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


@app.post("/game/levelup")
def game_levelup(req: LevelUpRequest):
    """Fase 4.1: aplica UMA escolha de level up (habilidade ou atributo).

    Validação 100% server-side (progression.apply_choice): escolha inexistente,
    habilidade inelegível (classe/nível/pré-requisito/ramo rival) ou atributo
    inválido → 400 e o save fica intocado."""
    _bind_corr(req.game_id, getattr(req, "action_id", None))
    lock = _game_lock(req.game_id) if not _database_profile() else nullcontext()
    with lock:
        file_to_load = _resolve_save_file(req.game_id)
        state = load_game_state(file_to_load)
        if not state:
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
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


@app.get("/game/saves", response_model=list[SaveSummary])
def get_saves():
    """R1: lista as campanhas salvas (mtime desc; corrompido é pulado)."""
    import persistence as persistence_mod

    return persistence_mod.list_saves()


@app.delete("/game/save/{game_id}")
def delete_save_endpoint(game_id: str, request: Request):
    """R2: exclui save + memória da sessão. Confirmação é da UI (uso local)."""
    import persistence as persistence_mod

    if _database_profile():
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
        prior = receipt_fn(principal, operation_id) if callable(receipt_fn) else None
        if prior:
            return prior
        digest = hashlib.sha256(f"delete:{game_uuid}".encode()).hexdigest()
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
            prior = receipt_fn(principal, operation_id) if callable(receipt_fn) else None
            if prior:
                _op_replayed("delete", operation_id)
                return prior
            _op_rejected("operation_in_progress", "delete", operation_id)
            raise HTTPException(status_code=409, detail="operation_in_progress") from exc
        except NotFound as exc:
            _fail_operation(claim, "not_found")
            raise HTTPException(status_code=404, detail="Save não encontrado.") from exc
    try:
        with _game_lock(game_id):
            removed = persistence_mod.delete_save(game_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="game_id inválido (esperado UUID).")
    if not removed:
        raise HTTPException(status_code=404, detail="Save não encontrado.")
    return {"ok": True}


@app.post("/game/chronicle/search")
def search_chronicle_endpoint(req: ChronicleSearchRequest):
    state = load_game_state(_resolve_save_file(req.game_id))
    if not state:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")
    from services.chronicle_search import search_chronicle

    try:
        semantic = None
        if _database_profile():
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


@app.get("/game/chronicle/export")
def export_chronicle(game_id: str | None = None):
    """R5: crônica como .txt (download) com separadores por capítulo."""
    from fastapi.responses import PlainTextResponse

    file_to_load = _resolve_save_file(game_id)
    state = load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")

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


# --- FRONTEND ESTÁTICO ---
# Servido na raiz "/". As rotas de API acima têm precedência sobre o mount.
# SPEC-267: só serve a build do app React (web/dist). Sem build a API sobe sem UI (`cd web && npm run build`).
_ROOT = os.path.dirname(os.path.abspath(__file__))
_WEB_DIST = os.path.join(_ROOT, "web", "dist")
if os.path.isdir(_WEB_DIST):
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn  # SPEC-317 R11: so o servidor local precisa; a Vercel nao importa

    # Auditoria A5: default local-only (API não tem auth até a Fase 10b).
    # Exponha na LAN conscientemente via RPG_HOST=0.0.0.0 no .env.
    uvicorn.run(app, host=os.getenv("RPG_HOST", "127.0.0.1"), port=8000)
