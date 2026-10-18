"""SPEC-239: configuração central de logging (um handler JSON para todo ``rpg.*``).

Idempotente. Toda linha sai em stdout como JSON com ``event``, ``level``, ``logger`` e ``ts``;
logs legados (string ``%s``) são embrulhados e redigidos. Nunca registra ``str(exc)``.
"""

from __future__ import annotations

import json
import logging
import os
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
            data = {"event": f"{record.name}.legacy", "message": redact(message)}
        elif "event" not in data:
            data["event"] = data.get("evt") or f"{record.name}.event"
        for key, value in correlation().items():  # SPEC-240 R4: logs diretos também correlacionam
            data.setdefault(key, value)
        if record.exc_info and record.exc_info[0] is not None:
            data.setdefault("error_type", record.exc_info[0].__name__)
        data["level"] = record.levelname.lower()
        data["logger"] = record.name
        data["ts"] = datetime.fromtimestamp(record.created, timezone.utc).isoformat(
            timespec="milliseconds").replace("+00:00", "Z")
        return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _parse_level(raw: str | None) -> tuple[int, bool]:
    if raw is None or not raw.strip():
        return logging.INFO, True
    level = _LEVELS.get(raw.strip().lower())
    return (level, True) if level is not None else (logging.INFO, False)


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
    prefix = "RPG_LOG_LEVEL_"
    for key, value in env.items():
        if key.startswith(prefix) and len(key) > len(prefix):
            area_level = _LEVELS.get(str(value).strip().lower())
            if area_level is not None:
                logging.getLogger(f"{_ROOT}.{key[len(prefix):].lower()}").setLevel(area_level)
    if not valid:
        from observability.telemetry import log_event
        log_event("logging", "config_invalid_level", level="warning", fallback="info")
