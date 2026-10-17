"""SPEC-215 — conhecimento por NPC e propagação limitada de notícias.

Owner ÚNICO do ledger privado de conhecimento. O ledger NÃO cria verdade: a
verdade do mundo continua sendo o `GameEvent` (event_log) + `WorldProjection`.
Aqui só existem RELAÇÕES sobre um assunto (`event_id` canônico ou `memory_id`
de `MemoryFact`):

- ``observed_by`` — o NPC estava presente (testemunha, hops=0);
- ``told_to``     — alguém contou (mensageiro, rumor local, jogador);
- ``believed_by`` — o NPC acredita no que viu/ouviu.

Ausência de relação = ``unknown``. Propagação é determinística (seed
``sha256(game_id|subject|from|to|hop)``), atrasada pela geografia
(`world_distance.travel_periods`) + atraso de mensageiro, com no máximo
``MAX_HOPS`` saltos e tetos de links/fila. Rumor/mentira nunca vira fato:
nenhuma função daqui escreve em event_log, projection ou `MemoryFact`.

Rollout: ``RPG_NPC_KNOWLEDGE=off|shadow|on`` (default ``off`` = comportamento
atual byte a byte). Puro: sem LLM, sem I/O; todas as funções devolvem listas/
dicts novos e nunca mutam o estado recebido.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("rpg.npc_knowledge")

MODES = ("off", "shadow", "on")
MAX_HOPS = 2
MAX_KNOWLEDGE_LINKS = 2000
MAX_QUEUE = 200
MAX_HEARD_PER_LOCATION = 100
MAX_HEARD_LOCATIONS = 100
MAX_DESTINATIONS = 4                  # destinos por hop (§3.3)
NPC_KNOWLEDGE_CONTEXT_MAX = 8         # R11
BELIEF_MIN_RELATIONSHIP = 6           # R9 [BALANCEAR] (= party.SCENE_ALLY_MIN_REL)
EVENT_SCAN_WINDOW = 200               # só eventos recentes entram (todos do turno)

RUMOR = "rumor"
# tipo -> (p de entrega por hop, raio máx. em períodos, hops)  [BALANCEAR]
SUBJECT_PARAMS: Dict[str, Tuple[float, int, int]] = {
    "npc_killed": (0.8, 15, 2),
    "location_control_changed": (0.9, 20, 2),
    "route_blocked": (0.7, 10, 1),
    "route_cleared": (0.7, 10, 1),
    "quest_completed": (0.5, 5, 1),
    RUMOR: (0.35, 5, 1),
}
# Testemunhável mas NUNCA propagado (R7).
WITNESS_ONLY_TYPES = {"secret_revealed"}
RUMOR_PROVENANCE = {"npc_claim", "inference"}

RELATIONS = ("observed_by", "told_to", "believed_by")
CHANNELS = ("witness", "messenger", "local_rumor", "player")
SUBJECT_KINDS = ("event", "memory_fact")
_RELATION_RANK = {"observed_by": 0, "believed_by": 1, "told_to": 2}
_TITLE_WORDS = {"lorde", "protetor", "comandante", "mestre", "velha", "velho",
                "senhor", "senhora", "irmao", "irma", "capitao", "dama", "lady"}


# --------------------------------------------------------------------------- #
# Primitivos
# --------------------------------------------------------------------------- #
def mode() -> str:
    raw = str(os.getenv("RPG_NPC_KNOWLEDGE", "off") or "").strip().lower()
    return raw if raw in MODES else "off"


def clock_index(world: Optional[dict]) -> int:
    """`day*5 + índice do período` (mesmo relógio de `world_utils.advance_clock`)."""
    from world_utils import PERIODS
    clock = (world or {}).get("world_clock") or {}
    try:
        day = int(clock.get("day", 1) or 1)
    except (TypeError, ValueError):
        day = 1
    period = clock.get("period")
    idx = PERIODS.index(period) if period in PERIODS else 0
    return day * len(PERIODS) + idx


def _sha(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _slug(name: str) -> str:
    return f"npc_{(name or 'desconhecido').lower().replace(' ', '_')}"


def _world(state: dict) -> dict:
    return state.get("world") or {}


def _turn(state: dict) -> int:
    return _int(_world(state).get("turn_count")) or 0


# --------------------------------------------------------------------------- #
# Identidade do holder (SPEC-149: aliases resolvem para UM holder)
# --------------------------------------------------------------------------- #
def holder_id(state: dict, ref: str) -> str:
    """`npc:<id canônico>` — mesmo id de `agents.npc._npc_id` (row.id ou slug)."""
    from services.entity_identity import find_runtime_npc_key, runtime_npc_aliases
    ref = str(ref or "").strip()
    if ref.startswith("npc:"):
        ref = ref[4:]
    if not ref:
        return ""
    npcs = state.get("npcs") or {}
    key = find_runtime_npc_key(npcs, ref)
    row = npcs.get(key) if key is not None else None
    if not isinstance(row, dict):
        wanted = runtime_npc_aliases(ref)
        for member in state.get("party") or []:
            if isinstance(member, dict) and wanted & runtime_npc_aliases(
                    str(member.get("name") or ""), member):
                row, key = member, str(member.get("name") or "")
                break
    if isinstance(row, dict):
        return f"npc:{row.get('id') or _slug(str(row.get('name') or key or ref))}"
    return f"npc:{ref if ref.startswith('npc_') else _slug(ref)}"


def _holders_for(state: dict, ref: str) -> Set[str]:
    out = {holder_id(state, ref)}
    raw = str(ref or "").strip()
    if raw:
        out.add(raw if raw.startswith("npc:") else f"npc:{raw}")
    return {h for h in out if h}


def _present_holders(state: dict) -> List[str]:
    """Testemunhas possíveis: NPCs em cena no local atual + party ativa presente."""
    from services.npc_layers import npcs_in_scene
    seen: List[str] = []
    for name in npcs_in_scene(state):
        hid = holder_id(state, name)
        if hid and hid not in seen:
            seen.append(hid)
    return seen


def _residents(state: dict, location_id: str) -> List[str]:
    """NPCs que vivem em `location_id` (fora da party ativa) + party esperando lá."""
    import gamedata
    from services.npc_layers import npc_alive
    loc = gamedata.get_location(location_id) or {}
    names = {location_id, str(loc.get("name") or "")} - {""}
    active_party = {holder_id(state, str(c.get("name") or ""))
                    for c in state.get("party") or []
                    if isinstance(c, dict) and c.get("active")}
    out: List[str] = []
    for key, row in sorted((state.get("npcs") or {}).items(), key=lambda kv: str(kv[0])):
        if not isinstance(row, dict) or not npc_alive(row):
            continue
        if str(row.get("home_location_id") or "") != location_id:
            continue
        hid = holder_id(state, str(key))
        if hid and hid not in active_party and hid not in out:
            out.append(hid)
    for member in state.get("party") or []:
        if (isinstance(member, dict) and not member.get("active")
                and npc_alive(member) and str(member.get("waiting_at") or "") in names):
            hid = holder_id(state, str(member.get("name") or ""))
            if hid and hid not in out:
                out.append(hid)
    return out


# --------------------------------------------------------------------------- #
# Assuntos
# --------------------------------------------------------------------------- #
def _event_by_id(state: dict, event_id: str) -> Optional[dict]:
    for ev in reversed(state.get("event_log") or []):
        if isinstance(ev, dict) and ev.get("event_id") == event_id:
            return ev
    return None


def _memory_by_id(state: dict, memory_id: str) -> Optional[dict]:
    for row in state.get("memory_facts") or []:
        if isinstance(row, dict) and row.get("memory_id") == memory_id:
            return row
    return None


def _subject_type(state: dict, kind: str, subject_id: str) -> str:
    if kind == "memory_fact":
        return RUMOR
    ev = _event_by_id(state, subject_id) or {}
    return str(ev.get("type") or "")


def _subject_text(state: dict, kind: str, subject_id: str) -> str:
    if kind == "memory_fact":
        row = _memory_by_id(state, subject_id) or {}
        return str(row.get("text") or "").strip()
    ev = _event_by_id(state, subject_id)
    if not ev:
        return ""
    projection = state.get("world_projection") or {}
    if ev.get("type") == "secret_revealed":
        rf = (projection.get("revealed_facts") or {}).get(subject_id) or {}
        return str(rf.get("fact") or "").strip()
    from services.context_builder import render_event
    return render_event(ev, projection)


def _is_secret(state: dict, text: str) -> bool:
    from services.memory_provenance import find_strict_unrevealed
    return bool(text) and bool(find_strict_unrevealed(text, state))


def _params(state: dict, kind: str, subject_id: str) -> Optional[Tuple[float, int, int]]:
    stype = _subject_type(state, kind, subject_id)
    params = SUBJECT_PARAMS.get(stype)
    if not params or stype in WITNESS_ONLY_TYPES:
        return None
    if _is_secret(state, _subject_text(state, kind, subject_id)):
        return None  # R7: assinatura hidden/secret não revelada nunca propaga
    return params


def _witnessable(event: dict) -> bool:
    etype = str(event.get("type") or "")
    return (etype in SUBJECT_PARAMS and etype != RUMOR) or etype in WITNESS_ONLY_TYPES


def _event_origin(state: dict, event: dict) -> str:
    import gamedata
    payload = event.get("payload") or {}
    for cand in (payload.get("location_id"), event.get("target_id")):
        if cand and gamedata.get_location(str(cand)):
            return str(cand)
    return str(_world(state).get("current_location_id") or "")


# --------------------------------------------------------------------------- #
# Construção de links
# --------------------------------------------------------------------------- #
def _link(holder: str, kind: str, subject_id: str, relation: str, *, source: str,
          channel: str, hops: int, clock: int, turn: int, **extra: Any) -> dict:
    row = {
        "link_id": _sha(holder, subject_id, relation, clock)[:16],
        "holder_id": holder, "subject_kind": kind, "subject_id": subject_id,
        "relation": relation, "source": source, "channel": channel,
        "hops": int(hops), "acquired_clock": int(clock), "acquired_turn": int(turn),
    }
    row.update({k: v for k, v in extra.items() if v not in (None, "")})
    return row


def _holder_subjects(links: Iterable[dict], holder: str) -> Set[str]:
    return {lk["subject_id"] for lk in links if lk.get("holder_id") == holder}


def record_witnesses(state: dict, event: dict, location_id: str, clock: int) -> List[dict]:
    """R2: NPCs presentes em `location_id` (o local atual) viram testemunhas."""
    if not isinstance(event, dict) or not _witnessable(event):
        return []
    here = str(_world(state).get("current_location_id") or "")
    if not location_id or location_id != here:
        return []
    sid = str(event.get("event_id") or "")
    if not sid:
        return []
    target = holder_id(state, str(event.get("target_id") or "")) if event.get(
        "target_id") else ""
    out: List[dict] = []
    for hid in _present_holders(state):
        if hid == target:
            continue
        for relation in ("observed_by", "believed_by"):
            out.append(_link(hid, "event", sid, relation, source="world", channel="witness",
                             hops=0, clock=clock, turn=_turn(state),
                             location_id=location_id, origin_location_id=location_id,
                             origin_clock=clock))
    return out


def _entity_names(state: dict, entity_id: str) -> Set[str]:
    from services import graph_resolver as gr
    from services.entity_identity import find_runtime_npc_key
    names = {str(entity_id)}
    try:
        ent = gr.get_entity(entity_id) or {}
    except Exception:
        ent = {}
    names.add(str(ent.get("name") or ""))
    names.update(str(a) for a in (ent.get("aliases") or []) if a)
    npcs = state.get("npcs") or {}
    key = find_runtime_npc_key(npcs, str(entity_id))
    row = npcs.get(key) if key is not None else None
    if isinstance(row, dict):
        names.update({str(key), str(row.get("name") or "")})
        names.update(str(a) for a in (row.get("aliases") or []) if a)
    return {_fold(n).strip() for n in names if n and n.strip()}


def _mentions(folded_text: str, names: Set[str]) -> bool:
    for name in names:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", folded_text):
            return True
        for token in re.findall(r"\w+", name):
            if len(token) >= 5 and token not in _TITLE_WORDS and re.search(
                    rf"(?<!\w){re.escape(token)}(?!\w)", folded_text):
                return True
    return False


def _player_known_events(state: dict) -> List[dict]:
    """Assuntos que o JOGADOR conhece: eventos registrados na crônica dele."""
    ids: Set[str] = set()
    for chapter in state.get("chronicle") or []:
        for entry in (chapter or {}).get("entries") or [] if isinstance(chapter, dict) else []:
            if isinstance(entry, dict) and entry.get("event_id"):
                ids.add(str(entry["event_id"]))
    return [ev for ev in state.get("event_log") or []
            if isinstance(ev, dict) and ev.get("event_id") in ids
            and str(ev.get("type") or "") in SUBJECT_PARAMS]


def record_player_told(state: dict, npc_id: str, player_text: str, clock: int) -> List[dict]:
    """R9: o jogador menciona entidade de um assunto que ELE conhece → `told_to`
    (+`believed_by` se relação ≥ BELIEF_MIN_RELATIONSHIP). Nunca cria fato."""
    from services.entity_identity import find_runtime_npc_key
    holder = holder_id(state, npc_id)
    folded = _fold(player_text)
    if not holder or not folded.strip():
        return []
    npcs = state.get("npcs") or {}
    key = find_runtime_npc_key(npcs, str(npc_id).removeprefix("npc:"))
    row = npcs.get(key) if key is not None else {}
    rel = _int((row or {}).get("relationship"))
    rel = 5 if rel is None else rel
    already = _holder_subjects(state.get("knowledge_links") or [], holder)
    out: List[dict] = []
    for ev in _player_known_events(state):
        sid = str(ev["event_id"])
        if sid in already or not ev.get("target_id"):
            continue
        if not _mentions(folded, _entity_names(state, str(ev["target_id"]))):
            continue
        if _is_secret(state, _subject_text(state, "event", sid)):
            continue
        relations = ["told_to"] + (["believed_by"] if rel >= BELIEF_MIN_RELATIONSHIP else [])
        for relation in relations:
            out.append(_link(holder, "event", sid, relation, source="player", channel="player",
                             hops=0, clock=clock, turn=_turn(state)))
        already.add(sid)
    return out


def inherit_local(state: dict, npc_id: str, location_id: str, clock: int) -> List[dict]:
    """R10: NPC novo em L herda, como rumor local, só o que JÁ chegou a L."""
    holder = holder_id(state, npc_id)
    heard = (state.get("location_heard") or {}).get(location_id) or []
    if not holder or not heard:
        return []
    already = _holder_subjects(state.get("knowledge_links") or [], holder)
    out: List[dict] = []
    for sid in heard:
        if sid in already:
            continue
        kind = "memory_fact" if _memory_by_id(state, sid) else "event"
        if _subject_type(state, kind, sid) in WITNESS_ONLY_TYPES:
            continue  # R7
        if _is_secret(state, _subject_text(state, kind, sid)):
            continue
        out.append(_link(holder, kind, sid, "told_to", source=f"loc:{location_id}",
                         channel="local_rumor", hops=0, clock=clock, turn=_turn(state),
                         location_id=location_id))
    return out


# --------------------------------------------------------------------------- #
# Propagação
# --------------------------------------------------------------------------- #
def schedule_propagation(state: dict, subject_kind: str, subject_id: str,
                         from_location_id: str, clock: int, hop: int = 1, *,
                         origin_location_id: Optional[str] = None,
                         origin_clock: Optional[int] = None) -> List[dict]:
    """R3/R4: agenda entregas seeded a partir de `from_location_id`."""
    from services.world_distance import reachable_within, travel_periods
    params = _params(state, subject_kind, subject_id)
    if not params or not from_location_id:
        return []
    p, radius, hops = params
    if p <= 0 or hop < 1 or hop > min(hops, MAX_HOPS):
        return []
    origin = origin_location_id or from_location_id
    o_clock = clock if origin_clock is None else int(origin_clock)
    heard = state.get("location_heard") or {}
    queued = {(d.get("subject_id"), d.get("to_location_id"))
              for d in state.get("knowledge_queue") or [] if isinstance(d, dict)}
    npc_locs = {str(r.get("home_location_id") or "")
                for r in (state.get("npcs") or {}).values() if isinstance(r, dict)}
    cands = []
    for loc, dist in reachable_within(from_location_id, radius).items():
        if loc in (from_location_id, origin) or subject_id in (heard.get(loc) or []):
            continue
        if (subject_id, loc) in queued:
            continue
        from_origin = travel_periods(origin, loc)
        if from_origin is None or from_origin > radius:
            continue
        cands.append((0 if loc in npc_locs else 1, dist, loc))
    out: List[dict] = []
    game_id = str(state.get("game_id") or "")
    for _rank, dist, loc in sorted(cands)[:MAX_DESTINATIONS]:
        seed = int(_sha(game_id, subject_id, from_location_id, loc, hop), 16)
        roll = (seed >> 64) % (1 << 32) / float(1 << 32)
        if roll >= p:
            continue
        due = int(clock) + int(dist) + 1 + seed % 3
        out.append({
            "delivery_id": _sha(subject_id, from_location_id, loc, hop)[:16],
            "subject_kind": subject_kind, "subject_id": subject_id,
            "subject_type": _subject_type(state, subject_kind, subject_id),
            "from_location_id": from_location_id, "to_location_id": loc,
            "hop": int(hop), "due_clock": due, "created_turn": _turn(state),
            "origin_location_id": origin, "origin_clock": o_clock,
        })
    return out


def _add_heard(heard: Dict[str, List[str]], loc: str, sid: str) -> None:
    if not loc or not sid:
        return
    rows = heard.setdefault(loc, [])
    if sid not in rows:
        rows.append(sid)


def deliver_due(state: dict, clock: int) -> dict:
    """Entrega idempotente de tudo com `due_clock ≤ clock`. Parcial ({} se nada)."""
    base = normalize_knowledge(state, legacy_default=False)
    queue = base["knowledge_queue"]
    due = [d for d in queue if d["due_clock"] <= int(clock)]
    if not due:
        return {}
    remaining = [d for d in queue if d["due_clock"] > int(clock)]
    links = list(base["knowledge_links"])
    heard = {k: list(v) for k, v in base["location_heard"].items()}
    for d in due:
        to, sid, kind = d["to_location_id"], d["subject_id"], d["subject_kind"]
        working = {**state, "knowledge_links": links, "knowledge_queue": remaining,
                   "location_heard": heard}
        _add_heard(heard, to, sid)
        rumor = kind == "memory_fact"
        for hid in _residents(working, to):
            if sid in _holder_subjects(links, hid):
                continue
            relations = ["told_to"] if rumor else ["told_to", "believed_by"]
            for relation in relations:
                links.append(_link(hid, kind, sid, relation,
                                   source=f"loc:{d['from_location_id']}", channel="messenger",
                                   hops=d["hop"], clock=d["due_clock"], turn=_turn(state),
                                   location_id=to,
                                   origin_location_id=d.get("origin_location_id"),
                                   origin_clock=d.get("origin_clock")))
        working = {**working, "knowledge_links": links, "location_heard": heard}
        remaining.extend(schedule_propagation(
            working, kind, sid, to, d["due_clock"], d["hop"] + 1,
            origin_location_id=d.get("origin_location_id"),
            origin_clock=d.get("origin_clock")))
    out = normalize_knowledge({"knowledge_links": links, "knowledge_queue": remaining,
                               "location_heard": heard}, legacy_default=False)
    out.pop("legacy_knowledge", None)
    return out


def turn_updates(state: dict) -> dict:
    """Ponto ÚNICO por turno (turn_finalizer): testemunhas + agendamento dos
    assuntos DESTE turno, herança de NPC criado no turno e entrega do que venceu.
    Idempotente (link_id/delivery_id determinísticos). Eventos de turnos
    anteriores nunca são distribuídos (R13: sem retroatividade)."""
    if mode() == "off":
        return {}
    world = _world(state)
    clock = clock_index(world)
    turn = _turn(state)
    here = str(world.get("current_location_id") or "")
    base = normalize_knowledge(state, legacy_default=False)
    links = list(base["knowledge_links"])
    queue = list(base["knowledge_queue"])
    heard = {k: list(v) for k, v in base["location_heard"].items()}

    def working() -> dict:
        return {**state, "knowledge_links": links, "knowledge_queue": queue,
                "location_heard": heard}

    for ev in (state.get("event_log") or [])[-EVENT_SCAN_WINDOW:]:
        if not isinstance(ev, dict) or _int(ev.get("turn")) != turn or not _witnessable(ev):
            continue
        sid = str(ev.get("event_id") or "")
        if not sid:
            continue
        origin = _event_origin(state, ev)
        links.extend(record_witnesses(working(), ev, origin, clock))
        if str(ev.get("type") or "") in WITNESS_ONLY_TYPES:
            continue  # R7: testemunhável, nunca vira rumor local nem propaga
        _add_heard(heard, origin, sid)
        queue.extend(schedule_propagation(working(), "event", sid, origin, clock, 1))

    for mf in state.get("memory_facts") or []:
        if (not isinstance(mf, dict) or mf.get("provenance") not in RUMOR_PROVENANCE
                or _int(mf.get("source_turn")) != turn or not mf.get("memory_id")):
            continue
        sid = str(mf["memory_id"])
        if _is_secret(state, str(mf.get("text") or "")):
            continue  # R7
        claimer = holder_id(state, str(mf.get("source_id") or "")) if str(
            mf.get("source_id") or "").startswith("npc:") else ""
        for hid in _present_holders(state):
            if hid == claimer:
                continue
            for relation in ("told_to", "believed_by"):
                links.append(_link(hid, "memory_fact", sid, relation,
                                   source=str(mf.get("source_id") or "world"),
                                   channel="witness", hops=0, clock=clock, turn=turn,
                                   location_id=here))
        _add_heard(heard, here, sid)
        queue.extend(schedule_propagation(working(), "memory_fact", sid, here, clock, 1))

    for key, row in (state.get("npcs") or {}).items():
        if (isinstance(row, dict) and _int(row.get("created_turn")) == turn
                and str(row.get("home_location_id") or "") == here and here):
            links.extend(inherit_local(working(), str(key), here, clock))

    merged = normalize_knowledge({"knowledge_links": links, "knowledge_queue": queue,
                                  "location_heard": heard}, legacy_default=False)
    merged.pop("legacy_knowledge", None)
    delivered = deliver_due({**state, **merged}, clock)
    merged.update(delivered)
    if (merged["knowledge_links"] == base["knowledge_links"]
            and merged["knowledge_queue"] == base["knowledge_queue"]
            and merged["location_heard"] == base["location_heard"]):
        return {}
    return merged


# --------------------------------------------------------------------------- #
# Leitura (contexto do NPC)
# --------------------------------------------------------------------------- #
def _holder_links(state: dict, npc_id: str) -> List[dict]:
    holders = _holders_for(state, npc_id)
    now = clock_index(_world(state))
    rows = normalize_knowledge(state, legacy_default=False)["knowledge_links"]
    return [lk for lk in rows if lk["holder_id"] in holders and lk["acquired_clock"] <= now]


def known_subject_ids(state: dict, npc_id: str) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {"observed": set(), "believed": set(), "heard": set()}
    for lk in _holder_links(state, npc_id):
        key = {"observed_by": "observed", "believed_by": "believed",
               "told_to": "heard"}[lk["relation"]]
        out[key].add(lk["subject_id"])
    return out


def _source_label(state: dict, source: str) -> str:
    import gamedata
    if source == "player":
        return "o viajante"
    if source.startswith("loc:"):
        loc = gamedata.get_location(source[4:]) or {}
        return f"viajantes de {loc.get('name') or source[4:]}"
    if source.startswith("npc:"):
        from services.entity_identity import find_runtime_npc_key
        npcs = state.get("npcs") or {}
        key = find_runtime_npc_key(npcs, source[4:])
        row = npcs.get(key) if key is not None else None
        return str((row or {}).get("name") or source[4:])
    return "testemunhas"


def knowledge_lines(state: dict, npc_id: str,
                    limit: int = NPC_KNOWLEDGE_CONTEXT_MAX) -> List[Tuple[str, str]]:
    """Até `limit` linhas rotuladas (`[VIU]`/`[OUVIU DE …]`/`[BOATO …]`), mais
    recentes primeiro. Conteúdo com assinatura secreta não revelada falha
    fechado (nunca entra no prompt)."""
    agg: Dict[str, dict] = {}
    for lk in _holder_links(state, npc_id):
        row = agg.setdefault(lk["subject_id"], {"kind": lk["subject_kind"], "rels": set(),
                                                "clock": -1, "source": "world"})
        row["rels"].add(lk["relation"])
        row["clock"] = max(row["clock"], lk["acquired_clock"])
        if lk["relation"] == "told_to":
            row["source"] = lk.get("source") or "world"
    out: List[Tuple[str, str]] = []
    for sid, row in sorted(agg.items(), key=lambda kv: (-kv[1]["clock"], kv[0])):
        if len(out) >= max(0, int(limit)):
            break
        text = _subject_text(state, row["kind"], sid)
        if not text or _is_secret(state, text):
            continue
        if row["kind"] == "memory_fact":
            label = "[BOATO, não confirmado]"
        elif "observed_by" in row["rels"]:
            label = "[VIU]"
        elif "believed_by" in row["rels"]:
            label = f"[OUVIU DE {_source_label(state, row['source'])}]"
        else:
            label = "[BOATO, não confirmado]"
        out.append((sid, f"{label} {text}"))
    return out


def npc_knowledge_block(state: dict, npc_id: str, limit: int = NPC_KNOWLEDGE_CONTEXT_MAX) -> str:
    lines = [line for _sid, line in knowledge_lines(state, npc_id, limit)]
    if not lines:
        return ""
    return "<O_QUE_VOCE_SABE>\n" + "\n".join(lines) + "\n</O_QUE_VOCE_SABE>"


# --------------------------------------------------------------------------- #
# Normalização (save/load, tolerante a adulteração)
# --------------------------------------------------------------------------- #
def _norm_link(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    holder, sid = raw.get("holder_id"), raw.get("subject_id")
    if not (isinstance(holder, str) and holder.startswith(("npc:", "loc:")) and len(holder) > 4):
        return None
    if not (isinstance(sid, str) and sid):
        return None
    kind, relation, channel = raw.get("subject_kind"), raw.get("relation"), raw.get("channel")
    if kind not in SUBJECT_KINDS or relation not in RELATIONS or channel not in CHANNELS:
        return None
    hops, clock = _int(raw.get("hops")), _int(raw.get("acquired_clock"))
    if hops is None or clock is None or not 0 <= hops <= MAX_HOPS:
        return None
    row = {"link_id": "", "holder_id": holder, "subject_kind": kind, "subject_id": sid,
           "relation": relation, "source": str(raw.get("source") or "world"),
           "channel": channel, "hops": hops, "acquired_clock": clock,
           "acquired_turn": _int(raw.get("acquired_turn")) or 0}
    link_id = raw.get("link_id")
    row["link_id"] = link_id if isinstance(link_id, str) and link_id else _sha(
        holder, sid, relation, clock)[:16]
    for key in ("location_id", "origin_location_id"):
        if isinstance(raw.get(key), str) and raw.get(key):
            row[key] = raw[key]
    if _int(raw.get("origin_clock")) is not None:
        row["origin_clock"] = _int(raw.get("origin_clock"))
    return row


def _norm_delivery(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    strs = ("delivery_id", "subject_id", "from_location_id", "to_location_id")
    if not all(isinstance(raw.get(k), str) and raw.get(k) for k in strs):
        return None
    if raw.get("subject_kind") not in SUBJECT_KINDS:
        return None
    hop, due = _int(raw.get("hop")), _int(raw.get("due_clock"))
    if hop is None or due is None or not 1 <= hop <= MAX_HOPS:
        return None
    row = {k: raw[k] for k in strs}
    row.update({"subject_kind": raw["subject_kind"], "hop": hop, "due_clock": due,
                "created_turn": _int(raw.get("created_turn")) or 0})
    for key in ("subject_type", "origin_location_id"):
        if isinstance(raw.get(key), str) and raw.get(key):
            row[key] = raw[key]
    if _int(raw.get("origin_clock")) is not None:
        row["origin_clock"] = _int(raw.get("origin_clock"))
    return row


def _cap_links(links: List[dict]) -> List[dict]:
    excess = len(links) - MAX_KNOWLEDGE_LINKS
    if excess <= 0:
        return links
    drop: Set[int] = set()
    # despejo: links `loc:` mais antigos, depois não-testemunho, nunca observed_by
    for predicate in (lambda lk: lk["holder_id"].startswith("loc:"),
                      lambda lk: lk["relation"] != "observed_by"):
        for i, lk in enumerate(links):
            if excess <= 0:
                break
            if i not in drop and predicate(lk):
                drop.add(i)
                excess -= 1
    kept = [lk for i, lk in enumerate(links) if i not in drop]
    return kept[-MAX_KNOWLEDGE_LINKS:]  # último recurso: ledger só de testemunhos


def normalize_knowledge(raw: Any, *, legacy_default: bool = True) -> dict:
    """Normaliza os 4 campos do ledger. `legacy_default` vale quando a chave
    `knowledge_links` não existe (save pré-SPEC-215 → True)."""
    raw = raw if isinstance(raw, dict) else {}
    links: Dict[str, dict] = {}
    for item in raw.get("knowledge_links") if isinstance(raw.get("knowledge_links"), list) else []:
        row = _norm_link(item)
        if row and row["link_id"] not in links:
            links[row["link_id"]] = row
    ordered = sorted(links.values(),
                     key=lambda lk: (lk["acquired_clock"], lk["acquired_turn"], lk["link_id"]))
    queue: Dict[str, dict] = {}
    for item in raw.get("knowledge_queue") if isinstance(raw.get("knowledge_queue"), list) else []:
        row = _norm_delivery(item)
        if row and row["delivery_id"] not in queue:
            queue[row["delivery_id"]] = row
    q_sorted = sorted(queue.values(), key=lambda d: (d["due_clock"], d["delivery_id"]))
    heard_raw = raw.get("location_heard") if isinstance(raw.get("location_heard"), dict) else {}
    heard: Dict[str, List[str]] = {}
    for loc in sorted(k for k in heard_raw if isinstance(k, str) and k)[:MAX_HEARD_LOCATIONS]:
        vals = heard_raw.get(loc)
        seen: List[str] = []
        for sid in vals if isinstance(vals, list) else []:
            if isinstance(sid, str) and sid and sid not in seen:
                seen.append(sid)
        if seen:
            heard[loc] = seen[-MAX_HEARD_PER_LOCATION:]
    if "knowledge_links" not in raw and "legacy_knowledge" not in raw:
        legacy = legacy_default
    else:
        value = raw.get("legacy_knowledge", False)
        legacy = value if isinstance(value, bool) else bool(value)
    return {"knowledge_links": _cap_links(ordered), "knowledge_queue": q_sorted[:MAX_QUEUE],
            "location_heard": heard, "legacy_knowledge": legacy}


# --------------------------------------------------------------------------- #
# Gate de contexto (consumido por services.context_builder)
# --------------------------------------------------------------------------- #
def context_gate(state: dict, npc_id: str) -> Optional[dict]:
    """None com `off`. Senão {mode, lines, filter} — `filter` = assuntos
    selecionados (≤8). Falha interna → lines=[], filter=set() (fail-closed)."""
    current = mode()
    if current == "off" or not npc_id:
        return None
    try:
        lines = knowledge_lines(state, npc_id, NPC_KNOWLEDGE_CONTEXT_MAX)
        error = None
    except Exception as exc:  # fail-closed: nunca abre para o pack onisciente
        lines, error = [], type(exc).__name__
        logger.warning("npc_knowledge gate falhou (%s); contexto do NPC sem fatos dinâmicos",
                       error)
    return {"mode": current, "lines": lines, "filter": {sid for sid, _ in lines},
            "error": error}


def log_shadow(npc_id: str, *, known: int, filtered: int, total: int) -> None:
    logger.info("rpg.npc_knowledge shadow npc=%s known=%d filtered=%d total_dynamic=%d",
                npc_id, known, filtered, total)
