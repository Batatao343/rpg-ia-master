"""SPEC-360 R20: cacar seguindo o rastro (regex fechada, encontro no lugar, surpresa do jogador)."""

from __future__ import annotations

import pytest

from services import fauna
from tests.test_spec360_sinais import ARAME, LAMA, presence, sim_with, state_at


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")


@pytest.mark.parametrize(
    "text",
    [
        "sigo o rastro",
        "Sigo as pegadas até o canal",
        "vou seguir o cheiro",
        "quero rastrear essa coisa",
        "vamos caçar o que deixou isso",
        "vou atrás do que deixou essas marcas",
        "Sigo o som pela viela",
        "rastreio o mercador",  # bate na regex; sem presenca nao vira caca (abaixo)
    ],
)
def test_hunt_intent_regex_positivos(text):
    assert fauna.hunt_intent(text)


@pytest.mark.parametrize(
    "text",
    ["olho a viela", "sigo para o Anel de Ferro", "um caco de vidro no chão", "descanso", "ataco"],
)
def test_hunt_intent_regex_negativos(text):
    assert not fauna.hunt_intent(text)


def test_rastreio_sem_presenca_nao_caca(on):
    st = state_at(sim={}, text="rastreio o mercador")
    assert fauna.hunt_hint(st, st["world"], 3, text="rastreio o mercador") is None


def test_sem_sinal_nao_caca(on):
    st = state_at(sim=sim_with(presence()), text="sigo o rastro")
    assert fauna.hunt_hint(st, st["world"], 3, text="sigo o rastro") is None


def test_caca_off_nao_caca(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "off")
    st = state_at(sim=sim_with(presence(shown=("rastro",))), text="sigo o rastro")
    assert fauna.hunt_hint(st, st["world"], 3, text="sigo o rastro") is None


def test_caca_dispara_no_lugar_com_surpresa_do_jogador(on):
    from agents import storyteller

    st = state_at(sim=sim_with(presence(shown=("rastro", "som"))), text="sigo o rastro")
    st["world"]["last_encounter_turn"] = 19  # cooldown ativo: a caca nao depende dele
    out = storyteller.storyteller_node(st)
    assert out["next"] == "combat_agent"
    assert out["combat_encounter_hint"]["reason"] == "caca"
    assert out["combat_encounter_hint"]["enemy_id"] == ARAME
    assert out["world"]["encounter_surprise"] == "player"
    assert out["world"]["last_encounter_turn"] == st["world"]["turn_count"]
    assert fauna.approach_line(ARAME) in out["messages"][0].content
    assert out["world_sim"]["fauna"]["presencas"][0]["status"] == "cacada"
    assert out["bestiary_knowledge"][ARAME]["sinais_vistos"] == ["rastro", "som"]


def test_caca_sem_presenca_cai_no_fluxo_de_hoje(on):
    from agents import storyteller

    out = storyteller.storyteller_node(state_at(loc=LAMA, sim={}, text="sigo o rastro"))
    assert out.get("next") != "combat_agent"
