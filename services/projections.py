"""SPEC-213 — canônico síncrono × projeções derivadas do arquivista.

O canônico (eventos, projeção do mundo, guard da prosa ao jogador, outcome)
é sempre aplicado e salvo no turno. Os DERIVADOS do arquivista (resumo
narrativo, fatos de memória extraídos pelo LLM, prosa da crônica) podem rodar
depois da resposta ao jogador quando ``RPG_PROJECTION_MODE=post_response`` E o
chamador abriu um ``deferral_scope`` (API/playtest, que drenam a projeção sob o
mesmo lock do turno — R9: nunca fire-and-forget).

Invariantes:
* ``canonical_version`` é monotônico (nunca volta, nem em restore; R4);
* ``projected_version <= canonical_version`` (R6);
* projeção de outra ``timeline_epoch`` nunca é aplicada (R7b);
* reaplicar o mesmo ``action_id`` não duplica nada (R8).

Nenhuma chamada LLM nova: o executor reaproveita ``agents.archivist``.
"""

from __future__ import annotations

import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Dict, List, Literal, Optional, TypedDict
from collections.abc import Callable, Iterator

from observability.telemetry import log_event as _log_event

MODE_ENV = "RPG_PROJECTION_MODE"
WAIT_ENV = "RPG_PROJECTION_WAIT_SECONDS"
DEFAULT_WAIT_SECONDS = 20.0
MAX_ATTEMPTS = 3
PROJECTIONS = ("summary", "memory", "chronicle")
STATUSES = ("pending", "completed", "failed", "stale")
ERROR_CODES = ("exception", "timeout", "epoch_mismatch", "superseded", "invariant")


class ProjectionEntry(TypedDict):
    status: Literal["pending", "completed", "failed", "stale"]
    projected_version: int
    action_id: str | None
    attempts: int
    last_error_code: str | None


class ProjectionState(TypedDict):
    canonical_version: int
    timeline_epoch: int
    summary: ProjectionEntry
    memory: ProjectionEntry
    chronicle: ProjectionEntry


_DEFER: ContextVar[bool] = ContextVar("rpg_projection_defer", default=False)


def projection_mode() -> str:
    """``inline`` (default, comportamento atual) ou ``post_response`` (modo A).

    ``job`` (modo B) não cria um kind novo: embeddings e compressão da crônica já
    são jobs (P2 default); para o resumo SMART o valor cai em ``inline``."""
    value = str(os.getenv(MODE_ENV, "inline") or "inline").strip().lower()
    return "post_response" if value == "post_response" else "inline"


