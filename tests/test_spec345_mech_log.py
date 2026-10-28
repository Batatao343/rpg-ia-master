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


def test_integra_no_no_de_combate_com_aliado(monkeypatch):
    """R6 pelo nó: ataque de aliado de cena sai com o nome dele no `last_mech_log`."""
    from langchain_core.messages import HumanMessage

    import agents.combat as combat_agent
    from services import conflict_orchestrator as orch
    from tests.test_api_jogadas import _state

    monkeypatch.setenv("RPG_CARD_DECK", "on")
    state = _state(monkeypatch)
    state["combat_simulation"] = {"enabled": False}
    state["combat"]["scene_allies"] = [{"id": "aldric", "name": "Mestre Aldric"}]
    target = str(state["enemies"][0].get("id") or state["enemies"][0].get("name"))

    def fake_round(scene, actors_by_id, sides, round_state, *a, **k):
        atk = {
            "actor_id": "aldric",
            "target_id": target,
            "dice_rolled": [5, 6],
            "dice_kept": [5, 6],
            "virtude": 1,
            "modificador": 0,
            "total": 12,
            "esquiva_alvo": 9,
            "resultado": "acerto",
            "acerto": True,
            "dano_final": 2,
        }
        return {
            "logs": ["troca"], "deaths": [], "terminal": [], "abyss": [], "attacks": [atk],
            "reactions": [], "last_stands": [], "stabilizations": [], "scars_pending": [],
            "resolved_turns": ["player"], "cards_used": [], "recidiva_event": None,
            "reason": None, "ended": False, "player_dead": False,
        }  # fmt: skip

    monkeypatch.setattr(orch, "run_round", fake_round)
    monkeypatch.setattr(combat_agent, "_narrate", lambda *a, **k: "Narração.")
    state["messages"] = [HumanMessage(content="ataco")]
    out = combat_agent._combat_node(state)
    log = out["combat"]["last_mech_log"]
    assert log and log[0].startswith("Mestre Aldric")
    assert all("?" not in line for line in log)
