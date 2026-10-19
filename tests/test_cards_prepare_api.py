"""SPEC-209 R4/R5/R9: preparar Cartas fora de combate, can_reorganize e cicatrizes."""

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

import persistence


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import api

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _new(client, level=3) -> str:
    r = client.post(
        "/game/new",
        json={
            "name": "Deck",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": level,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _load(gid):
    return persistence.load_game_state(persistence.save_path(gid))


def _save(state):
    assert persistence.save_game_state(state)


def _state_resp(client, gid):
    r = client.get("/game/state", params={"game_id": gid})
    assert r.status_code == 200, r.text
    return r.json()


def _prep(client, gid, ids):
    return client.post(
        "/game/cards/prepare",
        json={"game_id": gid, "prepared": ids, "action_id": str(uuid.uuid4())},
    )


def test_prepare_ok_persiste_e_reload(client):
    gid = _new(client)
    st = _load(gid)
    known = st["player"]["known_cards"]
    assert len(known) >= 2
    r = _prep(client, gid, [known[0]])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["prepared_cards"] == [known[0]]
    assert body["prepared_slots"] >= 1
    assert [c["id"] for c in body["cards"] if c["prepared"]] == [known[0]]
    assert _load(gid)["player"]["prepared_cards"] == [known[0]]
    cards = _state_resp(client, gid)["player_stats"]["cards"]
    assert [c["id"] for c in cards if c["prepared"]] == [known[0]]


def test_carta_fora_do_acervo_400(client):
    gid = _new(client)
    before = copy.deepcopy(_load(gid)["player"]["prepared_cards"])
    r = _prep(client, gid, ["carta_inexistente"])
    assert r.status_code == 400
    assert _load(gid)["player"]["prepared_cards"] == before


def test_excede_limite_400_save_intocado(client):
    gid = _new(client)
    st = _load(gid)
    from services import cards

    limit = cards.prepare_slots_for_level(st["player"]["level"])
    extras = [f"x{i}" for i in range(limit + 1)]
    st["player"]["known_cards"] = list(st["player"]["known_cards"]) + extras
    _save(st)
    before = _load(gid)["player"]["prepared_cards"]
    r = _prep(client, gid, list(st["player"]["known_cards"])[: limit + 1])
    assert r.status_code == 400
    assert _load(gid)["player"]["prepared_cards"] == before


def test_em_combate_409(client):
    gid = _new(client)
    st = _load(gid)
    st["combat"] = {"active": True, "round": 1, "order": []}
    _save(st)
    r = _prep(client, gid, [])
    assert r.status_code == 409


def test_zona_perigosa_409(client):
    gid = _new(client)
    st = _load(gid)
    st["world"]["danger_level"] = 5
    _save(st)
    assert _prep(client, gid, []).status_code == 409


def test_apex_409_com_location_injetada(client):
    gid = _new(client)
    st = _load(gid)
    st["world"]["current_location_id"] = "sk_fortaleza_vorr"
    st["world"]["danger_level"] = 1
    _save(st)
    r = _prep(client, gid, [])
    assert r.status_code == 409
    assert "apex" in r.text.lower() or "perigos" in r.text.lower()
    ps = _state_resp(client, gid)["player_stats"]
    assert ps["can_reorganize"]["allowed"] is False and ps["can_reorganize"]["reason"]
    # SPEC-265: recurso legado mana/stamina saiu da view pública do jogador
    assert not {"mana", "max_mana", "stamina", "max_stamina"} & set(ps)


def test_location_transitoria_nao_persistida(client):
    gid = _new(client)
    known = _load(gid)["player"]["known_cards"]
    assert _prep(client, gid, [known[0]]).status_code == 200
    assert "_location" not in _load(gid)
    _state_resp(client, gid)
    assert "_location" not in _load(gid)


def test_simulacao_409(client):
    gid = _new(client)
    st = _load(gid)
    st["combat_simulation"] = {"enabled": True}
    _save(st)
    assert _prep(client, gid, []).status_code == 409


def test_death_pending_409(client):
    gid = _new(client)
    st = _load(gid)
    st["death_pending"] = True
    _save(st)
    assert _prep(client, gid, []).status_code == 409


def test_replay_action_id_idempotente(client):
    gid = _new(client)
    known = _load(gid)["player"]["known_cards"]
    aid = str(uuid.uuid4())
    body = {"game_id": gid, "prepared": [known[0]], "action_id": aid}
    a = client.post("/game/cards/prepare", json=body)
    b = client.post("/game/cards/prepare", json=body)
    assert a.status_code == b.status_code == 200
    assert a.json()["prepared_cards"] == b.json()["prepared_cards"]


def test_can_reorganize_no_state(client):
    gid = _new(client)
    ps = _state_resp(client, gid)["player_stats"]
    assert ps["can_reorganize"] == {"allowed": True, "reason": ""}
    assert ps["prepared_slots"] >= 1


def test_can_reorganize_em_combate_tem_razao(client):
    gid = _new(client)
    st = _load(gid)
    st["combat"] = {"active": True, "round": 1, "order": []}
    _save(st)
    cr = _state_resp(client, gid)["player_stats"]["can_reorganize"]
    assert cr["allowed"] is False and "combate" in cr["reason"].lower()


def test_scars_projetadas(client):
    gid = _new(client)
    st = _load(gid)
    st["player"]["scars"] = [
        {
            "id": "scar_x_0",
            "consequencia_negativa": "Tremor na mão",
            "habilidade_positiva_relacionada": "Olhar frio",
            "origem": "Queda em Vorr",
        }
    ]
    _save(st)
    scars = _state_resp(client, gid)["player_stats"]["scars"]
    assert scars == [
        {
            "id": "scar_x_0",
            "origem": "Queda em Vorr",
            "consequencia_negativa": "Tremor na mão",
            "habilidade_positiva_relacionada": "Olhar frio",
        }
    ]


def test_save_sem_scars_carrega_sem_secao(client):
    gid = _new(client)
    st = _load(gid)
    st["player"].pop("scars", None)
    _save(st)
    assert _state_resp(client, gid)["player_stats"]["scars"] == []


def test_deck_campos_aditivos(client):
    gid = _new(client, level=4)
    ps = _state_resp(client, gid)["player_stats"]
    assert isinstance(ps["virtue_cards"], list)
    assert isinstance(ps["evolvable_card_ids"], list)
    assert "subclass" in ps
    assert set(ps["evolvable_card_ids"]) <= {c["id"] for c in ps["cards"]}


def test_prepare_entra_no_rate_limit(tmp_path, monkeypatch):
    """Revisão Sol: a rota muta o save — mesma janela de rate limit de equip/levelup."""
    import api

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_RATE_LIMIT", "2")
    api._rate_hits.clear()
    c = TestClient(api.app)
    codes = [
        c.post(
            "/game/cards/prepare",
            json={"game_id": "../x", "prepared": [], "action_id": str(uuid.uuid4())},
        ).status_code
        for _ in range(3)
    ]
    api._rate_hits.clear()
    assert codes[-1] == 429, codes
