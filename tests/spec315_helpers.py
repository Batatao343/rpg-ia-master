"""Helpers dos testes da SPEC-315 (rumores adotados pelo motor)."""

from __future__ import annotations

from services import rumors
from tests.spec312_helpers import base_state

TEXT = "Dizem nas docas que alguém escondeu algo valioso muito longe daqui"
HERE = "brekmar"
FAR = "floresta_sussurros"
CREATURE = "enemy_rato_peste_anel_lama"


def set_flags(monkeypatch, adopted: str = "on") -> None:
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_RUMORS_PROPOSED", "on")
    monkeypatch.setenv("RPG_RUMORS_ADOPTED", adopted)
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def state(day: int = 5, loc: str = HERE, **extra) -> dict:
    extra.setdefault("world_sim", {})
    extra.setdefault("messages", [])
    return base_state(day, loc, player={"name": "Aldric", "level": 1, "gold": 0}, **extra)


def claim(kind: str = "esconderijo", loc: str = FAR, entity: str = "") -> dict:
    return {"kind": kind, "location_id": loc, "entity_id": entity}


def adopted_row(
    rid: str = "r1",
    kind: str = "esconderijo",
    loc: str = FAR,
    *,
    truth: bool = True,
    born: int = 4,
    expires: int = 14,
    entity: str = "",
    materialized: int = 0,
    resolution: str = "",
) -> dict:
    return {
        "rumor_id": rid * 4 if len(rid) < 12 else rid,
        "seed_id": "narrador:" + rid,
        "family": "narrador",
        "location_id": loc,
        "entities": ["brekmar"],
        "subject": "lugar",
        "truth": truth,
        "quest_eligible": True,
        "adopted": True,
        "claim": claim(kind, loc, entity),
        "materialized_day": materialized,
        "born_day": born,
        "born_turn": born,
        "expires_day": expires,
        "perceived_day": born,
        "text": "Dizem que escondem algo",
        "resolution": resolution,
    }


def with_rows(st: dict, *rows: dict) -> dict:
    sim = dict(st.get("world_sim") or {})
    sim["rumors"] = [*(sim.get("rumors") or []), *rows]
    return {**st, "world_sim": sim}


def proposal(**kw):
    from services.structured_outputs import ProposedRumorWithClaim

    data = {"text": TEXT, "entity_ids": ["brekmar"], "location_id": ""}
    data.update(kw)
    return ProposedRumorWithClaim(**data)


def accept(st: dict, props, *, day: int = 5, quarantined: bool = False):
    extra: dict = {}
    sim, world, why = rumors.accept_proposed(
        st, props, turn=day, day=day, quarantined=quarantined, extra=extra
    )
    return sim, world, why, extra