def wait_seconds() -> float:
    try:
        value = float(os.getenv(WAIT_ENV, DEFAULT_WAIT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_WAIT_SECONDS
    return value if value > 0 else DEFAULT_WAIT_SECONDS


@contextmanager
def deferral_scope(enabled: bool | None = None) -> Iterator[bool]:
    """Abre a janela em que o arquivista pode adiar derivados. Só quem DRENA a
    projeção sob o lock do turno (API, playtest) deve abrir esta janela."""
    active = projection_mode() == "post_response" if enabled is None else bool(enabled)
    token = _DEFER.set(active)
    try:
        yield active
    finally:
        _DEFER.reset(token)


def deferral_active() -> bool:
    return bool(_DEFER.get())


# --- estado -------------------------------------------------------------------


def _int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _continuity(state: dict) -> tuple[int, int]:
    from services.continuity import normalize

    world_turn = _int((state.get("world") or {}).get("turn_count", 0))
    meta = normalize(state.get("continuity"), canonical_turn=world_turn)
    return int(meta["session_action_count"]), int(meta["timeline_epoch"])


def _entry(raw: Any, canonical: int) -> ProjectionEntry:
    raw = raw if isinstance(raw, dict) else {}
    status = raw.get("status") if raw.get("status") in STATUSES else "completed"
    projected = _int(raw.get("projected_version"), canonical) if raw else canonical
    code = raw.get("last_error_code")
    return {
        "status": status,
        # R6: derivado nunca à frente do canônico.
        "projected_version": min(projected, canonical),
        "action_id": str(raw["action_id"])[:64] if raw.get("action_id") else None,
        "attempts": _int(raw.get("attempts")),
        "last_error_code": code if code in ERROR_CODES else None,
    }


def normalize_projection_state(raw: Any, state: dict) -> ProjectionState:
    """Idempotente. Save sem ``projection_state`` (v8 e anteriores) nasce
    ``completed`` em ``canonical_version = continuity.session_action_count`` (R16).
    Restore de checkpoint não faz o contador voltar: a continuidade é monotônica."""
    session, epoch = _continuity(state)
    raw = raw if isinstance(raw, dict) else {}
    canonical = max(_int(raw.get("canonical_version")), session)
    out: dict[str, Any] = {"canonical_version": canonical, "timeline_epoch": epoch}
    for name in PROJECTIONS:
        out[name] = _entry(raw.get(name), canonical)
    return out  # type: ignore[return-value]


def normalize_plan(raw: Any) -> dict | None:
    """``pending_derived``: só a linha de base mínima (ids, nunca texto)."""
    if not isinstance(raw, dict):
        return None
    try:
        return {
            "new_event_ids": [str(x)[:80] for x in (raw.get("new_event_ids") or [])][:256],
            "new_rejections": bool(raw.get("new_rejections")),
            "turn": _int(raw.get("turn")),
            "epoch": _int(raw.get("epoch")),
            "canonical_version": (
                _int(raw["canonical_version"]) if raw.get("canonical_version") is not None else None
            ),
            "action_id": str(raw["action_id"])[:64] if raw.get("action_id") else None,
        }
    except Exception:
        return None


def make_plan(*, new_event_ids: list[str], new_rejections: bool, turn: int, epoch: int) -> dict:
    return normalize_plan(
        {
            "new_event_ids": list(new_event_ids),
            "new_rejections": new_rejections,
            "turn": turn,
            "epoch": epoch,
            "canonical_version": None,
            "action_id": None,
        }
    )  # type: ignore[return-value]


def stamp_commit(state: dict, action_id: str | None) -> dict:
    """Chamado no commit do turno (dono: API/playtest). Incrementa a versão
    canônica e marca as projeções adiadas como ``pending``. Muta e devolve."""
    raw = state.get("projection_state")
    previous = _int(raw.get("canonical_version")) if isinstance(raw, dict) else 0
    ps = normalize_projection_state(raw, state)
    session, epoch = _continuity(state)
    # +1 por turno commitado, alinhado à contagem monotônica da sessão (SPEC-102).
    canonical = max(previous + 1, session)
    ps["canonical_version"] = canonical
    ps["timeline_epoch"] = epoch
    plan = normalize_plan(state.get("pending_derived"))
    if plan is not None and plan["canonical_version"] is None:
        plan["canonical_version"] = canonical
        plan["epoch"] = epoch
        plan["action_id"] = (action_id or f"turn:{canonical}")[:64]
        for name in PROJECTIONS:
            ps[name].update(
                status="pending",
                action_id=plan["action_id"],
                attempts=0,
                last_error_code=None,
                projected_version=min(ps[name]["projected_version"], canonical - 1),
            )
        state["pending_derived"] = plan
    else:
        if plan is None:
            state["pending_derived"] = None
        for name in PROJECTIONS:
            # Sem derivado adiado neste turno: o derivado está em dia pela cadência.
            if ps[name]["status"] == "completed":
                ps[name]["projected_version"] = canonical
    state["projection_state"] = ps
    return state


def reconcile(state: dict) -> dict:
    """R7b: projeção pendente de outra época é cancelada (nunca aplicada)."""
    ps = normalize_projection_state(state.get("projection_state"), state)
    plan = normalize_plan(state.get("pending_derived"))
    if (
        plan is not None
        and plan["canonical_version"] is not None
        and plan["epoch"] != ps["timeline_epoch"]
    ):
        for name in PROJECTIONS:
            ps[name].update(status="failed", last_error_code="epoch_mismatch")
        plan = None
    state["projection_state"] = ps
    state["pending_derived"] = plan
    return state


def carry_over_restore(live: dict, restored: dict) -> dict:
    """R4/R7b no restore de checkpoint: ``canonical_version`` herda o máximo da
    linha do tempo viva (nunca decresce, mesmo que algum turno não tenha
    avançado ``session_action_count``) e a projeção da época antiga é cancelada."""
    live_ps = live.get("projection_state")
    live_version = _int(live_ps.get("canonical_version")) if isinstance(live_ps, dict) else 0
    ps = normalize_projection_state(restored.get("projection_state"), restored)
    ps["canonical_version"] = max(ps["canonical_version"], live_version)
    restored["projection_state"] = ps
    return reconcile(restored)


# --- modo B / perfis com banco (outbox em app.jobs) -----------------------------

JOB_KIND = "project_archive"


def dedupe_key(game_id: Any, epoch: int, action_id: str) -> str:
    """R8: ``{game_id}:{timeline_epoch}:{projection}:{action_id}`` (as três
    projeções do arquivista saem de uma única execução: ``archive``)."""
    return f"{game_id}:{int(epoch)}:archive:{action_id}"


def job_payload(document: dict) -> dict | None:
    """Payload do job ``project_archive`` para o documento commitado (ou None)."""
    plan = normalize_plan(document.get("pending_derived"))
    if plan is None or plan["canonical_version"] is None or not plan["action_id"]:
        return None
    return {
        "game_id": str(document.get("game_id")),
        "action_id": plan["action_id"],
        "epoch": plan["epoch"],
        "canonical_version": plan["canonical_version"],
    }


def has_pending(state: dict) -> bool:
    return normalize_plan(state.get("pending_derived")) is not None


def projection_status_view(state: dict) -> dict:
    """R13: só status/versões, nunca conteúdo."""
    ps = normalize_projection_state(state.get("projection_state"), state)
    return {
        "canonical_version": ps["canonical_version"],
        **{
            name: {"status": ps[name]["status"], "projected_version": ps[name]["projected_version"]}
            for name in PROJECTIONS
        },
    }


# --- R7: guard de reintrodução de NPC morto nos canais derivados --------------

_DEATH_WORDS = re.compile(
    r"\b(?:morr\w*|mort\w*|falec\w*|tomb\w*|caiu|cad[aá]ver\w*|corpo|sepult\w*|"
    r"luto|lembran\w*|mem[oó]ria|t[uú]mulo|enterr\w*|assassin\w*|matou|abatid\w*)\b",
    re.IGNORECASE,
)


def strip_dead_npc_presence(text: str, state: dict) -> tuple[str, list[dict]]:
    """Remove frases do derivado que citam NPC canonicamente morto SEM falar da
    morte (presença/fala de morto = reintrodução). Conservador: qualquer
    vocabulário de morte/memória ou marcador de relato preserva a frase."""
    from services.memory_provenance import _fold
    from services.narrative_evidence import QUALIFIED_MARKER
    from services.npc_layers import npc_alive

    projection = state.get("world_projection") or {}
    names = []
    for key, npc in (state.get("npcs") or {}).items():
        if isinstance(npc, dict) and not npc_alive(npc, projection=projection):
            name = str(npc.get("name") or key).strip()
            if len(name) >= 3:
                names.append(_fold(name))
    if not text or not names:
        return text, []
    pieces = re.split(r"((?<=[.!?])\s+|\n+)", str(text))
    kept: list[str] = []
    rejected: list[dict] = []
    turn = str(_int((state.get("world") or {}).get("turn_count", 0)))
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        sep = pieces[index - 1] if index else ""
        if not sentence.strip():
            continue
        folded = _fold(sentence)
        named = any(re.search(rf"\b{re.escape(n)}\b", folded) for n in names)
        if named and not _DEATH_WORDS.search(folded) and not QUALIFIED_MARKER.search(folded):
            rejected.append({"channel": "derived", "reason": "dead_npc_presence", "turn": turn})
            continue
        kept.append((sep if kept else "") + sentence)
    if not rejected:
        return text, []
    return "".join(kept).strip(), rejected


# --- execução ------------------------------------------------------------------


def run_pending(
    state: dict,
    *,
    executor: Callable[[dict, dict], dict] | None = None,
    clock: Callable[[], float] = time.monotonic,
    timeout: float | None = None,
) -> dict:
    """Executa a projeção pendente sobre o estado CANÔNICO atual (modo A).

    Deve ser chamado pelo dono do lock do turno. Nunca levanta: falha vira
    ``failed`` (retentado no próximo turno até ``MAX_ATTEMPTS``) e o derivado
    anterior permanece (R12). Devolve um NOVO dict de estado."""
    state = reconcile(dict(state))
    plan = state.get("pending_derived")
    if plan is None:
        return state
    ps = deepcopy(state["projection_state"])
    version = plan["canonical_version"]
    if version is None:
        version = ps["canonical_version"]
    applied = max(ps[name]["projected_version"] for name in PROJECTIONS)
    already = all(
        ps[name]["action_id"] == plan["action_id"] and ps[name]["status"] == "completed"
        for name in PROJECTIONS
    )
    if already or (
        version < applied and any(ps[name]["status"] == "completed" for name in PROJECTIONS)
    ):
        # R5/R8: versão mais velha que a aplicada ou mesma ação já aplicada.
        state["pending_derived"] = None
        return state
    if executor is None:
        from agents.archivist import run_derived_projection as executor  # noqa: N813
    limit = wait_seconds() if timeout is None else float(timeout)
    started = clock()
    error: str | None = None
    result: dict = {}
    try:
        result = dict(executor(state, plan) or {})
    except Exception as exc:
        _log_event("projection", "derived_failed", level="warning", error=type(exc).__name__)
        error = "exception"
    if error is None and (clock() - started) > limit:
        error = "timeout"
    if error is None and version > ps["canonical_version"]:
        error = "invariant"  # R6: jamais à frente do canônico
    if error is not None:
        attempts = max(ps[name]["attempts"] for name in PROJECTIONS) + 1
        for name in PROJECTIONS:
            ps[name].update(status="failed", attempts=attempts, last_error_code=error)
        state["projection_state"] = ps
        # Revisão Astra: no timeout o executor JÁ terminou (não é interrompível) e
        # pode ter gravado memória no FAISS (legacy); reexecutar duplicaria fatos
        # (R8). Desiste do derivado deste turno; a cadência seguinte o recompõe.
        if attempts >= MAX_ATTEMPTS or error == "timeout":
            state["pending_derived"] = None
        return state
    result.pop("messages", None)
    result.pop("projection_state", None)
    result.pop("pending_derived", None)
    new_state = {**state, **result}
    status = "stale" if ps["canonical_version"] > version else "completed"
    for name in PROJECTIONS:
        ps[name].update(
            status=status,
            projected_version=version,
            action_id=plan["action_id"],
            last_error_code=None,
        )
    if status == "stale":
        # R5: existe turno mais novo; a próxima passada do arquivista reagenda.
        new_state["archive_due"] = True
    new_state["projection_state"] = ps
    new_state["pending_derived"] = None
    return new_state
