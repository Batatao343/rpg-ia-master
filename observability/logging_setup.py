"""SPEC-239: configuração central de logging (um handler JSON para todo ``rpg.*``).

Idempotente. Toda linha sai em stdout como JSON com ``event``, ``level``, ``logger`` e ``ts``;
logs legados (string ``%s``) são embrulhados e redigidos. Nunca registra ``str(exc)``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from observability.telemetry import correlation, redact

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
           "error": logging.ERROR}
_ROOT = "rpg"
_MARK = "_rpg_json_handler"


class _StdoutHandler(logging.StreamHandler):
    """Resolve ``sys.stdout`` a cada emissão (captura do pytest / redirecionamentos)."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout

    @stream.setter
    def stream(self, _value) -> None:
        pass


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        data: dict[str, Any] | None = None
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict):
                data = parsed
        except (ValueError, TypeError):
            pass
        if data is None:
            data = {"event": f"{record.name}.legacy", "message": _redact_legacy(message)}
        elif "event" not in data:
            data["event"] = data.get("evt") or f"{record.name}.event"
        for key, value in correlation().items():  # SPEC-240 R4: logs diretos também correlacionam
            data.setdefault(key, value)
        if record.exc_info and record.exc_info[0] is not None:
            from observability.telemetry import safe_stack
            data.setdefault("error_type", record.exc_info[0].__name__)
            data.setdefault("stack", safe_stack(record.exc_info[1]) if record.exc_info[1] else [])
        from observability.boot import INSTANCE_REF   # SPEC-249 R4
        data.setdefault("instance_ref", INSTANCE_REF)
        data["level"] = record.levelname.lower()
        data["logger"] = record.name
        data["ts"] = datetime.fromtimestamp(record.created, timezone.utc).isoformat(
            timespec="milliseconds").replace("+00:00", "Z")
        return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _redact_legacy(message: str) -> str:
    """Logs legados ``%s`` não passam por ``pseudonym``: ids crus (UUID) viram pseudônimo
    e IPv4 vira ``[IP]`` (revisão Sol SPEC-239/240)."""
    from observability.telemetry import pseudonym
    cleaned = _UUID_RE.sub(lambda m: "ref:" + pseudonym(m.group(0).lower()), message)
    cleaned = _IPV4_RE.sub("[IP]", cleaned)
    return redact(cleaned)


def _parse_level(raw: str | None) -> tuple[int, bool]:
    if raw is None or not raw.strip():
        return logging.INFO, True
    level = _LEVELS.get(raw.strip().lower())
    return (level, True) if level is not None else (logging.INFO, False)


class _MinLevelFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.min_level = logging.WARNING

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self.min_level


_QUIET_THIRD_PARTY = _MinLevelFilter()


def configure_logging(env: Mapping[str, str] | None = None) -> None:
    env = os.environ if env is None else env
    logger = logging.getLogger(_ROOT)
    level, valid = _parse_level(env.get("RPG_LOG_LEVEL"))
    logger.setLevel(level)
    # Tests (caplog) set RPG_LOG_PROPAGATE=1; production keeps a single JSON stream.
    logger.propagate = env.get("RPG_LOG_PROPAGATE", "0") == "1"
    if not any(getattr(h, _MARK, False) for h in logger.handlers):
        handler = _StdoutHandler()
        handler.setFormatter(JsonLineFormatter())
        setattr(handler, _MARK, True)
        logger.addHandler(handler)
    # Revisão Sol (smoke Vercel): o root logger da Vercel publica ``httpx`` em INFO — uma linha
    # não-JSON por chamada de provider, com a URL inteira (~4/turno). Só em debug.
    # Filtro (não só nível): o SDK ``openai`` re-sobe ``httpx`` para INFO no import (OPENAI_LOG).
    _QUIET_THIRD_PARTY.min_level = logging.DEBUG if level <= logging.DEBUG else logging.WARNING
    for noisy in ("httpx", "httpcore", "httpx2"):   # httpx2 = cliente HTTP do SDK openai
        noisy_logger = logging.getLogger(noisy)
        if _QUIET_THIRD_PARTY not in noisy_logger.filters:
            noisy_logger.addFilter(_QUIET_THIRD_PARTY)
    prefix = "RPG_LOG_LEVEL_"
    for key, value in env.items():
        if key.startswith(prefix) and len(key) > len(prefix):
            area_level = _LEVELS.get(str(value).strip().lower())
            if area_level is not None:
                logging.getLogger(f"{_ROOT}.{key[len(prefix):].lower()}").setLevel(area_level)
    if not valid:
        from observability.telemetry import log_event
        log_event("logging", "config_invalid_level", level="warning", fallback="info")
