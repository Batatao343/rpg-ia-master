"""SPEC-328 R5-R17 - rodada com várias jogadas, Pacto, reação da mão, shadow e save/load."""

import copy
import json
import random

import pytest

from services import card_piles as cp
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


@pytest.fixture(autouse=True)
def _folego_3(monkeypatch):
    """Cenários escritos para Fôlego 3 e teto 6; o padrão calibrado (2) tem teste próprio."""
    monkeypatch.setattr(cp, "FOLEGO_BASE", 3)
    monkeypatch.setattr(cp, "FOLEGO_MAX", 6)


HAND = ["bas_san_golpe", "bas_san_guarda", "bas_san_golpe", "san_esquiva", "san_finta"]


def _player(**kw):
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Sangromante",
        "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "known_cards": ["san_esquiva", "san_finta"],
        "prepared_cards": ["san_esquiva", "san_finta"],
        "entropy": 6,
        "max_entropy": 10,
        "abyss_charge": 0,
    }
    p.update(kw)
    p = orch.ensure_combat_sheet(p, is_player=True)
    cp.migrate_deck(p)
    return p


def _enemy():
    return orch.ensure_combat_sheet(
        {
            "id": "gob_1",
            "name": "Goblin",
            "type": "Minion",
            "hp": 40,
            "max_hp": 40,
            "ac": 11,
            "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
        }
    )


def _setup(mode="on", hand=HAND, **pkw):
    player, enemy = _player(**pkw), _enemy()
    piles = cp.start_piles(player, 11)
    piles["mao"] = list(hand)
    scene = cs.new_scene()
    for aid in ("player", "gob_1"):
        cs.place(scene, aid)
    cs.freeze(scene)
    state = {"player": player, "_piles": piles, "_deck_mode": mode}
    return (
        scene,
        {"player": player, "gob_1": enemy},
        {"hero": ["player"], "enemy": ["gob_1"]},
        state,
    )


def _plays(*steps):
    return ct.TurnDeclaration(actor_id="player", jogadas=list(steps))


def _card(cid, target="gob_1"):
    return ct.TurnStep(kind="card", card_id=cid, target_id=target)


def _run(scene, actors, sides, state, decl, seed=5):
    return orch.run_round(
        scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(seed)
    )


def test_jogadas_acao_e_atalho_da_primeira():
    d = _plays(_card("bas_san_golpe"), _card("bas_san_guarda", "player"))
    assert d.acao.card_id == "bas_san_golpe" and len(d.plays()) == 2
    assert ct.TurnDeclaration(actor_id="p", acao=ct.TurnStep(kind="pass")).plays()[0].kind == "pass"
    assert ct.TurnDeclaration(actor_id="p").plays() == []


def test_duas_cartas_resolvem_em_ordem_e_pagam_folego():
    scene, actors, sides, state = _setup()
    out = _run(
        scene,
        actors,
        sides,
        state,
        _plays(_card("bas_san_golpe"), _card("bas_san_guarda", "player")),
    )
    used = [u["card_id"] for u in out["cards_used"] if u["actor_id"] == "player"]
    assert used == ["bas_san_golpe", "bas_san_guarda"]
    piles = state["_piles"]
    assert piles["folego"] == cp.FOLEGO_BASE - 2 and piles["folego_emprestado"] == 0
    assert sorted(piles["descarte"]) == ["bas_san_golpe", "bas_san_guarda"]
    assert sorted(piles["mao"]) == sorted(["bas_san_golpe", "san_esquiva", "san_finta"])
    assert out["resolved_turns"].count("player") == 1
    assert actors["gob_1"]["vitalidade"] < actors["gob_1"]["max_vitalidade"] or out["attacks"]


def test_mesma_carta_em_mao_duas_vezes_e_permitida():
    scene, actors, sides, state = _setup()
    out = _run(scene, actors, sides, state, _plays(_card("bas_san_golpe"), _card("bas_san_golpe")))
    used = [u["card_id"] for u in out["cards_used"] if u["actor_id"] == "player"]
    assert used == ["bas_san_golpe", "bas_san_golpe"]
    assert state["_piles"]["mao"].count("bas_san_golpe") == 0


def test_carta_fora_da_mao_rejeita_sem_gastar_nada():
    scene, actors, sides, state = _setup()
    before = (copy.deepcopy(state["_piles"]), copy.deepcopy(actors["player"]["entropy"]))
    out = _run(scene, actors, sides, state, _plays(_card("san_corte_troca")))
    assert out["action_refused"] and out["deck_refused"]
    assert out["resolved_turns"] == [] and out["cards_used"] == []
    assert "não está na sua mão" in " ".join(out["logs"])
    assert (state["_piles"], actors["player"]["entropy"]) == before


def test_entropia_propria_da_carta_insuficiente_rejeita_a_lista_inteira():
    scene, actors, sides, state = _setup(entropy=0)
    before = copy.deepcopy(state["_piles"])
    out = _run(
        scene, actors, sides, state, _plays(_card("bas_san_golpe"), _card("san_finta", "player"))
    )
    assert out["deck_refused"] and out["cards_used"] == []
    assert "Entropia insuficiente" in " ".join(out["logs"])
    assert state["_piles"] == before


