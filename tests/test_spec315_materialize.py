"""SPEC-315 Etapa 3: materializacao pelos writers existentes (achado, encontro, NPC)."""

from __future__ import annotations

import random

import pytest

import agents.storyteller as stt
import gamedata
from services import economy, exploration, npc_world, rumors
from services import rumor_adoption as ra
from tests.spec315_helpers import CREATURE, FAR, HERE, adopted_row, set_flags, state, with_rows
from tests.test_ambient_consumers import _Spy, _story_state

UNIQUE = "art_adaga_vidro_dragao"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)
    monkeypatch.setenv("RPG_NPC_WORLD", "on")


def _at_far(day: int = 5, *rows, **extra):
    st = state(day, FAR, **extra)
    return with_rows(st, *rows) if rows else st


def test_cache_uses_roll_loot_no_unique_gold_cap(monkeypatch):
    calls: list[tuple] = []

    def fake(region, danger, rng=None, **kw):
        calls.append((region, danger, kw.get("boost")))
        return {"item_id": UNIQUE if len(calls) < 3 else "pocao_cura", "rarity": "x", "gold": 999}

    monkeypatch.setattr(economy, "roll_loot", fake)
    loc = gamedata.get_location("pradaria_ruinas")
    player, world = {"gold": 0, "inventory": []}, {}
    note, got = exploration.grant_rumor_cache(
        player, world, loc, random.Random(1), kind="item_perdido", gold_max=40
    )
    assert got["item_id"] == "pocao_cura" and got["gold"] == 0  # unico re-sorteado; item = sem ouro
    assert all(c[0] == loc["region_id"] and c[1] == loc["danger"] and c[2] is False for c in calls)
    assert player["gold"] == 0 and UNIQUE not in str(player["inventory"])
    # esconderijo sem item (pool vazio): ouro limitado a 40
    monkeypatch.setattr(economy, "roll_loot", lambda *a, **k: {"item_id": None, "gold": 999})
    player = {"gold": 5, "inventory": []}
    _n, got = exploration.grant_rumor_cache(
        player, {}, loc, random.Random(2), kind="esconderijo", gold_max=40
    )
    assert got["gold"] == 40 and player["gold"] == 45 and "nunca" not in note


def test_cache_marks_looted_and_never_repeats():
    inst = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    st = _at_far(5, inst, messages=[])
    assert ra.due_materialization(st, "search", FAR, 5, "Procuro por todo lado") is inst
    upd, marked = ra.materialize(st, inst, 5)
    assert FAR in upd["world"]["looted_locations"] and marked["materialized_day"] == 5
    assert set(upd) == {
        "player",
        "world",
        "note",
        "events",
    }  # R20: nenhum evento fora do turno do heroi
    sim = ra.commit(st["world_sim"], inst["rumor_id"], 5, marked["materialization"])
    after = {**st, "world_sim": sim, "world": upd["world"]}
    assert ra.due_materialization(after, "search", FAR, 6, "procuro") is None
    # writer unico idempotente
    assert rumors.mark_materialized(sim, inst["rumor_id"], 6, {"kind": "cache"}) is sim


def test_search_vocab_or_quest_triggers():
    inst = adopted_row("aaaaaaaaaaaa", "item_perdido", FAR, truth=True)
    st = _at_far(5, inst)
    assert ra.due_materialization(st, "search", FAR, 5, "Converso com o taverneiro") is None
    for text in (
        "procuro",
        "Vasculho tudo",
        "cavo o chão",
        "reviro o entulho",
        "busco",
        "investigo",
    ):
        assert ra.due_materialization(st, "search", FAR, 5, text) is inst
    assert ra.due_materialization(st, "search", "skallgard", 5, "procuro") is None  # outro local
    quest = {
        "world_kind": "investigar_rumor",
        "status": "active",
        "lore_anchor": {"id": inst["rumor_id"]},
    }
    assert ra.due_materialization(st, "quest", FAR, 5) is None
    assert ra.due_materialization({**st, "quests": [quest]}, "quest", FAR, 5) is inst
    # janela: born_day + 1 .. expires_day
    assert ra.due_materialization(_at_far(4, inst), "search", FAR, 4, "procuro") is None
    assert ra.due_materialization(_at_far(15, inst), "search", FAR, 15, "procuro") is None


