"""SPEC-333 R4-R6 - Forja do baralho: Esquecer (descanso longo / templo), Afiar, Purgar, API."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import persistence
from services import card_piles as cp
from services import card_rewards as cr
from services import cards

TEMPLO = "nova_arcadia"  # cidade segura = templo/curandeiro
ESTRADA = "pradaria_ruinas"  # sem templo


def _starter(class_name="Sangromante"):
    pool = [
        c["id"]
        for c in cards.cards_for_class(class_name)
        if not c.get("subclasse") and c.get("tipo") == "ativa" and c.get("level_req", 1) == 1
    ][:6]
    p = {
        "class_name": class_name,
        "level": 3,
        "known_cards": list(pool),
        "prepared_cards": list(pool[:4]),
        "gold": 100,
        "entropy": 5,
        "max_entropy": 10,
        "inventory": [],
    }
    cp.migrate_deck(p)
    return p


def _state(loc=TEMPLO, **world):
    return {"player": _starter(), "world": {"current_location_id": loc, "danger_level": 1, **world}}


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _extra_card(st):
    """Uma Carta não-básica do baralho (a que o jogador quer esquecer)."""
    basics = {c for ids in cards.basicas_for_class("Sangromante").values() for c in ids}
    return next(c for c in st["player"]["deck"] if c not in basics)


# ------------------------------------------------------------------ Esquecer (R4)
def test_esquecer_so_depois_de_descanso_longo():
    st = _state(ESTRADA)
    cid = _extra_card(st)
    res = cr.forget(st, cid, "descanso")
    assert not res["ok"] and "descanso longo" in res["error"]
    cr.on_long_rest(st["player"])
    copies = st["player"]["deck"].count(cid)
    res = cr.forget(st, cid, "descanso")
    assert res["ok"] and st["player"]["forja_esquecer"] == 0
    assert st["player"]["deck"].count(cid) == copies - 1  # só UMA cópia
    assert cid in st["player"]["known_cards"]  # o Acervo fica
    assert not cr.forget(st, cid, "descanso")["ok"]  # uma carga por descanso


def test_descanso_longo_real_concede_a_carga(monkeypatch):
    import world_utils

    player = _starter()
    player.update(
        {
            "vitalidade": 3,
            "max_vitalidade": 20,
            "virtudes": {"forca": 2, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1},
            "ferimentos": {"leve": [], "grave": [], "critico": []},
        }
    )
    out, _world = world_utils.apply_rest(player, {"current_location_id": ESTRADA})
    assert out.get("forja_esquecer") == 1
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    out2, _ = world_utils.apply_rest(_starter() | {"vitalidade": 3, "max_vitalidade": 20}, {})
    assert "forja_esquecer" not in out2


def test_esquecer_no_templo_custa_ouro_sem_limite():
    st = _state(TEMPLO)
    cid = _extra_card(st)
    gold = st["player"]["gold"]
    res = cr.forget(st, cid, "templo")
    assert res["ok"] and st["player"]["gold"] == gold - cr.FORGET_GOLD
    assert cr.forget(_state(ESTRADA), cid, "templo")["ok"] is False  # fora de templo
    poor = _state(TEMPLO)
    poor["player"]["gold"] = 1
    assert "ouro" in cr.forget(poor, _extra_card(poor), "templo")["error"]


def test_esquecer_bloqueado_em_combate_e_sem_baralho():
    st = _state()
    st["player"]["forja_esquecer"] = 1
    st["combat"] = {"active": True}
    res = cr.forget(st, _extra_card(st), "descanso")
    assert not res["ok"] and res["conflito"]
    st2 = _state()
    st2["player"].pop("deck")
    assert not cr.forget(st2, "x", "templo")["ok"]


def test_baralho_abaixo_do_minimo_completa_com_basicas():
    st = _state()
    p = st["player"]
    basics = cards.basicas_for_class("Sangromante")
    p["deck"] = [basics["golpe"][0]] * 6 + [basics["guarda"][0]] * 5 + [_extra_card(st)]
    assert len(p["deck"]) == cards.DECK_MIN
    cid = _extra_card(st)
    assert cr.forget(st, cid, "templo")["ok"]
    assert len(p["deck"]) == cards.DECK_MIN  # R6: completou com básicas
    assert cid not in p["deck"]
    # básica no mínimo não adianta esquecer
    assert not cr.forget(st, basics["golpe"][0], "templo")["ok"]


# ------------------------------------------------------------------ Afiar (R5)
def _com_material(st, qty=1):
    st["player"]["inventory"] = [{"id": "essencia_de_cinza", "qty": qty}]


def _comum_do_acervo(st):
    pool = [
        c["id"]
        for c in cards.cards_for_class("Sangromante")
        if cr.rarity_of(c) == "comum" and cr.can_sharpen_card(c) and c.get("tipo") == "ativa"
    ]
    cid = pool[0]
    if cid not in st["player"]["known_cards"]:
        st["player"]["known_cards"].append(cid)
    return cid


def test_afiar_consome_material_e_vira_versao_mais():
    st = _state(ESTRADA)
    cid = _comum_do_acervo(st)
    base = cards.effective_card(st["player"], cid)
    assert not cr.sharpen(st, cid)["ok"]  # sem material
    _com_material(st, 2)
    res = cr.sharpen(st, cid)
    assert res["ok"] and st["player"]["inventory"] == [{"id": "essencia_de_cinza", "qty": 1}]
    sharp = cards.effective_card(st["player"], cid)
    key = "dano_base" if "dano_base" in base["efeito"] else "valor"
    assert key in base["efeito"], base["efeito"]
    assert sharp["efeito"][key] == base["efeito"][key] + 1
    assert cards.get_card(cid)["efeito"] == base["efeito"]  # catálogo intocado
    assert not cr.sharpen(st, cid)["ok"]  # uma vez só


def test_afiar_usa_a_definicao_da_propria_carta(monkeypatch):
    st = _state(ESTRADA)
    cid = _comum_do_acervo(st)
    _com_material(st)
    card = dict(cards.get_card(cid))
    card["afiada"] = {"custo_folego": 0}
    monkeypatch.setattr(cards, "_CARDS", {**cards.all_cards(), cid: card})
    assert cr.sharpen(st, cid)["ok"]
    assert cards.effective_card(st["player"], cid)["custo_folego"] == 0


def test_afiar_recusa_carta_fora_do_acervo_e_nao_comum():
    st = _state(ESTRADA)
    _com_material(st)
    assert not cr.sharpen(st, "inexistente")["ok"]
    rara = next(
        c["id"]
        for c in cards.all_cards().values()
        if cr.rarity_of(c) == "rara" and c.get("tipo") == "ativa"
    )
    st["player"]["known_cards"].append(rara)
    assert "comuns" in cr.sharpen(st, rara)["error"]
    assert st["player"]["inventory"] == [{"id": "essencia_de_cinza", "qty": 1}]


# ------------------------------------------------------------------ Purgar Cicatriz (R8)
def _cicatriz(st):
    scar = {"id": "scar_braco_0", "origem": "braco", "consequencia_negativa": "x"}
    assert cr.register_scar_curse(st["player"], scar) == "mld_cicatriz_braco"
    return scar


def test_maldicao_da_cicatriz_nao_se_esquece_nem_sai_do_baralho_por_set_deck():
    st = _state()
    _cicatriz(st)
    p = st["player"]
    assert p["deck"].count("mld_cicatriz_braco") == 1
    assert not cr.forget(st, "mld_cicatriz_braco", "templo")["ok"]
    sem = [c for c in p["deck"] if c != "mld_cicatriz_braco"]
    res = cards.set_deck(st, sem)
    assert not res["ok"] and "Purgar" in res["error"]
    assert cards.set_deck(st, list(p["deck"]))["ok"]  # com a maldição, o baralho vale


def test_purgar_no_templo_e_com_medico_custa_ouro():
    st = _state()
    _cicatriz(st)
    p = st["player"]
    assert not cr.purge_curse(st, "scar_braco_0", "medico")["ok"]  # sem Médico de Campo
    st["party"] = [{"class_name": "Médico de Campo", "active": True}]
    assert cr.purge_curse(st, "scar_braco_0", "medico")["ok"]
    assert "mld_cicatriz_braco" not in p["deck"] and p["cicatriz_cartas"] == []
    assert p["gold"] == 100 - cr.PURGE_GOLD
    assert len(p["deck"]) >= cards.DECK_MIN
    assert not cr.purge_curse(st, "scar_braco_0", "templo")["ok"]  # já purgada
    st2 = _state(ESTRADA)
    _cicatriz(st2)
    assert not cr.purge_curse(st2, "scar_braco_0", "templo")["ok"]  # fora do templo


# ------------------------------------------------------------------ API (espólio + forja)
@pytest.fixture()
def client(tmp_path, monkeypatch):
    import api

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _new(client):
    r = client.post(
        "/game/new",
        json={
            "name": "Forja",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 4,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _load(gid):
    return persistence.load_game_state(persistence.save_path(gid))


def _save(state):
    assert persistence.save_game_state(state)


def _post(client, path, gid, **body):
    return client.post(path, json={"game_id": gid, "action_id": str(uuid.uuid4()), **body})


def _stats(client, gid):
    r = client.get("/game/state", params={"game_id": gid})
    assert r.status_code == 200, r.text
    return r.json()["player_stats"]


def test_blocos_novos_so_aparecem_com_a_flag_on(client, monkeypatch):
    gid = _new(client)
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    ps = _stats(client, gid)
    assert "espolio_pendente" not in ps and "forja" not in ps
    r = _post(client, "/game/espolio", gid, card_id=None)
    assert r.status_code == 409 and r.json()["code"] == "card_rewards_off"
    r = _post(client, "/game/forja", gid, acao="afiar", card_id="x")
    assert r.status_code == 409 and r.json()["code"] == "card_rewards_off"


def test_espolio_pela_api_aceita_recusa_e_persiste(client, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    gid = _new(client)
    st = _load(gid)
    st["player"].pop("espolio_pendente", None)
    cr.grant_after_conflict(
        st, st["player"], conflict_id="c", seed=5, defeated=[], objective_result=None, turn=1
    )
    _save(st)
    ps = _stats(client, gid)
    ofertas = ps["espolio_pendente"]["ofertas"]
    assert len(ofertas) == 3 and ps["espolio_pendente"]["recusa_ouro"] == 15
    r = _post(client, "/game/espolio", gid, card_id="nao_esta_no_espolio")
    assert r.status_code == 400 and r.json()["code"] == "espolio_rejected"
    pick = ofertas[0]["id"]
    r = _post(client, "/game/espolio", gid, card_id=pick)
    assert r.status_code == 200, r.text
    assert pick in _load(gid)["player"]["known_cards"]
    assert "espolio_pendente" not in _stats(client, gid)
    # recusa em um segundo espólio
    st = _load(gid)
    gold = st["player"]["gold"]
    cr.grant_after_conflict(
        st, st["player"], conflict_id="c2", seed=6, defeated=[], objective_result=None, turn=2
    )
    _save(st)
    r = _post(client, "/game/espolio", gid, card_id=None)
    assert r.status_code == 200 and _load(gid)["player"]["gold"] == gold + 15


def test_forja_pela_api(client, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    gid = _new(client)
    st = _load(gid)
    cp.migrate_deck(st["player"])
    st["player"]["forja_esquecer"] = 1
    st["world"]["current_location_id"] = ESTRADA
    st["world"]["danger_level"] = 1
    _save(st)
    forja = _stats(client, gid)["forja"]
    assert forja["permitido"] and forja["esquecer"]["descanso"] and forja["baralho"]
    cid = next(r["id"] for r in forja["baralho"] if not r["id"].startswith("bas_"))
    r = _post(client, "/game/forja", gid, acao="esquecer", card_id=cid, via="descanso")
    assert r.status_code == 200, r.text
    assert _load(gid)["player"]["forja_esquecer"] == 0
    r = _post(client, "/game/forja", gid, acao="esquecer", card_id=cid, via="descanso")
    assert r.status_code == 400 and r.json()["code"] == "forja_rejected"
    r = _post(client, "/game/forja", gid, acao="inventada")
    assert r.status_code == 422
