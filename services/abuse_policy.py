"""SPEC-219: politica unica de abuso -- classes de rota, limites por IP/owner, cota diaria e IP real.

Tudo aqui e determinístico e sem LLM. ``classify`` mapeia (metodo, path) para UMA classe; o
middleware aplica o limite por IP, a fronteira de sessao aplica o limite por owner e os
handlers que gastam LLM chamam ``enforce_daily_quota`` ANTES de invocar o grafo.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone, UTC
from typing import Any, NamedTuple
from collections.abc import Mapping

_ID = r"[^/]+"


class RouteClass(NamedTuple):
    name: str
    pattern: re.Pattern[str]
    methods: frozenset[str]
    ip_limit: int
    owner_limit: int          # 0 = sem limite por owner nesta camada
    window_s: int
    daily_quota: bool


def _rc(name: str, pattern: str, methods: tuple[str, ...], ip: int, owner: int,
        *, window: int = 60, daily: bool = False) -> RouteClass:
    return RouteClass(name, re.compile(pattern), frozenset(methods), ip, owner, window, daily)


# Ordem importa: a primeira classe que casa vence (``read_auth`` e a rede de seguranca final).
ROUTE_CLASSES: dict[str, RouteClass] = {c.name: c for c in (
    _rc("turn", r"^/game/(action|action/stream|death)$", ("POST",), 60, 20, daily=True),
    _rc("llm_aux", r"^/game/(new|prologue|art/brief|combat-simulator)$", ("POST",), 30, 6, daily=True),
    _rc("embedding", r"^/game/chronicle/search$", ("POST",), 30, 10),
    _rc("quote", rf"^/game/{_ID}/art/(quote|confirm|player/confirm)$", ("POST",), 30, 10),
    _rc("mutation",
        rf"^/game/(equip|levelup|cards/prepare)$|^/game/save/{_ID}$|^/game/{_ID}/art/{_ID}/quality$",
        ("POST", "DELETE"), 60, 30),
    _rc("payments", r"^/account/(checkout|purchases/google/verify)$", ("POST",), 15, 5),
    _rc("export", rf"^/account/export$|^/game/{_ID}/audit-export$", ("GET", "POST"), 30, 6),
    _rc("stt", r"^/account/transcriptions$", ("POST",), 30, 0),   # owner: 5/min no proprio handler
    _rc("latency", r"^/telemetry/client-latency$", ("POST",), 30, 0),
    _rc("telemetry", r"^/telemetry/client-error$", ("POST",), 30, 0),   # SPEC-244 (publico, so IP)
    _rc("read_auth", r"^/(game|account)(/|$)", ("GET", "HEAD"), 300, 120),
)}

LEGACY_DEFAULT_ENV = "RPG_RATE_LIMIT"


def classify(method: str, path: str) -> RouteClass | None:
    method = method.upper()
    for cls in ROUTE_CLASSES.values():
        if method in cls.methods and cls.pattern.match(path):
            return cls
    return None


def _env_int(env: Mapping[str, str], name: str) -> int | None:
    raw = str(env.get(name, "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def limits_for(cls: RouteClass, env: Mapping[str, str] | None = None) -> tuple[int, int]:
    """(ip_limit, owner_limit) efetivos. ``0`` desliga aquele escopo.

    Precedencia: ``RPG_LIMIT_<CLASS>_IP/_OWNER`` > ``RPG_RATE_LIMIT`` (legado; so IP, exceto
    ``read_auth``) > default da classe. ``RPG_RATE_LIMIT=0`` desliga TUDO por minuto (suite/smoke).
    """
    env = os.environ if env is None else env
    legacy = _env_int(env, LEGACY_DEFAULT_ENV)
    if legacy is not None and legacy <= 0:
        return 0, 0
    key = cls.name.upper()
    ip = _env_int(env, f"RPG_LIMIT_{key}_IP")
    if ip is None:
        ip = legacy if (legacy is not None and cls.name != "read_auth") else cls.ip_limit
    owner = _env_int(env, f"RPG_LIMIT_{key}_OWNER")
    if owner is None:
        owner = cls.owner_limit
    return max(ip, 0), max(owner, 0)


def daily_quota_limit(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    value = _env_int(env, "RPG_DAILY_TURN_QUOTA")
    return 600 if value is None else max(value, 0)


# --- IP real -----------------------------------------------------------------

def _first_valid(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",")[0].strip()
    return first if 0 < len(first) <= 64 and re.fullmatch(r"[0-9A-Fa-f:.]+", first) else None


def client_ip(request: Any, env: Mapping[str, str] | None = None) -> str:
    """IP do cliente. Nunca levanta: qualquer header ausente/malformado cai em ``client.host``.

    * ``VERCEL`` setado: ``x-vercel-forwarded-for`` (a plataforma o sobrescreve, o cliente nao
      controla) e, na falta, ``x-real-ip``.
    * ``RPG_TRUSTED_PROXY_HOPS=N>0``: N-esimo valor da DIREITA de ``x-forwarded-for`` (o que o
      N-esimo proxy confiavel anexou; valores a esquerda sao spoofaveis).
    * senao ``request.client.host``.
    """
    env = os.environ if env is None else env
    headers = getattr(request, "headers", None) or {}
    fallback = getattr(getattr(request, "client", None), "host", None) or "unknown"
    try:
        if str(env.get("VERCEL", "")).strip():
            found = _first_valid(headers.get("x-vercel-forwarded-for")) or _first_valid(
                headers.get("x-real-ip"))
            if found:
                return found
        hops = _env_int(env, "RPG_TRUSTED_PROXY_HOPS") or 0
        if hops > 0:
            parts = [p.strip() for p in str(headers.get("x-forwarded-for", "")).split(",") if p.strip()]
            if len(parts) >= hops:
                candidate = _first_valid(parts[-hops])
                if candidate:
                    return candidate
    except Exception:
        pass
    return fallback


# --- cota diaria ---------------------------------------------------------------

class QuotaDecision(NamedTuple):
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


def seconds_until_utc_midnight(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((nxt - now).total_seconds()))


class MemoryDailyQuota:
    """Contador em memoria (testes / perfis sem Postgres)."""

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, str], int] = {}

    def bump(self, owner_id: Any, cls: str, limit: int, *, now: datetime | None = None) -> QuotaDecision:
        now = now or datetime.now(UTC)
        key = (str(owner_id), now.date().isoformat(), cls)
        count = self._counts.get(key, 0)
        if count >= limit:
            return QuotaDecision(False, count, limit, seconds_until_utc_midnight(now))
        self._counts[key] = count + 1
        return QuotaDecision(True, count + 1, limit, 0)


def rate_limited_body(detail: str, scope: str, retry_after: int) -> dict[str, Any]:
    return {"detail": detail, "scope": scope, "retry_after_seconds": int(retry_after)}


# SPEC-246: sob ataque, ``abuse.blocked`` sai 1x/min por (classe, escopo, chave); a metrica conta todos.
_BLOCK_LOG_INTERVAL_S = 60.0
_block_log_last: dict[tuple[str, str, str], float] = {}


def record_block(cls: str, scope: str, *, owner: Any = None, ip: str | None = None,
                 retry_after: int | None = None, limit: int | None = None) -> None:
    """Metrica (labels fechados, sem ids) + log JSON pseudonimizado e amostrado. Nunca levanta."""
    try:
        import time

        from observability.metrics import metrics
        from observability.telemetry import log_event, pseudonym
        metrics.increment("rpg_rate_limited_total", {"class": cls, "scope": scope})
        owner_ref = pseudonym(owner) if owner else None
        ip_ref = pseudonym(ip) if ip else None
        key = (cls, scope, owner_ref or ip_ref or "")
        now = time.monotonic()
        last = _block_log_last.get(key)
        if last is not None and now - last < _BLOCK_LOG_INTERVAL_S:
            return
        if len(_block_log_last) > 5000:
            _block_log_last.clear()
        _block_log_last[key] = now
        log_event("abuse", "blocked", level="warning", cls=cls, scope=scope,
                  owner_ref=owner_ref, ip_ref=ip_ref,
                  retry_after_s=int(retry_after) if retry_after is not None else None,
                  limit=int(limit) if limit is not None else None)
    except Exception:  # silent-ok: contabilidade de bloqueio nunca derruba a resposta 429
        pass


def limiter_unavailable(site: str, exc: BaseException) -> None:
    """SPEC-246 R4: limitador/cota indisponivel segue FAIL-OPEN (SPEC-219), mas visivel.

    ``site`` e um codigo fechado (authfail|owner_minute|daily_quota); so a classe da excecao."""
    try:
        from observability.metrics import metrics
        from observability.telemetry import log_event
        metrics.increment("rpg_rate_limiter_errors_total", {"site": site})
        log_event("abuse", "limiter_unavailable", level="error", site=site,
                  error_type=type(exc).__name__)
    except Exception:  # silent-ok: o log do fail-open nunca derruba a rota
        pass
