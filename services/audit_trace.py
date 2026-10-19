"""SPEC-207: trilha de auditoria por turno (ring buffer `audit_trace` no save).

Escrito SÓ por `record_turn_trace`, na finalização canônica do turno (mesmo
ponto que `record_history`), dentro do commit. Guarda referências — ids,
visibilidade, seção — nunca texto de contexto, prompt ou resposta do LLM
(D-b). Campo ADITIVO: save antigo carrega com `[]` (sem bump de schema).

Zero LLM, zero rede. O coletor de `context_refs` é um ContextVar com lista
mutável (mesmo padrão de `_llm_turn_events` em api.py): nós do grafo
anexam e o finalizador lê.
"""
from __future__ import annotations

import contextvars
import os
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from collections.abc import Iterable, Iterator, Mapping

from services.memory_provenance import _CONFIDENCE_BY_PROVENANCE, accepted_secret_ids

DEFAULT_TRACE_LIMIT = 200

# Fases da SPEC-200 (observability.latency.PHASES) — persistência não fechou ainda.
_TIMING_KEYS = ("transport", "execution_mode", "ack_server_ms", "ttfmc_server_ms",
                "ttlt_server_ms", "phase_ms", "lock_wait_ms", "llm_attempts",
                "llm_fallbacks", "llm_failed_attempts", "providers_used",
                "cost_basis", "input_size")

# Enum FECHADO de erros (README_SCHEMA.md). Nunca mensagem de exceção crua.
ERROR_CODES = {
    "invoke_error": "llm_invoke_error",
    "invalid_structured": "structured_output_invalid",
    "stream_error": "llm_stream_error",
    "stream_interrupted": "llm_stream_error",  # SPEC-236: cut after the first chunk
    "circuit_open": "llm_circuit_open",
    "build_error": "llm_build_error",
}

_refs: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "rpg_audit_context_refs", default=None)


def trace_limit() -> int:
    try:
        return max(1, int(os.getenv("RPG_AUDIT_TRACE_MAX", str(DEFAULT_TRACE_LIMIT))))
    except ValueError:
        return DEFAULT_TRACE_LIMIT


@contextmanager
def collecting() -> Iterator[list[dict[str, Any]]]:
    """Abre o coletor de refs do turno (api._run_turn_collected)."""
    from services import mechanics_trace
    bucket: list[dict[str, Any]] = []
    token = _refs.set(bucket)
    try:
        with mechanics_trace.scope(recording=False):   # SPEC-251: so os passos do combat_node do turno
            yield bucket
    finally:
        _refs.reset(token)


def collected_refs() -> list[dict[str, Any]]:
    return list(_refs.get() or [])


# --------------------------------------------------------------------------- #
# Classificação de refs (taxonomia SPEC-206, sem texto)
# --------------------------------------------------------------------------- #
_MEMORY_LABEL = re.compile(
    r"^\[(CONFIRMADO|RELATO|ESPECULATIVO|NÃO VERIFICADO|RESUMO NARRATIVO)\s*\|\s*([a-z_]+)")
_KIND_BY_PROVENANCE = {
    "canonical_event": "fact",
    "player_observation": "perception",
    "npc_claim": "report",
    "inference": "suspicion",
    "legacy_unverified": "report",
}


def classify_fact(*, section: str, source_id: str, visibility: str, text: str) -> dict[str, Any]:
    """Ref de contexto: só id/seção/visibilidade + selo SPEC-206 derivado do
    rótulo estrutural já presente no texto (nunca do LLM). Não guarda o texto."""
    ref: dict[str, Any] = {"source_id": str(source_id or ""), "section": str(section or ""),
                           "visibility": str(visibility or "public"),
                           "knowledge_kind": None, "certainty": None, "source_kind": None}
    if section == "session_memory":
        match = _MEMORY_LABEL.match(text or "")
        if match:
            label, provenance = match.groups()
            if label == "RESUMO NARRATIVO":
                provenance = "inference"
            if provenance in _KIND_BY_PROVENANCE:
                kind = _KIND_BY_PROVENANCE[provenance]
                if provenance == "npc_claim":
                    from services.player_knowledge import _is_rumor_text
                    if _is_rumor_text(text):
                        kind = "rumor"
                certainty = _CONFIDENCE_BY_PROVENANCE[provenance]
                if label == "CONFIRMADO" and provenance == "canonical_event":
                    certainty = "confirmed"
                elif provenance == "canonical_event":
                    # rótulo diz que o ledger não confirmou: projetado como inferência
                    kind, provenance, certainty = "suspicion", "inference", "speculative"
                ref.update(knowledge_kind=kind, certainty=certainty, source_kind=provenance)
    elif section == "current_state" and ref["source_id"] and not ref["source_id"].startswith(
            ("ctrl:", "summ:")):
        ref.update(knowledge_kind="fact", certainty="confirmed", source_kind="canonical_event")
    return ref


