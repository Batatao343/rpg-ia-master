"""SPEC-332 R5: fases de chefe (baralho extra + padrão novo + troca narrada + presságio novo)."""

from __future__ import annotations

import random

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import enemy_decks as edk


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    edk.reload()


def _boss():
    return orch.ensure_combat_sheet(
        {
            "id": "chefe_1",
            "name": "Valerius",
            "categoria": "chefe",
            "arquetipo": "guardiao",
            "max_vitalidade": 40,
            "vitalidade": 40,
            "entropy": 10,
            "max_entropy": 10,
            "cartas": ["bst_postura_muralha"],
            "tactical_profile": {
                "priorities": [{"trigger": "sempre", "action_key": "attack"}],
                "padrao": ["ataque"],
                "fases": [
                    {
                        "ate_vitalidade_pct": 70,
                        "baralho_extra": ["bst_furia_final"],
                        "padrao": ["reforco_proprio", "ataque"],
                        "narracao": "{nome} cospe sangue e rasga o manto.",
                    },
                    {
                        "ate_vitalidade_pct": 30,
                        "baralho_extra": ["bst_golpe_mestre", "carta_que_nao_existe"],
                        "padrao": ["ataque"],
                    },
                ],
            },
        }
    )


def _world(boss):
    scene = cs.new_scene()
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        },
        is_player=True,
    )
    for i in ("player", "chefe_1"):
        cs.place(scene, i)
    cs.freeze(scene)
    return (
        scene,
        {"player": player, "chefe_1": boss},
        {"hero": ["player"], "ally": [], "enemy": ["chefe_1"]},
    )


def test_phase_changes_once_with_narration_extra_deck_and_pattern():
    boss = _boss()
    _, actors, sides = _world(boss)
    out: dict = {"logs": []}
    assert edk.apply_phases(actors, sides, out) is False  # vida cheia: fase 0
    assert edk.pattern_of(boss) == ["ataque"]
    boss["vitalidade"] = 25  # 62 %
    assert edk.apply_phases(actors, sides, out) is True
    assert boss["fase_idx"] == 1
    assert "bst_furia_final" in boss["cartas"]
    assert edk.pattern_of(boss) == ["reforco_proprio", "ataque"]
    assert out["logs"] == ["Valerius cospe sangue e rasga o manto."]
    assert out["fases"] == [{"actor_id": "chefe_1", "fase": 1}]
    assert edk.apply_phases(actors, sides, out) is False  # não repete a mesma fase


def test_phase_skips_forward_and_never_regresses_or_loads_unknown_cards():
    boss = _boss()
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 8  # 20 %: cruza as duas de uma vez
    out: dict = {}
    assert edk.apply_phases(actors, sides, out) is True
    assert boss["fase_idx"] == 2
    assert "bst_furia_final" in boss["cartas"] and "bst_golpe_mestre" in boss["cartas"]
    assert "carta_que_nao_existe" not in boss["cartas"]
    boss["vitalidade"] = 40  # curou: a fase não volta
    assert edk.apply_phases(actors, sides, out) is False
    assert boss["fase_idx"] == 2


def test_phases_inert_when_flag_off(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "off")
    boss = _boss()
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 5
    assert edk.apply_phases(actors, sides, {"logs": []}) is False
    assert "fase_idx" not in boss


def test_run_round_narrates_phase_and_recomputes_the_presságio(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    boss = _boss()
    scene, actors, sides = _world(boss)
    stale = {
        "chefe_1": [
            {
                "actor_id": "chefe_1",
                "idx": 0,
                "tipo": "ataque",
                "alvo_id": "player",
                "carta_id": None,
                "declaration": ct.TurnDeclaration(
                    actor_id="chefe_1", acao=ct.TurnStep(kind="pass")
                ).model_dump(),
            }
        ]
    }
    boss["vitalidade"] = 20
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}
    out = orch.run_round(
        scene, actors, sides, {}, declarations=decl, rng=random.Random(3), pressagios=stale
    )
    assert any("cospe sangue" in line for line in out["logs"])
    assert out["fases"] == [{"actor_id": "chefe_1", "fase": 1}]
    # o presságio congelado antigo (passar a vez) foi descartado e recalculado na nova fase
    assert not any("cumpre o que o presságio anunciava" in line for line in out["logs"][:1])
    assert boss["fase_idx"] == 1
