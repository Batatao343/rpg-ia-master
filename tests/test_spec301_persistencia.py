"""SPEC-301 Etapa 9 — persistência: round-trip e save antigo (R23/R24)."""

from __future__ import annotations

import json
import os

import persistence
from tests.spec301_support import joined, make_state, mission_quest


def _full(st):
    st = dict(st)
    st.update(
        {
            "narrative_summary": "",
            "archivist_last_run": 0,
            "chronicle": [],
            "messages": [],
            "party": [],
            "enemies": [],
            "campaign_plan": {},
        }
    )
    return st


def test_round_trip_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    st = _full(joined(make_state(), "legiao_ferro", merit=4, rank_index=1, marks=["x"]))
    st["game_id"] = "spec301_rt"
    st["faction_membership"]["legiao_ferro"]["rival_awareness"] = {"filhos_chama_azul": -1}
    for f in st["factions"]:
        if f["id"] == "legiao_ferro":
            f["influence"] = 4
            f["influence_periods"] = 2
    st["quests"] = [
        mission_quest("legiao_ferro", kind="sabotagem", tier=2, target="filhos_chama_azul")
    ]
    assert persistence.save_game_state(st)
    loaded = persistence.load_game_state(os.path.join(str(tmp_path), "spec301_rt.json"))
    assert loaded["faction_membership"] == st["faction_membership"]
    lf = next(f for f in loaded["factions"] if f["id"] == "legiao_ferro")
    assert lf["influence"] == 4 and lf["influence_periods"] == 2
    q = loaded["quests"][0]
    assert q["faction_id"] == "legiao_ferro" and q["mission_kind"] == "sabotagem"
    assert q["mission_tier"] == 2 and q["target_faction_id"] == "filhos_chama_azul"


def test_save_antigo_sem_campos_carrega(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    st = _full(make_state())
    st["game_id"] = "spec301_old"
    st["factions"] = [{k: v for k, v in f.items() if k != "influence"} for f in st["factions"]]
    assert persistence.save_game_state(st)
    path = os.path.join(str(tmp_path), "spec301_old.json")
    raw = json.load(open(path, encoding="utf-8"))
    raw.pop("faction_membership", None)  # save pré-301
    json.dump(raw, open(path, "w", encoding="utf-8"))
    loaded = persistence.load_game_state(path)
    assert loaded["faction_membership"] == {}
    import world_utils as wu

    assert all(f["influence"] == 0 for f in wu.ensure_factions(loaded["factions"]))
