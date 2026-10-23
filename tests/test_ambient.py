"""SPEC-296 Etapa 1 — services/ambient.py (puro, offline)."""

import copy

import gamedata
from services.ambient import ambient_block, append_news, danger_words, heard_block


def _world(loc="sk_fortaleza_vorr", **over):
    w = {
        "current_location_id": loc,
        "current_location": (gamedata.get_location(loc) or {}).get("name", loc),
        "world_clock": {"day": 3, "period": "Noite"},
        "time_of_day": "Noite",
        "turn_count": 4,
        "danger_level": 4,
        "weather_state": "nevasca",
    }
    w.update(over)
    return w


def test_danger_words_bands():
    assert danger_words(1) == danger_words(2) == "tranquilo"
    assert danger_words(3) == "tenso"
    assert danger_words(4) == "perigoso"
    assert danger_words(5) == danger_words(9) == "mortal"


def test_ambient_story_has_weather_light_exits():
    w = _world()
    out = ambient_block(w, {}, audience="story")
    assert out.startswith("<AMBIENTE>") and out.rstrip().endswith("</AMBIENTE>")
    assert "Nevasca" in out
    assert "escuridão" in out
    assert "Dia 3" in out
    conns = gamedata.get_connections(w["current_location_id"])
    assert conns
    assert "Saídas:" in out
    assert all(c["name"] in out for c in conns)


def test_ambient_npc_and_combat_omit_exits():
    w = _world()
    for aud in ("npc", "combat"):
        out = ambient_block(w, {}, audience=aud)
        assert "Saídas" not in out
        assert "Nevasca" in out


def test_ambient_global_weather_included():
    w = _world(weather_global={"id": "tempestade_eter", "until_turn": 99})
    out = ambient_block(w, {}, audience="story")
    assert "Fenômeno global ativo" in out
    assert "Clima local: Nevasca" in out


def test_ambient_deterministic():
    w = _world()
    assert ambient_block(w, {}, audience="story") == ambient_block(w, {}, audience="story")


def test_append_news_fifo_dedupe_cap():
    w = {"world_clock": {"day": 2, "period": "Tarde"}, "news": []}
    snap = copy.deepcopy(w)
    w2 = append_news(w, text="Luzes ao norte", location_id="a", location_name="A", turn=1)
    assert w == snap  # não muta
    assert w2["news"][0]["text"] == "Luzes ao norte"
    assert w2["news"][0]["source"] == "pulse" and w2["news"][0]["day"] == 2
    # dedupe (mesmo texto + local) e vazio
    w3 = append_news(w2, text="Luzes ao norte", location_id="a", location_name="A", turn=2)
    w3 = append_news(w3, text="   ", location_id="a", location_name="A", turn=2)
    assert len(w3["news"]) == 1
    # mesmo texto em outro local entra
    w3 = append_news(w3, text="Luzes ao norte", location_id="b", location_name="B", turn=3)
    assert len(w3["news"]) == 2
    for i in range(20):
        w3 = append_news(w3, text=f"r{i}", location_id="a", location_name="A", turn=10 + i)
    assert len(w3["news"]) == 12
    assert w3["news"][-1]["text"] == "r19"


def test_heard_block_last_three_and_empty():
    assert heard_block({}) == ""
    w = {"world_clock": {"day": 1, "period": "Manhã"}}
    for i in range(5):
        w = append_news(w, text=f"rumor{i}", location_id="a", location_name="Lá", turn=i)
    out = heard_block(w)
    assert "rumor4" in out and "rumor2" in out and "rumor1" not in out
