"""SPEC-200: linha do tempo de um turno (ack, TTFMC, TTLT e fases exclusivas).

Puro: sem I/O, sem rede, sem dependência do grafo. O relógio é injetável para
que o baseline offline seja determinístico (``FakeClock``). Nada aqui altera o
comportamento do jogo — só mede.
"""

from __future__ import annotations

import contextvars
import logging
import threading
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, Iterator, List, Optional


class TurnPhase(str, Enum):
    ROUTER = "router"
    CONTEXT = "context"
    NARRATOR = "narrator"
    ARCHIVIST = "archivist"
    PERSISTENCE = "persistence"
    OTHER = "other"


PHASES = tuple(p.value for p in TurnPhase)

# Nós do grafo -> fase (R2). Nós desconhecidos caem em OTHER.
NODE_PHASE: Dict[str, TurnPhase] = {
    "dm_router": TurnPhase.ROUTER,
    "campaign_manager": TurnPhase.ROUTER,
    "storyteller": TurnPhase.NARRATOR,
    "combat_agent": TurnPhase.NARRATOR,
    "npc_actor": TurnPhase.NARRATOR,
    "loot_agent": TurnPhase.NARRATOR,
    "archivist": TurnPhase.ARCHIVIST,
}


# Estratificação por tamanho de entrada (R17) — limiares fixos e documentados.
INPUT_SHORT_MAX = 40
INPUT_MEDIUM_MAX = 160


def input_size(chars: int) -> str:
    if chars <= INPUT_SHORT_MAX:
        return "short"
    if chars <= INPUT_MEDIUM_MAX:
        return "medium"
    return "long"


