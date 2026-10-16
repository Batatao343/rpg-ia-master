"""Server-side kill switches (SPEC-196 R4).

A switch is ``enabled`` unless a row (or the emergency env override) explicitly
turns it off. Failure to read the store keeps the last good snapshot, or "all
enabled" when none exists (fail-safe default) — except the keys listed in
``RPG_KILL_SWITCH_FAIL_CLOSED`` and, when ``RPG_DAILY_SPEND_CAP_BRL`` is set,
``image_generation``/``stt_fallback_expensive`` (SPEC-236 R10: fail closed).
Reading/continuing existing campaigns is never gated by any switch here.

Keys: ``image_generation``, ``stt_fallback_expensive``, ``model:<provider>/<model>``,
``decision_backend:jev``, ``new_purchases`` and ``new_purchases:<channel>``
(``stripe`` / ``google_play``).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Callable, Mapping, Protocol

from observability.metrics import metrics

KEY_RE = re.compile(
    r"^(image_generation|stt_fallback_expensive|model:[A-Za-z0-9._/-]{1,200}"
    r"|decision_backend:[a-z0-9_]{1,40}|new_purchases(:[a-z_]{1,40})?)$")
log = logging.getLogger("rpg.kill_switches")
IMAGE = "image_generation"
STT_FALLBACK = "stt_fallback_expensive"
JEV = "decision_backend:jev"
NEW_PURCHASES = "new_purchases"


def model_key(provider: str, model: str) -> str:
    return f"model:{provider}/{model}"


def purchases_key(channel: str) -> str:
    return f"{NEW_PURCHASES}:{channel}"


class SwitchOff(RuntimeError):
    """A paid or risky effect was refused because an operator switched it off."""

    def __init__(self, key: str) -> None:
        super().__init__("kill_switch_off")
        self.key = key
        self.code = "kill_switch_off"


class SwitchStore(Protocol):
    def load(self) -> dict[str, bool]: ...
    def set(self, key: str, enabled: bool, *, actor_id: str, reason: str) -> None: ...
    def audit(self, limit: int = 50) -> list[dict]: ...


def validate_change(key: str, actor_id: str, reason: str) -> None:
    if not KEY_RE.fullmatch(key or ""):
        raise ValueError("invalid_switch_key")
    if not actor_id or not str(actor_id).strip():
        raise ValueError("actor_required")
    if not reason or not reason.strip() or len(reason) > 500:
        raise ValueError("reason_required")


class MemorySwitchStore:
    """Reference store for tests/CLI dry-runs; mirrors the append-only audit."""

    def __init__(self, initial: Mapping[str, bool] | None = None) -> None:
        self.state: dict[str, bool] = dict(initial or {})
        self.audit_rows: list[dict] = []

    def load(self) -> dict[str, bool]:
        return dict(self.state)

    def set(self, key: str, enabled: bool, *, actor_id: str, reason: str) -> None:
        validate_change(key, actor_id, reason)
        self.audit_rows.append({
            "key": key, "previous_enabled": self.state.get(key, True),
            "enabled": bool(enabled), "actor_id": actor_id, "reason": reason,
            "at": time.time()})
        self.state[key] = bool(enabled)

    def audit(self, limit: int = 50) -> list[dict]:
        return list(reversed(self.audit_rows))[:limit]


def _daily_cap_configured() -> bool:
    """Same rule as ``daily_spend_cap.cap_from_env`` (kept local: that module imports this one)."""
    from decimal import Decimal, InvalidOperation
    raw = os.getenv("RPG_DAILY_SPEND_CAP_BRL", "").strip()
    try:
        return bool(raw) and Decimal(raw) > 0
    except InvalidOperation:
        return False


def _fail_closed_keys() -> set[str]:
    """RPG_KILL_SWITCH_FAIL_CLOSED=new_purchases,image_generation: keys that become OFF when the
    store is unreadable AND no good snapshot was ever loaded (default: none, i.e. fail open)."""
    raw = os.getenv("RPG_KILL_SWITCH_FAIL_CLOSED", "")
    keys = {k.strip() for k in raw.split(",") if KEY_RE.fullmatch(k.strip())}
    # SPEC-236 R10: with the daily spend cap configured, the switches the cap protects fail
    # CLOSED on a cold start with an unreadable store (otherwise a DB incident would reopen
    # image/STT-fallback spend that the cap had cut). Opt out: RPG_KILL_SWITCH_CAP_FAIL_OPEN=1.
    if _daily_cap_configured() and os.getenv("RPG_KILL_SWITCH_CAP_FAIL_OPEN", "") != "1":
        keys |= {IMAGE, STT_FALLBACK}
    return keys


def _env_off() -> set[str]:
    """Emergency override without DB: RPG_KILL_SWITCHES_OFF=key1,key2."""
    raw = os.getenv("RPG_KILL_SWITCHES_OFF", "")
    return {k.strip() for k in raw.split(",") if KEY_RE.fullmatch(k.strip())}


class KillSwitches:
    def __init__(self, store: SwitchStore | None = None, *, ttl: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._store = store
        self._ttl = ttl if ttl is not None else float(os.getenv("RPG_KILL_SWITCH_TTL_SECONDS", "5"))
        self._clock = clock
        self._cache: dict[str, bool] = {}
        self._loaded_at: float | None = None
        self._ever_loaded = False
        self._load_failed = False
        self._lock = threading.Lock()

    def _resolve_store(self) -> SwitchStore | None:
        if self._store is not None:
            return self._store
        if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() == "legacy":
            return None
        from infrastructure.kill_switch_store import PostgresSwitchStore
        from infrastructure.runtime import get_runtime
        pool = getattr(get_runtime().game_store, "pool", None)
        return PostgresSwitchStore(pool) if pool is not None else None

    def snapshot(self) -> dict[str, bool]:
        with self._lock:
            now = self._clock()
            if self._loaded_at is None or now - self._loaded_at >= self._ttl:
                try:
                    store = self._resolve_store()
                    if store is not None:
                        self._cache = store.load()
                        self._ever_loaded = True
                    self._load_failed = False
                except Exception as exc:  # fail-safe: keep last good snapshot, never disable
                    self._load_failed = True
                    log.warning("kill_switch_load_failed error=%s", type(exc).__name__)
                    metrics.increment("rpg_kill_switch_load_errors_total",
                                      {"error": type(exc).__name__})
                self._loaded_at = now  # back off on failure too
            state = dict(self._cache)
            unreadable = self._load_failed and not self._ever_loaded
        if unreadable:  # opt-in fail-closed: no cached value to fall back on
            for key in _fail_closed_keys():
                state[key] = False
        for key in _env_off():
            state[key] = False
        return state

    def is_enabled(self, key: str) -> bool:
        return self.snapshot().get(key, True)

    def require(self, key: str) -> None:
        if not self.is_enabled(key):
            raise SwitchOff(key)

    def invalidate(self) -> None:
        with self._lock:
            self._loaded_at = None


_SWITCHES = KillSwitches()


def get_switches() -> KillSwitches:
    return _SWITCHES


def set_switches(switches: KillSwitches | None) -> None:
    """Test/operator seam; ``None`` restores the default lazy store."""
    global _SWITCHES
    _SWITCHES = switches or KillSwitches()


def model_disabled(provider: str, model: str) -> bool:
    return not _SWITCHES.is_enabled(model_key(provider, model))


def require_purchases(channel: str) -> None:
    """``channel`` is the report channel: ``stripe`` or ``google_play``."""
    s = _SWITCHES.snapshot()
    for key in (NEW_PURCHASES, purchases_key(channel)):
        if not s.get(key, True):
            raise SwitchOff(key)
