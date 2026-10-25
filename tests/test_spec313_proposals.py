"""SPEC-313 Etapa 2: menu, validacao de ancora e guarda de texto."""

from __future__ import annotations

import re

import pytest

from services import lore_quests as lq
from services import quest_log
from services import world_quests as wq
from services.context_builder import estimate_tokens
from tests.spec313_helpers import (
    NPC_KEY,
    add_rumor,
    first_anchor,
    npc_state,
    proposal,
    setup_env,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def _offer(st, prop, menu, day=17):
    return wq.offer_from_proposal(st, prop, NPC_KEY, menu, day)


def test_menu_lists_regional_creatures_without_numbers():
    block, menu = lq.anchor_menu(npc_state(), NPC_KEY)
    assert block and menu
    body = block.split("</GANCHOS_POSSIVEIS>")[0].split("\n", 2)[2]
    assert not re.search(r"\d", body)
    assert not re.search(r"perigo|fraqueza|vulner|hp|dano", body, re.I)
    import gamedata

    for item in menu:
        if item["kind"] == "cacar_criatura":
            assert "skallgard" in gamedata.BESTIARY[item["anchor_id"]]["regions"]


def test_menu_never_contains_rumor_truth():
    blocks = []
    for truth in (True, False):
        st = npc_state(loc="nova_arcadia")
        add_rumor(st, truth=truth)
        block, menu = lq.anchor_menu(st, NPC_KEY)
        assert any(i["kind"] == "investigar_rumor" for i in menu)
        blocks.append(block)
    assert blocks[0] == blocks[1]
    assert "truth" not in blocks[0].lower()


def test_menu_absent_when_nothing_eligible(monkeypatch):
    assert lq.anchor_menu(npc_state(), NPC_KEY)[0]
    st = npc_state()
    st["npcs"][NPC_KEY]["in_scene"] = False
    assert lq.anchor_menu(st, NPC_KEY) == ("", [])
    setup_env(monkeypatch, lore="off")
    assert lq.anchor_menu(npc_state(), NPC_KEY) == ("", [])


def test_menu_token_budget():
    st = npc_state(loc="nova_arcadia", role="mercador", archetype="mercador_itinerante")
    add_rumor(st)
    block, _menu = lq.anchor_menu(st, NPC_KEY)
    assert estimate_tokens(block) <= 150
    assert block.count("\n") + 1 <= 12


def test_anchor_outside_menu_downgrades_to_common():
    st = npc_state()
    _block, menu = lq.anchor_menu(st, NPC_KEY)
    quests, created, reason = _offer(st, proposal("cacar_criatura", "enemy_inexistente"), menu)
    assert created is None and reason in lq.DOWNGRADE_REASONS and not quests


def test_boss_and_named_never_anchor():
    import gamedata

    bad = [
        e["id"]
        for e in gamedata.BESTIARY.values()
        if e.get("categoria") in ("chefe", "nomeado") and "skallgard" in (e.get("regions") or [])
    ]
    assert bad
    for eid in bad:
        assert lq._hunt_ok(eid, "skallgard") is None
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    assert not {i["anchor_id"] for i in menu} & set(bad)
    # mesmo "dentro do menu" forjado, a validacao do motor recusa
    forged = [{"kind": "cacar_criatura", "anchor_id": bad[0], "label": "x"}]
    assert lq.validate_anchor(st, "cacar_criatura", bad[0], NPC_KEY, forged)[0] is False


def test_escort_only_self_itinerant_alive_here():
    st = npc_state(loc="nova_arcadia", archetype="mercador_itinerante")
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    esc = [i for i in menu if i["kind"] == "escoltar"]
    assert esc
    # outro NPC como ancora
    other = [{**esc[0], "anchor_id": "npc_outro|" + esc[0]["anchor_id"].split("|")[1]}]
    assert lq.validate_anchor(st, "escoltar", other[0]["anchor_id"], NPC_KEY, other)[0] is False
    sedentary = npc_state(loc="nova_arcadia", archetype="sedentario")
    assert not [i for i in lq.anchor_menu(sedentary, NPC_KEY)[1] if i["kind"] == "escoltar"]
    dead = npc_state(loc="nova_arcadia", archetype="mercador_itinerante")
    dead["npcs"][NPC_KEY]["status"] = "morto"
    assert not [i for i in lq.anchor_menu(dead, NPC_KEY)[1] if i["kind"] == "escoltar"]
    away = npc_state(loc="nova_arcadia", archetype="mercador_itinerante")
    away["npc_sim"]["npcs"]["npc_rolf"]["pos"]["location_id"] = "brekmar"
    assert not [i for i in lq.anchor_menu(away, NPC_KEY)[1] if i["kind"] == "escoltar"]


def test_storyteller_kind_downgraded_to_common_quest():
    """R6: o caminho comum do `register_proposed_quests` ignora `kind`/`anchor_id`."""
    quests, created = quest_log.register_proposed_quests(
        [], [proposal("cacar_criatura", "enemy_lobo_invernal", title="Caçar lobos")], turn=3
    )
    assert len(created) == 1
    q = created[0]
    assert "world_kind" not in q and "lore_anchor" not in q and q["reward_gold"] == 0


def test_llm_text_with_days_or_gold_falls_back_to_template():
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "cacar_criatura")
    prop = proposal(
        "cacar_criatura",
        aid,
        title="Matar a fera em 3 dias",
        description="Pago 50 moedas pela pele.",
    )
    seed, why = lq.seed_for_proposal(st, prop, NPC_KEY, menu, 17)
    assert why == "" and seed.llm_title == "" and seed.llm_description == ""
    ok = proposal("cacar_criatura", aid, title="Lobos na trilha", description="Eles rondam.")
    seed, _ = lq.seed_for_proposal(st, ok, NPC_KEY, menu, 17)
    assert seed.llm_title == "Lobos na trilha" and seed.llm_description == "Eles rondam."


