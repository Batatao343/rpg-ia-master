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
    found = [
        m
        for m in _SNAKE.findall(text)
        if m in ARTIFACTS_DB or m in STATE_IDS or m == "item_desconhecido"
    ]
    found += re.findall(
        r"\balcancado\b", text
    )  # SPEC-364 R3/R29: a trilha nunca mostra o id sem acento
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
        {
            "item_name": "",
            "item_id": "item_desconhecido",
            "buy_price": 3,
            "sell_price": 1,
            "stock": 0,
        },
    ]
    printed = [f"- {q['item_name']}: x" for q in rows if str(q.get("item_name") or "").strip()]
    assert printed == [] and loot  # sem nome, sem linha


def test_weapon_name_from_catalog():
    weapon_id = next(
        i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name")
    )
    assert (
        round_log._weapon_name({"equipment": {"weapon": weapon_id}})
        == ARTIFACTS_DB[weapon_id]["name"]
    )


def test_no_internal_ids_in_round_surfaces():
    weapon_id = next(
        i for i, v in ARTIFACTS_DB.items() if v.get("type") == "weapon" and v.get("name")
    )
    actors = {
        "player": {"is_player": True, "name": "Haldor", "equipment": {"weapon": weapon_id}},
        "g1": {"name": "Goblin"},
    }
    out = {
        "attacks": [
            {
                "actor_id": "player",
                "target_id": "g1",
                "acerto": True,
                "resultado": "acerto",
                "dano_final": 3,
            }
        ],
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
        "RPG_CARD_DECK",
        "RPG_CARD_REWARDS",
        "RPG_ENEMY_INTENT",
        "RPG_SCENE_CARDS",
        "RPG_ENEMY_DECKS",
        "RPG_COMBAT_NONLETHAL",
    ):
        monkeypatch.setenv(key, "on")
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    new = client.post(
        "/game/new",
        json={
            "name": "Camp",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
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
        card = next(
            (m["id"] for m in hand if m.get("jogavel") and m.get("alvo") == "inimigo"), None
        )
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


def test_no_internal_ids_or_hero_name_in_history_r29(monkeypatch):
    """SPEC-364 R29/R16: 2 fugas seguidas, Cartas de Cena de Carga e condição, consulta do mercado com item
    livre longo — sem ids da trilha e sem linha na voz do nome do herói."""
    import random
    from copy import deepcopy

    from tests import spec364_board_helpers as hp

    hero = "Smoke4A"
    client, saved, gid = hp.api_client(monkeypatch, hero=hero)
    st = hp.open_combat(client, saved, gid)
    st["combat"]["scene"]["cartas_de_cena"] = [
        "nevoa_cinza_do_ermo",
        "vigilia_dos_druidas_cinzentos",
    ]
    st["combat"]["chase"] = {
        "trilha": "alcancado",
        "alcancado": True,
        "escapou": False,
        "fugitive_id": "player",
        "perseguidores": [e["id"] for e in st["enemies"]],
    }
    for enemy in st["enemies"]:
        enemy["pursuit_policy"] = "persegue"
    st["player"]["inventory"].append(
        {
            "id": "item_desconhecido",
            "qty": 1,
            "display_name": "Faca de esfolar de osso de baleia, cabo envolto em couro cru — a lâmina que Haldor usa",
        }
    )
    saved[gid] = deepcopy(st)
    texts: list[str] = []
    for seed in (3, 5):  # duas fugas seguidas
        random.seed(seed)
        r = client.post(
            "/game/action", json={"game_id": gid, "input_text": "Fugir", "action_kind": "flee"}
        )
        assert r.status_code == 200, r.text
        texts.append(str(r.json().get("message") or ""))
        if not (saved[gid].get("combat") or {}).get("active"):
            break
    saved[gid]["combat"] = {**(saved[gid].get("combat") or {}), "active": False}
    world = saved[gid]["world"]
    world["current_location_id"] = "na_anel_dourado"  # local com mercador
    world["visited"] = [*world.get("visited", []), "na_anel_dourado"]
    r = client.post(
        "/game/action", json={"game_id": gid, "input_text": "O que o mercador tem à venda?"}
    )
    texts.append(str(r.json().get("message") or ""))
    # P3-10: a consulta aconteceu de fato, com o item livre longo pelo nome curto
    assert "consulta sem transação" in texts[-1], texts[-1]
    assert (
        "Pelo que você carrega:" in texts[-1] and "Faca de esfolar de osso de baleia" in texts[-1]
    )
    assert "a lâmina que Haldor" not in texts[-1]
    history = client.get("/game/history", params={"game_id": gid}).json()["entries"]
    lines = [
        ln
        for blob in [*texts, *(str(e.get("text") or "") for e in history)]
        for ln in blob.splitlines()
    ]
    blob = "\n".join(lines)
    assert find_internal_ids(blob) == []
    assert "quase_livre" not in blob and "alcancado" not in blob
    for ln in lines:
        assert not ln.strip().startswith(hero) and f"{hero}:" not in ln, ln


def test_spec367_voice_omen_and_condition_end():
    """SPEC-367 R25: presságio sem o nome do herói e condição de inimigo sem formato cru."""
    from services import enemy_intent as ei

    actors = {
        "g1": {"id": "g1", "name": "Goblin", "family": "fera"},
        "h": {"id": "h", "name": "Smoke5A", "is_player": True},
    }
    row = ei.public_intent(
        {"actor_id": "g1", "tipo": "ataque", "alvo_id": "h", "carta_id": None},
        "desconhecida",
        actors_by_id=actors,
    )
    assert "Smoke5A" not in row["sinal"] and not find_internal_ids(row["sinal"])
    line = round_log._voce("Goblin-Mineiro: cego terminou.", "Mirela5")
    assert not re.match(r"^[^:]+: \w+ terminou", line) and ": cego terminou" not in line
