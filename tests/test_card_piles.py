"""SPEC-328 - pilhas puras do Baralho de Conflito (compra, descarte, Folego, Pacto)."""

import copy

import pytest

from services import card_piles as cp
from services import cards, content_validator

CLASSES = [
    "Devoto do Abismo",
    "Sangromante",
    "Corruptor",
    "Arcanista Cinzento",
    "Médico de Campo",
]


def _starter(class_name="Sangromante", n=4):
    pool = [
        c["id"]
        for c in cards.cards_for_class(class_name)
        if not c.get("subclasse") and c.get("tipo") == "ativa" and c.get("level_req", 1) == 1
    ]
    known = pool[:6]
    return {
        "class_name": class_name,
        "level": 1,
        "known_cards": known,
        "prepared_cards": known[:n],
        "entropy": 6,
        "max_entropy": 10,
    }


def _player():
    p = _starter()
    cp.migrate_deck(p)
    return p


# ------------------------------------------------------------------ custo_folego (R6)
@pytest.mark.parametrize(
    "card,expected",
    [
        ({"custo_folego": 2, "frequencia": "livre"}, 2),
        ({"custo_folego": 9}, 3),  # teto
        ({"frequencia": "livre", "efeito": {"kind": "protecao"}}, 0),
        ({"frequencia": "livre", "efeito": {"kind": "dano", "dano_base": 3}}, 1),
        ({"frequencia": "turno", "efeito": {"kind": "buff_acerto"}}, 1),
        ({"frequencia": "livre", "tier": 3, "efeito": {"kind": "protecao"}}, 2),
        ({"frequencia": "cena", "efeito": {"kind": "dano", "dano_base": 8}}, 2),
        ({"frequencia": "descanso_longo", "efeito": {"kind": "dano"}}, 3),
        ({"frequencia": "cena", "apex": True, "efeito": {"kind": "dano"}}, 3),
    ],
)
def test_custo_folego_default_por_regra(card, expected):
    assert cards.custo_folego(card) == expected


# ------------------------------------------------------------------ basicas (R2)
def test_basicas_tres_por_postura_e_lint_limpo():
    for cls in CLASSES:
        b = cards.basicas_for_class(cls)
        assert len(b["golpe"]) == 1 and len(b["guarda"]) == 1 and len(b["assinatura"]) == 1, cls
    basics = [c for c in cards.all_cards().values() if c.get("basica")]
    assert len(basics) == 15
    assert all(cards.custo_folego(c) == 1 for c in basics)
    errors = [f for f in content_validator.validate_cards() if f.severity == "error"]
    assert errors == []


def test_basicas_fora_do_acervo_e_da_progressao():
    ids = {c["id"] for c in cards.all_cards().values() if c.get("basica")}
    for cls in CLASSES:
        assert not ids & {c["id"] for c in cards.cards_for_class(cls)}


# ------------------------------------------------------------------ compra (R5)
def test_compra_deterministica_por_semente():
    p = _player()
    a = cp.start_piles(p, 123)
    b = cp.start_piles(p, 123)
    c = cp.start_piles(p, 124)
    assert a == b
    assert len(a["mao"]) == cp.MAO_BASE and a["folego"] == cp.FOLEGO_BASE
    assert sorted(a["mao"] + a["compra"]) == sorted(p["deck"])
    assert (a["mao"], a["compra"]) != (c["mao"], c["compra"])


def test_replay_apos_round_trip_json():
    import json

    p = _player()
    a = cp.start_piles(p, 7)
    b = json.loads(json.dumps(a))
    for piles in (a, b):
        for _ in range(6):
            cp.begin_round(piles)
    assert a == b  # `embaralhos` persistido -> mesma sequencia depois do reload


def test_descarta_mao_e_compra_ate_cinco():
    p = _player()
    piles = cp.start_piles(p, 1)
    old_hand = list(piles["mao"])
    piles["folego"] = 0
    cp.begin_round(piles)
    assert len(piles["mao"]) == cp.MAO_BASE
    assert piles["folego"] == cp.FOLEGO_BASE and piles["folego_emprestado"] == 0
    assert sorted(old_hand) == sorted(piles["descarte"])


def test_guardadas_sobrevivem_a_rodada():
    p = _player()
    piles = cp.start_piles(p, 1)
    keep = piles["mao"][0]
    piles["guardadas"] = [keep]
    cp.begin_round(piles)
    assert keep in piles["mao"] and len(piles["mao"]) == cp.MAO_BASE
    assert piles["guardadas"] == []


