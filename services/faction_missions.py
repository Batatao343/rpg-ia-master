"""SPEC-301 R11 — Missões de fação geradas pelo motor (nunca pelo LLM).

Título e descrição vêm do template autorado em ``data/faction_membership.json``; o motor só
escolhe qual (seed ``game_id:fid:turn``), resolve o local no mapa e cria a ``Quest`` com os
campos ``faction_id``/``mission_kind``/``mission_tier``/``target_faction_id``.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Mapping

import gamedata
from services import faction_membership as fm
from services import quest_log


def _valid_locations() -> set[str]:
    return quest_log._valid_location_ids()


def _seed(state: Mapping, fid: str) -> str:
    world = state.get("world") or {}
    return f"{state.get('game_id', '')}:{fid}:{int(world.get('turn_count', 0) or 0)}"


def _resolve_location(template: Mapping, rng: random.Random) -> tuple[bool, str]:
    """(utilizável, location_id). Sem ``location_ids`` = missão sem local (entrega ao NPC)."""
    wanted = [str(x) for x in (template.get("location_ids") or [])]
    if not wanted:
        return True, ""
    valid = _valid_locations()
    cands = [x for x in wanted if x in valid]
    if not cands:
        return False, ""
    return True, rng.choice(sorted(cands))


def mission_quest_from_template(
    template: Mapping, faction_id: str, turn: int, location_id: str, seed: str
) -> dict:
    kind = str(template.get("kind") or "apoio")
    quest = {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{template.get('id')}").hex,
        "title": str(template.get("title") or ""),
        "description": str(template.get("description") or ""),
        "status": "active",
        "origin_name": "",
        "origin_entity_id": "",
        "location_id": location_id,
        "created_turn": int(turn),
        "resolved_turn": 0,
        "reward_hint": "",
        "progress_log": [{"kind": "created", "turn": int(turn), "detail": ""}],
        "reward_gold": 0,
        "reward_delivered": False,
        "faction_id": faction_id,
        "mission_kind": kind,
        "mission_tier": max(1, min(3, int(template.get("tier") or 1))),
    }
    if kind == "sabotagem":
        quest["target_faction_id"] = str(template.get("target_faction_id") or "")
    return quest


def _active_count(quests: list[dict]) -> int:
    return sum(1 for q in quests if q.get("status") == "active")


def _has_active_mission(quests: list[dict], fid: str) -> bool:
    return any(
        q.get("faction_id") == fid
        and q.get("status") == "active"
        and q.get("mission_kind") != "rito"
        for q in quests
    )


def _templates(fid: str, kinds: tuple[str, ...]) -> list[dict]:
    return [
        t
        for t in (fm._cat(fid).get("mission_templates") or [])
        if isinstance(t, dict) and t.get("kind") in kinds
    ]


def offer_mission(state: Mapping, faction_id: str) -> tuple[list[dict], dict | None, str]:
    """-> (quests atualizadas, nova quest | None, nota). Sem mudança quando não há quest."""
    fid = str(faction_id or "")
    quests = [dict(q) for q in (state.get("quests") or []) if isinstance(q, dict)]
    rec = fm._record(state, fid)
    if rec.get("status") not in fm.ACTIVE_STATUSES:
        return quests, None, fm.refusal_note(state, fid, "nao_membro")
    if _has_active_mission(quests, fid):
        return quests, None, fm.refusal_note(state, fid, "missao_ativa")
    if _active_count(quests) >= quest_log.MAX_ACTIVE_QUESTS:
        return quests, None, fm.refusal_note(state, fid, "missoes_cheias")
    rank = fm._int(rec.get("rank_index"))
    seed = _seed(state, fid)
    rng = random.Random(seed)
    done_ids = {q.get("id") for q in quests}
    members = fm.active_memberships(state)
    pool: list[tuple[dict, str]] = []
    for t in sorted(_templates(fid, ("apoio", "sabotagem")), key=lambda x: str(x.get("id"))):
        if fm._int(t.get("min_rank")) > rank:
            continue
        if t.get("kind") == "sabotagem":
            target = str(t.get("target_faction_id") or "")
            row = fm._faction_row(state, target)
            if not row or row.get("defeated") or target in members:
                continue
        ok, loc = _resolve_location(t, rng)
        if not ok:
            continue
        pool.append((t, loc))
    if not pool:
        return quests, None, fm.refusal_note(state, fid, "sem_missao")
    # evita repetir a mesma missão enquanto houver outra disponível
    fresh = [
        (t, loc)
        for t, loc in pool
        if mission_quest_from_template(t, fid, 0, loc, seed)["id"] not in done_ids
        and not any(q.get("title") == t.get("title") and q.get("faction_id") == fid for q in quests)
    ]
    template, loc = rng.choice(fresh or pool)
    turn = fm._turn(state)
    quest = mission_quest_from_template(template, fid, turn, loc, seed)
    quests.append(quest)
    note = (
        f'[FAÇÃO] {fm.faction_name(state, fid)} lhe confia uma missão: "{quest["title"]}". '
        f"{quest['description']}"
    )
    return quests, quest, note


def rite_quest(state: Mapping, faction_id: str) -> tuple[list[dict], dict | None, str]:
    """Missão de rito de entrada (R4), a partir do template ``kind="rito"`` da fação."""
    fid = str(faction_id or "")
    quests = [dict(q) for q in (state.get("quests") or []) if isinstance(q, dict)]
    if _active_count(quests) >= quest_log.MAX_ACTIVE_QUESTS:
        return quests, None, fm.refusal_note(state, fid, "missoes_cheias")
    rng = random.Random(_seed(state, fid))
    for t in _templates(fid, ("rito",)):
        ok, loc = _resolve_location(t, rng)
        if ok:
            quest = mission_quest_from_template(t, fid, fm._turn(state), loc, _seed(state, fid))
            quests.append(quest)
            return quests, quest, ""
    return quests, None, fm.refusal_note(state, fid, "sem_missao")


def mission_locations_exist(fid: str) -> bool:
    """Lint: todo template tem ao menos um local no mapa."""
    return all(
        not (t.get("location_ids")) or any(gamedata.get_location(x) for x in t["location_ids"])
        for t in fm._cat(fid).get("mission_templates") or []
    )
