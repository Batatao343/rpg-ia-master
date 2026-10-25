"""SPEC-315 Etapa 1: alegacao fechada, schema por flag e validacao em Python."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents import storyteller as stt
from services import rumor_adoption as ra
from services import rumors
from services.structured_outputs import ProposedRumor, ProposedRumorWithClaim, RumorClaim
from tests.spec315_helpers import (
    CREATURE,
    FAR,
    HERE,
    TEXT,
    accept,
    adopted_row,
    claim,
    proposal,
    set_flags,
    state,
    with_rows,
)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)


def test_claim_kind_closed_invalid_dropped_keeps_rumor():
    upd = stt.StoryUpdateWithRumorClaims(
        narrative="x",
        proposed_rumors=[
            {
                "text": TEXT,
                "entity_ids": ["brekmar"],
                "claim": {"kind": "dar_ouro", "location_id": FAR},
            },
            {"text": TEXT + " e mais", "entity_ids": ["brekmar"], "claim": "lixo"},
            {"text": TEXT + " ainda", "entity_ids": ["brekmar"], "claim": claim()},
        ],
    )
    assert [p.claim is None for p in upd.proposed_rumors] == [True, True, False]
    assert set(RumorClaim.model_fields) == {"kind", "location_id", "entity_id"}  # R1: sem valor


def test_schema_has_claim_only_with_flag(monkeypatch):
    assert "claim" not in ProposedRumor.model_fields
    assert "claim" in ProposedRumorWithClaim.model_fields
    assert stt._story_schema_for_rumors(rumors) is stt.StoryUpdateWithRumorClaims
    set_flags(monkeypatch, "off")
    assert stt._story_schema_for_rumors(rumors) is stt.StoryUpdateWithRumors
    set_flags(monkeypatch, "shadow")
    assert stt._story_schema_for_rumors(rumors) is stt.StoryUpdateWithRumorClaims
    monkeypatch.setenv("RPG_RUMORS_PROPOSED", "off")
    assert ra.mode() == "off"
    assert stt._story_schema_for_rumors(rumors) is stt.StoryUpdate


def test_default_mode_is_shadow(monkeypatch):
    monkeypatch.delenv("RPG_RUMORS_ADOPTED", raising=False)
    assert ra.mode() == "shadow"


@pytest.mark.parametrize(
    "c",
    [
        claim("criatura_avistada", FAR, ""),
        claim("criatura_avistada", FAR, "creature_inexistente"),
        claim("npc_em_local", FAR, ""),
        claim("esconderijo", FAR, "brekmar"),
        claim("perigo_na_estrada", FAR, CREATURE),
    ],
)
def test_entity_kind_mismatch_rejected(c):
    assert ra.validate_claim(state(), c, 5) == "entity_kind"


def test_here_and_family_rejected():
    assert ra.validate_claim(state(), claim("esconderijo", HERE), 5) == "here"
    st = state(loc="na_anel_lama")
    assert ra.validate_claim(st, claim("esconderijo", "na_taverna_javali"), 5) == "here"  # filho
    assert ra.validate_claim(state(), claim("esconderijo", "local_que_nao_existe"), 5) == "location"
    assert ra.validate_claim(state(), claim("esconderijo", FAR), 5) == ""


def test_canon_by_kind(monkeypatch):
    st = state()
    # esconderijo: alvo saqueado, bau curado e outra alegacao de achado ativa no local
    looted = {**st, "world": {**st["world"], "looted_locations": [FAR]}}
    assert ra.validate_claim(looted, claim("esconderijo", FAR), 5) == "canon"
    assert ra.validate_claim(st, claim("item_perdido", "pm_profundezas"), 5) == "canon"  # bau
    busy = with_rows(st, adopted_row("aaaaaaaaaaaa", "esconderijo", FAR))
    assert ra.validate_claim(busy, claim("item_perdido", FAR), 5) == "canon"
    # perigo na estrada: povoado nao
    assert ra.validate_claim(st, claim("perigo_na_estrada", "skallgard"), 5) == "canon"
    assert ra.validate_claim(st, claim("perigo_na_estrada", "montanhas_afiadas"), 5) == ""
    # criatura: sem BOSS
    import gamedata

    boss = next(
        k for k, e in gamedata.BESTIARY.items() if __import__("encounter_budget").is_boss(e)
    )
    assert ra.validate_claim(st, claim("criatura_avistada", FAR, boss), 5) == "canon"
    assert ra.validate_claim(st, claim("criatura_avistada", FAR, CREATURE), 5) == ""


def _npc_state(**entry):
    from services import npc_world

    sim = npc_world._new_sim(5)
    sim["npcs"]["npc_x"] = {
        "archetype": "sedentario",
        "home": HERE,
        "pos": {"location_id": HERE, "since_day": 1, "arrive_day": None},
        "status": "",
        "frozen": False,
        **entry,
    }
    sim["roster"] = ["npc_x"]
    return state(npc_sim=sim, npcs={"X": {"id": "npc_x", "name": "X", "known_by_player": True}})


def test_canon_npc(monkeypatch):
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    c = claim("npc_em_local", FAR, "npc_x")
    monkeypatch.setattr(ra, "_entity_known", lambda *_a: True)
    assert ra.validate_claim(_npc_state(), c, 5) == ""
    assert ra.validate_claim(_npc_state(dead=True), c, 5) == "canon"
    assert ra.validate_claim(_npc_state(status="capturado"), c, 5) == "canon"
    assert ra.validate_claim(_npc_state(escort={"to": "x"}), c, 5) == "canon"
    from services import npc_world

    assert ra.validate_claim(state(), c, 5) == "canon"  # fora do elenco simulado
    monkeypatch.setattr(npc_world, "is_leader", lambda _r: True)  # D5: lider nunca
    assert ra.validate_claim(_npc_state(), c, 5) == "canon"
    monkeypatch.setenv("RPG_NPC_WORLD", "off")
    monkeypatch.setattr(npc_world, "is_leader", lambda _r: False)
    assert ra.validate_claim(_npc_state(), c, 5) == "canon"


def test_secret_and_hidden_rejected(monkeypatch):
    st = state()
    monkeypatch.setattr(ra, "_entity", lambda eid: {"visibility": "hidden"} if eid == FAR else {})
    assert ra.validate_claim(st, claim("esconderijo", FAR), 5) == "secret"
    monkeypatch.undo()
    set_flags(monkeypatch)
    from services import memory_provenance as mp

    monkeypatch.setattr(mp, "find_strict_unrevealed", lambda *_a, **_k: "segredo_x")
    assert ra.validate_claim(st, claim("esconderijo", FAR), 5) == "secret"
    monkeypatch.undo()
    set_flags(monkeypatch)
    from services import world_validators as wv

    monkeypatch.setattr(wv, "canonical_secret_detail", lambda *_a, **_k: "a —x→ b")
    assert ra.validate_claim(st, claim("criatura_avistada", FAR, CREATURE), 5) == "secret"


def test_secret_faction_gate(monkeypatch):
    from services import npc_self, npc_world

    monkeypatch.setattr(npc_world, "npc_faction", lambda *_a: "fac_sombria")
    monkeypatch.setattr(npc_self, "_faction_is_secret", lambda fid: True)
    monkeypatch.setattr(npc_self, "_faction_known", lambda *_a: False)
    c = claim("npc_em_local", FAR, "npc_x")
    assert ra._secret_reason(state(), c) == "secret"
    monkeypatch.setattr(npc_self, "_faction_known", lambda *_a: True)
    assert ra._secret_reason(state(), c) == ""
    monkeypatch.setattr(npc_self, "_faction_is_secret", lambda fid: False)
    monkeypatch.setattr(npc_self, "_faction_known", lambda *_a: False)
    assert ra._secret_reason(state(), c) == ""  # fação publica


def test_player_steered_loot_rejected():
    st = state(messages=[HumanMessage(content="Conte-me do esconderijo na Floresta dos Sussurros")])
    assert ra.validate_claim(st, claim("esconderijo", FAR), 5) == "player_steered"
    assert ra.validate_claim(st, claim("item_perdido", FAR), 5) == "player_steered"
    # nao-achado nao e "encomendavel"
    assert ra.validate_claim(st, claim("perigo_na_estrada", "montanhas_afiadas"), 5) == ""
    old = state(
        messages=[
            HumanMessage(content="Sobre a Floresta dos Sussurros?"),
            *[HumanMessage(content=f"outra coisa {i}") for i in range(3)],
        ]
    )
    assert ra.validate_claim(old, claim("esconderijo", FAR), 5) == ""  # fora das 3 ultimas


def test_quarantine_rejects():
    assert ra.validate_claim(state(), claim(), 5, quarantined=True) == "quarantine"
    sim, _world, why, extra = accept(state(), [proposal(claim=claim())], quarantined=True)
    assert sim is None and set(why) == {"quarantine"} and not extra


def test_accepted_claim_marks_instance(monkeypatch):
    monkeypatch.setattr(ra, "_truth_roll", lambda *_a: True)
    sim, world, why, extra = accept(state(), [proposal(claim=claim())])
    assert why == [] and extra["adopted"] is True
    inst = sim["rumors"][-1]
    assert inst["adopted"] is True and inst["truth"] is True and inst["quest_eligible"] is True
    assert inst["claim"] == claim() and inst["location_id"] == FAR and inst["materialized_day"] == 0
    assert sim["adopt_log"] == [5] and sim["rumor_last_perceived_day"] == 5
    assert "claim" not in str(world["news"][-1])  # R26: nunca em world.news


def test_rejected_claim_keeps_312_rumor():
    sim, _w, why, extra = accept(state(), [proposal(claim=claim("esconderijo", HERE))])
    inst = sim["rumors"][-1]
    assert why == [] and inst["truth"] is False and inst["quest_eligible"] is False
    assert "claim" not in inst and "adopted" not in inst and not extra


def test_fallbackllm_without_field_is_safe():
    updates: dict = {}
    stt._apply_proposed_rumors(state(), updates, AIMessage(content="erro"), 5, False)
    assert updates == {}
    plain = stt.StoryUpdateWithRumors(
        narrative="x", proposed_rumors=[{"text": TEXT, "entity_ids": ["brekmar"]}]
    )
    stt._apply_proposed_rumors(state(), updates, plain, 5, False)
    assert updates["world_sim"]["rumors"][-1]["truth"] is False  # 312 pura, sem claim
