"""SPEC-300 — alma dos companheiros (mecânica Python determinística).

A LLM só NARRA o que este módulo decidiu (bloco ``<COMPANHEIROS>`` em
``services.companion_prompt``). Aprovação 0..100 e o vetor de valores são INTERNOS: a API e
os prompts só veem rótulos (vocabulário de ``services.reputation``: hostil/desconfiado/
neutro/amistoso/leal). Único escritor de ``companion_souls``: :func:`apply_turn`, chamado
pelo ``turn_finalizer``.
"""

from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from services import companion_tags as ctags

_DATA = Path(__file__).resolve().parent.parent / "data"

AXES = ("compaixao", "honra", "ordem", "ganancia", "fe", "coragem", "abismo")

# --- constantes [BALANCEAR] -------------------------------------------------- #
K_ALIGN = 2
TAG_CAP = 10
FACTION_DIRECT = 8
TURN_CAP = 15
MIN_NOTICE = 2
PRISONER_START_APPROVAL = 20
WARN_BELOW = 25
CLEAR_WARN_AT = 35
LEAVE_BELOW = 15
LOYAL_LEAVE_BELOW = 5
BETRAY_BELOW = 8
BETRAY_GOLD_FRACTION = 0.25
BETRAY_GOLD_CAP = 60
ESTRANGED_DAYS = 3
REVIVE_BONUS = 10
REVIVE_CAP = 40
PERSONAL_REVEAL_AT = 55
PERSONAL_DONE_BONUS = 15
LOYAL_AT = 70
ROMANCE_OPEN_AT = 65
ROMANCE_BOND_AT = 75
ROMANCE_COMMIT_AT = 85
ROMANCE_BREAK_BELOW = 40
ROMANCE_REOPEN_DAYS = 5
ROMANCE_BOND_RESTS = 2
REACTION_TTL = 3
MAX_REACTIONS = 3
TELEGRAPH_MIN_DAYS = 1

# Vocabulário alinhado a ``reputation.NpcTier`` (SPEC-298): nada de números fora daqui.
_LABEL_BANDS: tuple[tuple[int, str], ...] = (
    (14, "hostil"),
    (34, "desconfiado"),
    (59, "neutro"),
    (79, "amistoso"),
    (100, "leal"),
)


class FateNotTelegraphed(Exception):
    """``apply_companion_fate`` sem telegrama válido (R26)."""


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def mode() -> Literal["off", "shadow", "on"]:
    raw = str(os.environ.get("RPG_COMPANION_SOUL", "on") or "on").strip().lower()
    return raw if raw in ("off", "shadow", "on") else "on"  # type: ignore[return-value]


def romance_enabled() -> bool:
    return str(os.environ.get("RPG_COMPANION_ROMANCE", "on") or "on").strip().lower() != "off"


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _world(state: dict) -> dict:
    w = state.get("world") if isinstance(state, dict) else None
    return w if isinstance(w, dict) else {}


def _turn(state: dict) -> int:
    return _int(_world(state).get("turn_count"))


def _day(state: dict) -> int:
    clock = _world(state).get("world_clock") or {}
    return max(1, _int(clock.get("day"), 1))


def _here(state: dict) -> str:
    return str(_world(state).get("current_location_id") or "")


def comp_id(comp: dict) -> str:
    return str(comp.get("origin_npc") or comp.get("id") or "")


