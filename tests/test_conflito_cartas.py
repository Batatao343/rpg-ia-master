"""Suíte da spec conflito-02: Cartas, Acervo, Preparação, Ruptura, Evolução.

100% determinístico, offline. Exercita o motor `services/cards.py` sobre as
cartas de exemplo em `data/cards/`."""

import pytest

import gamedata
from services import cards


def _state(**player_over):
    player = {
        "class_name": "Devoto do Abismo", "level": 1,
        "entropy": 14, "max_entropy": 14, "abyss_charge": 0,
        "known_cards": ["golpe_devoto", "muralha_viva", "conviccao_passiva"],
        "prepared_cards": ["golpe_devoto", "muralha_viva"],
        "card_usage": {}, "virtue_cards": [], "evolved_cards": {},
    }
    player.update(player_over)
    return {"player": player, "world": {"danger_level": 1}, "combat": {"active": False}}


# --------------------------------------------------------------------------
# Etapa 1 — slots + frequência + custo
# --------------------------------------------------------------------------
def test_prepare_slots_for_level():
    assert cards.prepare_slots_for_level(1) == 4
    assert cards.prepare_slots_for_level(3) == 4
    assert cards.prepare_slots_for_level(4) == 5
    assert cards.prepare_slots_for_level(6) == 5
    assert cards.prepare_slots_for_level(7) == 6
    assert cards.prepare_slots_for_level(9) == 6
    assert cards.prepare_slots_for_level(10) == 7


def test_cards_de_exemplo_carregam():
    todas = cards.all_cards()
    assert "golpe_devoto" in todas
    assert cards.get_card("muralha_viva")["ruptura"]  # tem Ruptura


def test_use_card_respeita_frequencia_cena():
    st = _state()
    r1 = cards.use_card(st, "muralha_viva")  # 1×cena
    assert r1["ok"], r1
    r2 = cards.use_card(st, "muralha_viva")  # 2ª na mesma cena -> bloqueia
    assert not r2["ok"] and "já foi usada" in r2["error"]
    # reset de cena libera de novo
    cards.reset_card_usage(st, "cena")
    r3 = cards.use_card(st, "muralha_viva")
    assert r3["ok"]


def test_use_card_livre_nao_limita():
    st = _state()
    for _ in range(5):
        assert cards.use_card(st, "golpe_devoto")["ok"]  # frequencia livre


def test_use_card_respeita_custo_entropia():
    st = _state(entropy=2)
    # muralha_viva custa 3 > 2
    r = cards.use_card(st, "muralha_viva")
    assert not r["ok"] and "insuficiente" in r["error"].lower()
    assert st["player"]["entropy"] == 2  # nada debitado


def test_use_card_debita_entropia():
    st = _state(entropy=10)
    cards.use_card(st, "muralha_viva")  # custo 3
    assert st["player"]["entropy"] == 7


def test_use_card_precisa_estar_preparada():
    st = _state(prepared_cards=["golpe_devoto"])
    r = cards.use_card(st, "muralha_viva")  # conhecida mas não preparada
    assert not r["ok"] and "não está preparada" in r["error"]


def test_reset_turno_nao_libera_carta_de_cena():
    st = _state()
    cards.use_card(st, "muralha_viva")            # 1×cena
    cards.reset_card_usage(st, "turno")           # reset de turno NÃO zera cena
    r = cards.use_card(st, "muralha_viva")
    assert not r["ok"]


# --------------------------------------------------------------------------
# Etapa 4 — reorganização (gate de segurança)
# --------------------------------------------------------------------------
def test_reorganizar_em_zona_segura():
    st = _state()
    r = cards.set_prepared(st, ["golpe_devoto", "conviccao_passiva"])
    assert r["ok"]
    assert st["player"]["prepared_cards"] == ["golpe_devoto", "conviccao_passiva"]


def test_reorganizar_bloqueado_em_combate():
    st = _state()
    st["combat"] = {"active": True}
    r = cards.set_prepared(st, ["golpe_devoto"])
    assert not r["ok"] and "seguro" in r["error"].lower()


