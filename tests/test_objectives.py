"""SPEC-331 R4/R5 - Objetivo com regra (catálogo fechado, desfecho próprio)."""

import random

import pytest

from services import card_effects as fx
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import scene_cards as sc

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}


def _actor(aid, **kw):
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _setup(objetivo, ids=("player", "e", "npc")):
    scene = cs.new_scene(
        [
            {"id": "z0", "name": "A", "connections": ["z1"]},
            {"id": "z1", "name": "B", "connections": []},
        ]
    )
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    scene["objetivo"] = objetivo
    actors = {i: _actor(i) for i in ids}
    ctx = fx.Ctx(
        scene=scene,
        actors_by_id=actors,
        sides={"hero": ["player"], "ally": ["npc"] if "npc" in ids else [], "enemy": ["e"]},
        rng=random.Random(1),
    )
    return scene, actors, ctx


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")


def test_ausencia_de_objetivo_e_derrotar_todos():
    scene, _, ctx = _setup(None)
    assert sc.check_objective(ctx, 9) is None
    assert sc.sanitize_objective(None, scene) == {"tipo": "derrotar_todos"}
    assert sc.sanitize_objective({"tipo": "inventado"}, scene) == {"tipo": "derrotar_todos"}


def test_objetivo_invalido_vira_padrao():
    scene, _, _ = _setup(None)
    scene["enemies"] = [{"id": "e"}]
    scene["objects"] = [{"id": "o1"}]
    assert sc.sanitize_objective({"tipo": "proteger", "alvo": "fantasma"}, scene) == {
        "tipo": "derrotar_todos"
    }
    assert sc.sanitize_objective({"tipo": "alcancar_zona", "alvo": "z1"}, scene)["alvo"] == "z1"
    assert sc.sanitize_objective({"tipo": "destruir_objeto", "alvo": "o1"}, scene)["alvo"] == "o1"
    got = sc.sanitize_objective({"tipo": "interromper_ritual", "n": 99}, scene)
    assert got == {"tipo": "interromper_ritual", "alvo": "e", "n": 6}
    assert sc.sanitize_objective({"tipo": "sobreviver_n_rodadas"}, scene)["n"] == 5


def test_sobreviver_n_rodadas():
    scene, _, ctx = _setup({"tipo": "sobreviver_n_rodadas", "n": 3})
    assert sc.check_objective(ctx, 2) is None
    assert sc.check_objective(ctx, 3)
    assert scene["objetivo_resultado"] == "cumprido"


def test_proteger_falha_se_o_alvo_cai_e_cumpre_se_os_inimigos_caem():
    scene, actors, ctx = _setup({"tipo": "proteger", "alvo": "npc"})
    assert sc.check_objective(ctx, 1) is None
    actors["npc"]["dead"] = True
    assert sc.check_objective(ctx, 2)
    assert scene["objetivo_resultado"] == "falhou"
    scene2, actors2, ctx2 = _setup({"tipo": "proteger", "alvo": "npc"})
    actors2["e"]["dead"] = True
    assert sc.check_objective(ctx2, 2)
    assert scene2["objetivo_resultado"] == "cumprido"


def test_alcancar_zona():
    scene, _, ctx = _setup({"tipo": "alcancar_zona", "alvo": "z1"})
    assert sc.check_objective(ctx, 1) is None
    scene["positions"]["player"]["zone_id"] = "z1"
    assert sc.check_objective(ctx, 2)
    assert scene["objetivo_resultado"] == "cumprido"


def test_destruir_objeto():
    scene, _, ctx = _setup({"tipo": "destruir_objeto", "alvo": "altar"})
    cs.add_object(scene, {"id": "altar", "name": "Altar"}, from_trigger=True)
    assert sc.check_objective(ctx, 1) is None
    scene["objects"][0]["destroyed"] = True
    assert sc.check_objective(ctx, 2)
    assert scene["objetivo_resultado"] == "cumprido"


def test_interromper_ritual_cumpre_ou_falha_no_prazo():
    scene, actors, ctx = _setup({"tipo": "interromper_ritual", "alvo": "e", "n": 3})
    assert sc.check_objective(ctx, 2) is None
    assert sc.check_objective(ctx, 3) == "O ritual se completa."
    assert scene["objetivo_resultado"] == "falhou"
    scene2, actors2, ctx2 = _setup({"tipo": "interromper_ritual", "alvo": "e", "n": 3})
    actors2["e"]["incapacitated"] = True
    assert sc.check_objective(ctx2, 1) == "O ritual foi interrompido."
    assert scene2["objetivo_resultado"] == "cumprido"


def test_capturar_vivo_exige_ninguem_morto():
    scene, actors, ctx = _setup({"tipo": "capturar_vivo"})
    actors["e"]["incapacitated"] = True
    actors["e"]["nonlethal_by"] = "player"
    assert sc.check_objective(ctx, 1)
    assert scene["objetivo_resultado"] == "cumprido"
    scene2, actors2, ctx2 = _setup({"tipo": "capturar_vivo"})
    actors2["e"]["dead"] = True
    sc.check_objective(ctx2, 1)
    assert scene2["objetivo_resultado"] == "falhou"


def test_run_round_encerra_com_desfecho_proprio():
    player, e, npc = _actor("player"), _actor("e"), _actor("npc")
    scene = cs.new_scene()
    for i in ("player", "e", "npc"):
        cs.place(scene, i)
    cs.freeze(scene)
    scene["objetivo"] = {"tipo": "sobreviver_n_rodadas", "n": 2}
    sides = {"hero": ["player"], "ally": ["npc"], "enemy": ["e"]}
    actors = {"player": player, "e": e, "npc": npc}
    out1 = orch.run_round(
        scene,
        actors,
        sides,
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        rng=random.Random(3),
    )
    assert not out1.get("objetivo")
    out2 = orch.run_round(
        scene,
        actors,
        sides,
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        rng=random.Random(3),
    )
    assert out2["ended"] and out2["objetivo"] == {
        "tipo": "sobreviver_n_rodadas",
        "resultado": "cumprido",
    }


def test_flag_off_ignora_objetivo(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    scene, _, ctx = _setup({"tipo": "sobreviver_n_rodadas", "n": 2})
    assert sc.check_objective(ctx, 5) is None
    assert "objetivo_resultado" not in scene


def test_outcome_do_no_de_combate_segue_o_objetivo():
    from agents.combat import _encounter_outcome

    en = [{"status": "ativo"}]
    kw = dict(player={"conscious": True}, enemies=en, hero_fled=False, player_dead=False)
    assert _encounter_outcome(**kw) == "defeat"
    assert _encounter_outcome(**kw, objective_result="cumprido") == "victory"
    assert _encounter_outcome(**{**kw, "enemies": []}, objective_result="falhou") == "defeat"
