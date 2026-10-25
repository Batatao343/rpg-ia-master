"""SPEC-309 Etapa 1 (R1-R5, R20, R21): templates do motor em `render_event`."""

from __future__ import annotations

import re

import pytest

from services import world_director as wd
from services.context_builder import render_event

_PREFIX = re.compile(r"^\[turno \d+\] ")

_CASES = [
    (
        "location_state_changed",
        "brekmar",
        {"state": "cerco", "previous": "", "severity": 2, "crisis_id": "c1", "cause": "guerra"},
        "Brekmar agora está sitiada.",
    ),
    (
        "location_state_changed",
        "skallgard",
        {"state": "festa", "previous": "", "cause": "calendario", "festival_id": "noite_dos_nomes"},
        "Skallgard está em luto: Noite dos Nomes.",
    ),
    (
        "location_state_changed",
        "brekmar",
        {"state": "", "previous": "cerco", "severity": 0, "crisis_id": "c1"},
        "Brekmar não está mais sitiada.",
    ),
    (
        "world_crisis_warning",
        "skallgard",
        {"kind": "guerra", "region_id": "skallgard", "crisis_id": "c2", "earliest_day": 9},
        "Há sinais de guerra em",
    ),
    ("companion_left", "c1", {"name": "Mira"}, "Mira deixou o grupo."),
    ("companion_betrayed", "c1", {"name": "Mira", "gold": 50}, "Mira traiu o grupo e partiu."),
    ("companion_fate", "c1", {"name": "Mira", "fate": "morto"}, "Mira não voltou"),
    (
        "crime_witnessed",
        "crime1",
        {"crime_type": "furto", "location_id": "brekmar", "jurisdiction_id": "j"},
        "Houve um furto em Brekmar.",
    ),
    ("quest_failed", "q1", {"quest_title": "O Sino"}, "Missão fracassada: O Sino."),
    (
        "npc_fate_learned",
        "n1",
        {"name": "Orik", "fate": "morto", "location_id": "brekmar"},
        "Chegou a notícia: Orik morreu em Brekmar.",
    ),
]


def _ev(etype, target, payload, turn=7):
    return {
        "type": etype,
        "target_id": target,
        "payload": payload,
        "turn": turn,
        "actor_id": "engine",
    }


@pytest.mark.parametrize("etype,target,payload,expected", _CASES)
def test_each_new_type_renders_nonempty(etype, target, payload, expected):
    """R1."""
    text = render_event(_ev(etype, target, payload))
    assert _PREFIX.match(text), text
    assert expected in text


@pytest.mark.parametrize("etype,target,payload,expected", _CASES)
def test_no_digits_besides_turn_prefix(etype, target, payload, expected):
    """R2: nenhum numero fora do `[turno N]`."""
    body = _PREFIX.sub("", render_event(_ev(etype, target, payload)))
    assert body and not re.search(r"\d", body)
    for word in ("severidade", "pressão", "tensão", "fase", "banda", "multa", "recompensa"):
        assert word not in body.lower()


def test_law_resolved_and_unique_items():
    from services import law_codes

    code = next(iter(law_codes._load()["codes"].values()), None)
    if code:
        text = render_event(
            _ev("law_resolved", code["id"], {"jurisdiction_id": code["id"], "mode": "fine"})
        )
        assert code["name"] in text and "multa paga" in text
        assert not re.search(r"\d", _PREFIX.sub("", text))
    import gamedata

    art = next(iter(gamedata.ARTIFACTS_DB))
    name = gamedata.ARTIFACTS_DB[art]["name"]
    assert name in render_event(_ev("unique_item_claimed", art, {"holder": "player"}))
    assert name in render_event(_ev("unique_item_lost", art, {"holder": "mercador"}))


def test_unknown_faction_not_named():
    """R3: aviso de guerra nao carrega nome de faccao do catalogo."""
    ev = wd._ev(
        "g",
        3,
        "world_crisis_warning",
        "skallgard",
        {
            "kind": "guerra",
            "region_id": "skallgard",
            "crisis_id": "c",
            "faction_id": "clas_combate",
        },
    )
    import gamedata

    text = render_event(ev)
    fac = gamedata.FACTIONS.get("clas_combate") or {}
    assert text and (not fac.get("name") or fac["name"] not in text)


def test_unique_item_other_holder_is_empty():
    assert render_event(_ev("unique_item_claimed", "x", {"holder": "mercador"})) == ""


def test_npc_fate_learned_only_dead_or_captured():
    assert render_event(_ev("npc_fate_learned", "n", {"name": "A", "fate": "ferido"})) == ""
    assert "foi capturado" in render_event(
        _ev("npc_fate_learned", "n", {"name": "A", "fate": "capturado"})
    )


def test_unknown_key_drops_sentence():
    assert (
        render_event(_ev("crime_witnessed", "c", {"crime_type": "xyz", "location_id": "brekmar"}))
        == ""
    )
    assert render_event(_ev("law_resolved", "j", {"jurisdiction_id": "j", "mode": "xyz"})) == ""
    assert (
        render_event(_ev("world_crisis_warning", "s", {"kind": "xyz", "region_id": "skallgard"}))
        == ""
    )


@pytest.mark.parametrize(
    "etype", sorted({c[0] for c in _CASES} | {"law_resolved", "unique_item_lost"})
)
def test_legacy_payload_does_not_raise(etype):
    """R21: payload vazio nunca levanta."""
    assert isinstance(render_event({"type": etype, "turn": 1}), str)
    assert isinstance(render_event({"type": etype, "turn": 1, "payload": None}), str)


def test_unknown_type_still_empty():
    assert render_event({"type": "algo_novo", "turn": 1}) == ""


def test_impact_weights_registered():
    from services.context_builder import _IMPACT_BY_TYPE

    assert _IMPACT_BY_TYPE["location_state_changed"] == 0.9
    assert _IMPACT_BY_TYPE["npc_fate_learned"] == 0.9


def test_npc_knowledge_subject_text_for_state_change():
    """R20: rumor de NPC ganha texto, sem numero."""
    from services import npc_knowledge

    ev = wd._ev(
        "g",
        3,
        "location_state_changed",
        "brekmar",
        {
            "state": "cerco",
            "previous": "",
            "severity": 3,
            "crisis_id": "c",
            "cause": "guerra",
            "day": 3,
        },
    )
    text = npc_knowledge._subject_text({"event_log": [ev]}, "event", ev["event_id"])
    assert "sitiada" in text
    assert not re.search(r"\d", _PREFIX.sub("", text))
