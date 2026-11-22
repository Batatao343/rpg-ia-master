"""SPEC-422: registro deterministico do arquivista (sem LLM) em dois tipos de turno.

- T0 `discarded`: a resposta do LLM seria descartada pelo proprio codigo (`suppress_free_facts`
  sem conflito); o registro e o mesmo de hoje, so sem pagar a chamada.
- T1 `rest`: descanso sem gancho estruturado; o resumo ganha uma frase de template.

Este modulo so CALCULA (marcas, decisao, `MemoryUpdate`). O unico writer de `narrative_summary`,
`memory_facts` e `chronicle` continua sendo `agents/archivist.py` (R2). Nada aqui chama LLM.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from services import latency_flags

if TYPE_CHECKING:  # pragma: no cover
    from agents.archivist import MemoryUpdate

RecordKind = Literal["rest", "discarded"]

# R9: lista fixa de gatilhos (so nomes; nunca texto do jogador ou da narracao).
TRIGGER_REASONS = (
    "conflict",
    "canonical_facts",
    "archive_due",
    "archive_due_low",
    "canonical_only",
    "pending_npc_memory",
    "vector_retry",
    "cadence",
)
_REST_PREFIXES = ("O herói descansou em ", "O herói tentou descansar em ")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def record_mode() -> str:
    return latency_flags.archive_record_mode()


# --- marcas do narrador (R3, R11) --------------------------------------------------------------


def _archive_low_mark(t: Any, same_region: Callable[[], bool]) -> dict:
    """SPEC-318 R5 (movido de storyteller.py sem mudar a condicao): viagem na mesma regiao,
    sem descanso/beat/evento/missao, e baixo valor."""
    if (
        latency_flags.archive_low_wanted()
        and t.dest
        and t.rested_player is None
        and not t.beat_done
        and not t.updates.get("pending_world_events")
        and "quests" not in t.updates
        and "memory_canonical_facts" not in t.updates
        and same_region()
    ):
        return {"archive_low": t.turn}
    return {}


def _rest_without_hook(t: Any, rumor_new: bool) -> bool:
    """R3: descanso que rodou, sem viagem, encontro, morte nem gancho estruturado."""
    introduced = (
        [] if t.quarantine_llm_payload else (getattr(t.update, "introduced_npcs", None) or [])
    )
    return bool(
        t.rest_note
        and not t.dest
        and t.rested_player is not None
        and not t.rested_player.get("dead")
        and not t.enc
        and not t._fauna_sign_shown
        and not t.beat_done
        and not introduced
        and "quests" not in t.updates
        and not t.pending_llm_events
        and not rumor_new
    )


def story_marks(t: Any, *, same_region: Callable[[], bool], rumor_new: bool = False) -> dict:
    """Marcas transitorias do narrador (`archive_low` e `archive_record`); `{}` com flags off."""
    marks = _archive_low_mark(t, same_region)
    if latency_flags.archive_record_marks_wanted() and _rest_without_hook(t, rumor_new):
        mark: dict = {"kind": "rest", "turn": t.turn}
        if getattr(t, "rest_blocked", None):
            mark["blocked"] = str(t.rest_blocked)
        marks["archive_record"] = mark
    return marks


# --- decisao no arquivista (R1, R5, R7) ---------------------------------------------------------


def _valid_rest_mark(state: dict, turn: int) -> dict | None:
    mark = state.get("archive_record")
    if not isinstance(mark, dict) or mark.get("kind") != "rest":
        return None
    try:
        return mark if int(mark.get("turn")) == int(turn) else None
    except (TypeError, ValueError):
        return None


def _cadence_due(state: dict, turn: int) -> bool:
    from agents.archivist import _ARCHIVE_EVERY

    return (int(turn) - int(state.get("archivist_last_run", 0) or 0)) >= _ARCHIVE_EVERY


def exclusion_reason(state: dict, turn: int, *, conflict_summary: Any) -> str | None:
    """Primeira condicao de T1 que excluiu o turno (`None` = nenhuma: T1 vale)."""
    if _valid_rest_mark(state, turn) is None:
        return "no_rest_mark"
    if conflict_summary:
        return "conflict"
    if _cadence_due(state, turn):
        return "cadence"
    return None


def classify(
    state: dict, turn: int, *, conflict_summary: Any, suppress_free_facts: bool
) -> tuple[RecordKind | None, str | None]:
    """`(tipo, motivo)` independente da flag: T0 antes de T1; sem tipo, o motivo da exclusao."""
    if suppress_free_facts and not conflict_summary:
        return "discarded", None
    reason = exclusion_reason(state, turn, conflict_summary=conflict_summary)
    return ("rest", None) if reason is None else (None, reason)


def decide(
    state: dict,
    turn: int,
    *,
    conflict_summary: Any,
    suppress_free_facts: bool,
    deferred: bool = False,
) -> RecordKind | None:
    """Tipo do registro deterministico a aplicar (so com `on`); `shadow` apenas loga.

    Com projecao adiada (SPEC-213, `deferred`) a flag nao tem efeito (R7)."""
    mode = record_mode()
    if mode == "off" or deferred:
        return None
    kind, reason = classify(
        state, turn, conflict_summary=conflict_summary, suppress_free_facts=suppress_free_facts
    )
    if mode == "shadow":
        from observability.telemetry import log_event

        log_event(
            "archivist",
            "record_shadow",
            level="info",
            kind=kind,
            would_skip=kind is not None,
            reason=reason or "",
        )
        return None
    return kind


def log_trigger(state: dict, turn: int) -> None:
    """R9: loga os motivos que mantiveram o gate, so com `shadow`/`on` (`off` = hoje)."""
    if record_mode() == "off":
        return
    from observability.telemetry import log_event

    log_event("archivist", "trigger", level="info", reasons=trigger_reasons(state, turn))


# --- registro (R4) -----------------------------------------------------------------------------


def _local_name(state: dict) -> str:
    from gamedata import get_location

    world = state.get("world") or {}
    loc = get_location(world.get("current_location_id", "")) or {}
    return str(loc.get("name") or world.get("current_location") or "um lugar desconhecido")


def rest_sentence(state: dict, mark: dict | None = None) -> str:
    """Uma frase `pt-BR`, sem numero na superficie (R4)."""
    from world_utils import clock_label

    world = state.get("world") or {}
    cal = (state.get("world_sim") or {}).get("calendar")
    clock = clock_label(world, cal if isinstance(cal, dict) else None)
    local = _local_name(state)
    weather = (mark or {}).get("blocked")
    if weather:
        return f"O herói tentou descansar em {local}, mas o clima ({weather}) não deixou; agora é {clock}."
    return f"O herói descansou em {local}; agora é {clock} e ele recuperou parte das forças."


def rest_summary(current_summary: str, state: dict, mark: dict | None = None) -> str:
    """Resumo anterior + frase de template; nao acumula (a frase anterior e trocada)."""
    from services.memory_summary import compact_summary

    pieces = _SENTENCE_SPLIT.split((current_summary or "").strip())
    if pieces and pieces[-1].startswith(_REST_PREFIXES):
        pieces = pieces[:-1]
    base = " ".join(p for p in pieces if p)
    return compact_summary(f"{base} {rest_sentence(state, mark)}".strip())


def memory_update(
    kind: RecordKind, *, current_summary: str, state: dict, mark: dict | None = None
) -> MemoryUpdate:
    """O `MemoryUpdate` montado em Python que entra no mesmo ramo de sucesso do arquivista."""
    from agents.archivist import MemoryUpdate

    summary = current_summary
    if kind == "rest":
        summary = rest_summary(current_summary, state, mark)
    return MemoryUpdate(new_summary=summary, important_facts=[], chronicle_entry="")


# --- linhas de rejeicao do resumo (R11, extraido de archivist.py) -------------------------------


def summary_rejection_rows(
    turn: int, location: list[dict], inventory: list[dict], npc: list[dict]
) -> list[dict]:
    base = {"turn": int(turn), "provenance": "narrative_summary"}
    return [
        *[{**base, "reason": "location_region_contradiction", **row} for row in location],
        *[{**base, "reason": "inventory_possession_contradiction", **row} for row in inventory],
        *[{**base, "reason": "npc_identity_contradiction", **row} for row in npc],
    ]


# --- gatilhos (R9) -----------------------------------------------------------------------------


def trigger_reasons(state: dict, turn: int) -> list[str]:
    """Quais gatilhos mantiveram o gate (so nomes da lista fixa)."""
    from agents.archivist import _VECTOR_RETRY_EVERY

    out: list[str] = []
    if state.get("conflict_summary"):
        out.append("conflict")
    if state.get("memory_canonical_facts"):
        out.append("canonical_facts")
    if state.get("archive_due"):
        out.append("archive_due_low" if state.get("archive_low") == turn else "archive_due")
    if state.get("memory_fact_policy") == "canonical_only":
        out.append("canonical_only")
    if state.get("pending_npc_memory"):
        out.append("pending_npc_memory")
    if state.get("pending_memory_facts") and int(turn) % _VECTOR_RETRY_EVERY == 0:
        out.append("vector_retry")
    if _cadence_due(state, turn):
        out.append("cadence")
    return out