def test_reorganizar_bloqueado_em_perigo():
    st = _state()
    st["world"]["danger_level"] = 4
    r = cards.set_prepared(st, ["golpe_devoto"])
    assert not r["ok"]


def test_reorganizar_rejeita_carta_fora_do_acervo():
    st = _state()
    r = cards.set_prepared(st, ["carta_inexistente"])
    assert not r["ok"] and "Acervo" in r["error"]


def test_reorganizar_respeita_limite_do_nivel():
    st = _state(level=1, known_cards=["golpe_devoto", "muralha_viva", "conviccao_passiva",
                                      "corte_sangrento", "hemorragia"])
    # nível 1 = 4 slots; tentar 5 falha
    r = cards.set_prepared(st, ["golpe_devoto", "muralha_viva", "conviccao_passiva",
                                "corte_sangrento", "hemorragia"])
    assert not r["ok"] and "Máximo 4" in r["error"]


# --------------------------------------------------------------------------
# Etapa 3 — evolução Caminho A/B
# --------------------------------------------------------------------------
def test_evolucao_so_a_partir_do_nivel_4():
    st = _state(level=3)
    r = cards.evolve_card(st, "golpe_devoto", "A")
    assert not r["ok"] and "nível 4" in r["error"]


def test_evolucao_caminho_unico():
    st = _state(level=4)
    r1 = cards.evolve_card(st, "golpe_devoto", "A")
    assert r1["ok"]
    assert st["player"]["evolved_cards"]["golpe_devoto"] == "A"
    # segunda evolução da mesma carta -> rejeitada
    r2 = cards.evolve_card(st, "golpe_devoto", "B")
    assert not r2["ok"] and "único" in r2["error"]


def test_evolucao_caminho_invalido():
    st = _state(level=4)
    r = cards.evolve_card(st, "golpe_devoto", "C")
    assert not r["ok"]


# --------------------------------------------------------------------------
# Etapa 5 — Ruptura
# --------------------------------------------------------------------------
def test_ruptura_gera_carga_mesmo_pagando_custo():
    st = _state(entropy=10, abyss_charge=0)
    r = cards.use_ruptura(st, "muralha_viva")  # custo 3, tem ruptura
    assert r["ok"], r
    assert st["player"]["entropy"] == 7          # custo pago da Entropia
    assert st["player"]["abyss_charge"] == 1     # +1 Carga


def test_ruptura_carga_nova_nao_paga_a_propria():
    # Entropia exata para 1 uso; a Carga gerada não vira recurso p/ pagar de novo
    st = _state(entropy=3, abyss_charge=0)
    r = cards.use_ruptura(st, "muralha_viva")
    assert r["ok"]
    assert st["player"]["entropy"] == 0
    assert st["player"]["abyss_charge"] == 1
    # nova ruptura na mesma cena falha por frequência (não por Carga virar recurso)
    r2 = cards.use_ruptura(st, "muralha_viva")
    assert not r2["ok"]


def test_ruptura_sem_ruptura_na_carta():
    st = _state()
    r = cards.use_ruptura(st, "golpe_devoto")  # não tem ruptura
    assert not r["ok"] and "Ruptura" in r["error"]


# --------------------------------------------------------------------------
# Etapa 2 — Criação com Cartas (Acervo 6 / Preparadas 4 / 2 de Virtude)
# --------------------------------------------------------------------------
def test_criacao_monta_acervo_e_preparadas():
    import os
    os.environ["RPG_FORCE_MOCK"] = "1"
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "Vael", "class_name": "Corruptor", "race": "Humano",
        "region": "Nova Arcádia", "level": 1,
        "virtudes": {"mente": 4, "corpo": 3, "agilidade": 2, "carisma": 1, "forca": 1},
    })
    assert len(sheet["known_cards"]) == 6
    assert len(sheet["prepared_cards"]) == 4
    assert set(sheet["prepared_cards"]) <= set(sheet["known_cards"])
    assert len(sheet["virtue_cards"]) == 2
    assert all("card_id" in vc and "estagio" in vc for vc in sheet["virtue_cards"])
    assert sheet["card_usage"] == {} and sheet["evolved_cards"] == {}


