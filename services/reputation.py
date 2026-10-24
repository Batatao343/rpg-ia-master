"""SPEC-298 — Reputação em quatro níveis (NPC, fação, local, raça/origem).

Dono único de ``npcs[*].relationship`` (fora da criação), ``factions[*].reputation``/
``disposition`` e ``location_fame``. Núcleo puro e determinístico: sem LLM, sem I/O
além do cache de dados curados. O LLM só classifica e narra (VISAO § Restrições).

Regra de ouro: ninguém muda de ideia sobre o jogador sem ter visto ou ouvido algo.
Fação só muda quando testemunhou (presença) ou quando a notícia chega (SPEC-215);
fama por local só cresce com testemunha ou notícia entregue ali.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

_LOG = logging.getLogger("rpg.reputation")
_DATA = Path(__file__).resolve().parent.parent / "data"

NpcTier = Literal["hostil", "desconfiado", "neutro", "amistoso", "leal"]
FactionTier = Literal["hostil", "desconfiado", "neutro", "amistoso", "aliado"]

REL_MIN, REL_MAX = 0, 10
REL_STEP_CAP = 1  # teto por FONTE por turno (llm ±1, engine ±1 => ±2 efetivo)
FAME_MAX = 100
MAX_FAME_DEEDS = 100
MAX_HEARD_DEEDS = 50
MAX_RECENT_CHANGES = 3
PENDING_TTL_DAYS = 30
MAX_PENDING = 100

_NPC_BANDS: tuple[tuple[int, NpcTier], ...] = (
    (1, "hostil"),
    (3, "desconfiado"),
    (6, "neutro"),
    (8, "amistoso"),
    (10, "leal"),
)
VALID_RACES = (
    "race_humanos",
    "race_elfos",
    "race_anoes_fuligem",
    "race_vrel",
    "race_cinzeus",
    "race_osshari",
)
_RACE_TAGS = {
    "humano": "race_humanos",
    "elfo": "race_elfos",
    "anao": "race_anoes_fuligem",
    "vrel": "race_vrel",
    "cinzeu": "race_cinzeus",
    "osshari": "race_osshari",
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _fold(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).strip().lower()


def _world(state: Mapping) -> dict:
    w = state.get("world") if isinstance(state, Mapping) else None
    return w if isinstance(w, dict) else {}


def _turn(state: Mapping) -> int:
    return _int(_world(state).get("turn_count"))


def _day(state: Mapping) -> int:
    clock = _world(state).get("world_clock") or {}
    return max(1, _int(clock.get("day"), 1))


def _here(state: Mapping) -> str:
    return str(_world(state).get("current_location_id") or "")


# --------------------------------------------------------------------------- #
# Faixas e rótulos (R2–R4)
# --------------------------------------------------------------------------- #
def npc_tier(relationship: Any) -> NpcTier:
    value = max(REL_MIN, min(REL_MAX, _int(relationship, 5)))
    for ceiling, label in _NPC_BANDS:
        if value <= ceiling:
            return label
    return "leal"


def faction_tier(reputation: Any) -> FactionTier:
    rep = _int(reputation)
    if rep <= -40:
        return "hostil"
    if rep <= -10:
        return "desconfiado"
    if rep < 10:
        return "neutro"
    if rep < 40:
        return "amistoso"
    return "aliado"


def _renown_label(value: int) -> str:
    if value >= 60:
        return "lendário"
    if value >= 30:
        return "afamado"
    if value >= 10:
        return "conhecido"
    return "desconhecido"


def _infamy_label(value: int) -> str:
    if value >= 60:
        return "odiado"
    if value >= 30:
        return "temido"
    if value >= 10:
        return "malvisto"
    return "—"


def _clamp_fame(value: Any) -> int:
    return max(0, min(FAME_MAX, _int(value)))


def fame_view(renown: Any, infamy: Any) -> dict[str, str]:
    return {
        "renown_label": _renown_label(_clamp_fame(renown)),
        "infamy_label": _infamy_label(_clamp_fame(infamy)),
    }


def fame_at(state: Mapping, location_id: str) -> dict[str, Any]:
    """Interface estável (R16): ``{renown, infamy, renown_label, infamy_label}``."""
    entry = (state.get("location_fame") or {}).get(location_id) or {}
    renown, infamy = _clamp_fame(entry.get("renown")), _clamp_fame(entry.get("infamy"))
    return {"renown": renown, "infamy": infamy, **fame_view(renown, infamy)}


def reveal_ceiling(tier: str) -> str:
    """R23: teto de revelação de fação por faixa do NPC."""
    return {"neutro": "existencia", "amistoso": "objetivo", "leal": "progresso"}.get(tier, "")


def knowledge_lines_cap(tier: str) -> int:
    """R23: teto de linhas de conhecimento injetadas no prompt do NPC."""
    return {"hostil": 0, "desconfiado": 2, "neutro": 4, "amistoso": 6, "leal": 8}.get(tier, 4)


# --------------------------------------------------------------------------- #
# Avisos (R26) — templates fixos, sem LLM e sem número
# --------------------------------------------------------------------------- #
def _notice(kind: str, subject_id: str, text: str, turn: int) -> dict:
    return {"kind": kind, "subject_id": subject_id, "text": text, "turn": turn}


def npc_notice_text(name: str, delta: int) -> str:
    if delta < 0:
        return f"{name} não gostou disso."
    return f"{name} parece mais à vontade com você."


def _push_recent(row: dict, turn: int, text: str) -> None:
    rows = [r for r in (row.get("recent_changes") or []) if isinstance(r, dict)]
    rows.append({"turn": turn, "text": text})
    row["recent_changes"] = rows[-MAX_RECENT_CHANGES:]


# --------------------------------------------------------------------------- #
# Nível 1 — NPC (R1)
# --------------------------------------------------------------------------- #
def apply_npc_delta(
    state: Mapping,
    npc_key: str,
    delta: int,
    *,
    reason: str,
    source: Literal["llm", "engine"],
    cap: int = REL_STEP_CAP,
) -> tuple[dict, dict | None]:
    """Único escritor de ``relationship`` pós-criação. Devolve ``(npc_row, aviso|None)``.

    Teto de ±1 por FONTE por turno (SPEC-230): LLM ±1 somado ao motor ±1 = ±2.
    """
    row = (state.get("npcs") or {}).get(npc_key)
    if not isinstance(row, dict):
        return {}, None
    row = dict(row)
    turn = _turn(state)
    budget = dict(row.get("_rel_budget") or {})
    if budget.get("turn") != turn:
        budget = {"turn": turn}
    used = _int(budget.get(source))
    wanted = _int(delta)
    capped = max(-cap, min(cap, used + wanted)) - used
    old = _int(row.get("relationship"), 5) if row.get("relationship") is not None else 5
    new = max(REL_MIN, min(REL_MAX, old + capped))
    applied = new - old
    budget[source] = used + applied
    row["_rel_budget"] = budget
    if applied == 0:
        return row, None
    row["relationship"] = new
    name = str(row.get("name") or npc_key)
    text = npc_notice_text(name, applied)
    _push_recent(row, turn, text)
    del reason  # auditoria é do chamador (event_log/memória); sem número na superfície
    return row, _notice("npc", str(row.get("id") or npc_key), text, turn)


# --------------------------------------------------------------------------- #
# Nível 4 — raça e origem (R5–R9)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _origins() -> dict:
    try:
        return json.loads((_DATA / "origins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"races": [], "regions": []}


@lru_cache(maxsize=1)
def race_table() -> dict:
    try:
        return json.loads((_DATA / "race_attitudes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"races": {}, "human_cultures": {}, "local_rules": []}


def resolve_race_id(value: Any) -> str:
    """Id de raça a partir de id ou nome exibível (sem caixa/acento). ``""`` = neutro."""
    key = _fold(value)
    if not key:
        return ""
    for race in _origins().get("races", []):
        if key in (_fold(race.get("id")), _fold(race.get("name"))):
            return str(race.get("id"))
    return ""


def resolve_region_id(value: Any) -> str:
    key = _fold(value)
    if not key:
        return ""
    for region in _origins().get("regions", []):
        if key in (_fold(region.get("id")), _fold(region.get("name"))):
            return str(region.get("id"))
    return ""


def region_id_of(location_id: str) -> str:
    """Local do mapa (``region`` é nome exibível) -> id de região de origins.json."""
    if not location_id:
        return ""
    import gamedata

    loc = gamedata.get_location(location_id) or {}
    return resolve_region_id(loc.get("region"))


def player_race_id(player: Mapping) -> str:
    rid = str(player.get("race_id") or "")
    return rid if rid in VALID_RACES else resolve_race_id(player.get("race"))


def npc_race_id(npc: Mapping) -> str:
    """R6: campo explícito válido -> tags do grafo -> ``""``."""
    rid = str(npc.get("race_id") or "")
    if rid in VALID_RACES:
        return rid
    from services import graph_resolver as gr

    for cand in (npc.get("id"), npc.get("entity_id")):
        ent = gr.get_entity(str(cand)) if cand else None
        for tag in (ent or {}).get("tags") or []:
            mapped = _RACE_TAGS.get(_fold(tag))
            if mapped:
                return mapped
    return ""


def _entry_value(block: Mapping | None, target: str) -> int:
    if not isinstance(block, Mapping):
        return 0
    entry = block.get(target) or block.get("*") or {}
    return _int(entry.get("value")) if isinstance(entry, Mapping) else 0


def race_attitude(state: Mapping, npc: Mapping) -> int:
    """R7: atitude do NPC (observador) em relação ao jogador, -2..+2."""
    target = player_race_id(state.get("player") or {})
    observer = npc_race_id(npc)
    if not target or not observer:
        return 0
    table = race_table()
    home_region = region_id_of(str(npc.get("home_location_id") or ""))
    if observer == "race_humanos":
        value = 0
        for culture in (table.get("human_cultures") or {}).values():
            if home_region and home_region in (culture.get("regions") or []):
                value = _entry_value(culture, target)
                break
    else:
        value = _entry_value((table.get("races") or {}).get(observer), target)
    for rule in table.get("local_rules") or []:
        if home_region and rule.get("region") == home_region and rule.get("target") == target:
            value += _int(rule.get("value"))
    return max(-2, min(2, value))


def npc_faction_id(npc: Mapping) -> str:
    """Fação do NPC: campo explícito ou aresta ``member_of``/``leads`` do grafo."""
    for key in ("faction_id", "faction"):
        if npc.get(key):
            return str(npc[key])
    from services import graph_resolver as gr

    nid = str(npc.get("id") or "")
    if not nid:
        return ""
    for etype in ("member_of", "leads"):
        for edge in gr.resolve_edges(None, entity_id=nid, edge_type=etype):
            if edge.get("source") == nid:
                return str(edge.get("target") or "")
    return ""


def _faction_row(state: Mapping, faction_id: str) -> dict:
    for f in state.get("factions") or []:
        if isinstance(f, dict) and f.get("id") == faction_id:
            return f
    return {}


def initial_relationship(state: Mapping, npc: Mapping) -> tuple[int, dict[str, int]]:
    """R8: ``5 + raça + origem + fama + fação``, clampado em 2..8 (+ auditoria)."""
    player = state.get("player") or {}
    home = str(npc.get("home_location_id") or _here(state) or "")
    race_term = race_attitude(state, npc)
    region = region_id_of(home)
    origin_id = str(player.get("origin_region_id") or "")
    origin_term = 1 if origin_id and region and origin_id == region else 0
    fame = fame_at(state, home) if home else {"renown": 0, "infamy": 0}
    fame_term = 0
    if fame["renown"] >= 30:
        fame_term += 2
    elif fame["renown"] >= 10:
        fame_term += 1
    if fame["infamy"] >= 30:
        fame_term -= 2
    elif fame["infamy"] >= 10:
        fame_term -= 1
    faction_term = 0
    fid = npc_faction_id(npc)
    frow = _faction_row(state, fid) if fid else {}
    if frow and frow.get("knows_player"):
        faction_term = max(-2, min(2, round(_int(frow.get("reputation")) / 25)))
    value = max(2, min(8, 5 + race_term + origin_term + fame_term + faction_term))
    basis = {
        "race": race_term,
        "origin": origin_term,
        "fame": fame_term,
        "faction": faction_term,
    }
    return value, basis


def refuses(state: Mapping, npc: Mapping, kind: str) -> bool:
    """R9: recusa rara — só atitude -2 E relação pessoal <= 2. Conversa nunca recusa."""
    if kind not in ("comercio", "favor"):
        return False
    rel = _int(npc.get("relationship"), 5) if npc.get("relationship") is not None else 5
    return race_attitude(state, npc) == -2 and rel <= 2


# --------------------------------------------------------------------------- #
# Nível 2 — fação por feitos (R10–R13)
# --------------------------------------------------------------------------- #
# (direção, magnitude) -> (delta fação, delta NPC, renome, infâmia)  [BALANCEAR]
_FACTION_DEED_TABLE: dict[tuple[str, str], tuple[int, int, int, int]] = {
    ("ajudou", "menor"): (4, 1, 3, 0),
    ("ajudou", "maior"): (10, 1, 8, 0),
    ("prejudicou", "menor"): (-6, -1, 0, 3),
    ("prejudicou", "maior"): (-15, -1, 0, 8),
}
QUEST_DEED = {"faction": 8, "npc": 1, "renown": 10}
KILL_DEED = {"faction": -12, "npc": -1, "infamy": 15, "renown_hostile": 5}

_EXTRA_DEED_KINDS: dict[str, dict] = {}


def faction_deed_delta(direction: str, magnitude: str = "menor") -> int:
    row = _FACTION_DEED_TABLE.get((str(direction), str(magnitude or "menor")))
    return row[0] if row else 0


def register_deed_kind(event_type: str, weights: Mapping[str, int]) -> None:
    """R16: outras specs (SPEC-299 crimes) registram tipos de feito com pesos
    ``{faction_delta, npc_delta, renown, infamy}``. O tipo vira assunto
    testemunhável/propagável da SPEC-215 (``player_deed``)."""
    _EXTRA_DEED_KINDS[str(event_type)] = {k: _int(v) for k, v in dict(weights).items()}
    from services import npc_knowledge

    npc_knowledge.PLAYER_DEED_TYPES.add(str(event_type))


def deed_event_types() -> set[str]:
    return {"faction_deed", "quest_completed", "npc_killed", *_EXTRA_DEED_KINDS}


def _faction_of_entity(entity_id: str) -> str:
    from services import graph_resolver as gr

    ent = gr.get_entity(entity_id)
    if not ent:
        return ""
    if ent.get("type") == "faction":
        return entity_id
    return npc_faction_id({"id": entity_id})


def _faction_of_victim(state: Mapping, victim_id: str) -> str:
    fid = _faction_of_entity(victim_id)
    if fid:
        return fid
    for row in (state.get("npcs") or {}).values():
        if isinstance(row, dict) and row.get("id") == victim_id:
            return npc_faction_id(row)
    return ""


def _enemies(faction_a: str, faction_b: str, projection: dict | None) -> bool:
    from services import graph_resolver as gr

    if not faction_a or not faction_b:
        return False
    for edge in gr.resolve_edges(projection, entity_id=faction_a, edge_type="enemy_of"):
        if faction_b in (edge.get("source"), edge.get("target")):
            return True
    return False


def deed_info(state: Mapping, event: Mapping) -> dict | None:
    """Pesos de um evento aceito (DEED_TABLE §3.3). ``None`` = não é feito do jogador."""
    etype = str(event.get("type") or "")
    payload = event.get("payload") or {}
    projection = state.get("world_projection") or {}
    loc = str(payload.get("location_id") or _here(state))
    controller = None
    if loc:
        from services import graph_resolver as gr

        controller = gr.get_current_controller(loc, projection)
    if etype == "faction_deed":
        fid = str(event.get("target_id") or "")
        row = _FACTION_DEED_TABLE.get(
            (str(payload.get("direction")), str(payload.get("magnitude") or "menor"))
        )
        if not fid or not row:
            return None
        fd, nd, renown, infamy = row
        if infamy and controller != fid:
            infamy = 0  # infâmia só se a fação controla o local
        return {
            "kind": etype,
            "faction_id": fid,
            "faction_delta": fd,
            "npc_delta": nd,
            "renown": renown,
            "infamy": infamy,
            "location_id": loc,
            "direction": str(payload.get("direction")),
        }
    if etype == "quest_completed":
        qid = str(payload.get("quest_id") or "")
        quest = next((q for q in state.get("quests") or [] if q.get("id") == qid), {})
        origin = str(quest.get("origin_entity_id") or "")
        fid = _faction_of_entity(origin) if origin else ""
        if not fid:
            return None
        return {
            "kind": etype,
            "faction_id": fid,
            "faction_delta": QUEST_DEED["faction"],
            "npc_delta": QUEST_DEED["npc"],
            "renown": QUEST_DEED["renown"],
            "infamy": 0,
            "location_id": loc,
            "direction": "ajudou",
            "origin_npc": origin,
        }
    if etype == "npc_killed":
        if str(event.get("actor_id") or "") != "player":
            return None
        victim = str(event.get("target_id") or "")
        fid = _faction_of_victim(state, victim)
        hostile = bool(fid and controller and _enemies(fid, controller, projection))
        return {
            "kind": etype,
            "faction_id": fid,
            "faction_delta": KILL_DEED["faction"] if fid else 0,
            "npc_delta": KILL_DEED["npc"],
            "renown": KILL_DEED["renown_hostile"] if hostile else 0,
            "infamy": 0 if hostile else KILL_DEED["infamy"],
            "location_id": loc,
            "direction": "prejudicou",
            "victim": victim,
        }
    extra = _EXTRA_DEED_KINDS.get(etype)
    if extra is not None:
        target = str(event.get("target_id") or "")
        fid = target if _faction_of_entity(target) == target and target else ""
        fid = fid or str(payload.get("faction_id") or "")
        fd = extra.get("faction_delta", 0)
        return {
            "kind": etype,
            "faction_id": fid,
            "faction_delta": fd,
            "npc_delta": extra.get("npc_delta", 0),
            "renown": extra.get("renown", 0),
            "infamy": extra.get("infamy", 0),
            "location_id": loc,
            "direction": "ajudou" if fd > 0 else "prejudicou",
        }
    return None


def faction_witnessed(state: Mapping, faction_id: str, exclude_id: str = "") -> bool:
    """A fação viu: controla o local atual ou tem membro presente (``in_scene`` explícito).

    ``exclude_id`` tira a vítima de um ``npc_killed`` das testemunhas; NPC legado sem
    ``in_scene`` não conta como testemunha universal (SPEC-298 review P1-2/P2-3)."""
    if not faction_id:
        return False
    from services import graph_resolver as gr
    from services.npc_layers import npc_alive

    loc = _here(state)
    if loc and gr.get_current_controller(loc, state.get("world_projection")) == faction_id:
        return True
    for key, row in (state.get("npcs") or {}).items():
        if not isinstance(row, dict) or row.get("in_scene") is not True or not npc_alive(row):
            continue
        if exclude_id and exclude_id in (
            str(key),
            str(row.get("id") or ""),
            str(row.get("name") or ""),
        ):
            continue
        if npc_faction_id(row) == faction_id:
            home = str(row.get("home_location_id") or "")
            if not home or not loc or home == loc:
                return True
    return False


def faction_in_scene(state: Mapping, faction_id: str, projection: dict | None = None) -> bool:
    """R11: fação *em cena* — presença, ou quest ativa de origem ligada a ela."""
    if faction_witnessed({**state, "world_projection": projection or {}}, faction_id):
        return True
    for q in state.get("quests") or []:
        if (
            isinstance(q, dict)
            and q.get("status") == "active"
            and q.get("origin_entity_id")
            and _faction_of_entity(str(q["origin_entity_id"])) == faction_id
        ):
            return True
    return False


def intercession_available(state: Mapping, faction_id: str) -> bool:
    """R24: há um favor de intercessão pendente para a fação?"""
    for row in (state.get("npcs") or {}).values():
        inter = (
            ((row or {}).get("favors") or {}).get("intercession") if isinstance(row, dict) else None
        )
        if isinstance(inter, dict) and inter.get("faction_id") == faction_id:
            return True
    return False


def _consume_intercession(npcs: dict, faction_id: str) -> dict:
    out = dict(npcs)
    for key, row in npcs.items():
        inter = (
            ((row or {}).get("favors") or {}).get("intercession") if isinstance(row, dict) else None
        )
        if isinstance(inter, dict) and inter.get("faction_id") == faction_id:
            new_row = dict(row)
            new_row["favors"] = {**(row.get("favors") or {}), "intercession": None}
            out[key] = new_row
            return out
    return out


def _apply_faction(
    state: Mapping,
    factions: list,
    npcs: dict,
    faction_id: str,
    delta: int,
    deed_id: str,
    notice: bool = False,
) -> tuple[list, dict, dict | None, int]:
    """Aplica ``delta`` assinado na fação. Devolve (factions, npcs, evento, delta_aplicado)."""
    from world_utils import apply_reputation

    if delta < 0 and intercession_available({**state, "npcs": npcs}, faction_id):
        delta = -(abs(delta) // 2)
        npcs = _consume_intercession(npcs, faction_id)
    if delta == 0:
        return factions, npcs, None, 0
    direction = "ajudou" if delta > 0 else "prejudicou"
    new_factions, rep_ev = apply_reputation(factions, faction_id, direction, abs(delta))
    if not rep_ev:
        return factions, npcs, None, 0
    turn = _turn(state)
    out = []
    for f in new_factions:
        if f.get("id") == faction_id:
            f = dict(f)
            f["knows_player"] = True
            if notice:  # só quando o jogador é avisado (testemunhou + fação conhecida)
                _push_recent(f, turn, f"{f.get('name') or faction_id} vai lembrar disso.")
        out.append(f)
    proposal = {
        "type": "reputation_changed",
        "actor_id": "player",
        "target_id": faction_id,
        "payload": {
            "delta": rep_ev["delta"],
            "new_value": rep_ev["reputation"],
            "reason": direction,
            "deed_id": deed_id,
        },
        "source": "reputation",
    }
    return out, npcs, proposal, rep_ev["delta"]


def _known_faction(state: Mapping, faction_id: str) -> bool:
    return bool(((state.get("faction_intel") or {}).get(faction_id) or {}).get("known"))


def _add_fame(fame: dict, loc: str, subject_id: str, renown: int, infamy: int) -> tuple[dict, bool]:
    """Idempotente por (local, assunto). Devolve (fame, rótulo_mudou)."""
    if not loc or not subject_id or (not renown and not infamy):
        return fame, False
    entry = dict(fame.get(loc) or {})
    deeds = list(entry.get("deeds") or [])
    if subject_id in deeds:
        return fame, False
    before = fame_view(entry.get("renown", 0), entry.get("infamy", 0))
    entry["renown"] = _clamp_fame(_int(entry.get("renown")) + renown)
    entry["infamy"] = _clamp_fame(_int(entry.get("infamy")) + infamy)
    deeds.append(subject_id)
    entry["deeds"] = deeds[-MAX_FAME_DEEDS:]
    out = dict(fame)
    out[loc] = entry
    after = fame_view(entry["renown"], entry["infamy"])
    return out, before != after


def deed_known_at(state: Mapping, subject_id: str, location_id: str) -> bool:
    """R16: o local já contou este feito na sua fama?"""
    entry = (state.get("location_fame") or {}).get(location_id) or {}
    return subject_id in (entry.get("deeds") or [])


def add_location_fame(
    state: Mapping, location_id: str, subject_id: str, renown: int = 0, infamy: int = 0
) -> dict | None:
    """Escritor público da fama por local (SPEC-299 R15). Idempotente por
    ``(local, subject_id)``. Devolve o novo ``location_fame`` ou None se nada mudou."""
    current = dict(state.get("location_fame") or {})
    fame, _changed = _add_fame(current, location_id, subject_id, renown, infamy)
    return fame if fame != current else None


def _present_witnesses(state: Mapping, victim_id: str = "") -> list[str]:
    from services import npc_knowledge

    victim = npc_knowledge.holder_id(dict(state), victim_id) if victim_id else ""
    return [h for h in npc_knowledge._present_holders(dict(state)) if h != victim]


def process_deeds(state: Mapping, accepted_events: list[dict]) -> dict:
    """Feitos aceitos neste lote -> fação (se testemunhou) / pendência / fama local.

    ``state`` já traz ``event_log`` com os eventos aceitos. Devolve updates parciais;
    ``reputation_events`` (propostas ``reputation_changed``) fica para o chamador
    construir e anexar ao log. Nunca levanta.
    """
    from services import npc_knowledge

    factions = list(state.get("factions") or [])
    npcs = dict(state.get("npcs") or {})
    fame = dict(state.get("location_fame") or {})
    pending = list(state.get("reputation_pending") or [])
    notices = [n for n in (state.get("reputation_notices") or []) if isinstance(n, dict)]
    turn = _turn(state)
    here = _here(state)
    rep_events: list[dict] = []
    changed = False
    for ev in accepted_events:
        if not isinstance(ev, dict):
            continue
        try:
            info = deed_info({**state, "factions": factions, "npcs": npcs}, ev)
        except Exception as exc:  # silent-ok: feito malformado nunca derruba o turno
            _LOG.warning("deed_info falhou: %s", type(exc).__name__)
            info = None
        if not info:
            continue
        sid = str(ev.get("event_id") or "")
        loc = info["location_id"] or here
        ev.setdefault("payload", {})
        ev["payload"]["location_id"] = loc
        ev["payload"]["deed"] = {
            "faction_id": info["faction_id"],
            "npc_delta": info["npc_delta"],
            "renown": info["renown"],
            "infamy": info["infamy"],
            "direction": info["direction"],
        }
        changed = True
        # --- fama: só com testemunha presente (ou notícia entregue depois) ---
        if loc == here and _present_witnesses(state, str(info.get("victim") or "")):
            fame, label_changed = _add_fame(fame, loc, sid, info["renown"], info["infamy"])
            if label_changed:
                notices.append(_notice("fame", loc, _fame_text(loc), turn))
        # --- fação: testemunhou -> aplica; senão pendência (modo on) ---
        fid, fd = info["faction_id"], info["faction_delta"]
        if not fid or not fd:
            continue
        known = _known_faction(state, fid)
        if faction_witnessed(state, fid, str(info.get("victim") or "")):
            factions, npcs, proposal, applied = _apply_faction(
                state, factions, npcs, fid, fd, sid, notice=known
            )
            if proposal:
                rep_events.append(proposal)
                if known:
                    fname = (_faction_row({"factions": factions}, fid) or {}).get("name") or fid
                    notices.append(_notice("faction", fid, f"{fname} vai lembrar disso.", turn))
        elif npc_knowledge.mode() == "on" and not any(
            p.get("subject_id") == sid and p.get("faction_id") == fid for p in pending
        ):
            pending.append(
                {"subject_id": sid, "faction_id": fid, "delta": fd, "created_day": _day(state)}
            )
    out: dict[str, Any] = {}
    if not changed:
        return out
    out["factions"] = factions
    out["npcs"] = npcs
    out["location_fame"] = fame
    out["reputation_pending"] = pending[-MAX_PENDING:]
    out["reputation_notices"] = notices
    out["reputation_events"] = rep_events
    return out


def _fame_text(loc: str) -> str:
    import gamedata

    name = (gamedata.get_location(loc) or {}).get("name") or loc
    return f"Em {name}, já falam de você."


# --------------------------------------------------------------------------- #
# Fim de turno (finalizer): entregas, reações e avisos
# --------------------------------------------------------------------------- #
def _deed_events(state: Mapping) -> list[dict]:
    out = []
    for ev in (state.get("event_log") or [])[-400:]:
        if isinstance(ev, dict) and isinstance((ev.get("payload") or {}).get("deed"), dict):
            out.append(ev)
    return out


def turn_updates(state: Mapping) -> dict:
    """Ponto único no ``turn_finalizer``: fama por notícia entregue, pendências de
    fação, reação de NPCs ao que ouviram e avisos do turno. Determinístico."""
    from services import npc_knowledge

    turn = _turn(state)
    here = _here(state)
    updates: dict[str, Any] = {}
    # avisos são sobrescritos a cada turno: só ficam os do turno corrente
    notices = [
        n
        for n in (state.get("reputation_notices") or [])
        if isinstance(n, dict) and _int(n.get("turn"), -1) == turn
    ]
    cur_notices = list(state.get("reputation_notices") or [])
    deeds = _deed_events(state)
    on = npc_knowledge.mode() == "on"
    if on and deeds:
        fame = dict(state.get("location_fame") or {})
        heard = state.get("location_heard") or {}
        for ev in deeds:
            sid = str(ev.get("event_id") or "")
            d = ev["payload"]["deed"]
            origin = str(ev["payload"].get("location_id") or "")
            for loc, sids in heard.items():
                if loc == origin or sid not in (sids or []):
                    continue  # origem só vale com testemunha (process_deeds)
                fame, label_changed = _add_fame(
                    fame, loc, sid, _int(d.get("renown")), _int(d.get("infamy"))
                )
                if label_changed and loc == here:
                    notices.append(_notice("fame", loc, _fame_text(loc), turn))
        if fame != (state.get("location_fame") or {}):
            updates["location_fame"] = fame
    if on and state.get("reputation_pending"):
        updates.update(_deliver_pending(state, deeds))
    if on and deeds:
        react = _npc_reactions({**state, **updates}, deeds)
        if react:
            updates["npcs"] = react["npcs"]
            notices.extend(react["notices"])
    debt = debt_updates({**state, **updates})
    if debt:
        updates["npcs"] = debt["npcs"]
        notices.extend(debt["notices"])
    if notices != cur_notices:
        updates["reputation_notices"] = notices
    return updates


def _deliver_pending(state: Mapping, deeds: list[dict]) -> dict:
    from services import graph_resolver as gr
    from services import npc_knowledge

    pending = [p for p in state.get("reputation_pending") or [] if isinstance(p, dict)]
    if not pending:
        return {}
    day = _day(state)
    heard = state.get("location_heard") or {}
    by_id = {str(e.get("event_id")): e for e in deeds}
    factions = list(state.get("factions") or [])
    npcs = dict(state.get("npcs") or {})
    keep: list[dict] = []
    new_events: list[dict] = []
    for p in pending:
        sid, fid = str(p.get("subject_id")), str(p.get("faction_id"))
        if day - _int(p.get("created_day"), day) > PENDING_TTL_DAYS:
            continue  # expirou sem efeito
        ev = by_id.get(sid)
        origin = str(((ev or {}).get("payload") or {}).get("location_id") or "")
        arrived = False
        for loc, sids in heard.items():
            if (
                loc != origin
                and sid in (sids or [])
                and gr.get_current_controller(loc, state.get("world_projection")) == fid
            ):
                arrived = True
                break
        if not arrived:
            for key, row in npcs.items():
                if isinstance(row, dict) and npc_faction_id(row) == fid:
                    known = npc_knowledge.known_subject_ids(dict(state), str(key))
                    if sid in known["heard"]:
                        arrived = True
                        break
        if not arrived:
            keep.append(p)
            continue
        factions, npcs, proposal, _ = _apply_faction(
            state, factions, npcs, fid, _int(p.get("delta")), sid
        )
        if proposal:
            new_events.append(proposal)
    out: dict[str, Any] = {"reputation_pending": keep}
    if factions != list(state.get("factions") or []):
        out["factions"] = factions
        out["npcs"] = npcs
    if new_events:
        from services.event_processor import _build_event

        log = list(state.get("event_log") or [])
        for prop in new_events:
            log.append(_build_event(prop, _turn(state)))
        out["event_log"] = log
    return out


def _npc_reactions(state: Mapping, deeds: list[dict]) -> dict | None:
    """R15: NPC que ouviu/viu um feito que o afeta ajusta ±1, uma vez por assunto."""
    from services import npc_knowledge
    from services.npc_layers import is_in_scene

    npcs = dict(state.get("npcs") or {})
    notices: list[dict] = []
    changed = False
    for key, row in sorted(npcs.items(), key=lambda kv: str(kv[0])):
        if not isinstance(row, dict) or not row.get("name"):
            continue
        heard_deeds = list(row.get("heard_deeds") or [])
        known: dict[str, set[str]] | None = None
        nfid = npc_faction_id(row)
        for ev in deeds:
            sid = str(ev.get("event_id") or "")
            d = ev["payload"]["deed"]
            if sid in heard_deeds or not nfid or d.get("faction_id") != nfid:
                continue
            if _int(d.get("npc_delta")) == 0:
                continue
            if known is None:
                known = npc_knowledge.known_subject_ids(dict(state), str(key))
            if sid not in (known["observed"] | known["heard"]):
                continue
            new_row, notice = apply_npc_delta(
                {**state, "npcs": npcs},
                key,
                1 if _int(d["npc_delta"]) > 0 else -1,
                reason="deed",
                source="engine",
            )
            if not new_row:
                continue
            heard_deeds.append(sid)
            new_row["heard_deeds"] = heard_deeds[-MAX_HEARD_DEEDS:]
            npcs[key] = new_row
            changed = True
            if notice and is_in_scene(new_row) and new_row.get("known_by_player", True):
                notices.append(notice)
    return {"npcs": npcs, "notices": notices} if changed else None


# --------------------------------------------------------------------------- #
# Migração (R28)
# --------------------------------------------------------------------------- #
def ensure_reputation_fields(state: dict) -> dict:
    """Backfill idempotente com defaults neutros. NPCs existentes NÃO recalculam relação."""
    if not isinstance(state, dict):
        return state
    state.setdefault("location_fame", {})
    state.setdefault("reputation_pending", [])
    state.setdefault("reputation_notices", [])
    player = state.get("player")
    if isinstance(player, dict):
        if player.get("race_id") not in VALID_RACES:
            player["race_id"] = resolve_race_id(player.get("race"))
        player.setdefault("origin_region_id", "")
    world = state.get("world")
    if isinstance(world, dict):
        world.setdefault("shelter", None)
    npcs = state.get("npcs")
    if isinstance(npcs, dict):
        for row in npcs.values():
            if isinstance(row, dict):
                row.setdefault("race_id", "")
                row.setdefault("relationship_basis", {})
                row.setdefault("heard_deeds", [])
                row.setdefault("favors", {})
    return state


# --------------------------------------------------------------------------- #
# Efeitos econômicos (R17-R19)
# --------------------------------------------------------------------------- #
_PRICE_BAND = {
    "hostil": 1.30,
    "desconfiado": 1.15,
    "neutro": 1.00,
    "amistoso": 0.92,
    "leal": 0.85,
}
PRICE_FACTOR_MIN, PRICE_FACTOR_MAX = 0.75, 1.50
TRAIT_PRICE_STEP = 0.03


def find_keeper(state: Mapping, merchant_id: str) -> tuple[str | None, dict]:
    """(chave em ``state.npcs``, linha) do keeper do mercador, se já registrado."""
    wanted = _keeper_npc_id(merchant_id, None)
    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict) and (
            row.get("keeper_of") == merchant_id or row.get("id") == wanted
        ):
            return key, row
    return None, {}


def _keeper_npc_id(merchant_id: str, keeper: Mapping | None) -> str:
    if keeper and keeper.get("npc_id"):
        return str(keeper["npc_id"])
    return f"merchant_{merchant_id}"


def build_keeper(state: Mapping, merchant_id: str, merchant: Mapping) -> tuple[str, dict]:
    """Linha determinística do keeper (pura: não toca o estado). ``("", {})`` sem keeper."""
    keeper = merchant.get("keeper") if isinstance(merchant, Mapping) else None
    if not isinstance(keeper, Mapping):
        return "", {}
    from services import graph_resolver as gr
    from services import npc_layers

    home = str(merchant.get("location_id") or "")
    if keeper.get("npc_id"):
        ent = gr.get_entity(str(keeper["npc_id"])) or {}
        name = str(ent.get("name") or keeper["npc_id"])
        role = str(ent.get("role") or merchant.get("name") or "Mercador")
        nid = str(keeper["npc_id"])
    else:
        name = str(keeper.get("name") or merchant.get("name") or merchant_id)
        role = str(keeper.get("role") or "Mercador")
        nid = _keeper_npc_id(merchant_id, keeper)
    row = {
        "id": nid,
        "name": name,
        "role": role,
        "persona": f"{role}. Negocia com firmeza e fala pouco de si.",
        "location": home,
        "race_id": str(keeper.get("race_id") or ""),
        "keeper_of": merchant_id,
        "memory": [],
    }
    row = npc_layers.ensure_npc_fields(row, str(state.get("game_id", "")), home, in_scene=True)
    row["known_by_player"] = False
    row["race_id"] = row["race_id"] if row["race_id"] in VALID_RACES else npc_race_id(row)
    rel, basis = initial_relationship(state, row)
    row["relationship"], row["relationship_basis"] = rel, basis
    return name, row


def keeper_for_price(state: Mapping, merchant_id: str, merchant: Mapping) -> dict:
    """Keeper registrado, ou o virtual idêntico ao que seria criado (sem mutar)."""
    _, row = find_keeper(state, merchant_id)
    return row or build_keeper(state, merchant_id, merchant)[1]


def ensure_keeper(state: dict, merchant_id: str, merchant: Mapping) -> tuple[str | None, dict]:
    """R17: o keeper vira registro em ``state.npcs`` na primeira visita, SEM LLM.

    Muta ``state['npcs']`` no lugar (mesmo padrão de ``_ensure_stock`` com ``world``);
    sem ``npcs`` no estado não persiste nada e devolve o virtual."""
    key, row = find_keeper(state, merchant_id)
    if key is not None:
        return key, row
    name, row = build_keeper(state, merchant_id, merchant)
    if not row:
        return None, {}
    npcs = state.get("npcs")
    if isinstance(npcs, dict):
        npcs[name] = row
        return name, row
    return None, row


def relation_price_mult(state: Mapping, keeper: Mapping, mode: str) -> float:
    """R18: faixa × traço ``comercio``; venda usa o inverso; clamp 0,75..1,50."""
    from services.npc_layers import trait_dc_modifier

    band = _PRICE_BAND[npc_tier(keeper.get("relationship"))]
    trait = 1 + TRAIT_PRICE_STEP * trait_dc_modifier(dict(keeper), "comercio")
    buy_factor = band * trait
    factor = buy_factor if mode == "buy" else (1.0 / buy_factor if buy_factor else 1.0)
    return max(PRICE_FACTOR_MIN, min(PRICE_FACTOR_MAX, factor))


# --------------------------------------------------------------------------- #
# Abordagens sociais e favores (R20-R24) — resolvidas em Python ANTES do LLM
# --------------------------------------------------------------------------- #
SOCIAL_APPROACHES = ("conversar", "intimidar", "sondar", "pedir_favor", "pagar_divida")
FAVOR_KINDS = ("esconder", "emprestar", "interceder")
FAVOR_COOLDOWN_DAYS = 3
LOAN_AMOUNT = 50  # [BALANCEAR]
LOAN_DUE_DAYS = 7
BASE_SOCIAL_DC = 12
_REVEAL_ORDER = ("", "existencia", "objetivo", "progresso")
_ATTITUDE_PHRASE = {
    "hostil": "despreza você",
    "desconfiado": "desconfia de você",
    "neutro": "ainda não decidiu o que pensar de você",
    "amistoso": "gosta de você",
    "leal": "confia em você",
}


def normalize_social_intent(approach: Any, favor_kind: Any = None) -> dict:
    """Valor inválido vira ``conversar`` / ``None`` (nunca derruba o turno)."""
    ap = approach if approach in SOCIAL_APPROACHES else "conversar"
    fk = favor_kind if favor_kind in FAVOR_KINDS else None
    return {"approach": ap, "favor_kind": fk}


def _seeded_rng(state: Mapping, npc: Mapping, tag: str):
    import hashlib
    import random

    raw = f"{state.get('game_id', '')}|{_turn(state)}|{npc.get('id') or npc.get('name')}|{tag}"
    return random.Random(int(hashlib.sha256(raw.encode()).hexdigest(), 16))


def _player_actor(state: Mapping) -> dict:
    return dict(state.get("player") or {})


def social_check(state: Mapping, npc: Mapping, approach: str) -> dict:
    """R21/R22. Puro: devolve o resultado; quem aplica é o ``npc_actor``.

    ``{approach, success, dc, roll, rel_delta, reveal_mode, reveal_trait, notice}``.
    """
    from services.conflict_resolution import general_test
    from services.npc_layers import trait_dc_modifier

    out: dict[str, Any] = {
        "approach": approach,
        "success": None,
        "rel_delta": 0,
        "reveal_mode": None,
        "reveal_trait": None,
        "notice": None,
    }
    name = str(npc.get("name") or "O interlocutor")
    if approach == "intimidar":
        fame = fame_at(state, _here(state))
        bonus = -3 if fame["infamy"] >= 60 else -2 if fame["infamy"] >= 30 else 0
        dc = BASE_SOCIAL_DC + trait_dc_modifier(dict(npc), "intimidacao") + bonus
        rng = _seeded_rng(state, npc, "intimidar")
        roll = general_test(_player_actor(state), "forca", dc, rng=rng)
        out.update(
            success=bool(roll["sucesso"]),
            dc=dc,
            roll=roll,
            rel_delta=-1,
            reveal_mode="up" if roll["sucesso"] else "none",
        )
        out["notice"] = (
            f"{name} cede, mas não esquece."
            if roll["sucesso"]
            else f"{name} não se deixa intimidar."
        )
    elif approach == "sondar":
        dc = BASE_SOCIAL_DC + trait_dc_modifier(dict(npc), "insight")
        rng = _seeded_rng(state, npc, "sondar")
        roll = general_test(_player_actor(state), "mente", dc, rng=rng)
        out.update(success=bool(roll["sucesso"]), dc=dc, roll=roll)
        hidden = list(npc.get("hidden_traits") or [])
        if roll["sucesso"]:
            if hidden:
                out["reveal_trait"] = hidden[0]
            phrase = _ATTITUDE_PHRASE[npc_tier(npc.get("relationship"))]
            out["notice"] = f"Você percebe que {name} {phrase}."
    return out


def favor_decision(state: Mapping, npc: Mapping, kind: str) -> dict:
    """R24: decisão determinística. ``{ok, code, kind}``."""
    from services.npc_layers import trait_dc_modifier

    result: dict[str, Any] = {"ok": False, "code": "unknown", "kind": kind}
    if kind not in FAVOR_KINDS:
        return result
    if refuses(state, npc, "favor"):
        return {**result, "code": "refuses"}
    favors = npc.get("favors") or {}
    last = favors.get("last_day")
    if last is not None and _day(state) - _int(last) < FAVOR_COOLDOWN_DAYS:
        return {**result, "code": "cooldown"}
    base = 9 if kind == "emprestar" else 7
    required = max(1, min(10, base + trait_dc_modifier(dict(npc), "persuasao")))
    rel = _int(npc.get("relationship"), 5) if npc.get("relationship") is not None else 5
    if rel < required:
        return {**result, "code": "too_cold"}
    if kind == "interceder" and not npc_faction_id(npc):
        return {**result, "code": "no_faction"}
    if kind == "emprestar" and isinstance(favors.get("debt"), dict):
        return {**result, "code": "debt_open"}
    return {**result, "ok": True, "code": "ok"}


def apply_favor(state: Mapping, npc_key: str, npc: Mapping, kind: str) -> dict:
    """Efeitos de um favor aceito. Devolve patches ``{npc, player?, world?, notice}``."""
    from services.npc_knowledge import clock_index

    day = _day(state)
    row = dict(npc)
    favors = dict(row.get("favors") or {})
    favors["last_day"] = day
    patch: dict[str, Any] = {}
    name = str(row.get("name") or npc_key)
    if kind == "esconder":
        world = dict(_world(state))
        world["shelter"] = {
            "npc_id": str(row.get("id") or npc_key),
            "location_id": _here(state),
            "until_clock": clock_index(world) + 2,
        }
        patch["world"] = world
        text = f"{name} esconde você por um tempo."
    elif kind == "emprestar":
        player = _player_actor(state)
        from services.economy import clamp_gold

        player["gold"] = clamp_gold(player, _int(player.get("gold")) + LOAN_AMOUNT)
        patch["player"] = player
        favors["debt"] = {
            "amount": LOAN_AMOUNT,
            "due_day": day + LOAN_DUE_DAYS,
            "overdue_applied": False,
        }
        text = f"{name} empresta algumas moedas e espera ser pago."
    else:
        favors["intercession"] = {"faction_id": npc_faction_id(row)}
        text = f"{name} promete intervir a seu favor."
    row["favors"] = favors
    patch["npc"] = row
    patch["notice"] = _notice("favor", str(row.get("id") or npc_key), text, _turn(state))
    return patch


def pay_debt(state: Mapping, npc_key: str, npc: Mapping) -> dict:
    """``pagar_divida``: Python debita (``clamp_gold`` da economia)."""
    from services.economy import clamp_gold

    debt = (npc.get("favors") or {}).get("debt")
    if not isinstance(debt, dict):
        return {"ok": False, "code": "no_debt"}
    player = _player_actor(state)
    amount = _int(debt.get("amount"))
    if _int(player.get("gold")) < amount:
        return {"ok": False, "code": "insufficient_gold"}
    player["gold"] = clamp_gold(player, _int(player.get("gold")) - amount)
    row = dict(npc)
    row["favors"] = {**(npc.get("favors") or {}), "debt": None}
    name = str(row.get("name") or npc_key)
    return {
        "ok": True,
        "code": "ok",
        "player": player,
        "npc": row,
        "notice": _notice(
            "favor", str(row.get("id") or npc_key), f"{name} dá a dívida por quitada.", _turn(state)
        ),
    }


def clamp_reveal(level: str, tier: str, mode: str | None = None) -> str:
    """R23: nível de revelação pedido pelo LLM, limitado pela faixa (``""`` = descartar)."""
    idx = _REVEAL_ORDER.index(reveal_ceiling(tier))
    if mode == "none":
        idx = 0
    elif mode == "up":
        idx = min(len(_REVEAL_ORDER) - 1, idx + 1)
    wanted = _REVEAL_ORDER.index(level) if level in _REVEAL_ORDER else 0
    return _REVEAL_ORDER[min(wanted, idx)]


def _social_prompt(social: Mapping) -> str:
    approach = social.get("approach")
    if approach == "intimidar":
        if social.get("success"):
            return "o jogador intimidou você e você CEDEU a contragosto."
        return "o jogador tentou intimidar você e você NÃO se deixa intimidar; feche-se."
    if approach == "sondar":
        if social.get("success"):
            return "o jogador tenta ler suas intenções e você deixa transparecer algo de si."
        return "o jogador tenta ler suas intenções; você não entrega nada."
    return str(social.get("favor_prompt") or "o jogador faz um pedido pessoal.")


def attitude_block(state: Mapping, npc: Mapping, social: Mapping | None = None) -> str:
    """R25: ``<ATITUDE>`` do prompt do NPC — rótulo, motivos qualitativos, sem números."""
    tier = npc_tier(npc.get("relationship"))
    basis = npc.get("relationship_basis") or {}
    motives: list[str] = []
    if _int(basis.get("race")) < 0:
        motives.append("tem preconceito contra a raça do jogador")
    elif _int(basis.get("race")) > 0:
        motives.append("simpatiza com a raça do jogador")
    if _int(basis.get("origin")) > 0:
        motives.append("considera o jogador conterrâneo")
    if _int(basis.get("fame")) > 0:
        motives.append("ouviu falar bem do jogador por aqui")
    elif _int(basis.get("fame")) < 0:
        motives.append("ouviu falar mal do jogador por aqui")
    if npc.get("heard_deeds"):
        motives.append("soube de feitos do jogador")
    lines = [f"Atitude atual em relação ao jogador: {tier}."]
    if motives:
        lines.append("Motivos: " + "; ".join(motives) + ".")
    if social and social.get("approach") not in (None, "conversar"):
        lines.append(f"Abordagem do jogador neste turno: {_social_prompt(social)}")
    return "<ATITUDE>\n" + "\n".join(lines) + "\n</ATITUDE>"


def fame_line(state: Mapping) -> str:
    """R25: linha de fama do local atual para o storyteller (vazia se desconhecido)."""
    view = fame_at(state, _here(state))
    parts = []
    if view["renown_label"] != "desconhecido":
        parts.append(f"o jogador é {view['renown_label']} aqui")
    if view["infamy_label"] != "—":
        parts.append(f"é visto como {view['infamy_label']} aqui")
    return ("Fama local: " + "; ".join(parts) + ".") if parts else ""


def debt_updates(state: Mapping) -> dict:
    """Dívida vencida: relação −2 uma vez (+ aviso). Parcial; ``{}`` se nada vence."""
    npcs = dict(state.get("npcs") or {})
    day, changed, notices = _day(state), False, []
    for key, row in sorted(npcs.items(), key=lambda kv: str(kv[0])):
        debt = ((row or {}).get("favors") or {}).get("debt") if isinstance(row, dict) else None
        if not isinstance(debt, dict) or debt.get("overdue_applied"):
            continue
        if day <= _int(debt.get("due_day")):
            continue
        new_row, notice = apply_npc_delta(
            {**state, "npcs": npcs}, key, -2, reason="debt", source="engine", cap=2
        )
        if not new_row:
            continue
        new_row["favors"] = {**(row.get("favors") or {}), "debt": {**debt, "overdue_applied": True}}
        npcs[key] = new_row
        changed = True
        del notice
        if new_row.get("in_scene") is True and new_row.get("known_by_player", True):
            name = str(new_row.get("name") or key)
            notices.append(
                _notice(
                    "favor",
                    str(new_row.get("id") or key),
                    f"{name} cobra a dívida atrasada.",
                    _turn(state),
                )
            )
    return {"npcs": npcs, "notices": notices} if changed else {}