def test_false_or_unadopted_never_due():
    false_row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=False)
    legacy = {**adopted_row("bbbbbbbbbbbb", "esconderijo", FAR), "adopted": False}
    st = _at_far(5, false_row, legacy)
    for trig in ("search", "quest", "travel"):
        assert ra.due_materialization(st, trig, FAR, 5, "procuro") is None


def test_encounter_hint_like_law_hint_scaled_by_level():
    from world_utils import check_encounter

    inst = adopted_row("aaaaaaaaaaaa", "criatura_avistada", "nova_arcadia", entity=CREATURE)
    world = {
        "current_location_id": "nova_arcadia",
        "danger_level": 3,
        "world_clock": {"day": 5, "period": "Manhã"},
        "turn_count": 9,
        "last_encounter_turn": 9,  # cooldown ATIVO: o boato ignora so esta vez
    }
    st = state(5, "nova_arcadia")
    low = ra.encounter_hint(st, inst, dict(world), 1, 9)
    assert low["reason"] == "rumor" and low["enemy_id"] == CREATURE and low["always_combat"] is True
    enc = check_encounter(world, [], {}, 9, player_level=1, rumor_hint=low)
    assert enc["reason"] == "rumor" and enc["enemy_id"] == CREATURE
    assert world["encounter_eff_danger"] == low["eff_danger"]
    assert (
        check_encounter(dict(world), [], {}, 9, player_level=1) is None
    )  # sem hint: cooldown vale
    # perigo na estrada: criatura sorteada da regiao; forca escala pelo nivel
    road = adopted_row("bbbbbbbbbbbb", "perigo_na_estrada", "montanhas_afiadas")
    w2 = {**world, "current_location_id": "montanhas_afiadas"}
    lv1 = ra.encounter_hint(st, road, dict(w2), 1, 9)
    lv20 = ra.encounter_hint(st, road, dict(w2), 20, 9)
    assert lv1["eff_danger"] == 2 and lv20["eff_danger"] == 3 and lv1["always_combat"] is False
    assert gamedata.BESTIARY[lv1["enemy_id"]]["name"] == lv1["hint"]
    # apex nao escala
    w3 = {**world, "current_location_id": "ma_boca", "danger_level": 4}
    assert ra.encounter_hint(st, road, w3, 1, 9)["eff_danger"] == 4


def test_dedupe_exempts_rumor_encounter():
    world = {"last_encounter_id": "X", "last_encounter_loc": "a", "current_location_id": "a"}
    enc = {"reason": "rumor", "hint": "X"}
    assert stt._dedupe_encounter(enc, world) is enc
    assert stt._dedupe_encounter({"reason": "random", "hint": "X"}, world) is None


def _story_at_far(text: str, rows, **world_extra):
    st = _story_state(
        world_extra={"current_location": "Floresta", "current_location_id": FAR, **world_extra},
        text=text,
    )
    st["world"]["world_clock"] = {"day": 5, "period": "Manhã"}
    st["world_sim"] = _full_sim(st, rows)
    return st


def _full_sim(st: dict, rows) -> dict:
    from services import world_engine as we

    day = int(st["world"]["world_clock"]["day"])
    sim = we._new_sim(str(st["game_id"]), day, [], "on")
    sim["calm_until_day"] = day + 30
    sim["rumors"] = list(rows)
    sim["rumor_last_perceived_day"] = 1
    return sim


def test_storyteller_search_grants_once_and_marks(monkeypatch):
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy())
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    out = stt.storyteller_node(_story_at_far("Procuro e vasculho o local", [row]))
    sim = out["world_sim"]
    mat = sim["rumors"][0]
    assert mat["materialized_day"] == 5 and mat["materialization"]["kind"] == "cache"
    assert FAR in out["world"]["looted_locations"]
    assert out["player"].get("gold", 0) <= 40 and mat["materialization"]["gold"] <= 40
    assert out["player"].get("inventory") or out["player"].get("gold")
    # segunda busca no mesmo estado ja marcado: nada novo
    st2 = _story_at_far("Procuro de novo", sim["rumors"])
    st2["world"]["looted_locations"] = out["world"]["looted_locations"]
    again = stt.storyteller_node(st2)
    assert "player" not in again  # nada novo foi concedido
    assert (again.get("player") or {"gold": 0}).get("gold", 0) == 0


