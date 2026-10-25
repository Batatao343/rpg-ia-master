"""SPEC-312 Etapa 3: percepcao (regra de ouro), teto diario, world.news e API."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services import rumors
from services import world_perception as wperc
from tests.spec312_helpers import base_state, make_rumor


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _perceive(state, sim):
    from agents import storyteller as stt

    tick = SimpleNamespace(sim_key="world_sim", days_ticked=1, world_sim=sim)
    return stt._perceive_world(state, state["world"], [], {}, tick)


def test_regional_channel_requires_settlement_or_origin_family():
    sim: dict = {}
    item = make_rumor(sim, region="pantano_melancolia", loc="pantano_melancolia")
    # heroi em local nao povoado da mesma regiao, fora da familia do local de origem
    st = base_state(5, "pm_profundezas")
    assert rumors.perceivable(st, item) is False
    # na origem (familia): percebe
    assert rumors.perceivable(base_state(5, "pantano_melancolia"), item) is True
    # outra regiao: nunca
    assert rumors.perceivable(base_state(5, "brekmar"), item) is False
    # povoado da regiao (cidade/favela/porto) percebe mesmo longe do local de origem
    item2 = make_rumor(sim, region="nova_arcadia", loc="na_anel_dourado", seed_id="rumor_x", day=6)
    assert rumors.perceivable(base_state(5, "na_anel_ferro"), item2) is True  # cidade
    assert rumors.perceivable(base_state(5, "na_anel_lama"), item2) is True  # favela
    assert rumors.perceivable(base_state(5, "na_taverna_javali"), item2) is True  # pai: favela
    item3 = make_rumor(sim, region="brekmar", loc="brekmar", seed_id="rumor_y", day=6)
    assert rumors.perceivable(base_state(5, "bk_docas_velhas"), item3) is True  # origem/porto
    item4 = make_rumor(
        sim, region="pradaria_ruinas", loc="pradaria_ruinas", seed_id="rumor_z", day=6
    )
    assert rumors.perceivable(base_state(5, "pr_ruinas_assombradas"), item4) is False  # ermo


def test_heard_channel_requires_location_heard_and_215_on(monkeypatch):
    sim: dict = {}
    item = make_rumor(sim, region="brekmar", loc="brekmar")
    st = base_state(
        5, "pr_ruinas_assombradas", location_heard={"pr_ruinas_assombradas": [item["subject_id"]]}
    )
    assert rumors.perceivable(st, item) is False  # 215 off
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    assert rumors.perceivable(st, item) is True
    assert rumors.channel_of(st, item) == "b"
    st2 = base_state(5, "pr_ruinas_assombradas")
    assert rumors.perceivable(st2, item) is False


def test_max_one_new_rumor_per_day_and_per_action():
    sim: dict = {}
    a = make_rumor(sim, "rumor_a", day=5)
    b = make_rumor(sim, "rumor_b", day=4)
    st = base_state(5, "nova_arcadia")
    seen = rumors.limit_perceived(st, sim, [a, b], 5)
    assert len(seen) == 1 and seen[0] is a  # o mais recente
    rumors.mark_perceived(sim, [a["subject_id"]], 5)
    # segunda acao no mesmo dia: nenhum rumor novo
    assert rumors.limit_perceived(st, sim, [b], 5) == []
    # dia seguinte: o excedente pode ser percebido
    assert rumors.limit_perceived(st, sim, [b], 6) == [b]


def test_excess_rumor_stays_pending_until_ttl():
    sim: dict = {}
    a = make_rumor(sim, "rumor_a", day=5)
    b = make_rumor(sim, "rumor_b", day=4)
    sim["pending_digest"] = [a, b]
    st = base_state(5, "nova_arcadia")
    world, seen = _perceive(st, sim)
    assert [i["subject_id"] for i in seen] == [a["subject_id"]]
    assert [i["subject_id"] for i in sim["pending_digest"]] == [b["subject_id"]]
    # passado o TTL de 10 dias o item sai do digest
    st2 = base_state(16, "nova_arcadia")
    sim["pending_digest"] = [b]
    _perceive(st2, sim)
    assert sim["pending_digest"] == []


def test_non_rumor_items_unaffected_by_cap():
    from services.world_director import digest_item

    sim: dict = {}
    r = make_rumor(sim, "rumor_a", day=5)
    sig = digest_item(
        "g",
        5,
        "sinal",
        "nova_arcadia",
        "nova_arcadia",
        "praga.crise.inicio",
        {"local": "nova_arcadia"},
    )
    st = base_state(5, "nova_arcadia")
    sim["last_event_seq"] = 0
    out = rumors.limit_perceived(st, sim, [sig, r], 5)
    assert sig in out and r in out
    sim["rumor_last_perceived_day"] = 5
    out = rumors.limit_perceived(st, sim, [sig, r], 5)
    assert out == [sig]


def test_news_entry_has_kind_and_expiry_and_template_text():
    sim: dict = {}
    r = make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", day=5)
    sim["pending_digest"] = [r]
    st = base_state(5, "na_anel_dourado")
    world, seen = _perceive(st, sim)
    assert len(seen) == 1
    entry = world["news"][-1]
    assert entry["kind"] == "rumor" and entry["rumor_id"] == r["subject_id"]
    assert entry["expires_day"] == 15 and entry["source"] == "world_engine"
    assert entry["text"] == wperc.render(st, r)
    assert "Lorde Protetor" in entry["text"] or "cama" in entry["text"]
    # mark_perceived gravou
    inst = rumors.instance({"world_sim": sim}, r["subject_id"])
    assert inst["perceived_day"] == 5 and sim["rumor_last_perceived_day"] == 5
    assert r["subject_id"] in sim["perceived_ids"]


def test_prune_news_removes_expired_rumors_only():
    world = {
        "news": [
            {"text": "a", "kind": "rumor", "expires_day": 9},
            {"text": "b", "kind": "rumor", "expires_day": 20},
            {"text": "c"},
        ]
    }
    out = rumors.prune_news(world, 10)
    assert [n["text"] for n in out["news"]] == ["b", "c"]


def test_rumor_news_cap_keeps_crisis_news():
    news = [{"text": f"c{i}"} for i in range(3)]
    news += [{"text": f"r{i}", "kind": "rumor", "expires_day": 50} for i in range(7)]
    out = rumors.prune_news({"news": news}, 10)
    texts = [n["text"] for n in out["news"]]
    assert texts[:3] == ["c0", "c1", "c2"]
    assert [t for t in texts if t.startswith("r")] == ["r3", "r4", "r5", "r6"]


def test_heard_block_marks_boato_and_hides_expired():
    from services.ambient import heard_block

    world = {
        "world_clock": {"day": 12},
        "news": [
            {"day": 1, "location_name": "X", "text": "velho", "kind": "rumor", "expires_day": 11},
            {
                "day": 11,
                "location_name": "Y",
                "text": "dizem algo",
                "kind": "rumor",
                "expires_day": 21,
            },
            {"day": 11, "location_name": "Z", "text": "ponte caiu"},
        ],
    }
    out = heard_block(world)
    assert "velho" not in out
    assert "(boato) dizem algo" in out and "(boato) ponte" not in out
    assert "nunca como fato confirmado" in out
    plain = heard_block({"news": [{"day": 1, "location_name": "Z", "text": "ponte caiu"}]})
    assert "(boato)" not in plain and "nunca como fato" not in plain


def test_api_news_kind_only_no_truth_or_ids():
    import api

    sim: dict = {}
    r = make_rumor(sim, "rumor_valerius_nao_come_nem_dorme", day=5, truth=False)
    sim["pending_digest"] = [r]
    st = base_state(5, "na_anel_dourado")
    world, _seen = _perceive(st, sim)
    world["news"].append(
        {"day": 5, "period": "Manhã", "location_name": "Z", "text": "ponte", "turn": 5}
    )
    block = api._world_block(world, {}, [], {}, sim)
    kinds = {n["text"]: n["kind"] for n in block["news"]}
    assert kinds["ponte"] == "noticia" and "boato" in kinds.values()
    blob = json.dumps(block, ensure_ascii=False)
    for forbidden in (
        "truth",
        "rumor_id",
        "seed_id",
        "expires_day",
        "confiabilidade",
        r["subject_id"],
    ):
        assert forbidden not in blob
    # rumor expirado nao sai pela API
    world["world_clock"]["day"] = 30
    assert all(n["kind"] != "boato" for n in api._world_block(world, {}, [], {}, sim)["news"])


def test_world_quests_and_npc_beliefs_ignore_rumor_items():
    from services import npc_world, world_quests

    sim: dict = {}
    r = make_rumor(sim, "rumor_a", day=5)
    seed = SimpleNamespace(
        kind="frear_ascensao",
        npc_id="",
        faction_id="f",
        crisis_kind="guerra",
        region_id="nova_arcadia",
        location_id="",
        source_event_id="",
        world_source_id="",
    )
    assert world_quests._item_matches(seed, r) is False
    beliefs, events = npc_world.on_perceived(base_state(5), [r])
    assert beliefs == {} and events == []


def test_unknown_faction_names_never_in_render():
    sim: dict = {}
    r = make_rumor(sim, "rumor_a_legiao_esta_fabricando_soldados_a_partir_de_mortos", day=5)
    text = wperc.render(base_state(5), r)
    assert "Legião de Ferro" not in text and "legião" in text.lower()
