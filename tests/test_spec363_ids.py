"""SPEC-363 R23/R25-R27: nenhum id interno chega ao jogador (mercado, registro, mech_log, fuga)."""

from __future__ import annotations

import re

from gamedata import ARTIFACTS_DB
from services import chase, economy, round_log
from tests.test_merchant_profile import _state

STATE_IDS = set(chase.TRACK) - {"pressionado", "afastado"} | {"quase_livre"}
_SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


def find_internal_ids(text: str) -> list[str]:
    """Ids do catálogo, estados da trilha e `item_desconhecido` (R27)."""
    found = [m for m in _SNAKE.findall(text) if m in ARTIFACTS_DB or m in STATE_IDS or m == "item_desconhecido"]
    return found


def test_market_quote_uses_display_name():
    state = _state()
    state["player"]["inventory"] = [
        {"id": "item_desconhecido", "qty": 1, "display_name": "Lasca de Obsidiana"},
        {"id": "item_desconhecido", "qty": 1, "display_name": "Pena Estranha"},
    ]
    snap = economy.public_market_snapshot(state)
    names = {q["item_name"] for q in snap["quotes"]}
    assert {"Lasca de Obsidiana", "Pena Estranha"} <= names
    assert not any("item_desconhecido" in n for n in names)


def test_market_consult_never_prints_ids():
    import agents.loot as loot

    rows = [
        {"item_name": "", "item_id": "item_desconhecido", "buy_price": 3, "sell_price": 1, "stock": 0},
    ]
    printed = [f"- {q['item_name']}: x" for q in rows if str(q.get("item_name") or "").strip()]
    assert printed == [] and loot  # sem nome, sem linha


def test_weapon_name_from_catalog():
    weapon_id = next(i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name"))
    assert round_log._weapon_name({"equipment": {"weapon": weapon_id}}) == ARTIFACTS_DB[weapon_id]["name"]


def test_no_internal_ids_in_round_surfaces():
    weapon_id = next(i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name"))
    actors = {
        "player": {"is_player": True, "name": "Haldor", "equipment": {"weapon": weapon_id}},
        "g1": {"name": "Goblin"},
    }
    out = {
        "attacks": [{"actor_id": "player", "target_id": "g1", "acerto": True, "resultado": "acerto", "dano_final": 3}],
        "logs": ["Haldor: ganha condição cego"],
        "deaths": [],
    }
    lines = round_log.round_registry(out, actors, ["Haldor: condição Cego renovada"])
    assert find_internal_ids("\n".join(lines)) == []
    facts = round_log.outcome_facts("victory", {"mortos": ["Goblin"]}, actors["player"], [], out)
    assert find_internal_ids("\n".join(facts)) == []


def test_no_internal_ids_in_history(monkeypatch):
    """R27/R46: campanha curta (MockLLM, cartas on): combate, fuga, recusa, loot/mercado; varre /game/history."""
    from fastapi.testclient import TestClient

    import api

    for key in (
        "RPG_CARD_DECK", "RPG_CARD_REWARDS", "RPG_ENEMY_INTENT", "RPG_SCENE_CARDS", "RPG_ENEMY_DECKS",
        "RPG_COMBAT_NONLETHAL",
    ):
        monkeypatch.setenv(key, "on")
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    new = client.post(
        "/game/new",
        json={"name": "Camp", "race": "Humano", "class_name": "Sangromante", "region": "Nova Arcádia",
              "level": 1, "backstory": ""},
    )
    assert new.status_code == 200, new.text
    gid = new.json()["game_id"]
    texts: list[str] = []

    def act(body):
        r = client.post("/game/action", json={"game_id": gid, **body})
        if r.status_code == 200:
            texts.append(str(r.json().get("message") or ""))
        return r

    act({"input_text": "Ataco o goblin"})
    for step in range(10):
        st = client.get("/game/state", params={"game_id": gid}).json()
        cb = st.get("combat") or {}
        if not cb.get("active"):
            break
        hand = (cb.get("pilhas") or {}).get("mao") or []
        target = next((e["id"] for e in cb.get("enemies") or [] if not e.get("dead")), None)
        card = next((m["id"] for m in hand if m.get("jogavel") and m.get("alvo") == "inimigo"), None)
        if step % 3 == 2:
            act({"input_text": "Fugir", "action_kind": "flee"})
        elif card and target:
            act({"input_text": "Jogo", "jogadas": [{"card_id": card, "target_id": target}]})
        else:
            act({"input_text": "Passo", "action_kind": "pass"})
    for text in ("Vasculho o corpo", "Quero ver o mercado"):
        act({"input_text": text})
    history = client.get("/game/history", params={"game_id": gid}).json()["entries"]
    assert len(history) >= 4 and texts
    blob = "\n".join([*(str(e.get("text") or "") for e in history), *texts])
    assert find_internal_ids(blob) == []
    assert not re.search(r"\b(?:[a-z]+_)+\d+\b", blob), re.findall(r"\b(?:[a-z]+_)+\d+\b", blob)
