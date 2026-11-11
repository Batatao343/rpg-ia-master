"""
api.py
Interface REST API para o RPG Engine.
Atualizado para suportar Memória Híbrida (Game ID e Resumo).
Fase 10: game_id validado (UUID) na borda, CORS por env, rate limit mínimo,
log JSON por turno.
"""

import os
import re
import sys
import time
import uuid  # <--- Necessário para gerar IDs de sessão
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from observability.telemetry import log_event as _log_event

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do seu motor
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
from infrastructure.runtime import assert_boot_policy, docs_enabled
from llm_setup import LLMAttemptEvent, set_llm_attempt_telemetry_hook, set_llm_telemetry_hook
import main  # noqa: F401  # SPEC-381: mesma posicao de import; game_graph mora em routes.turn
from persistence import IncompatibleSaveError
from services.usage_metering import normalize_attempts

import api_core
from api_core import (
    QuotaExceeded,
    _CLIENT_ERROR_PATH,
    _client_ip,
    _current_request_id,
    _error_response,
    _llm_attempt_events,
    _llm_turn_events,
    _log_csrf_rejection,
    _metrics_authorized,
)


# --- reexports (SPEC-381 R9): mesmo objeto do modulo-lar; nome patchado nunca entra ---
from api_core import (
    _begin_state_mutation as _begin_state_mutation,
    _enforce_owner_budget as _enforce_owner_budget,
    _enqueue_art_generation as _enqueue_art_generation,
    _llm_log_fields as _llm_log_fields,
    _meter_auxiliary_operation as _meter_auxiliary_operation,
    _release_failed as _release_failed,
    _turn_logger as _turn_logger,
)
from api_models import (
    ActionRequest as ActionRequest,
    ArtConfirmRequest as ArtConfirmRequest,
    ArtQualityRequest as ArtQualityRequest,
    ArtQuoteRequest as ArtQuoteRequest,
    CombatSimulatorRequest as CombatSimulatorRequest,
    CreateCharacterRequest as CreateCharacterRequest,
    GameResponse as GameResponse,
    PlayStepRequest as PlayStepRequest,
)
from api_presenters import (
    _PORTRAIT_PRICE_CACHE as _PORTRAIT_PRICE_CACHE,
    _ParticipantNames as _ParticipantNames,
    _abyss_tier_view as _abyss_tier_view,
    _cards_block as _cards_block,
    _combat_block as _combat_block,
    _companion_feedback as _companion_feedback,
    _companion_labels as _companion_labels,
    _death_block as _death_block,
    _deck_view as _deck_view,
    _enemy_portrait as _enemy_portrait,
    _factions_block as _factions_block,
    _image_effect_open as _image_effect_open,
    _inventory_block as _inventory_block,
    _npcs_block as _npcs_block,
    _portrait_offer_price as _portrait_offer_price,
    _prepared_slots as _prepared_slots,
    _public_art_offer as _public_art_offer,
    _public_art_refs as _public_art_refs,
    _quest_block as _quest_block,
    _world_block as _world_block,
    format_response as format_response,
)
from routes.art import (
    _monster_quote_inputs as _monster_quote_inputs,
    _offer_brief_for_quote as _offer_brief_for_quote,
    confirm_player_art as confirm_player_art,
    create_image_quote as create_image_quote,
    dynamic_art_quality as dynamic_art_quality,
    dynamic_art_status as dynamic_art_status,
)
from routes.billing import (
    GooglePlayVerifyRequest as GooglePlayVerifyRequest,
    google_play_profile as google_play_profile,
    google_play_verify as google_play_verify,
)
from routes.ops import (
    ClientLatencyReport as ClientLatencyReport,
    _client_error_last as _client_error_last,
    _client_error_window as _client_error_window,
    _metrics_sql_cache as _metrics_sql_cache,
    health_check as health_check,
)
from routes.read import (
    _build_combat_simulator_state as _build_combat_simulator_state,
    combat_simulator_options as combat_simulator_options,
)
from routes.turn import (
    _apply_play_list as _apply_play_list,
    _drain_creature_gen as _drain_creature_gen,
    _drain_projection as _drain_projection,
    _drain_projection_db as _drain_projection_db,
    _pre_drain_in_turn as _pre_drain_in_turn,
    _prepare_checkpoint as _prepare_checkpoint,
    _stream_turn as _stream_turn,
    new_game as new_game,
)
# --- fim dos reexports ---


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
    body: dict[str, Any] = {
        "detail": [
            # SPEC-337 R19: nunca devolve ``input``/``ctx``/``url`` (eco de senha/segredo).
            {
                "type": e.get("type"),
                "loc": list(e.get("loc", ())),
                "msg": str(e.get("msg", "")),
            }
            for e in errors
        ],
        "code": "validation_failed",
    }
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
_CORS_ORIGINS = api_core._CORS_ORIGINS  # SPEC-381: lista unica, preenchida no lugar
_CORS_ORIGINS[:] = [
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


def _mount_router(router: APIRouter) -> None:
    """SPEC-381 R21: copia as APIRoute planas (include_router criaria um _IncludedRouter opaco)."""
    app.router.routes.extend(router.routes)


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
    if not api_core._database_profile() or not _session_scoped_path(
        request.url.path, request.query_params
    ):
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


from routes.auth import router as _auth_router

_mount_router(_auth_router)


# Fase 10 (R7) + SPEC-239: 1 linha JSON por turno; handler central em stdout.
from observability.logging_setup import configure_logging

configure_logging()
from observability.boot import log_boot_once  # SPEC-249

log_boot_once()


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


# Fase 10 (R6): rate limit mínimo por IP (janela deslizante em memória).
# RPG_RATE_LIMIT = req/min em /game/action e /game/new; 0 desliga (suíte/smoke).
_RATE_WINDOW_S = 60.0
_rate_hits: dict[str, deque] = defaultdict(deque)


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
    if api_core._database_profile():
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


@app.exception_handler(QuotaExceeded)
async def _quota_exceeded_handler(_request, exc: QuotaExceeded):
    return _blocked_response(exc.detail, exc.scope, exc.retry_after_seconds, status=exc.status_code)


from routes.ops import router as _ops_router

_mount_router(_ops_router)


from routes.read import router as _read_router

_mount_router(_read_router)


from routes.billing import router as _billing_router

_mount_router(_billing_router)


from routes.art import router as _art_router

_mount_router(_art_router)


from routes.turn import router as _turn_router

_mount_router(_turn_router)


from routes.play import router as _play_router

_mount_router(_play_router)


from routes.saves import router as _saves_router

_mount_router(_saves_router)


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