def test_llm_text_with_unknown_faction_falls_back_to_template():
    import gamedata

    st = npc_state()
    name = gamedata.seed_factions()[0]["name"]
    assert lq.safe_llm_text(st, f"Trabalho para {name}", set(), 400) == ""
    assert lq.safe_llm_text(st, "Trabalho simples", set(), 400) == "Trabalho simples"


def test_llm_text_with_other_creature_or_place_falls_back():
    st = npc_state()
    assert lq.safe_llm_text(st, "Vá até Brekmar caçar", {"Skallgard"}, 400) == ""
    assert lq.safe_llm_text(st, "Vá até Brekmar caçar", {"Brekmar"}, 400) != ""


def test_llm_reward_hint_discarded():
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    _q, created, _r = _offer(
        st, proposal("cacar_criatura", first_anchor(menu, "cacar_criatura")), menu
    )
    assert created["reward_hint"] == "modesta"
    assert "50" not in created["reward_hint"]


def test_faction_mission_same_turn_drops_anchored():
    from agents.npc import _apply_lore_proposals

    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    mission = {"id": "m1", "status": "active", "faction_id": "f", "created_turn": 17}
    p = proposal("cacar_criatura", first_anchor(menu, "cacar_criatura"))
    quests, _extras = _apply_lore_proposals(st, [mission], [p], NPC_KEY, menu, "npc_rolf", 17)
    assert quests == [mission]


def test_anchored_never_has_faction_fields():
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    _q, created, _r = _offer(
        st, proposal("cacar_criatura", first_anchor(menu, "cacar_criatura")), menu
    )
    assert not {"faction_id", "mission_kind", "mission_tier"} & set(created)
    from services import faction_membership

    assert faction_membership.active_mission_id({"quests": [created]}, "legiao_ferro") in ("", None)


def test_independent_of_player_stats():
    a, b = npc_state(), npc_state()
    a["player"] = {"level": 1, "gold": 5, "inventory": []}
    b["player"] = {"level": 20, "gold": 5000, "inventory": [{"id": "x"}] * 9}
    block_a, menu_a = lq.anchor_menu(a, NPC_KEY)
    block_b, menu_b = lq.anchor_menu(b, NPC_KEY)
    assert block_a == block_b and menu_a == menu_b
    sa, _ = lq.seed_for_proposal(
        a, proposal("cacar_criatura", first_anchor(menu_a, "cacar_criatura")), NPC_KEY, menu_a, 17
    )
    sb, _ = lq.seed_for_proposal(
        b, proposal("cacar_criatura", first_anchor(menu_b, "cacar_criatura")), NPC_KEY, menu_b, 17
    )
    assert sa == sb


def test_fallback_llm_message_creates_no_quest():
    """Guard de resiliencia: sem ProposedQuest o caminho nao cria nada nem levanta."""
    st = npc_state()
    quests, created, reason = wq.offer_from_proposal(st, None, NPC_KEY, [], 17)
    assert created is None and quests == [] and reason