@lru_cache(maxsize=1)
def _tables() -> dict:
    return json.loads((_DATA / "companion_values.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _quest_templates() -> dict:
    return json.loads((_DATA / "companion_quests.json").read_text(encoding="utf-8"))


def npc_row(state: dict, comp: dict) -> tuple[str, dict]:
    """Ficha de ``state.npcs`` do companheiro (``("", {})`` se não houver)."""
    from services.entity_identity import find_runtime_npc_key

    npcs = state.get("npcs") or {}
    origin = str(comp.get("origin_npc") or "")
    if origin:
        for key, row in npcs.items():
            if isinstance(row, dict) and row.get("id") == origin:
                return key, row
    key = find_runtime_npc_key(npcs, str(comp.get("name") or ""))
    if key is not None and isinstance(npcs.get(key), dict):
        return key, npcs[key]
    return "", {}


def _traits(npc: dict) -> list[str]:
    return [
        str(t) for t in [*(npc.get("hidden_traits") or []), *(npc.get("revealed_traits") or [])]
    ]


# --------------------------------------------------------------------------- #
# R1-R3 — valores e aprovação inicial
# --------------------------------------------------------------------------- #
def derive_values(npc: dict) -> dict[str, int]:
    """Soma (com clamp por eixo) de traços + fação + raça + região de origem. Sem LLM."""
    from services import reputation

    tab = _tables()
    out = dict.fromkeys(AXES, 0)

    def add(vec: dict | None) -> None:
        for axis, val in (vec or {}).items():
            if axis in out:
                out[axis] += _int(val)

    for tid in _traits(npc):
        add((tab.get("traits") or {}).get(tid))
    add((tab.get("factions") or {}).get(reputation.npc_faction_id(npc)))
    add((tab.get("races") or {}).get(reputation.npc_race_id(npc)))
    home = str(npc.get("home_location_id") or "")
    region = reputation.region_id_of(home) if home else ""
    add((tab.get("regions") or {}).get(region or home))
    return {a: _clamp(v, -2, 2) for a, v in out.items()}


def initial_approval(npc: dict, *, origin: str = "recruit") -> int:
    if origin == "prisoner":
        return PRISONER_START_APPROVAL
    rel = npc.get("relationship")
    rel_i = 5 if rel is None else _int(rel, 5)
    return _clamp(50 + 3 * (rel_i - 7), 40, 65)


def ensure_soul(state: dict, companion: dict) -> dict:
    """Alma nova (PURA) para um companheiro; ``values`` fica congelado na criação."""
    cid = comp_id(companion)
    key, row = npc_row(state, companion)
    source = dict(row) if row else dict(companion)
    if row:
        for k in ("faction", "faction_id", "race_id", "home_location_id"):
            source.setdefault(k, companion.get(k))
    origin = "prisoner" if companion.get("bound") == "rendicao" else "recruit"
    last = state.get("last_interaction_outcome") or {}
    if origin == "recruit" and not (last.get("kind") == "recruit" and last.get("progressed")):
        origin = "legacy"
    return {
        "companion_id": cid,
        "npc_key": key,
        "values": derive_values(source),
        "approval": initial_approval(source, origin="prisoner" if origin == "prisoner" else "x"),
        "origin": origin,
        "reactions": [],
        "warned_turn": None,
        "warned_day": None,
        "departure_pending": "",
        "departure_turn": None,
        "departed": "",
        "left_party_day": None,
        "betrayal_mode": "",
        "deliver_pending": False,
        "loyal": False,
        "grudge": False,
        "rests_together": 0,
        "negative_after_warn": False,
        "personal_quest": "none",
        "quest_ready_turn": None,
        "romance": "none",
        "romance_rests": 0,
        "romance_reopen_day": None,
        "telegraphs": [],
        "last_seen_day": _day(state),
        "last_combat": ctags.combat_result_id(state),
        "bound": "rendicao" if origin == "prisoner" else "",
    }


# --------------------------------------------------------------------------- #
# R6-R8 — deltas e rótulos
# --------------------------------------------------------------------------- #
def approval_label(approval: int) -> str:
    value = _clamp(_int(approval), 0, 100)
    for ceiling, label in _LABEL_BANDS:
        if value <= ceiling:
            return label
    return "leal"


def change_phrase(name: str, delta: int) -> str | None:
    from services import reputation

    mag = abs(_int(delta))
    if mag < MIN_NOTICE:
        return None
    if mag < 4:
        return f"{name} reparou nisso."
    if delta < 0:
        if mag >= 8:
            return f"{name} não vai esquecer isso."
        return reputation.npc_notice_text(name, delta)  # "X não gostou disso."
    return f"{name} aprovou muito." if mag >= 8 else f"{name} gostou disso."


def tag_delta(soul: dict, tag: dict, *, companion_faction: str) -> int:
    meta = ctags.catalog().get(tag["id"]) or {}
    values = soul.get("values") or {}
    align = sum(_int(w) * _int(values.get(a)) for a, w in (meta.get("axes") or {}).items())
    delta = _clamp(_int(meta.get("magnitude"), 1) * K_ALIGN * align, -TAG_CAP, TAG_CAP)
    if meta.get("faction_param") and tag.get("faction_id") and companion_faction:
        if tag["faction_id"] == companion_faction:
            delta += _int(tag.get("sign")) * FACTION_DIRECT
    return delta


def apply_tags(
    soul: dict, tags: list[dict], *, turn: int, companion_faction: str
) -> tuple[dict, int]:
    """Aplica as tags (PURA). Devolve ``(alma, delta do turno)``; reações só com |delta|>=2."""
    soul = deepcopy(soul)
    total = 0
    reactions = [r for r in (soul.get("reactions") or []) if isinstance(r, dict)]
    for tag in tags:
        delta = tag_delta(soul, tag, companion_faction=companion_faction)
        total += delta
        if abs(delta) >= MIN_NOTICE:
            rid = f"{turn}:{tag['id']}"
            reactions = [r for r in reactions if r.get("id") != rid]
            reactions.append({"id": rid, "tag": tag["id"], "delta": delta, "turn": turn})
    total = _clamp(total, -TURN_CAP, TURN_CAP)
    soul["approval"] = _clamp(_int(soul.get("approval"), 50) + total, 0, 100)
    soul["reactions"] = reactions[-MAX_REACTIONS:]
    if total < 0 and soul.get("warned_turn") is not None and turn > _int(soul["warned_turn"]):
        soul["negative_after_warn"] = True
    return soul, total


def _push_reaction(soul: dict, tag: str, turn: int, delta: int = 0) -> None:
    rid = f"{turn}:{tag}"
    rows = [r for r in (soul.get("reactions") or []) if r.get("id") != rid]
    rows.append({"id": rid, "tag": tag, "delta": delta, "turn": turn})
    soul["reactions"] = rows[-MAX_REACTIONS:]


# --------------------------------------------------------------------------- #
# R14-R16 — aviso, partida, traição
# --------------------------------------------------------------------------- #
def betrayal_mode(traits: list[str]) -> str:
    """Traição POR TRAÇO (decisão do dono): ``steal`` | ``deliver`` | ``""``."""
    tab = _tables()
    if set(traits) & set(tab.get("betrayal_blockers") or []):
        return ""
    bt = tab.get("betrayal_traits") or {}
    if set(traits) & set(bt.get("deliver") or []):
        return "deliver"
    if set(traits) & set(bt.get("steal") or []):
        return "steal"
    return ""


def update_warning(soul: dict, *, turn: int, day: int) -> dict:
    """Aviso ao cruzar ``WARN_BELOW`` e histerese em ``CLEAR_WARN_AT`` (PURA)."""
    soul = dict(soul)
    approval = _int(soul.get("approval"), 50)
    if soul.get("warned_turn") is None and approval < WARN_BELOW:
        soul.update(
            warned_turn=turn, warned_day=day, negative_after_warn=False, departure_pending=""
        )
        _push_reaction(soul, "aviso", turn)
    elif soul.get("warned_turn") is not None and approval >= CLEAR_WARN_AT:
        soul.update(
            warned_turn=None,
            warned_day=None,
            negative_after_warn=False,
            departure_pending="",
            departure_turn=None,
            betrayal_mode="",
        )
        soul["reactions"] = [
            r for r in (soul.get("reactions") or []) if r.get("tag") not in ("aviso", "despedida")
        ]
    return soul


def step_departure(
    soul: dict, *, turn: int, day: int, negative_after_warn: bool, traits: list[str]
) -> dict:
    """Marca a partida como pendente (PURA). Sem aviso prévio, NUNCA há partida (R14)."""
    soul = dict(soul)
    if soul.get("departure_pending") or soul.get("warned_turn") is None:
        return soul
    threshold = LOYAL_LEAVE_BELOW if soul.get("loyal") else LEAVE_BELOW
    if _int(soul.get("approval"), 50) >= threshold:
        return soul
    if turn <= _int(soul.get("warned_turn")):
        return soul
    day_turned = day > _int(soul.get("warned_day"), day)
    if not (day_turned or negative_after_warn):
        return soul
    mode_ = ""
    if not soul.get("loyal") and _int(soul.get("approval"), 50) < BETRAY_BELOW:
        mode_ = betrayal_mode(traits)
    soul["departure_pending"] = "betray" if mode_ else "leave"
    soul["betrayal_mode"] = mode_
    soul["departure_turn"] = turn
    _push_reaction(soul, "despedida", turn)
    return soul


# --------------------------------------------------------------------------- #
# R20-R22 — missão pessoal
# --------------------------------------------------------------------------- #
def _valid_location(loc: str) -> str:
    if not loc:
        return ""
    try:
        import gamedata

        return loc if gamedata.get_location(loc) else ""
    except Exception:  # silent-ok: local inválido apenas deixa a missão sem alvo
        return ""


def personal_quest_spec(state: dict, comp: dict) -> dict:
    """Texto 100% template/Codex (sem LLM). Fonte: gancho > traço > região > genérico."""
    from services import graph_resolver as gr

    _key, row = npc_row(state, comp)
    name = str(comp.get("name") or row.get("name") or "Companheiro")
    npc_id = str(comp.get("origin_npc") or row.get("id") or "")
    home = str(row.get("home_location_id") or "")
    ent = gr.get_entity(npc_id) if npc_id else None
    comps = (ent or {}).get("components") or {}
    hook = str(comps.get("hook") or "").strip()
    home = home or str(comps.get("home_location_id") or "")
    tpl = _quest_templates()
    place = home or "o lugar de onde veio"
    if hook:
        return {
            "title": f"O assunto de {name}",
            "description": hook,
            "reward_hint": f"a confiança de {name}",
            "location_id": _valid_location(home),
            "source": "hook",
        }
    chosen = None
    src = "fallback"
    for tid in _traits(row):
        if tid in (tpl.get("by_trait") or {}):
            chosen, src = tpl["by_trait"][tid], f"trait:{tid}"
            break
    if chosen is None:
        from services import reputation

        region = reputation.region_id_of(home) if home else ""
        by_region = tpl.get("by_region") or {}
        if (region or home) in by_region:
            chosen, src = by_region[region or home], "region"
    if chosen is None:
        chosen = tpl["fallback"]
    return {
        "title": chosen["title"].format(name=name),
        "description": chosen["description"].format(name=name, place=place),
        "reward_hint": chosen["reward_hint"].format(name=name),
        "location_id": _valid_location(home),
        "source": src,
    }


def quest_id_for(cid: str) -> str:
    return f"pq_{cid}"


def build_personal_quest(state: dict, comp: dict, *, turn: int) -> dict:
    spec = personal_quest_spec(state, comp)
    cid = comp_id(comp)
    return {
        "id": quest_id_for(cid),
        "title": spec["title"],
        "description": spec["description"],
        "status": "active",
        "origin_name": str(comp.get("name") or ""),
        "origin_entity_id": str(comp.get("origin_npc") or ""),
        "location_id": spec["location_id"],
        "created_turn": turn,
        "reward_hint": spec["reward_hint"],
        "progress_log": [{"kind": "created", "turn": turn, "detail": spec["source"]}],
        "completion_ready": False,
        "reward_delivered": False,
        "personal_of": cid,
    }


def reveal_ready(soul: dict) -> bool:
    return (
        soul.get("personal_quest") == "none"
        and _int(soul.get("approval")) >= PERSONAL_REVEAL_AT
        and _int(soul.get("rests_together")) >= 1
        and not soul.get("departed")
    )


# --------------------------------------------------------------------------- #
# R23-R25 — romance (fade-to-black; Python decide, a LLM só narra)
# --------------------------------------------------------------------------- #
def romance_blocked_by_traits(soul: dict, traits: list[str]) -> bool:
    """Traços de luto bloqueiam o romance até a missão pessoal ser concluída."""
    blockers = set(_tables().get("romance_blockers_until_personal_quest") or [])
    return bool(blockers & set(traits)) and soul.get("personal_quest") != "completed"


def romance_gate_open(soul: dict, traits: list[str], *, adult: bool = True) -> bool:
    return (
        romance_enabled()
        and adult
        and soul.get("romance") in ("none", "interesse", "vinculo", "compromisso")
        and not romance_blocked_by_traits(soul, traits)
        and _int(soul.get("approval")) >= ROMANCE_OPEN_AT
    )


def step_romance(
    soul: dict, *, traits: list[str], intent: bool, rest: bool, day: int, adult: bool = True
) -> dict:
    """Avança o estágio (PURA). Sem a flag de loja, o estágio nunca avança."""
    soul = dict(soul)
    stage = str(soul.get("romance") or "none")
    approval = _int(soul.get("approval"), 50)
    if not romance_enabled():
        return soul
    if stage in ("interesse", "vinculo", "compromisso") and approval < ROMANCE_BREAK_BELOW:
        soul["romance"] = "rompido"
        soul["romance_reopen_day"] = day + ROMANCE_REOPEN_DAYS
        return soul
    if stage == "rompido":
        if day >= _int(soul.get("romance_reopen_day"), day + 1):
            soul["romance"] = "none"
        return soul
    if not adult or romance_blocked_by_traits(soul, traits):
        return soul
    if stage == "none" and intent and approval >= ROMANCE_OPEN_AT:
        soul["romance"] = "interesse"
        soul["romance_rests"] = 0
    elif stage == "interesse" and rest:
        soul["romance_rests"] = _int(soul.get("romance_rests")) + 1
        if approval >= ROMANCE_BOND_AT and soul["romance_rests"] >= ROMANCE_BOND_RESTS:
            soul["romance"] = "vinculo"
    elif (
        stage == "vinculo"
        and rest
        and soul.get("personal_quest") == "completed"
        and approval >= ROMANCE_COMMIT_AT
    ):
        soul["romance"] = "compromisso"
    return soul


# --------------------------------------------------------------------------- #
# Writer único
# --------------------------------------------------------------------------- #
def _event(etype: str, turn: int, target: str, payload: dict, *, source: str = "engine") -> dict:
    return {
        "event_id": uuid.uuid4().hex,
        "turn": turn,
        "type": etype,
        "actor_id": "system",
        "target_id": target,
        "payload": payload,
        "source": source,
    }


def _is_dead(comp: dict) -> bool:
    return bool(comp.get("dead")) or str(comp.get("status") or "").lower() in ("morto", "dead")


def _last_human(state: dict) -> str:
    return ctags._last_human_text(state)


def _rest_turn(state: dict) -> bool:
    from world_utils import is_rest

    text = _last_human(state)
    if not text or not is_rest(text):
        return False
    combat = state.get("combat") or {}
    if combat.get("phase") in ("entering", "active", "resolving"):
        return False
    try:  # P2-5: descanso bloqueado pelo clima não recupera nada nem conta como convivência
        from world_utils import weather_effects

        if weather_effects(_world(state)).get("rest_block", False):
            return False
    except Exception:  # silent-ok: sem dado de clima, vale a regex
        pass
    return True


def _soul_for_quest(souls: dict, quest: dict) -> str:
    return str(quest.get("personal_of") or "")


def _fail_personal_quest(
    quests: list[dict], soul: dict, cid: str, *, turn: int, events: list[dict], name: str
) -> list[dict]:
    """Missão pessoal ativa de ``cid`` -> failed (evento ``quest_failed``)."""
    out = []
    for q in quests:
        if q.get("personal_of") == cid and q.get("status") == "active":
            q = {**q, "status": "failed", "resolved_turn": turn}
            events.append(
                _event(
                    "quest_failed",
                    turn,
                    cid,
                    {
                        "quest_id": q["id"],
                        "quest_title": q.get("title", ""),
                        "reason": "companion_gone",
                        "personal_of": cid,
                    },
                    source="system",
                )
            )
            soul["personal_quest"] = "failed"
        out.append(q)
    return out


def _acks(state: dict) -> set[str]:
    return {str(a) for a in (state.get("companion_voice_ack") or [])}


def apply_turn(state: dict) -> dict:
    """Writer único (R19). Devolve updates parciais; ``off`` = no-op."""
    from observability.telemetry import log_event
    from party import active_allies
    from services import chronicle as chron

    current_mode = mode()
    if current_mode == "off":
        return {}
    party = [dict(c) for c in (state.get("party") or []) if isinstance(c, dict)]
    souls: dict[str, dict] = {
        k: deepcopy(v)
        for k, v in (state.get("companion_souls") or {}).items()
        if isinstance(v, dict)
    }
    if not party and not souls:
        return {}
    turn, day = _turn(state), _day(state)
    live = current_mode == "on"
    ack = _acks(state)
    npcs = dict(state.get("npcs") or {})
    quests = [dict(q) for q in (state.get("quests") or []) if isinstance(q, dict)]
    events: list[dict] = []
    feedback: list[str] = []
    player = dict(state.get("player") or {})
    chronicle = list(state.get("chronicle") or [])
    gold_taken = 0
    changed_party = False
    changed_npcs = False
    changed_quests = False
    rest = _rest_turn(state)
    present_ids = {comp_id(c) for c in active_allies(state)}
    in_party_ids = {comp_id(c) for c in party if not c.get("transient")}
    cur_combat = ctags.combat_result_id(state)

    # 1. alma lazy / reencontro (R17) --------------------------------------- #
    for comp in party:
        if comp.get("transient"):
            continue
        cid = comp_id(comp)
        if not cid:
            continue
        if cid not in souls:
            souls[cid] = ensure_soul(state, comp)
        elif souls[cid].get("departed") and not _is_dead(comp):
            if souls[cid].get("departed") == "betrayed":
                continue  # R17: quem traiu nunca mais volta
            soul = souls[cid]
            # P2-1: o teto vale só para quem PARTIU; dispensado volta com a aprovação que tinha
            revived = (
                min(REVIVE_CAP, _int(soul.get("approval")) + REVIVE_BONUS)
                if soul.get("departed") == "left"
                else _int(soul.get("approval"))
            )
            soul.update(
                departed="",
                approval=revived,
                warned_turn=None,
                warned_day=None,
                departure_pending="",
                departure_turn=None,
                negative_after_warn=False,
                reactions=[],
                last_combat=cur_combat,
            )

    # 2. quem saiu do grupo sem a alma saber (dispensado / morto) ------------ #
    for cid, soul in souls.items():
        if soul.get("departed"):
            continue
        comp = next((c for c in party if comp_id(c) == cid), None)
        gone = comp is None
        dead = comp is not None and _is_dead(comp)
        if comp is None:  # P2-6: saiu da party porque morreu? (ficha do NPC / evento)
            _k, _row = npc_row(state, {"origin_npc": cid, "name": soul.get("npc_key") or cid})
            dead = bool(_row) and _is_dead(_row)
        if gone or dead:
            soul["departed"] = "dead" if dead else "dismissed"
            soul["left_party_day"] = day
            quests = _fail_personal_quest(quests, soul, cid, turn=turn, events=events, name=cid)
            changed_quests = True

    # 3. tags -> aprovação (só testemunhas, R7) ------------------------------ #
    tags = ctags.detect_choice_tags(state)
    for cid in sorted(present_ids & in_party_ids):
        soul = souls.get(cid)
        if soul is None or soul.get("departed"):
            continue
        comp = next(c for c in party if comp_id(c) == cid)
        _key, row = npc_row(state, comp)
        from services import reputation

        faction = reputation.npc_faction_id(row or comp)
        # consome o que foi narrado (R13) antes de enfileirar as novas reações
        soul["reactions"] = [
            r
            for r in (soul.get("reactions") or [])
            if f"r:{cid}:{r.get('id')}" not in ack and turn - _int(r.get("turn")) <= REACTION_TTL
        ]
        mine = [
            t
            for t in tags
            if not (t["source_ref"].startswith("combat:") and soul.get("last_combat") == cur_combat)
        ]
        soul2, delta = apply_tags(soul, mine, turn=turn, companion_faction=faction)
        soul.clear()
        soul.update(soul2)
        soul["last_seen_day"] = day
        phrase = change_phrase(str(comp.get("name") or cid), delta)
        if phrase and abs(delta) >= 4:
            feedback.append(phrase)
        # descanso (R21/R23): conta convivência
        if rest:
            soul["rests_together"] = _int(soul.get("rests_together")) + 1
    for soul in souls.values():
        if cur_combat:
            soul["last_combat"] = cur_combat

    # 4. aviso / partida pendente (R14-R15) ---------------------------------- #
    for cid in sorted(in_party_ids):
        soul = souls[cid]
        if soul.get("departed"):
            continue
        comp = next(c for c in party if comp_id(c) == cid)
        _key, row = npc_row(state, comp)
        before_warn = soul.get("warned_turn")
        soul2 = update_warning(soul, turn=turn, day=day)
        soul2 = step_departure(
            soul2,
            turn=turn,
            day=day,
            negative_after_warn=bool(soul2.get("negative_after_warn")),
            traits=_traits(row),
        )
        soul.clear()
        soul.update(soul2)
        name = str(comp.get("name") or cid)
        if before_warn is None and soul.get("warned_turn") is not None and live:
            feedback.append(f"{name} está perdendo a paciência com você.")

    # 5. romance (Python decide) --------------------------------------------- #
    if live and romance_enabled():
        for cid in sorted(present_ids & in_party_ids):
            soul = souls.get(cid)
            if soul is None or soul.get("departed"):
                continue
            comp = next(c for c in party if comp_id(c) == cid)
            _key, row = npc_row(state, comp)
            before = soul.get("romance")
            soul2 = step_romance(
                soul,
                traits=_traits(row),
                intent=f"intent:{cid}:romance" in ack,
                rest=rest,
                day=day,
                adult=_int(row.get("age"), 18) >= 18 if row else True,
            )
            soul.clear()
            soul.update(soul2)
            if soul.get("romance") != before:
                _push_reaction(soul, "estagio", turn)

    # 6. missão pessoal (R20-R22) -------------------------------------------- #
    here = _here(state)
    if live:
        for cid in sorted(present_ids & in_party_ids):
            soul = souls.get(cid)
            if soul is None or soul.get("departed"):
                continue
            comp = next(c for c in party if comp_id(c) == cid)
            has_quest = any(q.get("personal_of") == cid for q in quests)
            if (
                rest
                and not has_quest
                and f"topic:{cid}:quest" in ack
                and reveal_ready({**soul, "rests_together": _int(soul.get("rests_together"))})
            ):
                quests.append(build_personal_quest(state, comp, turn=turn))
                soul["personal_quest"] = "revealed"
                changed_quests = True
                log_event("companion", "personal_quest_revealed", level="info")
            for q in quests:
                if q.get("personal_of") != cid or q.get("status") != "active":
                    continue
                if (
                    soul.get("personal_quest") == "revealed"
                    and turn > _int(q.get("created_turn"))  # chegar DEPOIS de saber da missão
                    and q.get("location_id")
                    and q.get("location_id") == here
                ):
                    q["completion_ready"] = True
                    q["progress_log"] = [
                        *(q.get("progress_log") or []),
                        {"kind": "completion_ready", "turn": turn, "detail": here},
                    ]
                    soul["personal_quest"] = "ready"
                    soul["quest_ready_turn"] = turn
                    _push_reaction(soul, "resolucao", turn)
                    changed_quests = True
                elif soul.get("personal_quest") == "ready" and turn > _int(
                    soul.get("quest_ready_turn")
                ):
                    narrated = f"topic:{cid}:resolve" in ack
                    stale = turn - _int(soul.get("quest_ready_turn")) >= REACTION_TTL
                    if narrated or stale:
                        from services import quest_log

                        quests = quest_log.complete_quest(quests, q["id"], turn=turn)
                        soul["personal_quest"] = "completed"
                        soul["approval"] = _clamp(
                            _int(soul.get("approval")) + PERSONAL_DONE_BONUS, 0, 100
                        )
                        if soul["approval"] >= LOYAL_AT:
                            soul["loyal"] = True
                        events.append(
                            _event(
                                "quest_completed",
                                turn,
                                q["id"],
                                {
                                    "quest_id": q["id"],
                                    "quest_title": q.get("title", ""),
                                    "personal_of": cid,
                                },
                                source="system",
                            )
                        )
                        changed_quests = True
                        log_event("companion", "personal_quest_completed", level="info")
                        break

    # 7. execução da partida (R15/R16) --------------------------------------- #
    combat_active = (state.get("combat") or {}).get("phase") in ("entering", "active", "resolving")
    if live and not combat_active:
        for cid in sorted(in_party_ids):
            soul = souls.get(cid)
            if soul is None or soul.get("departed") or not soul.get("departure_pending"):
                continue
            if turn <= _int(soul.get("departure_turn")):
                continue
            # P2-4: só sai depois de a despedida ser NARRADA (companheiro presente);
            # sem narração o motor adia — nunca parte em silêncio.
            narrated = any(a.startswith(f"r:{cid}:") and a.endswith(":despedida") for a in ack)
            if not (narrated and cid in present_ids):
                continue
            comp = next(c for c in party if comp_id(c) == cid)
            name = str(comp.get("name") or cid)
            betray = soul["departure_pending"] == "betray"
            key, row = npc_row(state, comp)
            party = [c for c in party if comp_id(c) != cid]
            changed_party = True
            if key:
                new_row = dict(row)
                new_row["in_scene"] = False
                new_row["left_party_day"] = day
                rel = new_row.get("relationship")
                rel_i = 5 if rel is None else _int(rel, 5)
                new_row["relationship"] = 0 if betray else max(0, rel_i - 2)
                npcs[key] = new_row
                changed_npcs = True
            soul["departed"] = "betrayed" if betray else "left"
            soul["left_party_day"] = day
            soul["departure_pending"] = ""
            taken = 0
            if betray:
                soul["grudge"] = True
                if soul.get("betrayal_mode") == "steal":
                    taken = max(
                        0,
                        min(int(_int(player.get("gold")) * BETRAY_GOLD_FRACTION), BETRAY_GOLD_CAP),
                    )
                    player["gold"] = _int(player.get("gold")) - taken
                    gold_taken += taken
                else:  # deliver: hook para SPEC-299/302 (aviso a inimigos/lei -> emboscada)
                    soul["deliver_pending"] = True
            ev = _event(
                "companion_betrayed" if betray else "companion_left",
                turn,
                cid,
                {"name": name, "mode": soul.get("betrayal_mode") or "", "gold": taken},
            )
            events.append(ev)
            feedback.append(
                f"{name} traiu a sua confiança e partiu." if betray else f"{name} deixou o grupo."
            )
            quests = _fail_personal_quest(quests, soul, cid, turn=turn, events=events, name=name)
            changed_quests = True
            log_event("companion", "betrayed" if betray else "left", level="info")

    # 7b. destino SELADO de quem foi deixado na fuga (SPEC-325 R12) ------------- #
    if live:
        for cid in sorted({comp_id(c) for c in party if isinstance(c.get("pending_fate"), dict)}):
            comp = next((c for c in party if comp_id(c) == cid), None)
            soul = souls.get(cid)
            if comp is None or soul is None or not cid:
                continue
            pf = comp["pending_fate"]
            pday = _int(pf.get("day"), day)
            location = str(pf.get("location_id") or comp.get("waiting_at") or "")
            tele = [
                t
                for t in (soul.get("telegraphs") or [])
                if isinstance(t, dict) and t.get("source") == "abandono"
            ]
            if not any(_int(t.get("day")) == pday and not t.get("cancelled") for t in tele):
                # o próprio abandono é o telegrama (D1); o combate não escreve na alma
                soul["telegraphs"] = [
                    *(soul.get("telegraphs") or []),
                    {
                        "kind": "pedido_de_ajuda",
                        "day": pday,
                        "turn": turn,
                        "cancelled": False,
                        "source": "abandono",
                    },
                ][-5:]
            if comp.get("active") or (here == location and not combat_active):
                comp.pop("pending_fate", None)  # resgate: o herói voltou antes de 1 dia
                for t in soul.get("telegraphs") or []:
                    if isinstance(t, dict) and t.get("source") == "abandono":
                        t["cancelled"] = True
                changed_party = True
                log_event("companion", "abandon_rescued", level="info")
                continue
            if combat_active or day - pday < TELEGRAPH_MIN_DAYS:
                continue
            fate = str(pf.get("fate") or "")
            if not fate:  # fuga/esconderijo/reencontro: volta a esperar sem dano
                comp.pop("pending_fate", None)
                changed_party = True
                log_event("companion", "abandon_fate_none", level="info")
                continue
            interim = {
                **state,
                "party": party,
                "npcs": npcs,
                "companion_souls": souls,
                "quests": quests,
                "event_log": list(state.get("event_log") or []) + events,
                "chronicle": chronicle,
            }
            try:
                patch = apply_companion_fate(interim, cid, fate, day)
            except FateNotTelegraphed:
                continue
            events.extend(patch["event_log"][len(interim["event_log"]) :])
            party, npcs, souls, quests = (
                patch["party"],
                patch["npcs"],
                patch["companion_souls"],
                patch["quests"],
            )
            for member in party:
                if comp_id(member) == cid:
                    member.pop("pending_fate", None)
            changed_party = changed_npcs = changed_quests = True
            name = str(comp.get("name") or cid)
            feedback.append(
                f"Chegam notícias de {name}: "
                + {
                    "ferido": "ficou ferido ao ser deixado para trás.",
                    "capturado": "foi capturado.",
                    "morto": "não sobreviveu à separação.",
                }[fate]
            )
            log_event("companion", "abandon_fate_applied", level="info", fate=fate)

    # 8. escrita ---------------------------------------------------------------- #
    updates: dict[str, Any] = {"companion_souls": souls, "companion_voice_ack": None}
    if changed_party:
        updates["party"] = party
    if changed_npcs:
        updates["npcs"] = npcs
    if changed_quests:
        updates["quests"] = quests
    if events:
        log = list(state.get("event_log") or []) + events
        updates["event_log"] = log
        for ev in events:
            text = chron.render_milestone(ev, state.get("world_projection") or {})
            if text:
                chronicle = chron.append_entry(
                    chronicle, text=text, turn=turn, kind="milestone", event_id=ev["event_id"]
                )
        updates["chronicle"] = chronicle
    if gold_taken:
        updates["player"] = player
    updates["companion_feedback"] = feedback if live else []
    return updates


# --------------------------------------------------------------------------- #
# Interfaces para outras specs (R26/R27) — contrato + testes com dublê
# --------------------------------------------------------------------------- #
def companions_exposed(state: dict) -> list[dict]:
    """Companheiros VIVOS esperando longe do jogador (alvo do perigo off-screen)."""
    import gamedata

    day = _day(state)
    souls = state.get("companion_souls") or {}
    out = []
    for comp in state.get("party") or []:
        if not isinstance(comp, dict) or comp.get("active") or not comp.get("waiting_at"):
            continue
        if _is_dead(comp) or comp.get("pending_fate"):  # SPEC-325: destino já selado no abandono
            continue
        cid = comp_id(comp)
        soul = souls.get(cid) or {}
        if soul.get("departed"):
            continue
        loc = str(comp["waiting_at"])
        info = gamedata.get_location(loc) or {}
        out.append(
            {
                "companion_id": cid,
                "location_id": loc,
                "days_away": max(0, day - _int(soul.get("last_seen_day"), day)),
                "danger_level": _int(info.get("danger_level")),
            }
        )
    return out


def telegraph_companion_danger(state: dict, companion_id: str, kind: str, day: int) -> dict:
    """Registra o aviso ao jogador (rumor / pedido de ajuda). Devolve ``{companion_souls}``."""
    if kind not in ("rumor", "pedido_de_ajuda"):
        raise ValueError(f"kind inválido: {kind}")
    souls = deepcopy(state.get("companion_souls") or {})
    soul = souls.get(companion_id)
    if soul is None:
        raise KeyError(companion_id)
    soul["telegraphs"] = [
        *(soul.get("telegraphs") or []),
        {"kind": kind, "day": int(day), "turn": _turn(state), "cancelled": False},
    ][-5:]
    return {"companion_souls": souls}


def _fate_gate(state: dict, companion_id: str, day: int) -> None:
    soul = (state.get("companion_souls") or {}).get(companion_id) or {}
    comp = next(
        (c for c in state.get("party") or [] if isinstance(c, dict) and comp_id(c) == companion_id),
        None,
    )
    live_tel = [t for t in (soul.get("telegraphs") or []) if not t.get("cancelled")]
    if not live_tel or comp is None:
        raise FateNotTelegraphed(f"{companion_id}: sem telegrama")
    if int(day) - min(_int(t.get("day")) for t in live_tel) < TELEGRAPH_MIN_DAYS:
        raise FateNotTelegraphed(f"{companion_id}: telegrama do mesmo dia")
    if comp.get("active") or not comp.get("waiting_at"):
        raise FateNotTelegraphed(f"{companion_id}: jogador chamou o companheiro")
    if _here(state) == str(comp.get("waiting_at")):
        raise FateNotTelegraphed(f"{companion_id}: jogador voltou ao local")


def apply_companion_fate(state: dict, companion_id: str, fate: str, day: int) -> dict:
    """Aplica ``ferido|capturado|morto`` — RECUSA sem telegrama válido (R26). Updates parciais."""
    if fate not in ("ferido", "capturado", "morto"):
        raise ValueError(f"fate inválido: {fate}")
    _fate_gate(state, companion_id, day)
    from services import chronicle as chron
    from services import npc_layers

    turn = _turn(state)
    party = [dict(c) for c in state.get("party") or [] if isinstance(c, dict)]
    npcs = dict(state.get("npcs") or {})
    souls = deepcopy(state.get("companion_souls") or {})
    quests = [dict(q) for q in state.get("quests") or [] if isinstance(q, dict)]
    soul = souls[companion_id]
    comp = next(c for c in party if comp_id(c) == companion_id)
    name = str(comp.get("name") or companion_id)
    events: list[dict] = []
    if fate == "morto":
        npcs, party = npc_layers.apply_npc_death(npcs, party, name, turn)
        soul["departed"] = "dead"
        soul["left_party_day"] = int(day)
        quests = _fail_personal_quest(
            quests, soul, companion_id, turn=turn, events=events, name=name
        )
    elif fate == "capturado":
        comp["status"] = "capturado"
        comp["active"] = False
    else:
        comp["vitalidade"] = max(1, _int(comp.get("vitalidade"), 2) // 2)
    events.append(
        _event("companion_fate", turn, companion_id, {"name": name, "fate": fate, "day": int(day)})
    )
    if fate != "morto":
        party = [comp if comp_id(c) == companion_id else c for c in party]
    chronicle = list(state.get("chronicle") or [])
    for ev in events:
        text = chron.render_milestone(ev, state.get("world_projection") or {})
        if text:
            chronicle = chron.append_entry(
                chronicle, text=text, turn=turn, kind="milestone", event_id=ev["event_id"]
            )
    return {
        "party": party,
        "npcs": npcs,
        "companion_souls": souls,
        "quests": quests,
        "event_log": list(state.get("event_log") or []) + events,
        "chronicle": chronicle,
    }


def pending_betrayal_deliveries(state: dict) -> list[str]:
    """Ids de ex-companheiros que ENTREGAM o jogador (consumido por SPEC-299/302)."""
    return [
        cid
        for cid, soul in (state.get("companion_souls") or {}).items()
        if isinstance(soul, dict) and soul.get("deliver_pending")
    ]
