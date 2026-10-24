"""SPEC-303 Etapa 6: percepcao (regra de ouro), narracao e API (R20-R24)."""

from __future__ import annotations

import copy
import json

import pytest

import gamedata
from agents import storyteller
from agents import world_simulator as wsim
from services import world_calendar as wc
from services import world_engine as we
from services import world_perception as wperc
from services.world_director import digest_item
from tests.spec303_helpers import cal_for


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


GID = "00000000-0000-4000-8000-000000000303"


def _state(loc="nova_arcadia", **extra):
    return {
        "game_id": "g",
        "world": {
            "current_location_id": loc,
            "current_location": loc,
            "world_clock": {"day": 5, "period": "Manhã"},
            "turn_count": 5,
        },
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "npcs": {},
        **extra,
    }


def _festa(loc="skallgard", region="skallgard", **kw):
    return digest_item(
        "g",
        5,
        "festa",
        region,
        loc,
        "festa.inicio",
        {"local": loc, "festa": "Noite dos Nomes", "rotulo": "em luto"},
        **kw,
    )


def test_season_item_global_visibility_only_type():
    tpls = wperc._templates()["templates"]
    glob = {t for t, v in tpls.items() if v["visibility"] == "global"}
    assert glob and all(t.startswith("estacao.inicio.") for t in glob)
    item = digest_item("g", 5, "estacao", "", "", "estacao.inicio.inverno")
    for loc in ("nova_arcadia", "skallgard", "brekmar"):
        assert wperc.perceivable(_state(loc), [item]) == [item]
    # um item que NAO e do tipo `estacao` nunca vira onisciente pela visibilidade global
    fake = digest_item("g", 5, "sinal", "skallgard", "", "estacao.inicio.inverno")
    assert wperc.perceivable(_state("brekmar"), [fake]) == []


def test_far_festival_invisible_without_propagation():
    item = _festa(subject_id="ev-1")
    assert wperc.perceivable(_state("nova_arcadia"), [item]) == []
    heard = {"nova_arcadia": ["ev-1"]}
    assert wperc.perceivable(_state("nova_arcadia", location_heard=heard), [item]) == []  # 215 off


def test_far_festival_heard_via_location_heard(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    item = _festa(subject_id="ev-1")
    st = _state("nova_arcadia", location_heard={"nova_arcadia": ["ev-1"]})
    assert wperc.perceivable(st, [item]) == [item]
    assert wperc.perceivable(_state("nova_arcadia"), [item]) == []
    # quem esta la testemunha o inicio, e a regiao ouve o anuncio
    assert wperc.perceivable(_state("skallgard"), [_festa()]) != []
    near = digest_item(
        "g",
        5,
        "festa_proxima",
        "skallgard",
        "skallgard",
        "festa.proxima",
        {"local": "skallgard", "festa": "Noite dos Nomes"},
    )
    assert wperc.perceivable(_state("sk_farol_chama_negra"), [near]) == [near]  # regional
    assert wperc.perceivable(_state("brekmar"), [near]) == []


def test_templates_never_name_factions():
    names = {str(f.get("name", "")) for f in gamedata.seed_factions()}
    new = [
        t for t in wperc._templates()["templates"] if t.startswith(("estacao.", "passo.", "festa."))
    ]
    assert len(new) >= 11
    for tid in new:
        text = wperc._templates()["templates"][tid]["text"]
        assert "{faccao}" not in text and not any(n and n in text for n in names)


def test_season_render_uses_regional_label():
    item = digest_item("g", 5, "estacao", "", "", "estacao.inicio.inverno")
    assert "Noite Longa" in wperc.render(_state("skallgard"), item)
    assert "frio chegou" in wperc.render(_state("brekmar"), item)
    fest = wperc.render(_state("skallgard"), _festa())
    assert "Noite dos Nomes" in fest and "em luto" in fest


def test_storyteller_context_has_season_line_no_extra_llm_call(monkeypatch):
    world = {"current_location_id": "skallgard", "season": {"id": "outono"}}
    assert storyteller._season_line(world) == " Estação: Noite Longa."
    assert storyteller._season_line({"current_location_id": "skallgard"}) == ""
    monkeypatch.setenv("RPG_CALENDAR", "off")
    assert storyteller._season_line(world) == ""
    monkeypatch.setenv("RPG_CALENDAR", "on")

    from main import app
    from tests.test_fase2 import _state_for_graph

    class _Counting:
        calls = 0

        def with_structured_output(self, model):
            outer = self

            class _I:
                def invoke(self, _m):
                    outer.__class__.calls += 1
                    return model(text="Ecos do mundo.")

            return _I()

    def run(calendar_on: bool) -> int:
        monkeypatch.setenv("RPG_CALENDAR", "on" if calendar_on else "off")
        monkeypatch.setattr(wsim, "get_llm", lambda **kw: _Counting())
        _Counting.calls = 0
        st = _state_for_graph("vou descansar e acampar aqui")
        st["world"]["world_clock"] = {"day": 3, "period": "Noite"}
        sim = we.ensure_world_sim({**st, "world": st["world"]}, 3, st.get("factions"))
        sim["calm_until_day"] = 10_000
        sim["calendar"] = cal_for("primavera", 3)  # sem virada nem festa no dia 4
        st["world_sim"] = copy.deepcopy(sim)
        app.invoke(st)
        return _Counting.calls

    assert run(True) == run(False)


def test_api_world_block_has_season_only():
    import api

    w = {
        "current_location_id": "skallgard",
        "world_clock": {"day": 3, "period": "Manhã"},
        "season": {"id": "inverno", "label": "x", "day_in_season": 2},
    }
    block = api._world_block(w, {}, [], {})
    assert block["season"] == {"id": "inverno", "label": "Noite Longa"}
    blob = json.dumps(block, default=str)
    for banned in ("festivals", "epoch_offset", "closed_in", "day_in_season", "calendar"):
        assert banned not in blob
    assert api._world_block({"current_location_id": "skallgard"}, {}, [], {})["season"] is None


def test_save_load_roundtrip_calendar_festivals_season(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    cal = cal_for("verao", 5)
    sim = we.ensure_world_sim({"game_id": GID}, 1, [])
    sim["calendar"] = cal
    sim["festivals"] = [
        {
            "festa_id": "abc",
            "festival_id": "dia_da_fundacao",
            "year": 1,
            "start_day": 21,
            "end_day": 23,
            "status": "ativa",
            "location_ids": ["nova_arcadia"],
        }
    ]
    state = {
        "game_id": GID,
        "messages": [],
        "player": {},
        "world": {
            "season": {"id": "verao", "label": "Verão", "day_in_season": 3},
            "world_clock": {"day": 5, "period": "Manhã"},
        },
        "world_sim": sim,
    }
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(GID))
    assert loaded["world_sim"]["calendar"] == cal
    assert loaded["world_sim"]["festivals"] == sim["festivals"]
    assert loaded["world"]["season"]["id"] == "verao"
    assert wc.season_at(loaded["world_sim"]["calendar"], 5)["season"] == "verao"
