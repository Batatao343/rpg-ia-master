"""SPEC-381: rotas de ops (movidas de api.py, sem mudanca)."""

import os
import re
import threading
import time
import uuid
from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from observability.telemetry import log_event as _log_event
from infrastructure.db_roles import admin_connection
from infrastructure.runtime import is_hardened
import api_core
from api_core import (
    _CLIENT_ERROR_PATH,
    _CLIENT_LATENCY_PATH,
    _CORS_ORIGINS,
    _client_ip,
    _client_latency_enabled,
    _metrics_authorized,
    _turn_logger,
)

router = APIRouter()


# --- ENDPOINTS ---


@router.get("/health")
def health_check():
    return {
        "status": "online",
        "engine": "RPG IA v9.0 Hybrid Memory",
        "git_sha": os.getenv("GIT_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA") or "",
        "profile": os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() or "legacy",
        "hardened": is_hardened(os.environ),
    }


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


@router.post(_CLIENT_LATENCY_PATH, status_code=204, include_in_schema=False)
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


@router.post(_CLIENT_ERROR_PATH, status_code=204, include_in_schema=False)
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


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics(request: Request):
    from observability.metrics import metrics

    if not _metrics_authorized(request):
        return Response(status_code=404)
    if api_core._database_profile():
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
