from __future__ import annotations

import gamedata
import progression as pg
from services import cards


def _player(level=1, **extra):
    base = {
        "name": "Ava", "class_name": "Devoto do Abismo", "level": level,
        "xp": gamedata.XP_TABLE[level], "max_entropy": 20, "entropy": 20,
        "known_cards": ["dev_golpe_convite"], "prepared_cards": [],
        "pending_choices": [], "virtue_cards": [
            {"card_id": "virtude_forca", "virtude": "forca", "estagio": 2},
            {"card_id": "virtude_corpo", "virtude": "corpo", "estagio": 2},
        ],
    }
    base.update(extra)
    return base


def test_cap_xp_tier_e_slots_ate_20():
    assert pg.MAX_LEVEL == 20 and pg.xp_to_next(20) is None
    assert all(gamedata.XP_TABLE[level] < gamedata.XP_TABLE[level + 1]
               for level in range(1, 20))
    assert [gamedata.prepared_slots_for_level(level)
            for level in (1, 4, 7, 10, 13, 17, 20)] == [4, 5, 6, 7, 8, 9, 10]
    assert [gamedata.card_tier_for_level(level) for level in (9, 12, 15, 18, 20)] == [5, 6, 7, 8, 9]


def test_nivel_3_exige_subclasse_antes_da_carta_e_bloqueia_rival():
    player, _ = pg.grant_xp(_player(level=2), gamedata.XP_TABLE[3] - gamedata.XP_TABLE[2])
    assert [row["kind"] for row in player["pending_choices"]][:2] == ["subclass", "carta"]
    card_choice = next(row for row in player["pending_choices"] if row["kind"] == "carta")
    unchanged, err = pg.apply_choice(player, card_choice["id"], card_id="dev_cons_marca")
    assert unchanged is player and "subclasse" in err.lower()
    subclass_choice = player["pending_choices"][0]
    player, err = pg.apply_choice(player, subclass_choice["id"], subclass_id="consagrado")
    assert err is None and player["subclass"] == "consagrado"
    eligible = set(pg.eligible_cards(player))
    assert "dev_cons_marca" in eligible
    assert not any((cards.get_card(card_id) or {}).get("subclasse") in {"zeloso", "enlutado"}
                   for card_id in eligible)


def test_level_gate_e_apice_deterministica_uma_vez():
    player = _player(level=19, subclass="consagrado", xp=gamedata.XP_TABLE[19])
    assert "dev_consagrado_apice" not in pg.eligible_cards(player)
    player, events = pg.grant_xp(player, gamedata.XP_TABLE[20] - gamedata.XP_TABLE[19])
    assert player["level"] == 20
    assert player["known_cards"].count("dev_consagrado_apice") == 1
    assert not any(row["kind"] == "carta" for row in player["pending_choices"])
    assert any(event["type"] == "class_apex_unlocked" for event in events)
    again, card_id = pg.grant_apex_if_due(player, 20)
    assert card_id is None and again["known_cards"].count("dev_consagrado_apice") == 1


def test_maestria_virtude_teto_dois_e_total_tres():
    player = _player(level=20, pending_choices=[
        {"id": "lvl12-virtue-mastery", "level": 12, "kind": "virtue_mastery"},
        {"id": "lvl16-virtue-mastery", "level": 16, "kind": "virtue_mastery"},
        {"id": "lvl20-virtue-mastery", "level": 20, "kind": "virtue_mastery"},
    ])
    for level, card_id in ((12, "virtude_forca"), (16, "virtude_forca"), (20, "virtude_corpo")):
        player, err = pg.apply_choice(
            player, f"lvl{level}-virtue-mastery", virtue_card_id=card_id)
        assert err is None
    assert [row["mastery"] for row in player["virtue_cards"]] == [2, 1]
    assert pg.effective_virtue_card_stage(player["virtue_cards"][0]) == 4


def test_migracao_preserva_cartas_rivais_e_fixa_primeiro_ramo():
    legacy = _player(level=8, known_cards=["dev_zel_ciume", "dev_cons_marca"])
    normalized = pg.normalize_player_progression(legacy)
    assert normalized["known_cards"] == legacy["known_cards"]
    assert normalized["subclass"] == "zeloso"
    assert pg.normalize_player_progression(normalized) == normalized


def test_personagem_nivel_20_recebe_apice_ao_escolher_subclasse_tardiamente():
    player = pg.normalize_player_progression(_player(level=20))
    choice = next(row for row in player["pending_choices"] if row["kind"] == "subclass")
    player, error = pg.apply_choice(player, choice["id"], subclass_id="consagrado")
    assert error is None
    assert player["known_cards"].count("dev_consagrado_apice") == 1
    assert "lvl20:apex:dev_consagrado_apice" in player["progression_grants"]