@pytest.mark.parametrize(
    "cls",
    ["Devoto do Abismo", "Sangromante", "Corruptor", "Arcanista Cinzento", "Médico de Campo"],
)
def test_pacto_do_abismo_cobra_entropia_e_carga_em_todas_as_posturas(cls):
    golpe = cards.basicas_for_class(cls)["golpe"][0]
    scene, actors, sides, state = _setup(
        class_name=cls, entropy=3, max_entropy=10, hand=[golpe, golpe, golpe, golpe, golpe]
    )
    atk = ct.TurnStep(kind="attack", target_id="gob_1")
    out = _run(
        scene,
        actors,
        sides,
        state,
        _plays(_card(golpe), _card(golpe), atk, atk),
    )
    piles = state["_piles"]
    assert piles["folego"] == 0 and piles["folego_emprestado"] == 1 and piles["pacto_carga"]
    assert "Pacto do Abismo" in " ".join(out["logs"])
    pacto = [e for e in out["class_mechanics"] if e["kind"] == "pacto_abismo"]
    assert pacto and pacto[0]["entropia_extra"] == 2 and pacto[0]["emprestado"] == 1
    # o Pacto nao passa pelo gatilho de classe (nao gasta o teto por turno) e sempre da +1 Carga
    assert actors["player"]["abyss_charge"] >= 1


def test_pacto_sem_entropia_recusa_a_lista_sem_efeito():
    golpe = "bas_san_golpe"
    scene, actors, sides, state = _setup(entropy=1)
    atk = ct.TurnStep(kind="attack", target_id="gob_1")
    before = copy.deepcopy(state["_piles"])
    out = _run(scene, actors, sides, state, _plays(_card(golpe), _card(golpe), atk, atk))
    assert out["deck_refused"] and "Entropia insuficiente" in " ".join(out["logs"])
    assert state["_piles"] == before and actors["player"]["abyss_charge"] == 0


def test_pacto_nao_ocupa_o_teto_de_gatilho_de_classe():
    scene, actors, sides, state = _setup(class_name="Arcanista Cinzento", entropy=3)
    atk = ct.TurnStep(kind="attack", target_id="gob_1")
    _run(scene, actors, sides, state, _plays(atk, atk, atk, atk))
    assert int(actors["player"].get("_entropy_trigger_turn", 0) or 0) == 0


def test_reembolso_pos_pacto_desfaz_o_delta_do_pacto(monkeypatch):
    scene, actors, sides, state = _setup(entropy=6)
    state["_piles"]["folego"] = 0  # forca o Pacto na 1a jogada
    from services import conflict_orchestrator as o

    # a carta "nao resolve": o motor devolve sem registrar `cards_used`
    monkeypatch.setattr(o, "_resolve_actor_turn", lambda *a, **k: None)
    from services import card_deck_round as dr

    decl = _plays(_card("bas_san_golpe"))
    snap = (actors["player"]["entropy"], actors["player"]["abyss_charge"])
    dr.resolve_player_plays(
        scene,
        actors["player"],
        "player",
        actors,
        sides,
        decl,
        state,
        {"logs": [], "cards_used": []},
        random.Random(1),
    )
    assert (actors["player"]["entropy"], actors["player"]["abyss_charge"]) == snap
    p = state["_piles"]
    assert p["folego"] == 0 and p["folego_emprestado"] == 0 and not p["pacto_carga"]
    assert "bas_san_golpe" in p["mao"]


def test_guarda_sobrevive_as_jogadas_seguintes_da_rodada():
    scene, actors, sides, state = _setup()
    guardar = ct.TurnStep(kind="maneuver", maneuver="guardar")
    _run(scene, actors, sides, state, _plays(guardar, _card("bas_san_golpe")))
    # a Guarda foi posta na 1a jogada; a 2a (resolve_turn) nao pode zera-la
    # (o inimigo ainda agiu depois, entao checamos o estado da cena na saida)
    assert cs._pos(scene, "player")["guarding"] is True


def test_last_player_action_registra_a_lista(monkeypatch):
    import agents.combat as ac

    decl = _plays(_card("bas_san_golpe"), _card("bas_san_guarda", "player"))
    action = ac._canonical_player_action(decl, {"attacks": []})
    assert [p["card_id"] for p in action["plays"]] == ["bas_san_golpe", "bas_san_guarda"]
    single = ac._canonical_player_action(
        ct.TurnDeclaration(actor_id="player", acao=_card("bas_san_golpe")), {"attacks": []}
    )
    assert "plays" not in single


def test_pacto_nao_passa_de_dois_por_rodada():
    scene, actors, sides, state = _setup(entropy=20, max_entropy=20)
    atk = ct.TurnStep(kind="attack", target_id="gob_1")
    out = _run(scene, actors, sides, state, _plays(*([atk] * 6)))
    assert out["deck_refused"] and "no máximo 2" in " ".join(out["logs"])


