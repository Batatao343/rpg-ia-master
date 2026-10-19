"""SPEC-251: trace mecânico do conflito (rolagens, dano, reações, morte, fuga).

Contextvar por turno preenchido pelos serviços de conflito. NUNCA consome RNG nem
altera estado: só lê valores já calculados. Sem escopo aberto, `record_step` é no-op.
Privacidade (SPEC-222): refs são ids de catálogo (regex fechada) ou "player"; nenhum
nome, texto livre ou mensagem de exceção entra num passo.
"""
from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

KINDS = frozenset({"initiative", "attack", "save", "damage", "reaction", "condition",
                   "death_stage", "flee", "target_redirect"})
MAX_STEPS = 64
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.:\-]{0,63}$")
_DEATH_RANK = {"last_stand": 1, "terminal": 2, "stabilization_failed": 3,
               "revived": 3, "dead": 4}

_bucket: contextvars.ContextVar[Optional["_Bucket"]] = contextvars.ContextVar(
    "rpg_mechanics_trace", default=None)


class _Bucket:
    def __init__(self, recording: bool = True) -> None:
        self.recording = recording   # revisao P2/P3: so grava dentro do escopo do combate
        self.steps: List[Dict[str, Any]] = []
        self.truncated = 0
        self.agg: Dict[str, Any] = {
            "rounds": 0, "player_damage_taken": 0, "enemy_damage_dealt": 0,
            "reactions": 0, "death_stage_reached": None, "target_redirects": 0}


@contextmanager
def scope(*, recording: bool = True) -> Iterator["_Bucket"]:
    """Abre o coletor; aninhado, reaproveita o do escopo externo.

    ``recording=False`` (coletor do turno em ``audit_trace.collecting``) so guarda o balde: passos
    de nos fora do combate (teste geral do storyteller, dano de viagem/clima) NAO entram. O
    escopo interno do ``combat_node`` liga a gravacao enquanto dura (e restaura ao sair)."""
    current = _bucket.get()
    if current is not None:
        previous = current.recording
        current.recording = previous or recording
        try:
            yield current
        finally:
            current.recording = previous
        return
    bucket = _Bucket(recording)
    token = _bucket.set(bucket)
    try:
        yield bucket
    finally:
        _bucket.reset(token)


def active() -> bool:
    return _bucket.get() is not None


def token(value: Any) -> Optional[str]:
    """Token fechado (id de catálogo / código); qualquer outra coisa vira None."""
    if isinstance(value, str) and _TOKEN.match(value):
        return value
    return None


def ref_of(actor: Any) -> Optional[str]:
    if isinstance(actor, dict):
        if actor.get("is_player") or actor.get("player"):
            return "player"
        return token(actor.get("id"))
    return token(actor)


def _ints(values: Any) -> Optional[List[int]]:
    if values is None:
        return None
    try:
        return [int(v) for v in values]
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def record_step(kind: str, *, actor: Any = None, target: Any = None, dice: Any = None,
                kept: Any = None, modifier: Any = None, dc_or_defense: Any = None,
                result: Any = None, amount: Any = None, card_id: Any = None,
                reason: Any = None) -> None:
    bucket = _bucket.get()
    if bucket is None or not bucket.recording or kind not in KINDS:
        return
    try:
        step: Dict[str, Any] = {"kind": kind, "actor_ref": ref_of(actor),
                                "target_ref": ref_of(target), "dice": _ints(dice),
                                "kept": _ints(kept), "modifier": _num(modifier),
                                "dc_or_defense": _num(dc_or_defense),
                                "result": token(result), "amount": _num(amount),
                                "card_id": token(card_id), "reason": token(reason)}
        agg = bucket.agg
        if kind == "initiative":
            agg["rounds"] += 1
        elif kind == "damage":
            dealt = max(0, step["amount"] or 0)
            key = "player_damage_taken" if step["target_ref"] == "player" else "enemy_damage_dealt"
            agg[key] += dealt
        elif kind == "reaction":
            agg["reactions"] += 1
        elif kind == "target_redirect":
            agg["target_redirects"] += 1
        elif kind == "death_stage":
            stage = step["result"]
            if _DEATH_RANK.get(stage, 0) >= _DEATH_RANK.get(agg["death_stage_reached"], 0):
                agg["death_stage_reached"] = stage
        if len(bucket.steps) >= MAX_STEPS:
            bucket.truncated += 1
            return
        bucket.steps.append({k: v for k, v in step.items() if v is not None})
    except Exception:  # silent-ok: o trace jamais pode quebrar a mecânica do turno
        return


def snapshot() -> Optional[Dict[str, Any]]:
    """Passos do turno (cópia) ou None se vazio/sem escopo."""
    bucket = _bucket.get()
    if bucket is None or not (bucket.steps or bucket.truncated):
        return None
    return {"steps": [dict(s) for s in bucket.steps], "truncated": bucket.truncated}


def summary() -> Optional[Dict[str, Any]]:
    bucket = _bucket.get()
    if bucket is None or not (bucket.steps or bucket.truncated):
        return None
    return dict(bucket.agg)


def emit_turn_logs() -> None:
    """combat.mechanics (debug) + combat.summary (info) no fim do turno de combate."""
    snap, agg = snapshot(), summary()
    if snap is None or agg is None:
        return
    from observability.telemetry import log_event
    log_event("combat", "mechanics", level="debug", steps=snap["steps"],
              step_count=len(snap["steps"]), truncated=snap["truncated"])
    log_event("combat", "summary", level="info", **agg)