class FakeClock:
    """Relógio virtual: só avança quando mandado (zero espera real)."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._now

    def advance(self, seconds: float) -> float:
        with self._lock:
            self._now += max(0.0, float(seconds))
            return self._now


_clock_source: Callable[[], float] = time.monotonic


def set_clock(fn: Optional[Callable[[], float]]) -> None:
    """Troca o relógio default das timelines novas (None = monotonic)."""
    global _clock_source
    _clock_source = fn or time.monotonic


def now() -> float:
    return _clock_source()


_sinks: List[Callable[[Dict[str, Any]], None]] = []


def add_sink(fn: Callable[[Dict[str, Any]], None]) -> None:
    _sinks.append(fn)


def remove_sink(fn: Callable[[Dict[str, Any]], None]) -> None:
    try:
        _sinks.remove(fn)
    except ValueError:
        pass


class TurnTimeline:
    """Marcas de entrega + acumulador de fases exclusivas (thread-safe)."""

    def __init__(self, clock: Optional[Callable[[], float]] = None, *,
                 transport: str = "post") -> None:
        self._clock = clock or _clock_source
        self._lock = threading.RLock()
        self.transport = transport
        self.t0 = self._clock()
        self._cursor = self.t0
        self._end: Optional[float] = None
        self._marks: Dict[str, float] = {}
        self._phase_s: Dict[str, float] = {p: 0.0 for p in PHASES}
        self._stack: List[str] = []
        self._unassigned = 0.0
        self._pending_attempts: Dict[str, int] = {}
        self._llm_by_phase: Dict[str, int] = {}
        self.extra: Dict[str, Any] = {}
        self._log_hold = False
        self._log_pending: Optional[Callable[[], None]] = None

    # --- linha rpg.turn adiada (SPEC-212 R13) ---------------------------------
    def hold_log(self) -> None:
        """Stream: segura a linha `rpg.turn` ate as marcas ttfmc/ttlt existirem."""
        with self._lock:
            self._log_hold = True

    def submit_log(self, fn: Callable[[], None]) -> None:
        """Emite `fn` ja, ou o guarda se a entrega ainda esta em curso."""
        with self._lock:
            if self._log_hold:
                self._log_pending = fn
                return
        fn()

    def release_log(self) -> None:
        """Fim da entrega (ou desconexao): libera a linha guardada; o que chegar
        depois (worker apos client_gone) sai direto em `submit_log`."""
        with self._lock:
            self._log_hold = False
            fn, self._log_pending = self._log_pending, None
        if fn is not None:
            try:
                fn()
            except Exception:   # roda no `finally` do stream: nunca pula turn_delivery
                logging.getLogger(__name__).exception("linha rpg.turn adiada falhou")

    # --- marcas de entrega -------------------------------------------------
    def mark(self, name: str) -> None:
        """Registra a PRIMEIRA ocorrência de uma marca (idempotente)."""
        with self._lock:
            self._marks.setdefault(name, self._clock())

    def mark_ms(self, name: str) -> Optional[int]:
        with self._lock:
            value = self._marks.get(name)
        return None if value is None else int(round((value - self.t0) * 1000))

    # --- fases -------------------------------------------------------------
    def _tick(self) -> float:
        current = self._clock()
        seg = max(0.0, current - self._cursor)
        self._cursor = current
        return seg

    @contextmanager
    def phase(self, phase: TurnPhase) -> Iterator[None]:
        name = TurnPhase(phase).value
        with self._lock:
            seg = self._tick()
            if self._stack:
                self._phase_s[self._stack[-1]] += seg
            else:
                self._unassigned += seg
            self._stack.append(name)
        try:
            yield
        finally:
            with self._lock:
                seg = self._tick()
                self._phase_s[name] += seg
                if self._stack:
                    self._stack.pop()

    def node_done(self, node: str) -> None:
        """Um update do grafo chegou: o intervalo desde o último tick é do nó."""
        target = NODE_PHASE.get(node, TurnPhase.OTHER).value
        with self._lock:
            seg = self._tick()
            self._phase_s[target] += seg + self._unassigned
            self._unassigned = 0.0
            self._flush_pending(target)
            if "first_phase" not in self._marks:
                self._marks["first_phase"] = self._cursor

    def settle(self, to: TurnPhase = TurnPhase.OTHER) -> None:
        """Atribui o que sobrou (entre o último nó e a persistência) a ``to``."""
        with self._lock:
            seg = self._tick()
            self._phase_s[to.value] += seg + self._unassigned
            self._unassigned = 0.0
            self._flush_pending(to.value)

    def finish(self) -> None:
        with self._lock:
            if self._end is not None:
                return
            if self._stack:
                self._stack.clear()
            self.settle(TurnPhase.OTHER)
            self._end = self._cursor

    def _flush_pending(self, phase: str) -> None:
        for count in self._pending_attempts.values():
            self._llm_by_phase[phase] = self._llm_by_phase.get(phase, 0) + count
        self._pending_attempts.clear()

    def note_attempt(self, tier: str = "") -> None:
        """Atribui uma tentativa LLM à fase corrente (R17)."""
        with self._lock:
            if self._stack:
                top = self._stack[-1]
                self._llm_by_phase[top] = self._llm_by_phase.get(top, 0) + 1
            else:
                self._pending_attempts[tier] = self._pending_attempts.get(tier, 0) + 1

    # --- leitura -----------------------------------------------------------
    def total_ms(self) -> int:
        with self._lock:
            end = self._end if self._end is not None else self._clock()
        return int(round((end - self.t0) * 1000))

    def phase_ms(self) -> Dict[str, int]:
        """Fases em ms inteiros; soma == total_ms() (resto vai à maior fase)."""
        with self._lock:
            values = {p: int(round(s * 1000)) for p, s in self._phase_s.items()}
            end = self._end
        if end is not None:
            drift = self.total_ms() - sum(values.values())
            if drift:
                biggest = max(values, key=lambda k: values[k])
                values[biggest] += drift
        return values

    def llm_by_phase(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._llm_by_phase)

    def fields(self) -> Dict[str, Any]:
        return {
            "transport": self.transport,
            "pseudo_streaming": PSEUDO_STREAMING,
            "ack_server_ms": self.mark_ms("accepted"),
            "ttfmc_server_ms": self.mark_ms("ttfmc"),
            "ttlt_server_ms": self.mark_ms("ttlt"),
            "state_server_ms": self.mark_ms("state"),
            "phase_ms": self.phase_ms(),
            "llm_by_phase": self.llm_by_phase(),
            **self.extra,
        }


# Fixo enquanto _stream_turn fatiar mensagem pronta (SPEC-200, definições).
PSEUDO_STREAMING = True

_current: contextvars.ContextVar[Optional[TurnTimeline]] = contextvars.ContextVar(
    "rpg_turn_timeline", default=None)


def current_timeline() -> Optional[TurnTimeline]:
    return _current.get()


@contextmanager
def phase(phase_: TurnPhase) -> Iterator[None]:
    """No-op quando não há timeline (CLI/playtest sem API)."""
    timeline = _current.get()
    if timeline is None:
        yield
        return
    with timeline.phase(phase_):
        yield


def bind(timeline: Optional[TurnTimeline]) -> contextvars.Token:
    return _current.set(timeline)


def unbind(token: contextvars.Token) -> None:
    try:
        _current.reset(token)
    except ValueError:
        pass


@contextmanager
def accumulate(key: str) -> Iterator[None]:
    """Soma o tempo do bloco em ``extra[key]`` (ms). No-op sem timeline."""
    timeline = _current.get()
    if timeline is None:
        yield
        return
    started = timeline._clock()
    try:
        yield
    finally:
        spent = int(round((timeline._clock() - started) * 1000))
        with timeline._lock:
            timeline.extra[key] = int(timeline.extra.get(key, 0)) + spent


def publish(record: Dict[str, Any]) -> None:
    """Entrega o registro final a sinks (baseline). Nunca levanta."""
    for sink in list(_sinks):
        try:
            sink(record)
        except Exception:
            pass


def summarize_phases(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """p50/p95 (nearest-rank) e participação de cada fase sobre os registros."""
    out: Dict[str, Dict[str, float]] = {}
    totals = [sum((r.get("phase_ms") or {}).values()) for r in records]
    grand = sum(totals) or 1
    for p in PHASES:
        vals = [int((r.get("phase_ms") or {}).get(p, 0)) for r in records]
        out[p] = {"p50": percentile(vals, 50), "p95": percentile(vals, 95),
                  "share": round(sum(vals) / grand, 4)}
    return out


def percentile(values: List[int], pct: float) -> int:
    """Nearest-rank (mesmo critério de playtest.telemetry._percentile)."""
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1))))
    return int(s[idx])