def test_movimento_pre_e_pos_continuam_gratis():
    scene, actors, sides, state = _setup()
    decl = ct.TurnDeclaration(
        actor_id="player",
        pre_acao=ct.TurnStep(kind="move", direction="aproximar"),
        jogadas=[_card("bas_san_golpe"), _card("bas_san_golpe"), _card("bas_san_guarda", "player")],
        pos_acao=ct.TurnStep(kind="move", direction="afastar"),
    )
    out = _run(scene, actors, sides, state, decl)
    assert not out.get("deck_refused")
    assert state["_piles"]["folego"] == 0


def _enemy_attack_round(mode, hand, folego=None, reaction="san_esquiva"):
    scene, actors, sides, state = _setup(mode=mode, hand=hand)
    if folego is not None:
        state["_piles"]["folego"] = folego
    state["_player_reaction_card_id"] = reaction
    decl = ct.TurnDeclaration(
        actor_id="player", reaction_card_id=reaction, acao=ct.TurnStep(kind="pass")
    )
    out = _run(scene, actors, sides, state, decl)
    return out, state["_piles"]


def test_reacao_sai_da_mao_e_paga_o_folego_que_sobrou():
    out, piles = _enemy_attack_round("on", HAND, folego=2)
    assert out["reactions"]
    assert piles["folego"] == 1 and "san_esquiva" in piles["descarte"]
    assert "san_esquiva" not in piles["mao"]


def test_reacao_sem_folego_sobrando_nao_acontece():
    out, piles = _enemy_attack_round("on", HAND, folego=0)
    assert not out["reactions"] and "san_esquiva" in piles["mao"]


def test_reacao_fora_da_mao_nao_acontece():
    hand = [c for c in HAND if c != "san_esquiva"]
    out, piles = _enemy_attack_round("on", hand, folego=3)
    assert not out["reactions"]


def test_reacao_sem_baralho_segue_a_regra_de_antes():
    scene, actors, sides, state = _setup(mode="on")
    legacy_state = {"player": actors["player"], "_player_reaction_card_id": "san_esquiva"}
    decl = ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))
    out = _run(scene, actors, sides, legacy_state, decl)
    assert out["reactions"]  # sem `_piles`: combate antigo (R16)


def test_shadow_nao_muda_o_resultado_e_registra():
    results = {}
    for mode in ("off", "shadow"):
        scene, actors, sides, state = _setup(mode=mode)
        if mode == "off":
            state = {"player": actors["player"]}
        decl = ct.TurnDeclaration(actor_id="player", acao=_card("bas_san_golpe"))
        out = _run(scene, actors, sides, state, decl, seed=9)
        results[mode] = (
            out["logs"],
            actors["gob_1"]["vitalidade"],
            actors["player"]["vitalidade"],
            actors["player"]["entropy"],
        )
        if mode == "shadow":
            assert out["deck_shadow"]["ok"] and out["deck_shadow"]["plays"] == 1
            assert state["_piles"]["folego"] == cp.FOLEGO_BASE  # nada foi pago
    assert results["off"] == results["shadow"]


def test_round_trip_save_load_no_meio_do_conflito():
    scene, actors, sides, state = _setup()
    _run(
        scene,
        actors,
        sides,
        state,
        _plays(_card("bas_san_golpe"), _card("bas_san_guarda", "player")),
    )
    saved = json.loads(json.dumps(state["_piles"]))
    assert saved == state["_piles"]
    a, b = copy.deepcopy(state["_piles"]), saved
    for piles in (a, b):
        cp.begin_round(piles)
    assert a == b and len(a["mao"]) == cp.MAO_BASE


def test_decl_dict_com_jogadas_da_api_e_aceita():
    raw = {
        "actor_id": "player",
        "acao": {"kind": "card", "card_id": "bas_san_golpe", "target_id": "gob_1"},
        "jogadas": [
            {"kind": "card", "card_id": "bas_san_golpe", "target_id": "gob_1"},
            {"kind": "card", "card_id": "bas_san_guarda", "target_id": "player"},
        ],
    }
    scene, actors, sides, state = _setup()
    out = orch.run_round(
        scene, actors, sides, state, declarations={"player": raw}, rng=random.Random(2)
    )
    assert [u["card_id"] for u in out["cards_used"] if u["actor_id"] == "player"] == [
        "bas_san_golpe",
        "bas_san_guarda",
    ]


@pytest.mark.parametrize("cid,freq", [("san_finta", "turno")])
def test_carta_de_turno_so_uma_vez_por_rodada(cid, freq):
    assert cards.get_card(cid)["frequencia"] == freq
    scene, actors, sides, state = _setup(hand=[cid, cid, *HAND[:3]])
    out = _run(scene, actors, sides, state, _plays(_card(cid, "player"), _card(cid, "player")))
    assert out["deck_refused"] and "1× por rodada" in " ".join(out["logs"])
