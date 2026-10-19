"""SPEC-207: pacote de auditoria de sessão (ZIP determinístico, sob demanda).

Builder PURO: recebe um `AuditSource` já lido (Postgres owner-scoped ou save
local de fixture) e devolve bytes. Zero LLM, zero rede, nada retido. Toda
linha passa pela allowlist de `services.audit_redaction` antes de serializar e
o ZIP inteiro é varrido por PII no fim (falha fechada).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from services.audit_redaction import (
    PRIVATE_LABEL,
    AuditRedactionError,
    redact_record,
    scan_pii,
)
from services.audit_trace import project_state

FORMAT = "valoria-audit-export-v1"
EXPORT_SCHEMA_VERSION = 1
DEFAULT_MAX_TURNS = 500
DEFAULT_MAX_BYTES = 25 * 1024 * 1024

KNOWLEDGE_KINDS = frozenset({"fact", "report", "rumor", "suspicion", "perception"})
CERTAINTIES = frozenset({"confirmed", "reported", "speculative"})
SOURCE_KINDS = frozenset({"canonical_event", "player_observation", "npc_claim",
                          "inference", "legacy_unverified"})

FIXED_FILES = ("manifest.json", "state/initial_snapshot.json", "state/final_snapshot.json",
               "state/deltas.jsonl", "knowledge_visibility.jsonl", "errors.jsonl",
               "timings.jsonl", "AUDITOR_PROMPT.md", "README_SCHEMA.md")
_DOC_DIR = Path(__file__).resolve().parent.parent / "data" / "auditoria"
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class AuditLimits:
    max_turns: int = DEFAULT_MAX_TURNS
    max_bytes: int = DEFAULT_MAX_BYTES

    @classmethod
    def from_env(cls) -> "AuditLimits":
        def _int(name: str, default: int) -> int:
            try:
                return max(1, int(os.getenv(name, str(default))))
            except ValueError:
                return default
        return cls(_int("RPG_AUDIT_EXPORT_MAX_TURNS", DEFAULT_MAX_TURNS),
                   _int("RPG_AUDIT_EXPORT_MAX_BYTES", DEFAULT_MAX_BYTES))


@dataclass
class AuditSource:
    """Dados já lidos e filtrados pelo dono. `None` = fonte indisponível."""
    game_id: str
    state: Dict[str, Any]
    state_version: Optional[int] = None
    turns: Optional[List[Dict[str, Any]]] = None          # app.turns (+ op id)
    turns_reason: Optional[str] = None
    usage_cost: Optional[Dict[str, str]] = None           # operation_id -> USD
    usage_reason: Optional[str] = None
    events_by_turn: Optional[Dict[int, List[str]]] = None  # app.game_events
    events_reason: Optional[str] = None
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    owner_values: set = field(default_factory=set)


@dataclass
class AuditBundle:
    files: Dict[str, bytes]
    manifest: Dict[str, Any]


# --------------------------------------------------------------------------- #
# Allowlists por arquivo (chave fora daqui NUNCA sai)
# --------------------------------------------------------------------------- #
S = "scalar"
SESSION_SPEC = {k: S for k in ("turn_ref", "epoch", "sequence", "action_ref", "player_text",
                               "route", "speaker", "narration", "delta_ref", "timing_ref",
                               "cost_usd", "trace_available", "context_refs_unavailable")}
MECHANICS_STEP_SPEC = {k: ("list", S) if k in ("dice", "kept") else S for k in (
    "kind", "actor_ref", "target_ref", "dice", "kept", "modifier", "dc_or_defense", "result",
    "amount", "card_id", "reason")}
SESSION_SPEC.update(event_ids=("list", S), error_refs=("list", S),
                    mechanics={"steps": ("list", MECHANICS_STEP_SPEC), "truncated": S})
DELTA_SPEC = {"delta_ref": S, "turn_ref": S,
              "delta": ("map", {"before": "projected", "after": "projected"})}
KNOWLEDGE_ITEM_SPEC = {k: S for k in ("source_id", "section", "visibility", "purpose", "npc_id",
                                      "knowledge_kind", "certainty", "source_kind",
                                      "private_label")}
KNOWLEDGE_SPEC = {"turn_ref": S, "speaker": S, "items": ("list", KNOWLEDGE_ITEM_SPEC),
                  "player_revealed_secret_ids": ("list", S), "reveal_criteria_diverge": S,
                  "context_refs_unavailable": S}
ERROR_SPEC = {k: S for k in ("turn_ref", "action_ref", "node", "tier", "code", "recovered",
                             "fallback", "error_class", "error_ref", "unavailable", "reason")}
TIMING_SPEC = {"turn_ref": S, "action_ref": S, "latency_ms": S, "timing_partial": S,
               "client_timing": S, "unavailable": S, "reason": S,
               "timing": {"transport": S, "execution_mode": S, "ack_server_ms": S,
                          "ttfmc_server_ms": S, "ttlt_server_ms": S,
                          "phase_ms": ("map", S), "lock_wait_ms": S, "llm_attempts": S,
                          "llm_fallbacks": S, "llm_failed_attempts": S,
                          "providers_used": ("list", S), "cost_basis": S, "input_size": S}}
PRIVATE_SPEC = {"label": S, "arc_title": S, "climax": S, "current_step": S,
                "beats": ("list", {"description": S, "status": S}),
                "unrevealed_secret_ids": ("list", S)}
SNAPSHOT_SPEC = {"kind": S, "turn": S, "epoch": S, "state_version": S, "derivation": S,
                 "projection": "projected", "private_reference": PRIVATE_SPEC}
MANIFEST_SPEC = {k: S for k in ("format", "game_ref", "build_sha", "save_schema_version",
                                "export_schema_version", "generated_at", "truncated",
                                "truncation_reason", "state_version", "private_label",
                                "turn_count", "taxonomy_version", "trace_limit",
                                "client_timing")}
MANIFEST_SPEC.update(range={"first_turn_ref": S, "last_turn_ref": S, "epochs": ("list", S)},
                     unavailable=("map", S), files=("map", S), session_files=("list", S))


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _jsonl(rows: Iterable[Any]) -> bytes:
    return "".join(_dumps(r) + "\n" for r in rows).encode("utf-8")


def _turn_ref(epoch: int, turn: int) -> str:
    return f"t:{epoch}:{turn}"


def _scrub_player(text: Any) -> Optional[str]:
    return None if text is None else str(text)


# --------------------------------------------------------------------------- #
# Montagem
# --------------------------------------------------------------------------- #
def _turn_units(source: AuditSource) -> List[Dict[str, Any]]:
    """Uma unidade por linha do narrador em presentation_history."""
    from observability.telemetry import pseudonym
    state = source.state
    history = [row for row in state.get("presentation_history") or [] if isinstance(row, dict)]
    players = {(int(r.get("epoch", 0) or 0), int(r.get("turn", 0) or 0)): r.get("text")
               for r in history if r.get("role") == "player"}
    traces: Dict[Tuple[int, int], Dict[str, Any]] = {}
    from services.audit_trace import expand_trace
    for row in expand_trace(state.get("audit_trace") or []):
        if isinstance(row, dict):
            traces[(int(row.get("epoch", 0) or 0), int(row.get("turn", 0) or 0))] = row
    turn_rows = {str(r.get("presentation_entry_id")): r for r in source.turns or []
                 if r.get("presentation_entry_id")}
    units: List[Dict[str, Any]] = []
    for index, row in enumerate(r for r in history if r.get("role") == "narrator"):
        key = (int(row.get("epoch", 0) or 0), int(row.get("turn", 0) or 0))
        db = turn_rows.get(str(row.get("id")))
        trace = traces.get(key)
        op = str(db["operation_id"]) if db and db.get("operation_id") else None
        units.append({
            "index": index, "epoch": key[0], "turn": key[1], "row": row, "db": db,
            "trace": trace, "player_text": players.get(key),
            "operation_id": op,
            "action_ref": (pseudonym(op) if op else (trace or {}).get("action_ref")),
        })
    if units and all(u["db"] and u["db"].get("sequence") is not None for u in units):
        units.sort(key=lambda u: int(u["db"]["sequence"]))
    return units


def _speaker(unit: Dict[str, Any]) -> str:
    trace = unit["trace"]
    if trace and trace.get("speaker"):
        return str(trace["speaker"])
    row = unit["row"]
    kind = row.get("speaker_kind")
    if kind == "npc" and row.get("speaker_id"):
        return f"npc:{row['speaker_id']}"
    return "system" if kind == "system" else "narrator"


def _knowledge_items(trace: Mapping) -> List[Dict[str, Any]]:
    items = []
    from services.audit_trace import iter_context_refs
    for ref in iter_context_refs(trace):
        visibility = str(ref.get("visibility") or "public")
        item = {"source_id": ref.get("source_id"), "section": ref.get("section"),
                "visibility": visibility, "purpose": ref.get("purpose"),
                "npc_id": ref.get("npc_id")}
        if visibility == "public":
            kind, certainty, source_kind = (ref.get("knowledge_kind"), ref.get("certainty"),
                                            ref.get("source_kind"))
            valid = (kind in KNOWLEDGE_KINDS and certainty in CERTAINTIES
                     and source_kind in SOURCE_KINDS)
            item.update(knowledge_kind=kind if valid else None,
                        certainty=certainty if valid else None,
                        source_kind=source_kind if valid else None)
        else:
            # SPEC-206 R4: o jogador não vê — nunca inventar rótulo de certeza.
            item.update(knowledge_kind=None, certainty=None, source_kind=None,
                        private_label=PRIVATE_LABEL)
        items.append(item)
    return items


def _private_reference(state: Mapping) -> Dict[str, Any]:
    from services.memory_provenance import accepted_secret_ids
    from services.secret_signatures import SECRET_SIGNATURES
    plan = state.get("campaign_plan") or {}
    accepted = {s.casefold() for s in accepted_secret_ids(dict(state))}
    return {
        "label": PRIVATE_LABEL,
        "arc_title": plan.get("arc_title"),
        "climax": plan.get("climax"),
        "current_step": plan.get("current_step"),
        "beats": [{"description": b.get("description"), "status": b.get("status")}
                  for b in plan.get("beats") or [] if isinstance(b, Mapping)],
        "unrevealed_secret_ids": sorted(s for s in SECRET_SIGNATURES
                                        if s.casefold() not in accepted),
    }


def _initial_projection(final: Dict[str, Any], deltas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reaplica os deltas ao contrário a partir da projeção final."""
    proj = json.loads(_dumps(final))
    map_keys = sorted((k for k, v in proj.items() if isinstance(v, dict)), key=len, reverse=True)
    for delta in reversed(deltas):
        for path, change in delta.items():
            before = (change or {}).get("before")
            if path in proj and not isinstance(proj[path], dict):
                proj[path] = before
                continue
            parent = next((k for k in map_keys if path.startswith(k + ".")), None)
            if parent is None:
                proj[path] = before
                continue
            sub = path[len(parent) + 1:]
            if before is None:
                proj[parent].pop(sub, None)
            else:
                proj[parent][sub] = before
    return proj


