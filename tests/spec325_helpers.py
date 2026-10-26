"""Helpers compartilhados dos testes da SPEC-325 (combate via `combat_node` real)."""

from __future__ import annotations

import random

from langchain_core.messages import HumanMessage

from agents import combat as cbt


def make_state(enemies, intent="ataco o inimigo", *, declaration=None, player_over=None):
    from tests.test_fase43 import make_player

    p = make_player(hp=10, inventory=[])
    p.update(
        {
            "virtudes": {"forca": 5, "agilidade": 5, "corpo": 4, "mente": 1, "carisma": 1},
            "vitalidade": 40,
            "max_vitalidade": 40,
            "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
            "ferimentos": {"leve": [], "grave": [], "critico": []},
        }
    )
    p.update(player_over or {})
    first = enemies[0]["id"]
    return {
        "messages": [HumanMessage(content=intent)],
        "player": p,
        "enemies": enemies,
        "combat": {"round": 1, "active": True},
        "combat_target": enemies[0]["name"],
        "world": {"turn_count": 3},
        "bestiary_knowledge": {},
        "pending_world_events": [],
        "combat_declaration": declaration
        or {"actor_id": "player", "acao": {"kind": "attack", "target_id": first}},
    }


def lacaio(eid="e1", name="Goblin", **over):
    e = {
        "id": eid,
        "name": name,
        "type": "Minion",
        "categoria": "lacaio",
        "hp": 1,
        "max_hp": 1,
        "vitalidade": 1,
        "max_vitalidade": 1,
        "defense": 0,
        "esquiva": 0,
        "status": "ativo",
        "virtudes": {"forca": 0, "agilidade": 0, "corpo": 0, "mente": 0, "carisma": 0},
        "active_conditions": [],
        "attacks": [{"name": "M", "bonus": -20, "damage": "1d1"}],
        "attack_mod": 0,
    }
    e.update(over)
    return e


def run_node(state, monkeypatch, *, seed=1, narrate=None):
    """Roda o `combat_node` real com seed fixa. `narrate` captura as mensagens."""
    monkeypatch.setattr(cbt, "_narrate", narrate or (lambda *a, **k: "Fim."))
    random.seed(seed)
    return cbt.combat_node(state)
