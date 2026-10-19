"""Taxonomia de conhecimento visível ao jogador (SPEC-206).

Projeção **somente leitura** sobre o que o save já registra: cada entrada do
Codex/Bestiário do jogador ganha um selo (`KnowledgeStamp`) que diz se aquilo é
fato, relato, rumor, suspeita ou percepção — derivado de origem estrutural do
motor, nunca de LLM. A mesma passada aplica a regra fail-closed de visibilidade
da ENTRADA (nome, corpo, contagem, notas): entidade `hidden`/`secret` (ou de
visibilidade desconhecida) sem `secret_revealed` aceito some inteira.

Vocabulário compartilhado (dono = esta spec; SPEC-207/211/215 reutilizam o
objeto `knowledge` inteiro): `knowledge_kind` ∈ KnowledgeKind, `certainty` =
`MemoryConfidence`, `source_kind` = `MemoryProvenance`,
`first_seen_turn`/`last_updated_turn`.

Zero LLM, zero RAG, zero rede. Não escreve no estado e não muda o save.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional, TypedDict, get_args
from collections.abc import Iterable, Mapping

from services.memory_provenance import (
    _CONFIDENCE_BY_PROVENANCE,
    MemoryConfidence,
    MemoryProvenance,
    _fold,
    accepted_secret_ids,
    find_strict_unrevealed,
    source_is_applicable,
)
from services.narrative_evidence import QUALIFIED_MARKER
from services.secret_signatures import PUBLIC_RUMOR, SECRET_SIGNATURES

_LOG = logging.getLogger("rpg.player_knowledge")

TAXONOMY_VERSION = 1

KnowledgeKind = Literal["fact", "report", "rumor", "suspicion", "perception"]
KNOWLEDGE_KINDS: frozenset = frozenset(get_args(KnowledgeKind))
KIND_LABEL_PT: dict[str, str] = {
    "fact": "Fato confirmado",
    "report": "Relato",
    "rumor": "Rumor",
    "suspicion": "Suspeita",
    "perception": "Percepção",
}
LEGACY_LABEL_PT = "Relato não verificado"

CATEGORIES = ("locations", "factions", "characters", "creatures", "secrets")

# D1 (default do dono): notas só report/perception/suspicion/fact — rumor fica fora.
_NOTE_KINDS = frozenset({"fact", "report", "perception", "suspicion"})
_MAX_NOTES_PER_ENTRY = 20

# Origem estrutural -> prefixo de `source_ref` (§3.3).
_REF_PREFIX = {
    "visited": "visited",
    "revealed_fact": "event",
    "bestiary": "bestiary",
    "npc": "npc",
    "faction": "faction",
    "memory": "memory",
}


class KnowledgeStamp(TypedDict):
    knowledge_kind: KnowledgeKind
    certainty: MemoryConfidence
    source_kind: MemoryProvenance
    source_ref: str
    label: str
    first_seen_turn: int | None
    last_updated_turn: int | None
    stale: bool


class KnowledgeNote(KnowledgeStamp):
    memory_id: str
    text: str


def _turn(value: Any) -> int | None:
    """Turno válido do save ou None — nunca inventado (R3)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _current_turn(state: Mapping) -> int:
    return _turn((state.get("world") or {}).get("turn_count")) or 0


def _is_rumor_text(text: str) -> bool:
    return bool(QUALIFIED_MARKER.search(_fold(text)))


def _stamp(
    kind: str,
    source_kind: str,
    ref: str,
    first: int | None,
    last: int | None,
    *,
    stale: bool = False,
    label: str | None = None,
) -> KnowledgeStamp:
    if kind not in KNOWLEDGE_KINDS:
        raise ValueError(f"knowledge_kind fora da taxonomia: {kind!r}")
    return KnowledgeStamp(
        knowledge_kind=kind,  # type: ignore[typeddict-item]
        certainty=_CONFIDENCE_BY_PROVENANCE[source_kind],
        source_kind=source_kind,  # type: ignore[typeddict-item]
        source_ref=ref,
        label=label or KIND_LABEL_PT[kind],
        first_seen_turn=first,
        last_updated_turn=last,
        stale=bool(stale),
    )


