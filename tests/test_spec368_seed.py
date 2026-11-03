"""SPEC-368 R13 (P1-1) - round-trip save -> load -> /game/state: o save semeado mostra a cena do §6."""

from __future__ import annotations

import pytest

import persistence
from tests.fixtures import spec368_seed as sd


def _hand(v: dict) -> list[str]:
    return [m["id"] for m in (v.get("combat") or {}).get("pilhas", {}).get("mao", [])]


def _enemy_ids(v: dict) -> list[str]:
    return [e["id"] for e in (v.get("combat") or {}).get("enemies", [])]


def _seed(tmp_path, item, variant=""):
    gid = sd.seed_save(item, variant=variant, saves_dir=str(tmp_path))
    return gid, sd.view(gid, str(tmp_path))


def _state(tmp_path, gid, **flags) -> dict:
    with sd._legacy(str(tmp_path)), sd.env(flags):
        return persistence.load_game_state(persistence.save_path(gid))


def test_every_combat_item_has_a_seed():
    assert set(sd.ITEMS) == {1, 2, 3, 4, 5, 6, 7, 12, 13, 14}


def test_item1_pacto_hand_and_short_folego(tmp_path):
    _, v = _seed(tmp_path, 1)
    assert _hand(v) == ["bas_san_golpe", "bas_san_golpe", "bas_san_guarda"]
    assert v["combat"]["pilhas"]["folego"] == 1 and v["combat"]["round"] == 0


def test_item1_rollback_save_is_restored_when_the_flag_goes_off(tmp_path):
    gid, _ = _seed(tmp_path, 1, "rollback")
    state = _state(tmp_path, gid)
    assert "prepared_cards_pre_deck" in state["player"]  # baralho ativo no save
    before = list(state["player"]["prepared_cards_pre_deck"])
    again = _state(tmp_path, gid, RPG_CARD_DECK="off")
    assert (
        again["player"]["prepared_cards"] == before
        and "prepared_cards_pre_deck" not in again["player"]
    )


def test_item2_family_studied_has_an_omen(tmp_path):
    gid, v = _seed(tmp_path, 2)
    assert v["combat"].get("pressagios_publicos")
    enemy = _state(tmp_path, gid)["enemies"][0]
    assert enemy.get("revealed_cards")


@pytest.mark.parametrize(
    ("variant", "card"),
    [("", "san1_exp_segundo_ato"), ("rachadura", "cor1_ino_junta_emperrada")],
)
def test_item3_eco_and_rachadura_hands(tmp_path, variant, card):
    _, v = _seed(tmp_path, 3, variant)
    assert card in _hand(v)


def test_item4_escolta_objective(tmp_path):
    _, v = _seed(tmp_path, 4)
    assert (v["combat"].get("objetivo") or {}).get("tipo") == "proteger"
    assert len(_enemy_ids(v)) == 2


@pytest.mark.parametrize(
    ("variant", "prefix"),
    [
        ("", "enemy_soldado_legiao_ferro"),
        ("chefe", "enemy_boss_valerius"),
        ("nova", "mon_costurado_de_lentes"),
    ],
)
def test_item5_legion_boss_and_new_faction(tmp_path, variant, prefix):
    _, v = _seed(tmp_path, 5, variant)
    assert all(i.startswith(prefix) for i in _enemy_ids(v)) and _enemy_ids(v)
    assert v["combat"].get("pressagios_publicos")


def test_item6_dor_surda_in_hand_and_deterministic_spoils(tmp_path):
    _, v = _seed(tmp_path, 6)
    assert "sts_dor_surda" in _hand(v)
    assert any(i.startswith("enemy_degolador_mao_sombria") for i in _enemy_ids(v))
    gid, after = _seed(tmp_path, 6, "espolio")
    assert not (after.get("combat") or {}).get("active")
    pending = after["player_stats"].get("espolio_pendente") or {}
    assert any(
        c["id"].startswith("inf_fac_mao_sombria")
        if isinstance(c, dict)
        else c.startswith("inf_fac_mao_sombria")
        for c in pending.get("ofertas", [])
    )
    assert _state(tmp_path, gid)["player"]["forja_esquecer"] == 1  # descanso longo -> Esquecer


@pytest.mark.parametrize(("variant", "cls"), [("", "Corruptor"), ("medico", "Médico de Campo")])
def test_item7_corruptor_and_medico(tmp_path, variant, cls):
    _, v = _seed(tmp_path, 7, variant)
    assert v["player_stats"]["class_name"] == cls and _hand(v)


def test_item12_enemy_one_hit_from_victory(tmp_path):
    gid, v = _seed(tmp_path, 12)
    assert _hand(v)[0] == "bas_san_golpe"
    assert int(_state(tmp_path, gid)["enemies"][0]["vitalidade"]) == 1


@pytest.mark.parametrize(
    ("variant", "card"),
    [
        ("", "bas_dev_voto"),
        ("leitura", "arc1_cal_leitura"),
        ("armadura", "cor_ino_fadiga"),
        ("reacao", "dev_encaixe"),
    ],
)
def test_item13_355_hands(tmp_path, variant, card):
    _, v = _seed(tmp_path, 13, variant)
    assert card in _hand(v)


def test_item13_renegado_has_no_descarga_arcana(tmp_path):
    from services import cards

    gid, v = _seed(tmp_path, 13, "renegado")
    assert _enemy_ids(v)[0].startswith("enemy_renegado_ermo")
    names = [
        str((cards.get_card(c["id"] if isinstance(c, dict) else c) or {}).get("name", "")).lower()
        for c in _state(tmp_path, gid)["enemies"][0].get("cartas") or []
    ]
    assert "descarga arcana" not in names


def test_item14_quest_justa_is_in_the_save(tmp_path):
    gid, _ = _seed(tmp_path, 14)
    quests = _state(tmp_path, gid)["quests"]
    assert any(q.get("id") == "q368" and q.get("reward_card_planned") for q in quests)


def test_unknown_item_or_variant_is_refused(tmp_path):
    with pytest.raises(ValueError):
        sd.seed_save(8, saves_dir=str(tmp_path))
    with pytest.raises(ValueError):
        sd.seed_save(3, variant="x", saves_dir=str(tmp_path))


def test_item12_seeded_scene_is_playable_through_the_real_api(tmp_path):
    from fastapi.testclient import TestClient

    import api

    gid, v = _seed(tmp_path, 12)
    target = _enemy_ids(v)[0]
    with sd._legacy(str(tmp_path)):
        r = TestClient(api.app).post(
            "/game/action",
            json={
                "game_id": gid,
                "input_text": "Encerro a rodada: Golpe.",
                "jogadas": [{"card_id": "bas_san_golpe", "target_id": target}],
            },
        )
    assert r.status_code == 200, r.text
    after = sd.view(gid, str(tmp_path))
    assert (after.get("combat") or {}).get("active") is False or int(after["combat"]["round"]) >= 1