def note_context(pack: Any, *, purpose: str, npc_id: str | None = None) -> None:
    """Anexa as refs de um ContextPack ao coletor do turno (no-op sem coletor)."""
    bucket = _refs.get()
    if bucket is None:
        return
    for ref in list(getattr(pack, "context_refs", None) or []):
        row = dict(ref)
        row["purpose"] = purpose
        if purpose == "planning":
            # contexto do planejador é conhecimento só do engine (nunca narrado)
            row["visibility"] = "engine"
        if npc_id:
            row["npc_id"] = str(npc_id)
        bucket.append(row)


# --------------------------------------------------------------------------- #
# Projeção de estado + delta
# --------------------------------------------------------------------------- #
def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def project_state(state: Mapping) -> dict[str, Any]:
    """Projeção mínima e FECHADA do estado (sem cópia inteira)."""
    state = state or {}
    player = state.get("player") or {}
    world = state.get("world") or {}
    combat = state.get("combat") or {}
    out: dict[str, Any] = {}
    for key in ("vitalidade", "max_vitalidade", "entropy", "max_entropy", "abyss_charge",
                "gold", "xp", "level"):
        out[f"player.{key}"] = _scalar(player.get(key))
    inventory: dict[str, int] = {}
    for item in player.get("inventory") or []:
        if isinstance(item, Mapping):
            item_id = str(item.get("id") or item.get("name") or "")
            if item_id:
                try:
                    qty = int(item.get("qty", item.get("quantity", 1)) or 0)
                except (TypeError, ValueError):
                    qty = 1
                inventory[item_id] = inventory.get(item_id, 0) + qty
        elif isinstance(item, str):
            inventory[item] = inventory.get(item, 0) + 1
    out["player.inventory"] = dict(sorted(inventory.items()))
    for key in ("known_cards", "prepared_cards"):
        out[f"player.{key}"] = sorted(str(c) for c in (player.get(key) or []))
    clock = world.get("world_clock") or {}
    out["world.location_id"] = _scalar(world.get("current_location_id"))
    out["world.day"] = _scalar(clock.get("day") if isinstance(clock, Mapping) else None)
    out["world.period"] = _scalar(clock.get("period") if isinstance(clock, Mapping) else None)
    out["world.weather"] = _scalar(world.get("weather_state") or world.get("weather"))
    out["world.danger_level"] = _scalar(world.get("danger_level"))
    out["combat.active"] = bool(combat.get("active")) if isinstance(combat, Mapping) else False
    out["combat.round"] = _scalar(combat.get("round")) if isinstance(combat, Mapping) else None
    enemies: dict[str, Any] = {}
    for index, enemy in enumerate(state.get("enemies") or []):
        if isinstance(enemy, Mapping):
            key = str(enemy.get("id") or enemy.get("name") or f"enemy_{index}")
            enemies[key] = _scalar(enemy.get("vitalidade", enemy.get("hp")))
    out["combat.enemies"] = dict(sorted(enemies.items()))
    npcs: dict[str, Any] = {}
    for name, npc in (state.get("npcs") or {}).items():
        if isinstance(npc, Mapping):
            npcs[str(name)] = {"in_scene": bool(npc.get("in_scene")),
                               "relationship": _scalar(npc.get("relationship"))}
    out["npcs"] = dict(sorted(npcs.items()))
    quests: dict[str, Any] = {}
    for quest in state.get("quests") or []:
        if isinstance(quest, Mapping) and quest.get("id"):
            quests[str(quest["id"])] = _scalar(quest.get("status"))
    out["quests"] = dict(sorted(quests.items()))
    return out


