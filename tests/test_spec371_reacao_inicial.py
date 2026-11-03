"""SPEC-371 (dono 03/11, "Reação p/ toda Postura"): Arcanista e Médico nascem com uma Carta de
reação de tronco preparada, que dispara contra o golpe em curso sem gastar a Ação."""

from __future__ import annotations

import random

import pytest

import character_creator as cc
from services import card_effects as fx
from services import card_lint, cards
from services import conflict_orchestrator as orch
from services import conflict_turn as ct
from tests.test_round_multi_play import _setup

NOVAS = {
    "Arcanista Cinzento": ("arc1_ini_cinza_nos_olhos", "cego"),
    "Médico de Campo": ("med1_ini_pinca_no_tendao", "desarmado_risco"),
}
# Posturas que já nasciam com reação no Acervo: preparação congelada (nada muda nelas).
SEM_REACAO_INICIAL = {
    "Devoto do Abismo": ["dev_golpe_convite", "dev_muralha_viva", "dev_conviccao", "dev_aguentar"],
    "Sangromante": ["san_corte_troca", "san_finta", "san_esquiva", "san_pacto"],
    "Corruptor": ["cor_toque", "cor_esporos", "cor_carne_docil", "cor_farejar"],
}


@pytest.mark.parametrize("cls", sorted(NOVAS))
def test_carta_nova_lint_orcamento_e_identidade(cls):
    cid, cond = NOVAS[cls]
    assert cc.starting_reaction_id(cls) == cid
    card = cards.get_card(cid)
    assert card["tipo"] == "reacao" and card["classe"] == cls and not card.get("subclasse")
    assert card["gatilho"] == "ao_ser_atacado" and card["level_req"] == 1
    assert card["raridade"] == "comum" and card.get("onda") == 1
    pool = card_lint.load_pool()
    issues = card_lint.lint_card(card, [c for c in pool if c["id"] != cid])
    assert not issues, [str(i) for i in issues]
    assert fx.budget_error(card) is None
    efeito = fx.primary_effect(card)
    # não é reskin de `san_esquiva` (Esquiva) nem de `cor_membrana` (Proteção)
    assert efeito["kind"] == "aplicar_condicao" and efeito["condicao"] == cond


@pytest.mark.parametrize("cls", sorted(NOVAS))
def test_criacao_prepara_a_reacao_inicial(cls):
    cid, _ = NOVAS[cls]
    out = cc._resolve_starting_cards({}, cls, {})
    assert len(out["known_cards"]) == 6 and len(out["prepared_cards"]) == 4
    assert cid in out["known_cards"] and cid in out["prepared_cards"]
    # toma a vaga de uma Carta que não é ativa: os golpes e curas iniciais continuam
    ativas = [c for c in out["known_cards"][:4] if cards.get_card(c)["tipo"] == "ativa"]
    assert set(ativas) <= set(out["prepared_cards"])


@pytest.mark.parametrize("cls", sorted(SEM_REACAO_INICIAL))
def test_posturas_com_reacao_ja_no_acervo_nao_mudam(cls):
    assert cc.starting_reaction_id(cls) is None
    assert cc._resolve_starting_cards({}, cls, {})["prepared_cards"] == SEM_REACAO_INICIAL[cls]


def test_escolha_do_jogador_e_respeitada():
    known = ["arc_descarga", "arc_faisca", "arc_vazao", "arc_olho", "arc_aterramento"]
    out = cc._resolve_starting_cards(
        {"known_cards": known, "prepared_cards": known[:4]}, "Arcanista Cinzento", {}
    )
    assert out["prepared_cards"] == known[:4]


def test_keep_starting_reaction_toma_a_vaga_da_ultima_nao_ativa():
    cid = "arc1_ini_cinza_nos_olhos"
    known = ["arc_vazao", "arc_olho", "arc_faisca", "arc_descarga", cid]
    prep = ["arc_vazao", "arc_olho", "arc_faisca", "arc_descarga"]
    assert cc.keep_starting_reaction(prep, known, "Arcanista Cinzento", 4) == [
        "arc_vazao",
        cid,
        "arc_faisca",
        "arc_descarga",
    ]
    assert cc.keep_starting_reaction(prep[:3], known, "Arcanista Cinzento", 4) == prep[:3] + [cid]
    assert cc.keep_starting_reaction(prep, prep, "Arcanista Cinzento", 4) == prep  # fora do Acervo
    assert cc.keep_starting_reaction(prep, known, "Sangromante", 4) == prep


@pytest.mark.parametrize("cls", sorted(NOVAS))
def test_heroi_nivel_3_da_arena_tem_a_reacao_preparada(cls):
    from playtest.runner import _build_initial_state

    player = _build_initial_state("arena", 285, class_name=cls, start_level=3)["player"]
    assert NOVAS[cls][0] in player["prepared_cards"]


@pytest.mark.parametrize("cls", sorted(NOVAS))
def test_reacao_dispara_contra_o_golpe_e_marca_o_atacante(cls):
    cid, cond = NOVAS[cls]
    hits = 0
    for seed in range(20):
        scene, actors, sides, state = _setup(mode="off", class_name=cls)
        hero, gob = actors["player"], actors["gob_1"]
        hero["prepared_cards"] = list(dict.fromkeys([*hero["prepared_cards"], cid]))
        hero["entropy"] = 10
        state["_player_reaction_card_id"] = cid
        decl = ct.TurnDeclaration(
            actor_id="player", reaction_card_id=cid, acao=ct.TurnStep(kind="pass")
        )
        orch.run_round(
            scene,
            actors,
            sides,
            state,
            declarations={"player": decl},
            initiator="enemy",
            rng=random.Random(seed),
        )
        marks = [c for c in gob.get("active_conditions") or [] if c.get("source") == cid]
        if marks:
            hits += 1
            assert marks[0]["name"].lower().startswith(cond.split("_")[0])
    assert hits == 20