def derive_stamp(origin: str, record: Mapping, state: Mapping) -> KnowledgeStamp:
    """Tabela §3.2 — única fonte da derivação. Função pura.

    `origin` ∈ visited | revealed_fact | bestiary | npc | faction | memory.
    Levanta ValueError para origem/dado desconhecido (o chamador omite a entrada).
    """
    if origin not in _REF_PREFIX:
        raise ValueError(f"origem desconhecida: {origin!r}")
    record = record or {}
    prefix = _REF_PREFIX[origin]

    if origin == "visited":
        ref = f"{prefix}:{record['id']}"
        return _stamp("fact", "canonical_event", ref, None, None)

    if origin == "revealed_fact":
        ref = f"{prefix}:{record['event_id']}"
        turn = _turn(record.get("revealed_at_turn"))
        return _stamp("fact", "canonical_event", ref, turn, turn)

    if origin == "bestiary":
        ref = f"{prefix}:{record['id']}"
        first = _turn(record.get("first_seen_turn"))
        last = _turn(record.get("last_update_turn"))
        if int(record.get("fought", 0) or 0) >= 1:
            return _stamp("fact", "canonical_event", ref, first, last)
        return _stamp("rumor", "npc_claim", ref, first, last)

    if origin == "npc":
        ref = f"{prefix}:{record.get('entity_id') or record['name']}"
        first = _turn(record.get("created_turn"))
        last = _turn(record.get("last_seen_turn"))
        source = record.get("knowledge_source", "met") or "met"
        if source == "met":
            return _stamp("fact", "canonical_event", ref, first, last)
        if source == "mentioned":
            return _stamp("rumor", "npc_claim", ref, first, last)
        if source == "lore":
            return _stamp("report", "npc_claim", ref, first, last)
        raise ValueError(f"knowledge_source desconhecido: {source!r}")

    if origin == "faction":
        ref = f"{prefix}:{record['id']}"
        intel_turn = _turn(record.get("intel_turn"))
        stale = (
            bool(record.get("knows_goal"))
            and intel_turn is not None
            and intel_turn < _current_turn(state)
        )
        return _stamp("report", "npc_claim", ref, None, intel_turn, stale=stale)

    # memory — MemoryFact do ledger
    ref = f"{prefix}:{record['memory_id']}"
    turn = _turn(record.get("source_turn"))
    provenance = record.get("provenance") or "legacy_unverified"
    if provenance == "canonical_event":
        if source_is_applicable(record.get("source_id"), dict(state)):
            return _stamp("fact", "canonical_event", ref, turn, turn)
        # sem fonte aplicável: projetado como inferência (o ledger não muda)
        return _stamp("suspicion", "inference", ref, turn, turn)
    if provenance == "player_observation":
        return _stamp("perception", "player_observation", ref, turn, turn)
    if provenance == "npc_claim":
        kind = "rumor" if _is_rumor_text(str(record.get("text", ""))) else "report"
        return _stamp(kind, "npc_claim", ref, turn, turn)
    if provenance == "inference":
        return _stamp("suspicion", "inference", ref, turn, turn)
    if provenance == "legacy_unverified":
        return _stamp("report", "legacy_unverified", ref, turn, turn, label=LEGACY_LABEL_PT)
    raise ValueError(f"proveniência desconhecida: {provenance!r}")


# ---------------------------------------------------------------------------
# Visibilidade de entidade (fail-closed, paridade com rag.vis_rank)
# ---------------------------------------------------------------------------

_VIS_ORDER = {"public": 0, "hidden": 1, "secret": 2}


def _vis_rank(visibility: str | None) -> int:
    """Mesma regra de `rag.vis_rank` (sem importar o módulo RAG — R14):
    sem metadado = public; valor desconhecido = secret."""
    if visibility is None:
        return 0
    return _VIS_ORDER.get(visibility, 2)


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_FM_FIELD = re.compile(r"^(id|name|visibility):\s*(.*?)\s*$", re.MULTILINE)