def diff_projection(before: Mapping, after: Mapping) -> dict[str, dict[str, Any]]:
    """Diff por caminho; mapas por id viram caminhos `npcs.<id>` etc."""
    delta: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if isinstance(old, dict) or isinstance(new, dict):
            old_map, new_map = old or {}, new or {}
            for sub in sorted(set(old_map) | set(new_map)):
                if old_map.get(sub) != new_map.get(sub):
                    delta[f"{key}.{sub}"] = {"before": old_map.get(sub), "after": new_map.get(sub)}
        elif old != new:
            delta[key] = {"before": old, "after": new}
    return delta


# --------------------------------------------------------------------------- #
# Erros, timing, revelações
# --------------------------------------------------------------------------- #
def _grown(before: Any, after: Any) -> int:
    old = list(before or []) if isinstance(before, (list, tuple)) else []
    new = list(after or []) if isinstance(after, (list, tuple)) else []
    if new[:len(old)] == old:
        return max(0, len(new) - len(old))
    return len(new)


def turn_errors(previous_state: Mapping, state: Mapping,
                llm_attempts: Iterable[Mapping] = ()) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    attempts = [a for a in (llm_attempts or []) if isinstance(a, Mapping)]
    for index, attempt in enumerate(attempts):
        outcome = str(attempt.get("outcome") or "")
        if outcome == "success":
            continue
        tier = str(attempt.get("tier") or "")
        later = [a for a in attempts[index + 1:] if str(a.get("tier") or "") == tier]
        errors.append({
            "code": ERROR_CODES.get(outcome, "llm_other_error"),
            "node": None,
            "tier": tier or None,
            "recovered": any(a.get("outcome") == "success" for a in later),
            "fallback": "provider_next" if later else "none",
            "error_class": None,
        })
    for key, code, node in (("event_rejections", "event_rejected", "event_processor"),
                            ("narrative_rejections", "narrative_rejected", "narrative_guard"),
                            ("memory_rejections", "memory_rejected", "archivist")):
        for _ in range(_grown((previous_state or {}).get(key), (state or {}).get(key))):
            errors.append({"code": code, "node": node, "tier": None, "recovered": True,
                           "fallback": "rejected", "error_class": None})
    return errors


def timing_snapshot(timeline: Any) -> dict[str, Any] | None:
    """Copia a TurnTimeline da SPEC-200 com os nomes dela. None sem timeline."""
    if timeline is None:
        return None
    try:
        fields = dict(timeline.fields())
    except Exception:  # silent-ok: trilha opcional; export marca `unavailable` (SPEC-207)
        return None
    phases = dict(fields.get("phase_ms") or {})
    phases["persistence"] = None          # ainda aberta dentro do commit
    snap = {
        "transport": fields.get("transport"),
        "execution_mode": fields.get("execution_mode"),
        "ack_server_ms": fields.get("ack_server_ms"),
        "ttfmc_server_ms": fields.get("ttfmc_server_ms"),
        "ttlt_server_ms": fields.get("ttlt_server_ms"),
        "phase_ms": phases,
        "lock_wait_ms": fields.get("lock_wait_ms"),
        "llm_attempts": fields.get("llm_attempts"),
        "llm_fallbacks": fields.get("llm_fallbacks"),
        "llm_failed_attempts": fields.get("llm_failed_attempts"),
        "providers_used": list(fields.get("providers_used") or []),
        "cost_basis": fields.get("cost_usd_basis"),
        "input_size": fields.get("input_size"),
    }
    return {key: snap[key] for key in _TIMING_KEYS}


def reveal_status(state: Mapping) -> dict[str, Any]:
    """Critério estrito (SPEC-206 R5) + sinal de divergência do corpus permissivo."""
    from services.secret_signatures import SECRET_SIGNATURES, revealed_corpus
    accepted = sorted(accepted_secret_ids(dict(state)))
    corpus = revealed_corpus(dict(state)).casefold()
    by_corpus = {sid for sid, sigs in SECRET_SIGNATURES.items()
                 if any(str(sig).casefold() in corpus for sig in sigs)}
    strict = {sid for sid in SECRET_SIGNATURES if sid.casefold() in
              {a.casefold() for a in accepted}}
    return {"revealed_secret_ids": accepted, "reveal_criteria_diverge": by_corpus != strict}