def test_storyteller_false_claim_changes_nothing(monkeypatch):
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy())
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=False)
    out = stt.storyteller_node(_story_at_far("Procuro e vasculho o local", [row]))
    assert "player" not in out
    assert out.get("world", {}).get("looted_locations", []) == []
    assert (out.get("world_sim") or {"rumors": [row]})["rumors"][0].get("materialized_day") == 0


def test_rest_safety_respected(monkeypatch):
    """R16: descanso nunca dispara o hint (e o achado so vem de busca, nunca de descanso)."""
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy())
    row = adopted_row("aaaaaaaaaaaa", "criatura_avistada", FAR, entity=CREATURE)
    out = stt.storyteller_node(_story_at_far("Vou descansar e acampar aqui.", [row]))
    assert out.get("next") != "combat_agent"
    assert (out.get("world_sim") or {"rumors": [row]})["rumors"][0].get("materialized_day") == 0


def test_storyteller_arrival_encounter_commits_only_when_fires(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    row = adopted_row("aaaaaaaaaaaa", "criatura_avistada", "nova_arcadia", entity=CREATURE)
    st = _story_state(
        world_extra={"current_location": "Brekmar", "current_location_id": "brekmar"},
        text="Viajo para Nova Arcádia",
    )
    st["world"]["world_clock"] = {"day": 5, "period": "Manhã"}
    st["world_sim"] = _full_sim(st, [row])
    st["player"]["level"] = 1
    out = stt.storyteller_node(st)
    if out.get("next") == "combat_agent":
        assert out["combat_target"] == gamedata.BESTIARY[CREATURE]["name"]
        assert out["world_sim"]["rumors"][0]["materialization"]["kind"] == "encounter"
        assert out["world_sim"]["rumors"][0]["materialized_day"] == 5
    else:  # destino sem custo/inalcancavel: nada materializa
        assert (out.get("world_sim") or {"rumors": [row]})["rumors"][0].get("materialized_day") == 0


# --- NPC agendado (R17) --------------------------------------------------------------


def _npc_sim(**entry):
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
    return sim


def _walk(sim, days):
    trail = []
    for d in days:
        entry = sim["npcs"]["npc_x"]
        npc_world._step_position(state(d), "npc_x", entry, d, "g315", {}, "skallgard")
        trail.append(dict(entry["pos"]))
    return trail


def test_npc_schedule_travels_never_teleports():
    sim = npc_world.schedule_visit(_npc_sim(), "npc_x", FAR, 5, 12, "rid")
    assert sim["npcs"]["npc_x"]["rumor_visit"]["until_day"] == 12
    trail = _walk(sim, range(5, 16))
    first = trail[0]
    assert first["location_id"] == "" and first["travel_to"] == FAR  # viaja de verdade
    assert first["arrive_day"] > 5
    at_far = [i for i, p in enumerate(trail) if p.get("location_id") == FAR]
    assert at_far and trail[at_far[0] - 1].get("travel_to") == FAR  # nunca saltou de casa p/ FAR
    assert sim["npcs"]["npc_x"].get("rumor_visit") is None  # liberado depois de until_day
    assert any(p.get("travel_to") == HERE for p in trail)  # e volta para casa
    assert trail[-1].get("location_id") in (HERE, "")


def test_schedule_visit_ignores_unknown_npc():
    sim = _npc_sim()
    assert npc_world.schedule_visit(sim, "ninguem", FAR, 5, 12, "rid") is sim


def test_npc_peril_cancels_visit_inconclusivo():
    sim = npc_world.schedule_visit(_npc_sim(), "npc_x", FAR, 5, 12, "rid")
    sim["npcs"]["npc_x"]["status"] = "ferido"
    _walk(sim, [5])
    assert sim["npcs"]["npc_x"].get("rumor_visit") is None
    row = adopted_row("aaaaaaaaaaaa", "npc_em_local", FAR, entity="npc_x", truth=True)
    assert ra.resolve_outcome(row) == "inconclusivo"  # nunca materializou


def test_target_looted_or_npc_dead_after_adoption_is_inconclusivo(monkeypatch):
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    st = _at_far(5, row)
    st["world"]["looted_locations"] = [FAR]  # alguem saqueou entre a adocao e a chegada
    assert ra.due_materialization(st, "search", FAR, 5, "procuro") is None
    assert ra.resolve_outcome(row) == "inconclusivo"
    crea = adopted_row("bbbbbbbbbbbb", "criatura_avistada", FAR, entity=CREATURE)
    dead = _at_far(5, crea, world_projection={"entities": {CREATURE: {"alive": False}}})
    assert ra.due_materialization(dead, "travel", FAR, 5) is None
    npc = adopted_row("cccccccccccc", "npc_em_local", FAR, entity="npc_x")
    ded = _at_far(5, npc, npc_sim=_npc_sim(dead=True))
    assert ra.due_materialization(ded, "travel", FAR, 5) is None


def test_npc_arrival_marks_only_when_present():
    npc = adopted_row("cccccccccccc", "npc_em_local", FAR, entity="npc_x")
    sim = npc_world.schedule_visit(_npc_sim(), "npc_x", FAR, 5, 14, npc["rumor_id"])
    sim["npcs"]["npc_x"]["pos"] = {"location_id": FAR, "since_day": 6, "arrive_day": None}
    here = _at_far(6, npc, npc_sim=sim)
    assert ra.due_materialization(here, "travel", FAR, 6) is npc
    away = _at_far(6, npc, npc_sim=_npc_sim())  # sem visita agendada
    assert ra.due_materialization(away, "travel", FAR, 6) is None


def test_npc_arrives_after_hero_materializes_on_presence():
    """P2-5: o heroi ja esta no alvo; o NPC chega depois (gatilho `present`)."""
    npc = adopted_row("cccccccccccc", "npc_em_local", FAR, entity="npc_x")
    sim = npc_world.schedule_visit(_npc_sim(), "npc_x", FAR, 5, 14, npc["rumor_id"])
    travelling = _at_far(6, npc, npc_sim=sim)
    assert ra.due_materialization(travelling, "present", FAR, 6) is None  # ainda a caminho
    sim["npcs"]["npc_x"]["pos"] = {"location_id": FAR, "since_day": 7, "arrive_day": None}
    arrived = _at_far(8, npc, npc_sim=sim)
    assert ra.due_materialization(arrived, "present", FAR, 8) is npc
    # pela costura do storyteller: so marca, nada concedido
    sim_updates: dict = {}
    player, note, events = stt._rumor_cache_trigger(
        arrived, arrived["world"], sim_updates, "olho", []
    )
    assert player is None and note == "" and events == []
    assert sim_updates["world_sim"]["rumors"][0]["materialized_day"] == 8


def test_loot_node_search_at_target_materializes(monkeypatch):
    """P2-4: busca roteada para LOOT no alvo entrega o achado do boato."""
    import agents.loot as loot

    monkeypatch.setattr(loot, "get_llm", lambda *a, **k: _Spy())
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    st = _story_at_far("Vasculho o local", [row])
    st["loot_source"] = "TREASURE"
    out = loot.loot_node(st)
    assert out["world_sim"]["rumors"][0]["materialized_day"] == 5
    assert FAR in out["world"]["looted_locations"]
    assert out["world_sim"]["rumors"][0]["materialization"]["gold"] <= 40
    # alegacao falsa: cai no sorteio generico, sem marcar nada
    false_row = adopted_row("bbbbbbbbbbbb", "esconderijo", FAR, truth=False)
    st2 = _story_at_far("Vasculho o local", [false_row])
    st2["loot_source"] = "TREASURE"
    out2 = loot.loot_node(st2)
    assert "world_sim" not in out2 and FAR not in (out2["world"].get("looted_locations") or [])


def test_find_turn_llm_exception_keeps_world(monkeypatch):
    """P2-2: excecao do LLM no turno do achado nao perde `looted_locations` nem o rumor marcado."""

    class _Boom(_Spy):
        def invoke(self, msgs, *_a, **_k):
            raise RuntimeError("boom")

    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Boom())
    row = adopted_row("aaaaaaaaaaaa", "esconderijo", FAR, truth=True)
    out = stt.storyteller_node(_story_at_far("Procuro por todo lado", [row]))
    assert FAR in out["world"]["looted_locations"]
    assert out["world_sim"]["rumors"][0]["materialized_day"] == 5
    assert "O boato era" not in str(out["messages"][0].content)
