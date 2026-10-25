"""SPEC-315 Etapa 4: quest elegivel, desfecho, saves, shadow, vazamento e invariantes."""

from __future__ import annotations

import json

import pytest

from playtest import invariants as inv
from services import lore_quests as lq
from services import rumor_adoption as ra
from services import rumors
from tests.spec315_helpers import FAR, adopted_row, claim, proposal, set_flags, state, with_rows

DAY = 6


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)
    monkeypatch.setenv("RPG_NPC_WORLD", "on")


def _quest(rid: str) -> dict:
    return {"world_kind": "investigar_rumor", "lore_anchor": {"id": rid}, "status": "active"}


def test_adopted_is_quest_eligible_true_or_false():
    true_row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    false_row = adopted_row("bbbbbbbbbbbb", "esconderijo", "pradaria_ruinas", truth=False)
    st = with_rows(state(), true_row, false_row)
    offers = rumors.investigable(st, DAY)
    assert {o["rumor_id"] for o in offers} == {true_row["rumor_id"], false_row["rumor_id"]}
    # a oferta nunca revela a verdade: mesmas chaves nas duas
    assert {tuple(sorted(o)) for o in offers} == {tuple(sorted(offers[0]))}
    assert "truth" not in json.dumps(offers) and "claim" not in json.dumps(offers)
    # rejeitada/shadow continua nao elegivel (312 pura)
    legacy = {**false_row, "quest_eligible": False, "adopted": False}
    assert rumors.investigable(with_rows(state(), legacy), DAY) == []


def test_outcome_mapping():
    base = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR)
    assert ra.resolve_outcome({**base, "truth": False}) == "desmentido"
    assert ra.resolve_outcome({**base, "materialized_day": 5}) == "confirmado"
    assert ra.resolve_outcome({**base, "materialized_day": 0}) == "inconclusivo"
    assert ra.resolve_outcome({**base, "adopted": False, "truth": True}) == "confirmado"
    assert ra.resolve_outcome({**base, "adopted": False, "truth": False}) == "desmentido"
    for row, want in (
        (adopted_row("cccccccccccc", truth=False), "desmentido"),
        (adopted_row("dddddddddddd", truth=True, materialized=5), "confirmado"),
        (adopted_row("eeeeeeeeeeee", truth=True), "inconclusivo"),
    ):
        st = with_rows(state(), row)
        outcome, sim = lq.resolve_rumor_outcome(st, _quest(row["rumor_id"]), DAY)
        assert outcome == want and sim["rumors"][0]["resolution"] == want


def test_expiry_without_quest_resolves_same_outcome():
    rows = [
        adopted_row("aaaaaaaaaaaa", truth=True, expires=10),
        adopted_row("bbbbbbbbbbbb", truth=False, expires=10),
        adopted_row("cccccccccccc", truth=True, materialized=7, expires=10),
    ]
    sim = {"rumors": rows}
    rumors._cap_ledger(sim, 11)
    by = {r["rumor_id"]: r["resolution"] for r in sim["rumors"]}
    assert by == {
        rows[0]["rumor_id"]: "inconclusivo",
        rows[1]["rumor_id"]: "desmentido",
        rows[2]["rumor_id"]: "confirmado",
    }


def test_roundtrip_all_new_keys(tmp_path):
    import persistence

    gid = "33333333-3333-4333-8333-333333333333"
    row = adopted_row("aaaaaaaaaaaa", "npc_em_local", FAR, entity="npc_x", materialized=7)
    row["materialization"] = {"kind": "npc", "npc_ref": "npc_x"}
    st = state(world_sim={"rumors": [row], "adopt_log": [5, 7], "forced_adopt": []})
    st["game_id"] = gid
    st["npc_sim"] = {
        "version": 1,
        "npcs": {"npc_x": {"rumor_visit": {"location_id": FAR, "from_day": 5, "until_day": 12}}},
    }
    st["messages"] = []
    st["player"] = {"name": "T", "class_name": "x"}
    assert persistence.save_game_state(st)
    loaded = persistence.load_game_state(persistence._safe_save_path(gid))
    got = loaded["world_sim"]["rumors"][0]
    assert got["claim"] == row["claim"] and got["adopted"] is True
    assert got["materialized_day"] == 7 and got["materialization"]["kind"] == "npc"
    assert loaded["world_sim"]["adopt_log"] == [5, 7]
    assert loaded["npc_sim"]["npcs"]["npc_x"]["rumor_visit"]["until_day"] == 12


