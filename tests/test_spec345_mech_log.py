"""SPEC-345 R6: o mech log nomeia aliados e nunca mostra `?`."""

from __future__ import annotations

from services import combat_preview as cpv


def _atk(actor, target):
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
    }


ACTORS = [
    {"id": "player", "name": "Herói", "is_player": True},
    {"id": "bandido_2", "name": "Bandido 2"},
    {"id": "aldric", "name": "Mestre Aldric"},
]


def test_ataque_de_aliado_tem_nome():
    [line] = cpv.mech_log([_atk("aldric", "bandido_2")], ACTORS)
    assert line.startswith("Mestre Aldric") and "→ Bandido 2" in line


def test_aliado_sem_id_usa_nome():
    actors = [*ACTORS[:2], {"name": "Lyra"}]
    [line] = cpv.mech_log([_atk("Lyra", "bandido_2")], actors)
    assert line.startswith("Lyra")


def test_desconhecido_vira_alguem():
    lines = cpv.mech_log([_atk("fantasma", "player"), _atk("player", "sumido")], ACTORS)
    assert lines[0].startswith("Alguém")
    assert "→ Alguém" in lines[1]
    assert all("?" not in line for line in lines)
