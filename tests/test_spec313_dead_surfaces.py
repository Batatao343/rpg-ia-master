"""SPEC-313 Etapa 7: recolher_mortos, falha neutra e superficies (API/prompt)."""

from __future__ import annotations

import json
import re

import pytest

from services import event_processor as ep
from services import lore_quests as lq
from services import quest_log
from services import world_pressures as wp
from services import world_quests as wq
from tests.spec305_helpers import add_crisis, base_state, crisis_item
from tests.spec313_helpers import NPC_KEY, first_anchor, npc_state, proposal, setup_env

FORBIDDEN = ("morreu", "morto", "boato", "verdade", "fugiu")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def _escalated():
    st = base_state()
    rec = add_crisis(st, "praga", "brekmar", cid="praga-1")
    rec["severity"] = 2
    item = crisis_item("praga", "brekmar", "brekmar", tpl="crise.escala", item_kind="escala")
    return st, item


def test_dead_quest_from_perceived_escalation_once_per_crisis():
    st, item = _escalated()
    quests, created = wq.offer_from_perceived(st, [item], 17)
    dead = [q for q in created if q["world_kind"] == "recolher_mortos"]
    assert len(dead) == 1 and dead[0]["world_source_id"] == "mortos:praga-1"
    assert dead[0]["deadline_day"] == 17 + 4 and dead[0]["reward_gold_planned"] == 15
    st["quests"] = quests
    again, created2 = wq.offer_from_perceived(st, [item], 18)
    assert not [q for q in created2 if q["world_kind"] == "recolher_mortos"]
    assert len([q for q in again if q["world_kind"] == "recolher_mortos"]) == 1


def test_dead_quest_needs_perceived_escalation_and_actual_escalation():
    st, item = _escalated()
    assert not [
        q for q in wq.offer_from_perceived(st, [], 17)[1] if q["world_kind"] == "recolher_mortos"
    ]
    calm = base_state()
    add_crisis(calm, "praga", "brekmar", cid="praga-2")  # severidade 1: nao escalou
    assert not [s for s in wq.candidates(calm, 17) if s.kind == "recolher_mortos"]


def test_dead_and_conter_praga_coexist_distinct_sources():
    st, item = _escalated()
    _q, created = wq.offer_from_perceived(st, [item], 17)
    kinds = {q["world_kind"]: q["world_source_id"] for q in created}
    assert {"conter_praga", "recolher_mortos"} <= set(kinds)
    assert kinds["conter_praga"] != kinds["recolher_mortos"]


def test_dead_relief_and_fail_cause_praga():
    st, item = _escalated()
    _q, created = wq.offer_from_perceived(st, [item], 17)
    dead = next(q for q in created if q["world_kind"] == "recolher_mortos")
    events, _setback = ep._world_quest_derived(dead, st, 18)
    relief = events[0]["payload"]
    assert relief["pressure"] == "praga" and relief["delta"] == -10
    fail_ev = wq._quest_event(st, "quest_failed", dead, 21, "prazo")
    deltas = wp.event_deltas([fail_ev])
    assert deltas == {"brekmar": {"praga": 6}}


def test_other_lore_kinds_fail_without_world_effect():
    for kind in ("cacar_criatura", "entregar_material", "escoltar", "investigar_rumor"):
        q = {"id": "q", "world_kind": kind, "location_id": "brekmar", "region_id": "brekmar"}
        ev = wq._quest_event({"game_id": "g"}, "quest_failed", q, 5, "prazo")
        assert wp.event_deltas([ev]) == {}


def test_fail_texts_neutral_all_kinds_all_channels():
    st = base_state()
    for kind in lq.LORE_KINDS:
        cfg = wq.kind_cfg(kind)
        channels = list(cfg["description"]) + ["npc"]
        for channel in channels:
            seed = wq.QuestSeed(
                kind=kind,
                world_source_id="x",
                region_id="brekmar",
                location_id="brekmar",
                deadline_day=20,
                rumor_text="Dizem que algo anda acontecendo.",
                anchor_label="Lobo das Geleiras",
            )
            texts = wq.render_quest_text(st, seed, channel, origin="Rolf")
            low = " ".join(texts.values()).lower()
            assert not [w for w in FORBIDDEN if w in texts["fail_text"].lower()], (kind, channel)
            assert not re.search(r"\d+\s*(dia|dias|moeda|ouro|noite)", low), (kind, channel)
            assert "{" not in low, (kind, channel)  # nenhum placeholder sem preencher


def test_api_whitelist_hides_lore_internals():
    import api

    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    _q, created, _r = wq.offer_from_proposal(
        st, proposal("cacar_criatura", first_anchor(menu, "cacar_criatura")), NPC_KEY, menu, 17
    )
    block = api._quest_block({}, [created], st["world"])
    blob = json.dumps(block, ensure_ascii=False)
    for key in ("lore_anchor", "reward_gold_planned", "lore_origin_key", "lore_ref", "escort"):
        assert key not in blob
    assert created["lore_anchor"]["id"] not in blob
    view = block["side"][0]
    assert view["kind"] == "mundo" and view["reward_hint"] == "modesta"
    assert view["deadline_label"] in {"urgente", "em poucos dias", "há algum tempo"}


def test_outcome_label_only_after_completion():
    q = {"world_kind": "investigar_rumor", "status": "active", "outcome": "desmentido"}
    assert lq.outcome_label(q) == ""
    assert "outcome_label" not in quest_log.public_quest_view(q, 5)
    done = {**q, "status": "completed"}
    assert quest_log.public_quest_view(done, 5)["outcome_label"] == "era só boato"
    other = {"world_kind": "cacar_criatura", "status": "completed", "outcome": "desmentido"}
    assert "outcome_label" not in quest_log.public_quest_view(other, 5)


def test_prompt_block_shows_kind_in_words_no_ids_no_numbers():
    from agents.storyteller import _quests_ativas_block

    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "cacar_criatura")
    _q, created, _r = wq.offer_from_proposal(st, proposal("cacar_criatura", aid), NPC_KEY, menu, 17)
    block = _quests_ativas_block([created], {**st, "quests": [created]})
    assert "tipo: mundo" in block and "prazo:" in block
    assert aid not in block and "enemy_" not in block and "lore_" not in block
    assert not re.search(r"prazo: \d", block)