def test_legacy_save_behaves_as_312():
    old = {
        "rumor_id": "legacylegacy01",
        "seed_id": "narrador:x",
        "family": "narrador",
        "location_id": FAR,
        "entities": ["brekmar"],
        "truth": False,
        "quest_eligible": False,
        "born_day": 4,
        "expires_day": 14,
        "perceived_day": 4,
        "resolution": "",
    }
    st = with_rows(state(), old)
    assert ra.due_materialization(st, "search", FAR, 6, "procuro") is None
    assert ra.resolve_outcome(old) == "desmentido"
    assert rumors.mark_materialized(st["world_sim"], old["rumor_id"], 6, {}) is st["world_sim"]
    extra: dict = {}
    _sim, _w, why = rumors.accept_proposed(
        state(), [proposal()], turn=5, day=5, quarantined=False, extra=extra
    )
    assert why == [] and extra == {}
    rumors._cap_ledger(st["world_sim"], 40)  # sem chaves novas: nao levanta


def test_shadow_writes_no_adoption(monkeypatch):
    set_flags(monkeypatch, "shadow")
    assert ra.mode() == "shadow"
    inst = {"rumor_id": "abc", "expires_day": 15, "truth": False, "quest_eligible": False}
    out, npc_sim = ra.adopt(state(), dict(inst), claim(), 5)
    assert out == inst and npc_sim is None
    assert (
        ra.due_materialization(
            with_rows(state(), adopted_row("aaaaaaaaaaaa")), "search", FAR, 5, "procuro"
        )
        is None
    )  # shadow nunca materializa


def test_truth_and_claim_never_in_api_or_prompt():
    import api

    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True, materialized=5)
    row["materialization"] = {"kind": "cache", "gold": 12, "item_id": "pocao_cura"}
    sim = {"rumors": [row]}
    world = {
        "current_location_id": "brekmar",
        "world_clock": {"day": 5, "period": "Manhã"},
        "news": [],
    }
    st = with_rows(state(), row)
    st["world"]["news"] = []
    sim2, world2, _why = rumors.accept_proposed(
        st, [proposal(claim=claim())], turn=5, day=7, quarantined=False
    )[:3]
    blob = json.dumps(api._world_block(world, {}, [], {}, sim), ensure_ascii=False)
    for bad in ("truth", "claim", "adopted", "materializ", "rumor_visit", "esconderijo"):
        assert bad not in blob
    news = json.dumps((world2 or {}).get("news") or [], ensure_ascii=False)
    for bad in ("truth", "claim", "adopted", "materializ"):
        assert bad not in news
    # nem o texto de render do boato (prompt/digest) carrega a alegacao
    assert "esconderijo" not in rumors.render_news(st, row)


def test_invariants_detect_false_double_cap_teleport():
    good = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True, materialized=5)
    good["materialization"] = {"kind": "cache", "gold": 20, "item_id": "pocao_cura"}
    st = with_rows(state(), good)
    assert inv.check_rumor_adopt(st, st, 3) == []
    ids = lambda s, p: {v.check_id for v in inv.check_rumor_adopt(s, p, 3)}  # noqa: E731

    false_mat = {**good, "truth": False}
    assert "rumor_adopt.false_materialized" in ids(with_rows(state(), false_mat), st)
    twice = {**good, "materialized_day": 9}
    assert "rumor_adopt.double_materialized" in ids(with_rows(state(), twice), st)
    rich = {**good, "materialization": {"kind": "cache", "gold": 41}}
    assert "rumor_adopt.loot_over_cap" in ids(with_rows(state(), rich), st)
    unique = {**good, "materialization": {"kind": "cache", "item_id": "art_adaga_vidro_dragao"}}
    assert "rumor_adopt.loot_over_cap" in ids(with_rows(state(), unique), st)
    other = adopted_row("bbbbbbbbbbbb", "item_perdido", "pradaria_ruinas", materialized=12)
    other["materialization"] = {"kind": "cache", "gold": 0}
    assert "rumor_adopt.loot_over_cap" in ids(with_rows(state(), good, other), st)  # 2 em < 20 d
    tele = with_rows(state(), good)
    tele["npc_sim"] = {
        "npcs": {
            "npc_x": {
                "rumor_visit": {"location_id": FAR},
                "pos": {"location_id": "brekmar", "arrive_day": 9},
            }
        }
    }
    assert "rumor_adopt.npc_teleport" in ids(tele, st)


def test_became_fact_exempts_materialized_true():
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    row["text"] = "Dizem que alguem enterrou um cofre perto do velho carvalho caido"
    event = {"event_id": "e1", "detail": row["text"], "type": "x"}
    unresolved = {**with_rows(state(), row), "event_log": [event]}
    assert any(v.check_id == "rumor.became_fact" for v in inv.check_rumors(unresolved, None, 3))
    done = {**row, "materialized_day": 5, "materialization": {"kind": "cache"}}
    ok = {**with_rows(state(), done), "event_log": [event]}
    assert not any(v.check_id == "rumor.became_fact" for v in inv.check_rumors(ok, None, 3))
    false_mat = {**done, "truth": False}
    bad = {**with_rows(state(), false_mat), "event_log": [event]}
    assert any(v.check_id == "rumor.became_fact" for v in inv.check_rumors(bad, None, 3))