def test_monte_vazio_reembaralha_e_gera_um_fardo():
    p = _player()
    piles = cp.start_piles(p, 3)
    total = len(p["deck"])
    for _ in range(total):  # esgota o monte
        cp.begin_round(piles)
    assert piles["fardos"] >= 1
    everything = piles["compra"] + piles["mao"] + piles["descarte"] + piles["exaurida"]
    assert everything.count(cp.FARDO_ID) == piles["fardos"]
    assert len(everything) == total + piles["fardos"]


def test_reshuffle_adiciona_exatamente_um_fardo():
    p = _player()
    piles = cp.start_piles(p, 3)
    piles["descarte"], piles["compra"] = piles["compra"], []
    cp.reshuffle(piles)
    assert (piles["compra"].count(cp.FARDO_ID), piles["descarte"]) == (1, [])


# ------------------------------------------------------------------ pilhas por frequencia (R11)
def test_cena_exaure_e_livre_descarta():
    p = _player()
    piles = {**cp.start_piles(p, 1), "mao": ["bas_san_golpe", "san_finta"], "descarte": []}
    assert cp.play_to_pile(piles, "bas_san_golpe") == "descarte"
    cena = next(
        c["id"] for c in cards.all_cards().values() if c.get("frequencia") == "cena" and c["id"]
    )
    piles["mao"].append(cena)
    assert cp.play_to_pile(piles, cena) == "exaurida"
    assert cena in piles["exaurida"] and cena not in piles["descarte"]
    assert cp.exhaust(piles, "san_finta") and "san_finta" in piles["exaurida"]


def test_descanso_gasto_comeca_exaurido():
    p = _player()
    long_rest = next(
        c["id"]
        for c in cards.all_cards().values()
        if c.get("frequencia") == "descanso_longo" and c.get("tipo") == "ativa"
    )
    p["deck"] = p["deck"] + [long_rest]
    p["card_usage"] = {long_rest: {"used_since_long_rest": 1}}
    piles = cp.start_piles(p, 1)
    assert long_rest in piles["exaurida"]
    assert long_rest not in piles["compra"] + piles["mao"]


# ------------------------------------------------------------------ pagamento (R8, R10)
def _golpe():
    return cards.get_card("bas_san_golpe")


def test_pagamento_normal_so_folego():
    p = _player()
    piles = cp.start_piles(p, 1)
    plan = cp.pay(piles, p, _golpe())
    assert plan["ok"] and plan["emprestado"] == 0 and piles["folego"] == cp.FOLEGO_BASE - 1
    assert p["entropy"] == 6


def test_pacto_empresta_ate_dois_e_ganha_entropia_e_carga():
    p = _player()
    piles = cp.start_piles(p, 1)
    piles["folego"] = 0
    plan = cp.pay(piles, p, _golpe())
    assert plan == {"folego": 0, "emprestado": 1, "entropia_extra": 2, "ok": True, "motivo": ""}
    cp.apply_pact(piles, p, plan)
    assert p["entropy"] == 8 and piles["folego_emprestado"] == 1  # +2 Entropia
    assert p["abyss_charge"] == 1  # +1 Carga na 1a vez da rodada
    plan = cp.pay(piles, p, _golpe())
    cp.apply_pact(piles, p, plan)
    assert p["entropy"] == 10 and piles["folego_emprestado"] == 2  # clamp em max_entropy
    assert p["abyss_charge"] == 1  # Carga so 1x por rodada
    third = cp.can_pay(piles, p, _golpe())
    assert not third["ok"] and "no máximo 2" in third["motivo"]


def test_pacto_entropia_respeita_o_teto():
    p = _player()
    p["entropy"] = 9
    piles = cp.start_piles(p, 1)
    plan = {"emprestado": 1, "entropia_extra": 2}
    cp.apply_pact(piles, p, plan)
    assert p["entropy"] == p["max_entropy"]


def test_start_piles_nao_muda_a_ficha_e_deck_tem_rollback():
    p = _starter()
    before = copy.deepcopy(p)
    cp.start_piles(p, 1)  # shadow: so calcula
    assert p == before
    cp.activate_deck(p)
    assert p["prepared_cards_pre_deck"] == before["prepared_cards"]
    assert set(p["deck"]) <= set(p["prepared_cards"])
    cp.deactivate_deck(p)
    assert p["prepared_cards"] == before["prepared_cards"] and "prepared_cards_pre_deck" not in p
    cp.activate_deck(p)  # reativar com o baralho ja guardado re-deriva
    assert set(p["deck"]) <= set(p["prepared_cards"]) and "prepared_cards_pre_deck" in p