def _sensitive_values(source: AuditSource) -> set:
    """Valores reais que nunca podem sair: dono (id/subject/e-mail) + game_id cru."""
    return {str(v) for v in source.owner_values if v} | {str(source.game_id)}


def _files_for(source: AuditSource, units: List[Dict[str, Any]], *,
               truncated: bool, truncation_reason: Optional[str], build_sha: str,
               generated_at: str) -> Dict[str, bytes]:
    from observability.telemetry import pseudonym
    from persistence import SCHEMA_VERSION
    from services.audit_trace import trace_limit
    from services.player_knowledge import TAXONOMY_VERSION

    owner = _sensitive_values(source)
    sessions: Dict[int, List[Dict[str, Any]]] = {}
    deltas, knowledge, errors, timings, delta_maps = [], [], [], [], []
    for unit in units:
        ref = _turn_ref(unit["epoch"], unit["turn"])
        trace, db = unit["trace"], unit["db"]
        error_refs: List[str] = []
        if trace:
            for i, err in enumerate(trace.get("errors") or []):
                eref = f"e:{unit['epoch']}:{unit['turn']}:{i}"
                error_refs.append(eref)
                errors.append({"error_ref": eref, "turn_ref": ref, "action_ref": unit["action_ref"],
                               **{k: err.get(k) for k in ("node", "tier", "code", "recovered",
                                                          "fallback", "error_class")}})
        delta = (trace or {}).get("delta")
        delta_ref = f"d:{unit['epoch']}:{unit['turn']}" if isinstance(delta, dict) else None
        if delta_ref:
            deltas.append({"delta_ref": delta_ref, "turn_ref": ref, "delta": delta})
            delta_maps.append(delta)
        if source.events_by_turn is not None:
            event_ids = list(source.events_by_turn.get(unit["turn"], []))
        else:
            event_ids = [str(e.get("event_id")) for e in source.state.get("event_log") or []
                         if isinstance(e, dict) and e.get("event_id")
                         and int(e.get("turn", -1) or 0) == unit["turn"]]
        cost = None
        if unit["operation_id"] and source.usage_cost is not None:
            cost = source.usage_cost.get(unit["operation_id"])
        elif db and db.get("llm_cost_usd") is not None:
            cost = str(db["llm_cost_usd"])
        sessions.setdefault(unit["epoch"], []).append({
            "turn_ref": ref, "epoch": unit["epoch"],
            "sequence": int(db["sequence"]) if db and db.get("sequence") is not None else None,
            "action_ref": unit["action_ref"],
            "player_text": _scrub_player(unit["player_text"]),
            "route": (db or {}).get("route") or (trace or {}).get("route")
                     or unit["row"].get("type"),
            "speaker": _speaker(unit),
            "narration": unit["row"].get("text"),
            "event_ids": sorted(event_ids),
            "delta_ref": delta_ref,
            "timing_ref": f"tm:{unit['epoch']}:{unit['turn']}",
            "cost_usd": None if cost is None else str(cost),
            "error_refs": error_refs,
            "trace_available": trace is not None,
            "context_refs_unavailable": trace is None,
            **({"mechanics": trace["mechanics"]} if trace and trace.get("mechanics") else {}),
        })
        if trace:
            knowledge.append({"turn_ref": ref, "speaker": _speaker(unit),
                              "items": _knowledge_items(trace),
                              "player_revealed_secret_ids": list(
                                  trace.get("revealed_secret_ids") or []),
                              "reveal_criteria_diverge": bool(
                                  trace.get("reveal_criteria_diverge"))})
        else:
            knowledge.append({"turn_ref": ref, "speaker": _speaker(unit), "items": None,
                              "context_refs_unavailable": True})
        timing = (trace or {}).get("timing")
        timings.append({"turn_ref": ref, "action_ref": unit["action_ref"],
                        "latency_ms": (db or {}).get("latency_ms"),
                        "timing_partial": bool((trace or {}).get("timing_partial")),
                        "timing": timing, "client_timing": "not_exported"})

    for op in source.failed_operations:
        errors.append({"error_ref": f"e:op:{pseudonym(op.get('operation_id'))}",
                       "turn_ref": None, "action_ref": pseudonym(op.get("operation_id")),
                       "node": None, "tier": None, "code": "turn_failed", "recovered": False,
                       "fallback": "none", "error_class": op.get("error_class")})
    unavailable: Dict[str, str] = {}
    for name, value, reason in (("turns", source.turns, source.turns_reason),
                                ("usage_events", source.usage_cost, source.usage_reason),
                                ("game_events", source.events_by_turn, source.events_reason)):
        if value is None and reason:
            unavailable[name] = reason
    if "turns" in unavailable:
        errors.insert(0, {"unavailable": True, "reason": unavailable["turns"]})
        timings.insert(0, {"unavailable": True, "reason": unavailable["turns"]})

    state = source.state
    final_proj = project_state(state)
    world = state.get("world") or {}
    epoch_now = int((state.get("continuity") or {}).get("timeline_epoch", 0) or 0)
    final = {"kind": "final", "turn": int(world.get("turn_count", 0) or 0), "epoch": epoch_now,
             "state_version": source.state_version, "derivation": "save_projection",
             "projection": final_proj, "private_reference": _private_reference(state)}
    initial = {"kind": "initial",
               "turn": units[0]["turn"] if units else final["turn"],
               "epoch": units[0]["epoch"] if units else epoch_now,
               "state_version": None,
               "derivation": "final_projection_with_turn_deltas_reversed",
               "projection": _initial_projection(final_proj, delta_maps)}

    def red(rows, spec):
        return [redact_record(r, spec=spec, owner_values=owner) for r in rows]

    files: Dict[str, bytes] = {}
    session_names = []
    for epoch in sorted(sessions):
        name = f"sessions/{epoch}.jsonl"
        session_names.append(name)
        files[name] = _jsonl(red(sessions[epoch], SESSION_SPEC))
    files["state/initial_snapshot.json"] = (_dumps(redact_record(
        initial, spec=SNAPSHOT_SPEC, owner_values=owner)) + "\n").encode("utf-8")
    files["state/final_snapshot.json"] = (_dumps(redact_record(
        final, spec=SNAPSHOT_SPEC, owner_values=owner)) + "\n").encode("utf-8")
    files["state/deltas.jsonl"] = _jsonl(red(deltas, DELTA_SPEC))
    files["knowledge_visibility.jsonl"] = _jsonl(red(knowledge, KNOWLEDGE_SPEC))
    files["errors.jsonl"] = _jsonl(red(errors, ERROR_SPEC))
    files["timings.jsonl"] = _jsonl(red(timings, TIMING_SPEC))
    files["AUDITOR_PROMPT.md"] = (_DOC_DIR / "AUDITOR_PROMPT.md").read_bytes()
    files["README_SCHEMA.md"] = (_DOC_DIR / "README_SCHEMA.md").read_bytes()

    epochs = sorted(sessions)
    manifest = {
        "format": FORMAT,
        "game_ref": pseudonym(source.game_id),
        "build_sha": build_sha,
        "save_schema_version": SCHEMA_VERSION,
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "range": {"first_turn_ref": _turn_ref(units[0]["epoch"], units[0]["turn"]) if units else None,
                  "last_turn_ref": _turn_ref(units[-1]["epoch"], units[-1]["turn"]) if units else None,
                  "epochs": epochs},
        "turn_count": len(units),
        "truncated": truncated,
        "truncation_reason": truncation_reason,
        "state_version": source.state_version,
        "private_label": PRIVATE_LABEL,
        "taxonomy_version": TAXONOMY_VERSION,
        "trace_limit": trace_limit(),
        "client_timing": "not_exported",
        "unavailable": unavailable,
        "session_files": session_names,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (_dumps(redact_record(
        manifest, spec=MANIFEST_SPEC, owner_values=owner)) + "\n").encode("utf-8")
    return files


def _scan_files(files: Mapping[str, bytes], owner_values: Iterable[str]) -> List[str]:
    problems = []
    for name, data in sorted(files.items()):
        if name.endswith(".md"):
            continue  # documentação estática do repo (sem dado de jogador)
        for kind in scan_pii(data.decode("utf-8", errors="replace"), owner_values=owner_values):
            problems.append(f"pii:{kind}:{name}")
    return problems


def write_zip(files: Mapping[str, bytes]) -> bytes:
    """Ordem e metadados fixos → mesmos bytes para o mesmo input."""
    order = ["manifest.json"] + sorted(n for n in files if n.startswith("sessions/")) + [
        n for n in FIXED_FILES[1:] if n in files]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in order:
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            archive.writestr(info, files[name])
    return buffer.getvalue()


def build_audit_bundle(source: AuditSource, *, limits: AuditLimits = AuditLimits(),
                       build_sha: str = "unknown",
                       generated_at: Optional[str] = None) -> AuditBundle:
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    units = _turn_units(source)
    truncated, reason = False, None
    if len(units) > limits.max_turns:
        units = units[-limits.max_turns:]
        truncated, reason = True, "max_turns"
    while True:
        files = _files_for(source, units, truncated=truncated, truncation_reason=reason,
                           build_sha=build_sha, generated_at=generated_at)
        if len(write_zip(files)) <= limits.max_bytes or not units:
            break
        drop = max(1, len(units) // 10)
        units = units[drop:]
        truncated, reason = True, "max_bytes"
    if len(write_zip(files)) > limits.max_bytes:
        raise AuditRedactionError("audit_export_too_large")
    problems = _scan_files(files, _sensitive_values(source))
    if problems:
        raise AuditRedactionError(";".join(problems))
    manifest = json.loads(files["manifest.json"])
    return AuditBundle(files=files, manifest=manifest)


def verify_audit_zip(data: bytes, *, owner_values: Iterable[str] = ()) -> List[str]:
    """[] = íntegro: arquivos obrigatórios, hashes do manifest e scan de PII."""
    problems: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
    except zipfile.BadZipFile:
        return ["zip:invalid"]
    for name in FIXED_FILES:
        if name not in files:
            problems.append(f"missing:{name}")
    if not any(n.startswith("sessions/") and n.endswith(".jsonl") for n in files):
        problems.append("missing:sessions/<epoch>.jsonl")
    try:
        manifest = json.loads(files.get("manifest.json", b"{}"))
    except ValueError:
        return problems + ["manifest:invalid_json"]
    if manifest.get("format") != FORMAT:
        problems.append("manifest:format")
    hashes = manifest.get("files") or {}
    for name, data_bytes in files.items():
        if name == "manifest.json":
            continue
        if hashes.get(name) != hashlib.sha256(data_bytes).hexdigest():
            problems.append(f"hash:{name}")
    for name in hashes:
        if name not in files:
            problems.append(f"missing:{name}")
    problems.extend(_scan_files(files, owner_values))
    return problems


def bundle_zip(source: AuditSource, *, limits: Optional[AuditLimits] = None,
               build_sha: str = "unknown", generated_at: Optional[str] = None) -> bytes:
    bundle = build_audit_bundle(source, limits=limits or AuditLimits.from_env(),
                                build_sha=build_sha, generated_at=generated_at)
    data = write_zip(bundle.files)
    problems = verify_audit_zip(data, owner_values=_sensitive_values(source))
    if problems:
        raise AuditRedactionError(";".join(problems))
    return data
