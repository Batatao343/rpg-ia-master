"""SPEC-387 R19-R20: `proteger` só com ator; desfecho de objetivo falho conta a causa."""

from __future__ import annotations

import re
from types import SimpleNamespace

import agents.combat as combat
from services import round_log
from services import scene_cards as sc


def test_protect_target_must_be_actor():
    scene = {"enemies": [{"id": "e1"}], "npcs": [{"id": "ketil"}], "allies": []}
    assert sc.sanitize_objective({"tipo": "proteger", "alvo": "ketil"}, scene) == {
        "tipo": "derrotar_todos"
    }
    scene["allies"] = ["ketil"]
    assert sc.sanitize_objective({"tipo": "proteger", "alvo": "ketil"}, scene) == {
        "tipo": "proteger",
        "alvo": "ketil",
    }


def test_protect_old_save_not_failed(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    scene = {"objetivo": {"tipo": "proteger", "alvo": "ketil"}, "zones": [], "objects": []}
    ctx = SimpleNamespace(
        scene=scene,
        actors_by_id={"player": {"is_player": True, "id": "player"}, "e1": {"id": "e1"}},
        sides={"enemy": ["e1"], "hero": ["player"]},
    )
    assert sc.check_objective(ctx, 1) is None  # nunca "falhou" na rodada 1
    assert scene.get("objetivo_resultado") is None
    assert scene["objetivo"] == {"tipo": "derrotar_todos"}


def test_objective_failed_outcome_text():
    last = {
        "objetivo": {"tipo": "proteger", "resultado": "falhou", "motivo": "Escoltado não resistiu."}
    }
    player = {"name": "Kael", "conscious": True, "vitalidade": 9, "max_vitalidade": 10}
    facts = round_log.outcome_facts("objective_failed", {}, player, [], last)
    assert "Objetivo: Escoltado não resistiu." in facts
    assert any(f.startswith("Herói:") for f in facts)
    text = round_log.deterministic_outcome_text("objective_failed", {}, player, last_out=last)
    assert "O objetivo se perdeu: Escoltado não resistiu." in text and "segue de pé" in text
    assert not re.search(r"perde os sentidos|apaga|\bcai\b|tomba", text)
    fecho = combat._fecho("objective_failed", last)
    assert "Escoltado não resistiu" in fecho and "não narre queda nem desmaio" in fecho
    assert combat._fecho("defeat", last) == combat._OUTCOME_FECHO["defeat"]
