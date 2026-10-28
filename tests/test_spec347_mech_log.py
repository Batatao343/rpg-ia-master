"""SPEC-347 R5.2: reação/oportunidade/Última Ação saem rotuladas no log mecânico; ataque normal fica idêntico."""

from __future__ import annotations

from services import combat_preview as cpv

ACTORS = [
    {"id": "player", "name": "Herói", "is_player": True},
    {"id": "enemy_1", "name": "Saqueador"},
]


def _atk(actor, target, **extra):
    return {
        "actor_id": actor,
        "target_id": target,
        "dice_rolled": [6, 7],
        "dice_kept": [6, 7],
        "virtude": 0,
        "modificador": 0,
        "total": 13,
        "esquiva_alvo": 10,
        "resultado": "acerto",
        "acerto": True,
        "dano_final": 3,
        **extra,
    }


def test_counter_attack_labeled():
    [line] = cpv.mech_log([_atk("enemy_1", "player", fora_de_turno="Contra-ataque")], ACTORS)
    assert line.startswith("Saqueador · Contra-ataque → Você")


def test_opportunity_labeled():
    [line] = cpv.mech_log(
        [_atk("enemy_1", "player", fora_de_turno="Ataque de Oportunidade")], ACTORS
    )
    assert "Saqueador · Ataque de Oportunidade → Você" in line


def test_plain_attack_unchanged():
    [line] = cpv.mech_log([_atk("player", "enemy_1")], ACTORS)
    assert line == "Você → Saqueador · 2d10 6 + 7 +0 = 13 vs 10 · acerto · 3 dano"


def test_basic_attack_annotates_label(monkeypatch):
    import random

    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs

    scene = cs.new_scene()
    a = orch.ensure_combat_sheet(
        {"id": "a", "name": "A", "virtudes": {"forca": 3, "agilidade": 2, "corpo": 2}}
    )
    b = orch.ensure_combat_sheet(
        {"id": "b", "name": "B", "virtudes": {"forca": 1, "agilidade": 1, "corpo": 2}}
    )
    for i in ("a", "b"):
        cs.place(scene, i)
    out: dict = {"logs": [], "resolved_turns": []}  # dentro de uma rodada real
    orch._basic_attack(scene, a, "a", b, "b", out, random.Random(1), label="Contra-ataque")
    assert out["attacks"][0]["fora_de_turno"] == "Contra-ataque"


def test_basic_attack_outside_a_round_stays_unannotated():
    import random

    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs

    scene = cs.new_scene()
    a = orch.ensure_combat_sheet({"id": "a", "name": "A", "virtudes": {"forca": 3, "agilidade": 2, "corpo": 2}})
    b = orch.ensure_combat_sheet({"id": "b", "name": "B", "virtudes": {"forca": 1, "agilidade": 1, "corpo": 2}})
    for i in ("a", "b"):
        cs.place(scene, i)
    out: dict = {"logs": []}
    orch._basic_attack(scene, a, "a", b, "b", out, random.Random(1), label="Contra-ataque")
    assert "fora_de_turno" not in out["attacks"][0]