def test_criacao_medico_prioriza_cartas_autorais_v4():
    import os
    os.environ["RPG_FORCE_MOCK"] = "1"
    from character_creator import create_player_character

    sheet = create_player_character({
        "name": "Iria", "class_name": "Médico de Campo", "race": "Humano",
        "region": "Nova Arcádia", "level": 1,
        "virtudes": {
            "mente": 4, "carisma": 3, "corpo": 2,
            "agilidade": 1, "forca": 1,
        },
    })

    assert sheet["prepared_cards"][:2] == ["med_sutura", "med_torniquete"]
    assert "sutura_rapida" not in sheet["prepared_cards"]


def test_criacao_carta_de_virtude_estagio_pela_virtude():
    import os
    os.environ["RPG_FORCE_MOCK"] = "1"
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "Bruta", "class_name": "Devoto do Abismo", "race": "Humano", "level": 1,
        "virtudes": {"forca": 4, "corpo": 3, "carisma": 2, "mente": 1, "agilidade": 1},
        "virtue_cards": ["vc_forca_bruta", "vc_mente_lucida"],
    })
    by_id = {vc["card_id"]: vc for vc in sheet["virtue_cards"]}
    assert by_id["vc_forca_bruta"]["estagio"] == 2   # forca 4 -> Estágio II
    assert by_id["vc_mente_lucida"]["estagio"] == 1   # mente 1 -> Estágio I


# --------------------------------------------------------------------------
# Etapa 3 — Progressão: nova Carta OU evolução por nível
# --------------------------------------------------------------------------
def test_levelup_oferece_escolha_de_carta():
    from progression import grant_xp, XP_TABLE
    p = {"class_name": "Devoto do Abismo", "level": 1, "xp": 0, "max_hp": 40, "hp": 40,
         "max_entropy": 14, "entropy": 14, "virtudes": {"forca": 4, "corpo": 3,
         "carisma": 2, "mente": 1, "agilidade": 1}, "pending_choices": [],
         "known_cards": ["golpe_devoto"]}
    p, _ = grant_xp(p, XP_TABLE[2])
    assert any(c["kind"] == "carta" for c in p["pending_choices"])


def test_apply_choice_carta_nova():
    from progression import apply_choice
    p = {"class_name": "Devoto do Abismo", "level": 2, "known_cards": ["golpe_devoto"],
         "pending_choices": [{"id": "lvl2-carta", "level": 2, "kind": "carta"}]}
    out, err = apply_choice(p, "lvl2-carta", card_id="dev_muralha_viva")
    assert err is None
    assert "dev_muralha_viva" in out["known_cards"]
    assert out["pending_choices"] == []


def test_apply_choice_carta_nova_ou_evolucao_exclusivo():
    from progression import apply_choice
    p = {"class_name": "Devoto do Abismo", "level": 4, "known_cards": ["golpe_devoto"],
         "evolved_cards": {},
         "pending_choices": [{"id": "lvl4-carta", "level": 4, "kind": "carta"}]}
    out, err = apply_choice(p, "lvl4-carta", card_id="muralha_viva",
                            evolve_card_id="golpe_devoto", caminho="A")
    assert err is not None  # não pode as duas


def test_apply_choice_carta_evolucao():
    from progression import apply_choice
    p = {"class_name": "Devoto do Abismo", "level": 4, "known_cards": ["golpe_devoto"],
         "evolved_cards": {},
         "pending_choices": [{"id": "lvl4-carta", "level": 4, "kind": "carta"}]}
    out, err = apply_choice(p, "lvl4-carta", evolve_card_id="golpe_devoto", caminho="B")
    assert err is None
    assert out["evolved_cards"]["golpe_devoto"] == "B"
