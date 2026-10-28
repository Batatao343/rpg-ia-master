"""SPEC-355 R4: queda causada por Reacao grava golpe final com autoria."""

from __future__ import annotations

import random

from services import conflict_orchestrator as orch
from services import conflict_turn as ct
from services import round_log
from tests.test_round_multi_play import _setup

REACTION = "dev_encaixe"


def _blows(out: dict) -> list[dict]:
    return [b for b in out.get("final_blows") or [] if b.get("kind") == "reacao"]


def _hero_reaction_round(seed: int):
    scene, actors, sides, state = _setup(mode="off", class_name="Devoto do Abismo")
    gob = actors["gob_1"]
    gob.update({"categoria": "lacaio", "vitalidade": 1, "max_vitalidade": 6})
    hero = actors["player"]
    hero["prepared_cards"] = list(dict.fromkeys([*hero["prepared_cards"], REACTION]))
    hero["entropy"] = 10
    state["_player_reaction_card_id"] = REACTION
    decl = ct.TurnDeclaration(
        actor_id="player", reaction_card_id=REACTION, acao=ct.TurnStep(kind="pass")
    )
    out = orch.run_round(
        scene,
        actors,
        sides,
        state,
        declarations={"player": decl},
        initiator="enemy",
        rng=random.Random(seed),
    )
    return out, actors


def test_reaction_kill_records_final_blow():
    found = None
    for seed in range(40):
        out, actors = _hero_reaction_round(seed)
        if _blows(out):
            found = (out, actors)
            break
    assert found, "o contra-ataque precisa derrubar o atacante em alguma semente"
    out, _ = found
    blow = _blows(out)[0]
    assert blow["target_id"] == "gob_1"
    assert blow["by_actor_id"] == "player"
    assert blow["card_id"] == REACTION


def test_facts_and_fallback_name_reaction():
    for seed in range(40):
        out, _ = _hero_reaction_round(seed)
        if _blows(out):
            break
    else:
        raise AssertionError("sem queda por Reacao")
    names = {"player": "Você", "gob_1": "Goblin"}
    sentence = round_log.final_blow_sentence(out, names)
    assert "reação" in sentence and "Goblin" in sentence
    auth = round_log.authorship(out, names)
    assert auth["final_by_hero"] and auth["final_on_enemy"]
    assert any("de Você em Goblin" in ln for ln in auth["final_lines"])


def test_enemy_reaction_downs_hero_has_author():
    for seed in range(80):
        scene, actors, sides, state = _setup(mode="off", class_name="Devoto do Abismo")
        hero, gob = actors["player"], actors["gob_1"]
        gob["cartas"] = ["bst_casca_reativa"]
        gob["virtudes"]["forca"] = 5
        hero["vitalidade"] = 0
        hero["esquiva"] = 0
        hero["ferimento_espacos"] = {"leve": 1, "grave": 1, "critico": 1}
        hero["ferimentos"] = {  # a proxima ferida abre o ultimo Critico: a Reacao derruba o heroi
            "leve": [{"categoria": "leve", "regiao": "torso", "aplicado": True}],
            "grave": [{"categoria": "grave", "regiao": "torso", "aplicado": True}],
            "critico": [],
        }
        decl = ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id="gob_1")
        )
        out = orch.run_round(
            scene,
            actors,
            sides,
            state,
            declarations={"player": decl},
            initiator="heroes",
            rng=random.Random(seed),
        )
        blows = [b for b in _blows(out) if b["target_id"] == "player"]
        if blows:
            assert blows[0]["by_actor_id"] == "gob_1"
            assert blows[0]["card_id"] == "bst_casca_reativa"
            lines = round_log.authorship(out, {"player": "Você", "gob_1": "Goblin"})
            assert any("Goblin" in ln for ln in lines["final_lines"])
            return
    raise AssertionError("a Reacao inimiga nunca derrubou o heroi")
