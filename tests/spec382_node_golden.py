"""Harness do golden de nos da SPEC-382 (refatoracao pura de storyteller/combate).

Grava, por caso, o hash de: (a) dict devolvido, (b) estado de entrada apos a chamada (mutacao
in-place), (c) eventos de observabilidade (`rpg.*` + `record_step`), (d) arquivos escritos em
`tmp_path`. Os casos vivem em `spec382_node_cases.py`; o fixture e gravado UMA vez (Etapa 1).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

GOLDEN = Path(__file__).parent / "fixtures" / "spec382_node_golden.json"
DUMP_ENV = "SPEC382_DUMP"  # pasta: grava o texto normalizado de cada parte (diff de depuracao)

# Campos instaveis (uuid/relogio/latencia) removidos antes do hash; lista fechada na Etapa 1.
VOLATILE_KEYS = {"request_id", "trace_id", "span_id", "ts", "timestamp", "latency_ms", "elapsed_ms"}
_HEX_RE = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-f]*\d)[0-9a-f]{8,32}(?![0-9A-Za-z])")


def norm(obj: Any) -> Any:
    """Valor serializavel e estavel (mensagens -> (tipo, content); sets ordenados)."""
    if hasattr(obj, "model_dump"):
        return {"__model__": type(obj).__name__, **norm(obj.model_dump())}
    if hasattr(obj, "content") and hasattr(obj, "type") and not isinstance(obj, dict):
        return ["msg", type(obj).__name__, norm(obj.content)]
    if isinstance(obj, dict):
        return {
            _HEX_RE.sub("<hex>", str(k)): norm(v)
            for k, v in obj.items()
            if str(k) not in VOLATILE_KEYS
        }
    if isinstance(obj, (list, tuple)):
        return [norm(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((norm(v) for v in obj), key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(obj, float):
        return round(obj, 9)
    if isinstance(obj, str):
        return _HEX_RE.sub("<hex>", obj)
    if isinstance(obj, (int, bool)) or obj is None:
        return obj
    return repr(obj)


def dumps(obj: Any) -> str:
    return json.dumps(norm(obj), ensure_ascii=False, sort_keys=True, default=str, indent=0)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class _Sink(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.rows: list[list[str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("rpg"):
            msg = _HEX_RE.sub("<hex>", record.getMessage())
            if "llm.mock_selected" in msg:  # aviso uma-vez-por-processo: depende da ordem dos casos
                return
            msg = re.sub(r'"(?:' + "|".join(VOLATILE_KEYS) + ')": ?[^,}]+', '"<v>"', msg)
            self.rows.append([record.name, record.levelname, msg])


class Recorder:
    """Acumula as quatro partes de um caso (varias chamadas de no por caso)."""

    def __init__(self, monkeypatch, tmp_path: Path) -> None:
        self.mp, self.tmp = monkeypatch, tmp_path
        self.results: list[Any] = []
        self.states: list[Any] = []
        self.events: list[Any] = []
        self.trace: list[Any] = []
        self.sink = _Sink()
        from services import mechanics_trace

        orig = mechanics_trace.record_step
        trace = self.trace

        def spy(kind, *a, **kw):
            trace.append([kind, norm(kw.get("actor")), norm(kw.get("reason"))])
            return orig(kind, *a, **kw)

        monkeypatch.setattr(mechanics_trace, "record_step", spy)
        root = logging.getLogger()
        self._old_level = root.level
        root.addHandler(self.sink)
        root.setLevel(logging.DEBUG)
        from agents import combat

        monkeypatch.setattr(combat, "_OUTCOME_BUDGET_S", 600.0, raising=False)

    def close(self) -> None:
        root = logging.getLogger()
        root.removeHandler(self.sink)
        root.setLevel(self._old_level)

    def call(self, fn: Callable[[Any], Any], state: dict, *, seed: int = 1) -> Any:
        random.seed(seed)
        try:
            result = fn(state)
        except Exception as exc:  # noqa: BLE001 - o no nunca deveria levantar; se levantar, e parte do oraculo
            result = {"__raised__": type(exc).__name__}
        self.results.append(result)
        self.states.append(state)
        return result

    def files(self) -> list[list[str]]:
        rows = []
        for p in sorted(self.tmp.rglob("*")):
            if p.is_file():
                rel = p.relative_to(self.tmp).as_posix()
                raw = p.read_bytes()
                with contextlib.suppress(UnicodeDecodeError):  # texto: uuid varia por execucao
                    raw = _HEX_RE.sub("<hex>", raw.decode("utf-8")).encode("utf-8")
                rows.append([rel, hashlib.sha256(raw).hexdigest()[:12]])
        return rows

    def digest(self, name: str) -> dict[str, str]:
        self.events.extend(self.sink.rows)
        parts = {
            "result": dumps(self.results),
            "state": dumps(self.states),
            "events": dumps(self.events),
            "trace": dumps(self.trace),
            "files": dumps(self.files()),
        }
        dump = os.getenv(DUMP_ENV)
        if dump:
            out = Path(dump)
            out.mkdir(parents=True, exist_ok=True)
            for key, text in parts.items():
                (out / f"{name}.{key}.txt").write_text(text, encoding="utf-8")
        return {k: sha(v) for k, v in parts.items()}


def load_golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}


def save_golden(data: dict) -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
