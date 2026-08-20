"""Contratos de progressão após o cutover conflito-13 (Cartas + Virtudes)."""

import progression as pg
from services import cards


def _player(**over):
    player = {
        "name": "Ava", "class_name": "Devoto do Abismo", "level": 1, "xp": 0,
        "hp": 30, "max_hp": 30, "entropy": 16, "max_entropy": 16,
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 2},
        "known_cards": ["dev_golpe_convite"], "prepared_cards": ["dev_golpe_convite"],
        "card_usage": {}, "virtue_cards": [], "evolved_cards": {},
        "pending_choices": [],
    }
    player.update(over)
    return player


def test_level_up_oferece_carta_e_virtude():
    player, events = pg.grant_xp(_player(), pg.XP_TABLE[2])
    assert player["level"] == 2
    assert [choice["kind"] for choice in player["pending_choices"]] == ["carta", "virtude"]
    assert events[0]["type"] == "level_up"


def test_nivel_tres_oferece_subclasse_explica_e_carta():
    player, _ = pg.grant_xp(
        _player(level=2, xp=pg.XP_TABLE[2]), pg.XP_TABLE[3] - pg.XP_TABLE[2])
    assert [choice["kind"] for choice in player["pending_choices"]] == ["subclass", "carta"]


def test_eligible_cards_respeita_classe_e_subclasse():
    player = _player(
        level=4,
        subclass="consagrado",
        known_cards=["dev_golpe_convite", "dev_cons_marca"],
    )
    eligible = pg.eligible_cards(player)
    assert "dev_golpe_convite" not in eligible
    assert "dev_cons_liturgia" in eligible
    assert not any((cards.get_card(cid) or {}).get("subclasse") not in ("", "consagrado")
                   for cid in eligible)


def test_apply_choice_nova_carta():
    player = _player(pending_choices=[{"id": "lvl2-carta", "level": 2, "kind": "carta"}])
    out, err = pg.apply_choice(player, "lvl2-carta", card_id="dev_muralha_viva")
    assert err is None and "dev_muralha_viva" in out["known_cards"]
    assert not out["pending_choices"]


def test_apply_choice_virtude():
    player = _player(pending_choices=[{"id": "lvl2-virtude", "level": 2, "kind": "virtude"}])
    out, err = pg.apply_choice(player, "lvl2-virtude", virtude="forca")
    assert err is None and out["virtudes"]["forca"] == 3


def test_apply_choice_inexistente_nao_muta():
    player = _player()
    out, err = pg.apply_choice(player, "nao-existe", card_id="dev_muralha_viva")
    assert out is player and err