def _speaker(state: Mapping) -> str:
    from services.interlocutor import response_speaker
    try:
        speaker = response_speaker(state)
    except Exception:  # silent-ok: rotulo de auditoria; padrao seguro "narrator"
        return "narrator"
    if speaker.get("kind") == "npc" and speaker.get("id"):
        return f"npc:{speaker['id']}"
    if speaker.get("kind") == "system":
        return "system"
    return "narrator"


_REF_GROUP_KEYS = ("section", "visibility", "purpose", "npc_id",
                   "knowledge_kind", "certainty", "source_kind")


def _dedupe_refs(refs: Iterable[Mapping]) -> list[dict[str, Any]]:
    """Dedup + compactação: refs com os mesmos atributos viram UM grupo com a lista
    de `source_ids` (só chaves não nulas). Um turno real tem ~90 refs; por item com
    todas as chaves a linha passava de 19 KB e o ring de 200 inflava o save (~4 MB)."""
    seen: set = set()
    groups: dict[tuple, dict[str, Any]] = {}
    for ref in refs:
        key = (ref.get("source_id"), ref.get("purpose"), ref.get("npc_id"))
        if not ref.get("source_id") or key in seen:
            continue
        seen.add(key)
        attrs = tuple(ref.get(k) for k in _REF_GROUP_KEYS)
        group = groups.get(attrs)
        if group is None:
            group = {k: v for k, v in zip(_REF_GROUP_KEYS, attrs) if v is not None}
            group["source_ids"] = []
            groups[attrs] = group
        group["source_ids"].append(str(ref.get("source_id")))
    return list(groups.values())


def iter_context_refs(trace_row: Mapping) -> Iterator[dict[str, Any]]:
    """Expande `context_refs` (grupos compactos ou itens legados) em refs planas.
    Linha codificada como delta (`refs_add`/`refs_drop`) precisa de `expand_trace`."""
    for ref in (trace_row or {}).get("context_refs") or []:
        if not isinstance(ref, Mapping):
            continue
        base = {k: ref.get(k) for k in _REF_GROUP_KEYS}
        if isinstance(ref.get("source_ids"), list):
            for source_id in ref["source_ids"]:
                yield {"source_id": source_id, **base}
        elif ref.get("source_id"):
            yield {"source_id": ref.get("source_id"), **base}


def _flat(groups: Any) -> list[tuple]:
    return [(str(r["source_id"]),) + tuple(r.get(k) for k in _REF_GROUP_KEYS)
            for r in iter_context_refs({"context_refs": groups})]


def _group(flat: Iterable[tuple]) -> list[dict[str, Any]]:
    groups: dict[tuple, dict[str, Any]] = {}
    for item in flat:
        attrs = item[1:]
        group = groups.get(attrs)
        if group is None:
            group = {k: v for k, v in zip(_REF_GROUP_KEYS, attrs) if v is not None}
            group["source_ids"] = []
            groups[attrs] = group
        group["source_ids"].append(item[0])
    return list(groups.values())


_BASE_KEYS = ("section", "visibility", "knowledge_kind", "certainty", "source_kind")


def _base(group: Mapping) -> tuple:
    return tuple(group.get(k) for k in _BASE_KEYS)


def _prev_ids(prev_groups: list[dict[str, Any]], group: Mapping) -> list[str] | None:
    key = _base(group)
    for candidate in prev_groups:
        if _base(candidate) == key:
            return list(candidate.get("source_ids") or [])
    return None


def expand_trace(rows: Any) -> list[dict[str, Any]]:
    """Ring codificado → linhas com `context_refs` completo (grupos com `source_ids`).
    Lê também o formato item-a-item e o agrupado sem delta."""
    out: list[dict[str, Any]] = []
    prev: list[dict[str, Any]] = []
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        flat: list[tuple] = []
        for ref in row.get("context_refs") or []:
            if isinstance(ref, Mapping) and ref.get("ids_prev"):
                drop = set(ref.get("ids_drop") or [])
                ids = [i for i in (_prev_ids(prev, ref) or []) if i not in drop]
                ids += list(ref.get("ids_add") or [])
                attrs = tuple(ref.get(k) for k in _REF_GROUP_KEYS)
                flat.extend((str(i),) + attrs for i in ids)
            else:
                flat.extend(_flat([ref]))
        row["context_refs"] = _group(flat)
        if isinstance(row.get("timing"), dict):   # chaves nulas omitidas no ring
            row["timing"] = {k: row["timing"].get(k) for k in _TIMING_KEYS}
        prev = row["context_refs"]
        out.append(row)
    return out