def test_custo_entropia_da_carta_vale_alem_do_folego():
    p = _player()
    piles = cp.start_piles(p, 1)
    carta = {"id": "x", "name": "X", "custo_folego": 1, "custo_entropia": 7}
    assert not cp.can_pay(piles, p, carta)["ok"]  # 7 > entropia 6
    carta["custo_entropia"] = 6
    assert cp.can_pay(piles, p, carta)["ok"]


def test_reacao_nao_usa_pacto():
    p = _player()
    piles = cp.start_piles(p, 1)
    piles["folego"] = 0
    assert not cp.can_pay(piles, p, _golpe(), allow_pact=False)["ok"]


def test_fardo_injogavel():
    p = _player()
    piles = cp.start_piles(p, 1)
    piles["mao"] = [cp.FARDO_ID]
    plan = cp.plan_plays(piles, p, [_Step("card", cp.FARDO_ID)])
    assert not plan["ok"] and "Fardo" in plan["motivo"]


class _Step:
    def __init__(self, kind, card_id=None, maneuver=None):
        self.kind, self.card_id, self.maneuver = kind, card_id, maneuver


def test_plan_plays_valida_mao_folego_e_ordem_sem_efeito_colateral():
    p = _player()
    piles = cp.start_piles(p, 1)
    piles["mao"] = ["bas_san_golpe", "bas_san_guarda", "bas_san_golpe", "san_finta", "san_esquiva"]
    snapshot = (copy.deepcopy(piles), copy.deepcopy(p))
    ok = cp.plan_plays(piles, p, [_Step("card", "bas_san_golpe"), _Step("card", "bas_san_guarda")])
    assert ok["ok"] and ok["folego_total"] == 2
    fora = cp.plan_plays(piles, p, [_Step("card", "san_corte_troca")])
    assert not fora["ok"] and "mão" in fora["motivo"]
    quatro = cp.plan_plays(piles, p, [_Step("card", "bas_san_golpe")] * 2 + [_Step("attack")] * 2)
    assert quatro["ok"] and quatro["emprestado"] == 1  # 4 Folego: 3 + 1 do Pacto
    seis = cp.plan_plays(piles, p, [_Step("attack")] * 6)
    assert not seis["ok"]
    assert (piles, p) == snapshot


def test_movimento_e_gratis():
    p = _player()
    piles = cp.start_piles(p, 1)
    assert cp.step_folego(_Step("move")) == 0
    assert cp.step_folego(_Step("maneuver", maneuver="mover")) == 0
    assert cp.step_folego(_Step("maneuver", maneuver="guardar")) == 1
    assert cp.plan_plays(piles, p, [_Step("move")] * 9)["ok"]


# ------------------------------------------------------------------ set_deck (R1)
def _state(p):
    return {"player": p, "world": {"danger_level": 1}, "combat": {}}


def test_set_deck_valida_tamanho_copias_e_acervo():
    p = _player()
    st = _state(p)
    basics = cards.basicas_for_class("Sangromante")
    ids = basics["golpe"] * 6 + basics["guarda"] * 6
    assert cards.set_deck(st, ids)["ok"]  # basicas sem teto de copias
    assert p["deck"] == ids and set(ids) <= set(p["prepared_cards"])
    assert not cards.set_deck(st, ids[:11])["ok"]  # < 12
    assert not cards.set_deck(st, ids + basics["golpe"] * 20)["ok"]  # > 24
    outsider = next(c for c in cards.all_cards() if c not in p["known_cards"] and "dev_" in c)
    assert not cards.set_deck(st, ids[:11] + [outsider])["ok"]
    known = p["known_cards"][0]
    assert cards.set_deck(st, ids[:10] + [known, known])["ok"]  # comum: ate 2
    assert not cards.set_deck(st, ids[:9] + [known] * 3)["ok"]


def test_set_deck_recusa_em_combate():
    p = _player()
    st = _state(p)
    st["combat"] = {"active": True}
    assert not cards.set_deck(st, p["deck"])["ok"]


def test_visao_publica_nao_vaza_a_ordem_do_monte():
    p = _player()
    view = cp.public_view(cp.start_piles(p, 1))
    assert set(view) >= {"mao", "compra", "descarte", "exaurida", "folego"}
    assert isinstance(view["compra"], int) and len(view["mao"]) == cp.MAO_BASE


def test_flag_default_off_e_invalida_vira_off(monkeypatch):
    monkeypatch.delenv("RPG_CARD_DECK", raising=False)
    assert cp.mode() == "off"
    monkeypatch.setenv("RPG_CARD_DECK", "talvez")
    assert cp.mode() == "off"
    monkeypatch.setenv("RPG_CARD_DECK", "ON")
    assert cp.mode() == "on"