def _frontmatter_fields(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        head = fh.read(4096)
    match = _FM_RE.match(head)
    if not match:
        return {}
    return {k: v.strip().strip("'\"") for k, v in _FM_FIELD.findall(match.group(1))}


@functools.lru_cache(maxsize=4)
def _codex_meta(codex_dir: str) -> dict[str, dict[str, str]]:
    """id -> {name, visibility} lendo só o frontmatter (cacheado por diretório)."""
    out: dict[str, dict[str, str]] = {}
    for root, _dirs, files in os.walk(codex_dir):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fields = _frontmatter_fields(os.path.join(root, fname))
            if fields.get("id"):
                out[fields["id"]] = fields
    return out


def _codex_dir() -> str:
    from services.codex_loader import CODEX_DIR

    return CODEX_DIR


def _entity_visibility(entity_id: str) -> str | None:
    """Visibilidade mais restritiva entre grafo e frontmatter do Codex.
    Indisponibilidade de qualquer fonte => 'secret' (fail-closed, §3.6)."""
    try:
        from services import graph_resolver as gr

        entity = gr.get_entity(entity_id)
        graph_vis = entity.get("visibility") if isinstance(entity, dict) else None
        codex_vis = (_codex_meta(_codex_dir()).get(entity_id) or {}).get("visibility")
    except Exception:
        return "secret"
    candidates = [v for v in (graph_vis, codex_vis) if v is not None]
    if not candidates:
        return None
    return max(candidates, key=_vis_rank)


def _accepted_folded(state: Mapping) -> set:
    return {item.casefold() for item in accepted_secret_ids(dict(state))}


def entity_is_player_visible(entity_id: str | None, state: Mapping) -> bool:
    """Entidade sem id canônico não tem metadado de visibilidade (chamador já
    filtrou por `known_by_player`). Não-public só com `secret_revealed` aceito
    (R4/R5) — `narrative_summary`/`known_secrets` nunca liberam."""
    if not entity_id:
        return True
    if _vis_rank(_entity_visibility(entity_id)) == 0:
        return True
    return entity_id.casefold() in _accepted_folded(state)


def _hidden_catalog(state: Mapping) -> dict[str, str]:
    """id -> nome das entidades não-public ainda não reveladas (grafo + Codex)."""
    from services import graph_resolver as gr

    accepted = _accepted_folded(state)
    out: dict[str, str] = {}
    sources: list[tuple] = []
    for eid, ent in (gr.load_entities() or {}).items():
        if isinstance(ent, dict):
            sources.append((eid, ent.get("visibility"), ent.get("name", "")))
    for eid, fields in _codex_meta(_codex_dir()).items():
        sources.append((eid, fields.get("visibility"), fields.get("name", "")))
    for eid, vis, name in sources:
        if _vis_rank(vis) == 0 or str(eid).casefold() in accepted:
            continue
        out[str(eid)] = str(name or "")
    return out


_WS = re.compile(r"\s+")
_FIELD_SEP = " ¦ "  # separador entre campos: impede casamento entre campos


def _norm(text: Any) -> str:
    """Normalização da varredura (revisão Astra): sem acento, casefold e
    espaços colapsados — `raizes`/quebra de linha não escapam do filtro."""
    return _WS.sub(" ", _fold(str(text or ""))).strip()


def _text_of(obj: Any) -> str:
    """Concatena as folhas string/num de um JSON (valores, não chaves)."""
    out: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif value is not None and not isinstance(value, bool):
            out.append(str(value))

    walk(obj)
    return _FIELD_SEP.join(out)


def _strict_unrevealed(text: str, state: Mapping) -> str | None:
    """`find_strict_unrevealed` + mesma checagem sobre texto normalizado."""
    hit = find_strict_unrevealed(text, dict(state))
    if hit:
        return hit
    low = _norm(text)
    if not low:
        return None
    revealed = _accepted_folded(state)
    for secret_id, signatures in SECRET_SIGNATURES.items():
        if secret_id.casefold() in revealed:
            continue
        if any(_norm(sig) in low for sig in signatures):
            return secret_id
    return None


def _mentions_hidden(text: str, hidden: Mapping[str, str]) -> str | None:
    low = _norm(text)
    if not low:
        return None
    for eid, name in hidden.items():
        if _norm(eid) in low:
            return eid
        folded_name = _norm(name)
        if len(folded_name) >= 6 and folded_name in low:
            return eid
    return None


# ---------------------------------------------------------------------------
# Projeção
# ---------------------------------------------------------------------------


def _anchor_and_origin(category: str, entry: Mapping, state: Mapping) -> tuple:
    """(entity_id p/ visibilidade, ids de âncora de nota, origin, record)."""
    if category == "locations":
        eid = entry["id"]
        return eid, {eid}, "visited", {"id": eid}
    if category == "factions":
        fid = entry["id"]
        intel = dict(((state.get("faction_intel") or {}).get(fid)) or {})
        return fid, {fid}, "faction", {"id": fid, **intel}
    if category == "creatures":
        cid = entry["id"]
        rec = dict(((state.get("bestiary_knowledge") or {}).get(cid)) or {})
        return cid, {cid}, "bestiary", {"id": cid, **rec}
    if category == "characters":
        key = entry.get("_npc_key") or entry.get("name", "")
        npc = dict(((state.get("npcs") or {}).get(key)) or {})
        eid = entry.get("_entity_id") or None
        record = {
            **npc,
            "name": entry.get("name") or key,
            "entity_id": eid,
            "knowledge_source": entry.get("knowledge_source") or npc.get("knowledge_source", "met"),
        }
        anchors = {a for a in (eid, key, entry.get("name")) if a}
        return eid, anchors, "npc", record
    if category == "secrets":
        eid = entry.get("entity_id") or None
        event_id = entry.get("_event_id") or ""
        if not event_id or not eid:
            # sem âncora de visibilidade/evento: fail-closed (omitido)
            raise ValueError("segredo sem event_id/entity_id")
        record = {"event_id": event_id, "revealed_at_turn": entry.get("turn")}
        return eid, {eid}, "revealed_fact", record
    raise ValueError(f"categoria desconhecida: {category!r}")


def _memory_rows(state: Mapping) -> list[dict]:
    from services.memory_provenance import normalize_memory_facts

    try:
        return normalize_memory_facts(state.get("memory_facts") or [])
    except Exception:
        return []


def _notes_for(
    anchors: Iterable[str],
    memory: list[dict],
    state: Mapping,
    hidden: Mapping[str, str],
    counter: dict[str, int],
) -> list[KnowledgeNote]:
    folded = {a.casefold() for a in anchors if a}
    if not folded:
        return []
    notes: list[KnowledgeNote] = []
    for row in memory:
        entity_ids = [str(e) for e in row.get("canonical_entity_ids") or []]
        if not any(e.casefold() in folded for e in entity_ids):
            continue  # R9: sem âncora visível, nota não aparece
        if any(not entity_is_player_visible(e, state) for e in entity_ids):
            continue  # cita entidade oculta não revelada
        try:
            stamp = derive_stamp("memory", row, state)
        except Exception:
            continue
        if stamp["knowledge_kind"] not in _NOTE_KINDS:
            continue
        text = str(row.get("text", ""))
        secret = _strict_unrevealed(text, state)
        if secret:
            counter["redactions"] += 1
            text = PUBLIC_RUMOR.get(secret, "os rumores locais")
        if _mentions_hidden(text, hidden):
            counter["redactions"] += 1
            continue
        notes.append(KnowledgeNote(**stamp, memory_id=row["memory_id"], text=text))
    notes.sort(key=lambda n: (n["last_updated_turn"] is None, n["last_updated_turn"] or 0))
    return notes[-_MAX_NOTES_PER_ENTRY:]


def project_player_knowledge(state: Mapping, raw: Mapping[str, list]) -> dict:
    """Anota e filtra os blocos crus do Codex. Fail-closed por entrada."""
    hidden = _hidden_catalog(state)
    memory = _memory_rows(state)
    counter = {"redactions": 0}
    out: dict[str, Any] = {}
    for category in CATEGORIES:
        projected: list[dict] = []
        for entry in raw.get(category) or []:
            try:
                if not isinstance(entry, Mapping):
                    raise ValueError("entrada não-dict")
                eid, anchors, origin, record = _anchor_and_origin(category, entry, state)
                if not entity_is_player_visible(eid, state):
                    continue  # R4 — some inteira, sem contagem
                public = {k: v for k, v in entry.items() if not str(k).startswith("_")}
                blob = _text_of(public)
                if _strict_unrevealed(blob, state) or _mentions_hidden(blob, hidden):
                    counter["redactions"] += 1  # R6 — entrada inteira omitida
                    continue
                public["knowledge"] = derive_stamp(origin, record, state)
                public["notes"] = _notes_for(anchors, memory, state, hidden, counter)
                projected.append(public)
            except Exception as exc:  # §3.6: dado malformado -> omite, nunca 500
                _LOG.warning(
                    "entrada omitida", extra={"category": category, "reason": type(exc).__name__}
                )
        out[category] = projected
    out["meta"] = {
        "taxonomy_version": TAXONOMY_VERSION,
        "counts": {c: len(out[c]) for c in CATEGORIES},
        "redactions": counter["redactions"],
    }
    return out


# ---------------------------------------------------------------------------
# Oráculo determinístico (R12)
# ---------------------------------------------------------------------------


def _iter_stamped(codex: Mapping):
    for category in CATEGORIES:
        for entry in codex.get(category) or []:
            if not isinstance(entry, Mapping):
                continue
            yield category, entry.get("knowledge")
            for note in entry.get("notes") or []:
                yield category, note


def _fact_has_source(stamp: Mapping, state: Mapping) -> bool:
    """R7: `fact` só com fonte estrutural do motor verificável no save."""
    if stamp.get("source_kind") != "canonical_event":
        return False
    prefix, _, ref = str(stamp.get("source_ref", "")).partition(":")
    if not ref:
        return False
    if prefix == "visited":
        return ref in ((state.get("world") or {}).get("visited") or [])
    if prefix == "event":
        facts = (state.get("world_projection") or {}).get("revealed_facts") or {}
        return ref in facts
    if prefix == "bestiary":
        rec = (state.get("bestiary_knowledge") or {}).get(ref) or {}
        return int(rec.get("fought", 0) or 0) >= 1
    if prefix == "npc":
        from services.entity_identity import resolve_npc_entity_id

        for key, npc in (state.get("npcs") or {}).items():
            if not isinstance(npc, dict):
                continue
            ids = {key, npc.get("name"), resolve_npc_entity_id(npc, str(npc.get("name", key)))}
            if ref in ids:
                return (npc.get("knowledge_source", "met") or "met") == "met"
        return False
    if prefix == "memory":
        for row in _memory_rows(state):
            if row.get("memory_id") == ref:
                return row.get("provenance") == "canonical_event" and source_is_applicable(
                    row.get("source_id"), dict(state)
                )
        return False
    return False


def assert_no_player_leak(codex: Mapping, state: Mapping) -> list[str]:
    """[] = ok. Cada string descreve um vazamento (sem texto do segredo)."""
    problems: list[str] = []
    blob = json.dumps(codex, ensure_ascii=False, default=str)
    # chaves + valores (normalizados) — acento/quebra de linha não escapam
    scan = blob + _FIELD_SEP + _text_of(codex)

    # (a) id/nome de entidade não revelada (cobre retrato/URL de arte por id)
    low = _norm(scan)
    for eid, name in _hidden_catalog(state).items():
        folded_name = _norm(name)
        if _norm(eid) in low or (len(folded_name) >= 6 and folded_name in low):
            problems.append(f"a:hidden_entity:{eid}")

    # (b) assinatura de segredo não revelado em qualquer ponto do JSON
    secret = _strict_unrevealed(scan, state)
    if secret:
        problems.append(f"b:secret_signature:{secret}")

    # (c) contagem de categoria x lista filtrada
    counts = (
        ((codex.get("meta") or {}).get("counts"))
        if isinstance(codex.get("meta"), Mapping)
        else None
    )
    if not isinstance(counts, Mapping):
        problems.append("c:meta_counts_missing")
    else:
        for category in CATEGORIES:
            if counts.get(category) != len(codex.get(category) or []):
                problems.append(f"c:count_mismatch:{category}")

    # (d) taxonomia fechada + fact só com fonte de R7
    for category, stamp in _iter_stamped(codex):
        if not isinstance(stamp, Mapping):
            problems.append(f"d:missing_stamp:{category}")
            continue
        kind = stamp.get("knowledge_kind")
        if kind not in KNOWLEDGE_KINDS:
            problems.append(f"d:kind_outside_taxonomy:{category}")
        elif kind == "fact" and not _fact_has_source(stamp, state):
            problems.append(f"d:fact_without_source:{category}:{stamp.get('source_ref', '')}")
    return problems