def encode_trace(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Linhas completas → ring compacto. Cada grupo cujos `source_ids` derivam do
    grupo de mesma seção/visibilidade/selo da linha anterior guarda só o delta
    (`ids_prev` + `ids_add`/`ids_drop`): o contexto de um local quase não muda
    entre turnos (mesmo trocando narrador↔NPC). A 1ª linha do ring é sempre completa."""
    out: list[dict[str, Any]] = []
    prev: list[dict[str, Any]] | None = None
    for raw in rows:
        row = dict(raw)
        groups = _group(_flat(row.get("context_refs")))
        encoded: list[dict[str, Any]] = []
        for group in groups:
            ids = list(group["source_ids"])
            base_ids = _prev_ids(prev, group) if prev is not None else None
            if base_ids is not None:
                cur = set(ids)
                kept = [i for i in base_ids if i in cur]
                add = [i for i in ids if i not in set(base_ids)]
                if kept + add == ids:
                    small = {k: v for k, v in group.items() if k != "source_ids"}
                    small["ids_prev"] = True
                    drop = [i for i in base_ids if i not in cur]
                    if add:
                        small["ids_add"] = add
                    if drop:
                        small["ids_drop"] = drop
                    encoded.append(small)
                    continue
            encoded.append(group)
        row["context_refs"] = encoded
        if isinstance(row.get("timing"), dict):
            row["timing"] = {k: v for k, v in row["timing"].items() if v is not None}
        prev = groups
        out.append(row)
    return out


def record_turn_trace(state: dict, *, previous_state: Mapping | None = None,
                      action_id: str | None = None, timeline: Any = None,
                      llm_attempts: Iterable[Mapping] = (),
                      context_refs: Iterable[Mapping] | None = None) -> dict[str, Any]:
    """Grava UMA linha por action_id (replay idempotente) no ring buffer."""
    from observability.telemetry import pseudonym
    world = state.get("world") or {}
    turn = int(world.get("turn_count", 0) or 0)
    epoch = int((state.get("continuity") or {}).get("timeline_epoch", 0) or 0)
    action_ref = pseudonym(action_id) if action_id else None
    timing = timing_snapshot(timeline)
    refs = collected_refs() if context_refs is None else list(context_refs)
    entry: dict[str, Any] = {
        "turn": turn,
        "epoch": epoch,
        "action_ref": action_ref,
        "speaker": _speaker(state),
        "route": str(state.get("last_routed_intent") or state.get("next") or "") or None,
        "context_refs": _dedupe_refs(refs),
        "delta": (diff_projection(project_state(previous_state), project_state(state))
                  if previous_state is not None else None),
        "errors": turn_errors(previous_state or {}, state, llm_attempts),
        "timing": timing,
        "timing_partial": timing is not None,
        **reveal_status(state),
    }
    from services import mechanics_trace
    mechanics = mechanics_trace.snapshot()
    if mechanics:   # SPEC-251: aditivo, ausente em turno sem conflito
        entry["mechanics"] = mechanics
    trace = expand_trace(state.get("audit_trace") or [])
    if action_ref:
        trace = [row for row in trace if row.get("action_ref") != action_ref]
    else:
        trace = [row for row in trace
                 if row.get("action_ref") or (row.get("turn"), row.get("epoch")) != (turn, epoch)]
    trace.append(entry)
    state["audit_trace"] = encode_trace(trace[-trace_limit():])
    return entry


def normalize_audit_trace(value: Any) -> list[dict[str, Any]]:
    """Load/save: lista de dicts, cortada no limite (idempotente)."""
    if not isinstance(value, list):
        return []
    return encode_trace(expand_trace(value)[-trace_limit():])
