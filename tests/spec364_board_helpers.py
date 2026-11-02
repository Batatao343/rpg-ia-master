"""SPEC-364: helpers de teste para montar um conflito com Baralho aberto pela API (MockLLM, sem rede)."""

from __future__ import annotations

from copy import deepcopy

CARD_FLAGS = (
    "RPG_CARD_DECK",
    "RPG_CARD_REWARDS",
    "RPG_ENEMY_INTENT",
    "RPG_SCENE_CARDS",
    "RPG_ENEMY_DECKS",
    "RPG_COMBAT_NONLETHAL",
)


def api_client(monkeypatch, hero: str = "Smoke4A"):
    """TestClient com save/load em memoria (o teste pode semear o estado salvo) e cartas `on`."""
    from fastapi.testclient import TestClient

    import api

    for key in CARD_FLAGS:
        monkeypatch.setenv(key, "on")
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    saved: dict = {}

    def save(state):
        saved[state["game_id"]] = deepcopy(state)
        return True

    def load(path=None):
        if not path:
            return None
        gid = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(saved.get(gid))

    monkeypatch.setattr(api, "save_game_state", save)
    monkeypatch.setattr(api, "load_game_state", load)
    client = TestClient(api.app)
    new = client.post(
        "/game/new",
        json={
            "name": hero,
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert new.status_code == 200, new.text
    return client, saved, new.json()["game_id"]


def open_combat(client, saved, gid):
    """Abre o conflito pela narracao ('Ataco o goblin'); devolve o estado salvo com `pilhas`."""
    r = client.post("/game/action", json={"game_id": gid, "input_text": "Ataco o goblin"})
    assert r.status_code == 200, r.text
    st = saved[gid]
    assert (st.get("combat") or {}).get("active"), "conflito nao abriu"
    assert isinstance(st["combat"].get("pilhas"), dict)
    return st


def hand_attack_cards(client, gid):
    st = client.get("/game/state", params={"game_id": gid}).json()
    hand = (st.get("combat") or {}).get("pilhas", {}).get("mao") or []
    return [m for m in hand if m.get("jogavel") and m.get("alvo") == "inimigo"]


def hide_enemy(state: dict, enemy_id: str) -> None:
    pos = state["combat"]["scene"]["positions"][enemy_id]
    pos["hidden_from"] = ["player"]
    pos["ocultacao"] = "escondido"
    for key in ("approx_from",):
        pos.pop(key, None)
    for enemy in state["enemies"]:
        if enemy.get("id") == enemy_id:
            enemy["concealment"] = "escondido"


def add_second_enemy(state: dict) -> str:
    """Clona o 1o inimigo vivo (id novo) na lista e na cena; devolve o id novo."""
    base = next(e for e in state["enemies"] if not e.get("dead"))
    clone = deepcopy(base)
    new_id = f"{base['id']}_b"
    clone["id"] = new_id
    clone["name"] = "Corvo Rubro"  # nome distinto: sem renomear homônimos ("Goblin 1 B")
    state["enemies"].append(clone)
    positions = state["combat"]["scene"]["positions"]
    positions[new_id] = deepcopy(positions[base["id"]])
    # P3-8: o 2o inimigo também entra no manifesto do encontro, senão `reconcile_roster` o corta como intruso
    from services import encounter_manifest as em

    meta = state["combat"]
    if em.is_valid_manifest(meta.get("encounter")):
        meta["encounter"] = em.add_joined(meta["encounter"], clone, "teste", 0)
    return new_id
