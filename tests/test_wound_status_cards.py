"""SPEC-333 R7-R9 - Ferimento como carta de status, Cicatriz como maldição, Sussurro do Abismo."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import combat_mechanics as cm
import persistence
from services import card_effects as fx
from services import card_lint, cards, death_flow
from services import card_piles as cp
from services import card_rewards as cr
from services import card_status as cs
from services import conflict_orchestrator as orch
from services import conflict_scene as csc
from services import conflict_turn as ct

GID = "11111111-2222-4333-8444-555555555555"
STATUS = ("sts_dor_surda", "sts_membro_falho", "sts_sangue_olhos")
CURSES = (
    "mld_cicatriz_cabeca",
    "mld_cicatriz_torso",
    "mld_cicatriz_braco",
    "mld_cicatriz_perna",
    "mld_cicatriz_geral",
)
GOLPE = "bas_san_golpe"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    monkeypatch.setattr(cp, "FOLEGO_BASE", 3)
    monkeypatch.setattr(cp, "FOLEGO_MAX", 6)


def _player(**extra):
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Sangromante",
        "level": 3,
        "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "known_cards": [],
        "prepared_cards": [],
        "entropy": 6,
        "max_entropy": 10,
        "abyss_charge": 0,
        "gold": 100,
    }
    p.update(extra)
    p = orch.ensure_combat_sheet(p, is_player=True)
    cp.migrate_deck(p)
    return p


def _piles(player, hand=None, compra=None):
    piles = cp.start_piles(player, 11)
    if hand is not None:
        piles["mao"] = list(hand)
    if compra is not None:
        piles["compra"] = list(compra)
    return piles


# ------------------------------------------------------------------ as 9 Cartas autorais
@pytest.mark.parametrize("cid", STATUS + CURSES + ("sus_sussurro_abismo",))
def test_cartas_novas_passam_no_lint_e_tem_texto(cid):
    card = cards.get_card(cid)
    assert card is not None and card["origem"] == "cartas-333"
    pool = [c for c in card_lint.load_pool() if c["id"] != cid]
    assert card_lint.errors(card_lint.lint_card(card, pool)) == []
    assert fx.validate_card(card) == []
    assert fx.render_card_text(card)
    assert cid not in {c["id"] for c in cards.cards_for_class("Sangromante")}  # nunca no Acervo


def test_maldicoes_sao_fardo_com_vazao_e_nao_jogaveis():
    for cid in CURSES:
        card = cards.get_card(cid)
        assert cp.is_fardo(card) and cp.has_kw(card, "vazao")
        assert any(fx.gatilho(e) == "ao_descartar" for e in fx.normalize(card))


# ------------------------------------------------------------------ R7 Ferimento -> carta de status
def test_ferimento_novo_insere_a_carta_certa_no_topo_do_monte():
    p = _player()
    before = cs.wound_counts(p)
    p["ferimentos"]["leve"].append({"regiao": "torso"})
    p["ferimentos"]["grave"].append({"regiao": "braco"})
    piles = _piles(p, compra=["x1", "x2"])
    logs = cs.on_round_end(piles, p, before)
    assert piles["compra"][:2] == ["sts_membro_falho", "sts_dor_surda"] or piles["compra"][:2] == [
        "sts_dor_surda",
        "sts_membro_falho",
    ]
    assert len(logs) == 2
    assert "sts_dor_surda" not in p["deck"]  # vive só nas pilhas do conflito


def test_critico_vira_sangue_nos_olhos_e_sem_ferimento_novo_nada_acontece():
    p = _player()
    piles = _piles(p, compra=[])
    cs.on_round_end(piles, p, cs.wound_counts(p))
    assert not any(c in piles["compra"] for c in STATUS)
    before = cs.wound_counts(p)
    p["ferimentos"]["critico"].append({"regiao": "cabeca"})
    cs.on_round_end(piles, p, before)
    assert piles["compra"][0] == "sts_sangue_olhos"


def test_flag_off_ou_deck_off_nao_insere(monkeypatch):
    p = _player()
    piles = _piles(p, compra=[])
    p["ferimentos"]["grave"].append({"regiao": "braco"})
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    assert cs.on_round_end(piles, p, {"leve": 0, "grave": 0, "critico": 0}) == []
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    assert cs.on_round_end(piles, p, {"leve": 0, "grave": 0, "critico": 0}) == []
    assert not piles["compra"]


def test_membro_falho_tira_um_de_folego_na_rodada_em_que_e_comprada():
    p = _player()
    piles = _piles(p, compra=["sts_membro_falho", GOLPE, GOLPE, GOLPE, GOLPE, GOLPE])
    piles["mao"] = []
    cp.begin_round(piles)
    assert "sts_membro_falho" in piles["mao"] and piles["folego"] == 3
    logs = cs.on_hand_drawn(piles, p)
    assert piles["folego"] == 2 and logs
    assert cs.on_hand_drawn(piles, p) == [] and piles["folego"] == 2  # não repete
    cp.begin_round(piles)  # a rodada seguinte volta ao Fôlego cheio
    assert piles["folego"] == 3


def test_sangue_nos_olhos_deixa_cego_por_uma_rodada():
    p = _player()
    piles = _piles(p, compra=["sts_sangue_olhos", GOLPE, GOLPE, GOLPE, GOLPE, GOLPE])
    piles["mao"] = []
    cp.begin_round(piles)
    cs.on_hand_drawn(piles, p)
    cego = [c for c in p["active_conditions"] if str(c.get("name", "")).lower() == "cego"]
    assert cego and cego[0]["duration"] == 1 and cego[0].get("stat") == "advantage"


def test_dor_surda_pesa_uma_rodada_e_sai_do_ciclo():
    p = _player()
    piles = _piles(p, hand=["sts_dor_surda", GOLPE], compra=[GOLPE] * 6)
    cs.on_round_end(piles, p, cs.wound_counts(p))
    assert "sts_dor_surda" in piles["exaurida"] and "sts_dor_surda" not in piles["mao"]
    cp.begin_round(piles)
    assert "sts_dor_surda" not in piles["descarte"] + piles["compra"] + piles["mao"]


def test_status_nao_e_jogavel():
    p = _player()
    piles = _piles(p, hand=["sts_membro_falho"])
    step = ct.TurnStep(kind="card", card_id="sts_membro_falho", target_id="player")
    plan = cp.plan_plays(piles, p, [step])
    assert not plan["ok"] and "Fardo" in plan["motivo"]


# ------------------------------------------------------------------ nó de combate (integração)
def _node_state(monkeypatch, *, wound=None, ended=False):
    from services import conflict_orchestrator as o
    from tests.test_api_jogadas import _state

    state = _state(monkeypatch)
    state["combat_simulation"] = {"enabled": False}

    def fake_round(scene, actors_by_id, sides, round_state, *a, **k):
        if wound:
            actors_by_id["player"]["ferimentos"][wound[0]].append({"regiao": wound[1]})
        return {
            "logs": ["troca de golpes"],
            "deaths": [],
            "terminal": [],
            "abyss": [],
            "attacks": [],
            "reactions": [],
            "last_stands": [],
            "stabilizations": [],
            "scars_pending": [],
            "resolved_turns": ["player"],
            "cards_used": [],
            "recidiva_event": None,
            "reason": None,
            "ended": ended,
            "player_dead": False,
        }

    monkeypatch.setattr(o, "run_round", fake_round)
    import agents.combat as combat_agent

    monkeypatch.setattr(combat_agent, "_narrate", lambda *a, **k: "Narração.")
    state["messages"] = [HumanMessage(content="ataco")]
    return combat_agent, state


def test_no_de_combate_grave_vira_membro_falho_na_mao_e_some_no_fim(monkeypatch):
    agent, state = _node_state(monkeypatch, wound=("grave", "braco"))
    deck_before = list(state["player"]["deck"])
    state["combat"]["pilhas"]["compra"] = ["bas_san_guarda"] * 10
    out = agent._combat_node(state)
    piles = out["combat"]["pilhas"]
    assert "sts_membro_falho" in piles["mao"]  # chegou à mão da próxima rodada
    assert piles["folego"] == cp.FOLEGO_BASE - 1  # e já cobrou o Fôlego
    assert out["player"]["deck"] == deck_before  # o baralho do herói não muda
    # fim do conflito: as pilhas (e a carta de status) somem
    agent2, state2 = _node_state(monkeypatch, ended=True)
    out2 = agent2._combat_node(state2)
    assert "pilhas" not in out2["combat"]
    assert "cartas_cena" not in out2["player"]


def test_no_de_combate_com_flag_off_e_igual_a_antes(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    agent, state = _node_state(monkeypatch, wound=("grave", "braco"))
    state["combat"]["pilhas"]["compra"] = ["bas_san_guarda"] * 10
    out = agent._combat_node(state)
    assert not any(c in out["combat"]["pilhas"]["mao"] for c in STATUS)


# ------------------------------------------------------------------ R8 Cicatriz -> maldição
class _BoomLLM:
    def with_structured_output(self, _model):
        return self

    def invoke(self, *_a, **_k):
        raise RuntimeError("down")


def test_cicatriz_vira_maldicao_permanente_no_baralho_com_save_load(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    p = _player()
    p["ferimentos"]["grave"].append({"regiao": "braco"})
    p["scar_pending"] = True
    scar = death_flow.generate_scar(p, _BoomLLM())
    curse = "mld_cicatriz_braco"
    assert p["cicatriz_cartas"] == [{"scar_id": scar["id"], "card_id": curse}]
    assert p["deck"].count(curse) == 1 and curse in p["prepared_cards"]
    # idempotente por scar.id
    assert cr.register_scar_curse(p, scar) is None and p["deck"].count(curse) == 1
    # round-trip save/load e o conflito seguinte já embaralha a maldição
    state = {"game_id": GID, "player": p, "world": {}, "messages": []}
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(GID))["player"]
    assert loaded["cicatriz_cartas"] == p["cicatriz_cartas"] and curse in loaded["deck"]
    piles = cp.start_piles(loaded, 3)
    assert (piles["compra"] + piles["mao"]).count(curse) == 1


def test_cicatriz_com_flag_off_nao_toca_a_ficha(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    p = _player()
    deck = list(p["deck"])
    p["scar_pending"] = True
    death_flow.generate_scar(p, _BoomLLM())
    assert p["deck"] == deck and "cicatriz_cartas" not in p


def test_regiao_do_ferimento_escolhe_a_maldicao():
    assert cr.curse_card_for_scar({"id": "scar_perna_1", "origem": "x"}) == "mld_cicatriz_perna"
    assert cr.curse_card_for_scar({"id": "scar_x_1", "origem": "garra no torso"}) == (
        "mld_cicatriz_torso"
    )
    assert cr.curse_card_for_scar({"id": "scar_ombro_0", "origem": "?"}) == cr.SCAR_CURSE_DEFAULT


def test_baralho_ativado_depois_da_cicatriz_inclui_a_maldicao():
    p = {"class_name": "Sangromante", "prepared_cards": [], "known_cards": []}
    p["cicatriz_cartas"] = [{"scar_id": "s", "card_id": "mld_cicatriz_torso"}]
    cp.migrate_deck(p)
    assert "mld_cicatriz_torso" in p["deck"] and len(p["deck"]) <= cards.DECK_MAX


def _round_setup(player, hand):
    enemy = orch.ensure_combat_sheet(
        {
            "id": "gob_1",
            "name": "Goblin",
            "type": "Minion",
            "hp": 60,
            "max_hp": 60,
            "ac": 11,
            "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
        }
    )
    enemy["vitalidade"] = enemy["max_vitalidade"] = 60
    piles = cp.start_piles(player, 11)
    piles["mao"] = list(hand)
    scene = csc.new_scene()
    for aid in ("player", "gob_1"):
        csc.place(scene, aid)
    csc.freeze(scene)
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    cm.apply_condition(
        player, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
    )
    return (
        scene,
        {"player": player, "gob_1": enemy},
        {"hero": ["player"], "enemy": ["gob_1"]},
        state,
    )


def test_lado_positivo_da_cicatriz_dispara_por_vazao_ao_descartar():
    p = _player()
    scene, actors, sides, st = _round_setup(p, ["mld_cicatriz_braco", GOLPE])
    decl = ct.TurnDeclaration(
        actor_id="player", jogadas=[ct.TurnStep(kind="card", card_id=GOLPE, target_id="gob_1")]
    )
    out = orch.run_round(
        scene, actors, sides, st, declarations={"player": decl}, rng=random.Random(5)
    )
    assert {"kind": "vazao", "carta": "mld_cicatriz_braco"} in out["pilhas_eventos"]
    assert st["_piles"]["folego_bonus"] >= 1  # Braço de Cinza: +1 de Fôlego na próxima rodada


# ------------------------------------------------------------------ R9 Sussurro do Abismo
SUS = cs.SUSSURRO_ID


def _alto(p):
    p["abyss_charge"] = 9  # patamar severo em qualquer classe
    assert cm.abyss_tier(p) in ("moderado", "severo")


def test_sussurro_entra_uma_vez_por_cena_quando_a_carga_esta_alta():
    p = _player()
    piles = _piles(p)
    assert cs.on_start(piles, p) == [] and SUS not in piles["mao"]  # carga baixa
    _alto(p)
    cs.on_round_end(piles, p, cs.wound_counts(p))
    assert piles["compra"][0] == SUS and SUS in p["cartas_cena"]
    cs.on_round_end(piles, p, cs.wound_counts(p))
    assert (piles["compra"] + piles["mao"] + piles["descarte"]).count(SUS) == 1


def test_sussurro_ja_no_inicio_vai_para_a_mao():
    p = _player()
    _alto(p)
    piles = cp.start_piles(p, 4)
    cs.on_start(piles, p)
    assert SUS in piles["mao"]


def test_sussurro_joga_a_zero_de_folego_e_da_entropia():
    p = _player(entropy=3)
    _alto(p)
    piles = cp.start_piles(p, 4)
    cs.on_start(piles, p)
    step = ct.TurnStep(kind="card", card_id=SUS, target_id="gob_1")
    assert cp.step_folego(step) == 0
    piles["folego"] = 0
    plan = cp.plan_plays(piles, p, [step])
    assert plan["ok"] and plan["folego_total"] == 0 and plan["emprestado"] == 0
    res = cards.use_card({"player": p}, SUS)
    assert res["ok"] and p["entropy"] == 5  # +2 de Entropia


def test_sussurro_so_vale_dentro_do_conflito():
    p = _player()
    assert not cards.use_card({"player": p}, SUS)["ok"]  # fora da cena: não está preparada
    cs.cleanup(p)
    assert "cartas_cena" not in p


def test_sussurro_ignorado_por_duas_rodadas_apodrece_em_fardo():
    p = _player()
    _alto(p)
    piles = cp.start_piles(p, 4)
    cs.on_start(piles, p)
    cs.on_round_end(piles, p, cs.wound_counts(p))
    assert SUS in piles["mao"]  # 1ª rodada ignorada
    logs = cs.on_round_end(piles, p, cs.wound_counts(p))
    assert SUS not in piles["mao"] + piles["compra"] + piles["descarte"]
    assert cp.FARDO_ID in piles["mao"] and any("apodrece" in line for line in logs)
    assert "cartas_cena" in p and SUS not in p["cartas_cena"]


def test_sussurro_jogado_nao_apodrece_nem_volta():
    p = _player()
    _alto(p)
    piles = cp.start_piles(p, 4)
    cs.on_start(piles, p)
    cp.exhaust(piles, SUS)  # jogada: Frequência `cena` vai para Exaurida
    for _ in range(3):
        cs.on_round_end(piles, p, cs.wound_counts(p))
    assert cp.FARDO_ID not in piles["mao"] + piles["compra"] + piles["descarte"]
    assert piles["exaurida"].count(SUS) == 1 and SUS not in p["cartas_cena"]
