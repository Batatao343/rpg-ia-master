"""SPEC-329: Presságio — intenção do inimigo congelada antes da jogada."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import enemy_intent as ei


def _player(**kw):
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Devoto do Abismo",
        "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "entropy": 10,
        "max_entropy": 10,
        "abyss_charge": 0,
    }
    p.update(kw)
    return orch.ensure_combat_sheet(p, is_player=True)


def _enemy(eid, **kw):
    e = {
        "id": eid,
        "name": eid.capitalize(),
        "type": "Minion",
        "hp": 12,
        "max_hp": 12,
        "ac": 11,
        "entropy": 10,
        "cartas": [],
        "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
    }
    e.update(kw)
    return orch.ensure_combat_sheet(e)


def _world(enemies: dict[str, dict], *, ally_ids=()):
    scene = cs.new_scene()
    for i in ["player", *ally_ids, *enemies]:
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": _player(), **enemies}
    for aid in ally_ids:
        actors[aid] = orch.ensure_combat_sheet(
            {"id": aid, "name": "Aliada", "hp": 10, "max_hp": 10, "transient": True},
            is_ally=True,
        )
    sides = {"hero": ["player"], "ally": list(ally_ids), "enemy": list(enemies)}
    return scene, actors, sides


def _pass():
    return ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)


# --- flag ---------------------------------------------------------------------
def test_flag_default_off_and_invalid_value(monkeypatch):
    assert ei.mode() == "off"
    monkeypatch.setenv("RPG_ENEMY_INTENT", "talvez")
    assert ei.mode() == "off"
    monkeypatch.setenv("RPG_ENEMY_INTENT", "ON")
    assert ei.active()


# --- R1: previsão = decisão atual, sem efeito colateral -------------------------
def test_forecast_matches_current_decision_when_nothing_changes():
    scene, actors, sides = _world({"lobo": _enemy("lobo"), "urso": _enemy("urso")})
    frozen = ei.forecast_round(scene, actors, sides, random.Random(7))
    for eid in ("lobo", "urso"):
        late = orch.enemy_declaration(scene, eid, actors, sides, rng=random.Random(7))
        assert frozen[eid][0]["declaration"] == late.model_dump()
        assert frozen[eid][0]["tipo"] == "ataque"
        assert frozen[eid][0]["alvo_id"] == "player"


def test_forecast_has_no_side_effects():
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    actors["lobo"]["_forced_attack"] = True
    before = copy.deepcopy(actors)
    rng = random.Random(3)
    state = rng.getstate()
    ei.forecast_round(scene, actors, sides, rng)
    assert actors == before  # `_forced_attack` não foi consumido
    assert rng.getstate() == state  # rng real intacto


def test_forecast_skips_stunned_enemy():
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    actors["lobo"]["active_conditions"] = [{"name": "Atordoado", "control": "stun", "duration": 1}]
    assert ei.forecast_round(scene, actors, sides, random.Random(1)) == {}


# --- R6: determinismo ---------------------------------------------------------------
def test_forecast_and_round_are_deterministic_per_seed(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")

    def run():
        scene, actors, sides = _world({"lobo": _enemy("lobo")})
        frozen = ei.forecast_round(scene, actors, sides, random.Random(11))
        out = orch.run_round(
            scene,
            actors,
            sides,
            {"player": actors["player"]},
            declarations={"player": _pass()},
            rng=random.Random(11),
            pressagios=frozen,
        )
        return frozen, out["logs"], actors["player"]["vitalidade"]

    assert run() == run()


# --- R2/R3: visão pública por conhecimento -------------------------------------------
def test_public_intent_gradation_by_knowledge():
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    intent = {
        "actor_id": "lobo",
        "idx": 0,
        "tipo": "ataque",
        "alvo_id": "player",
        "carta_id": "arc_descarga",  # dano_base 4
        "declaration": {},
    }
    desconhecida = ei.public_intent(intent, "desconhecida", actors_by_id=actors)
    assert desconhecida["tipo"] == "ataque" and desconhecida["alvo_id"] == "player"
    assert desconhecida["faixa"] is None and desconhecida["carta_nome"] is None
    assert desconhecida["sinal"]

    conhecida = ei.public_intent(intent, "conhecida", actors_by_id=actors)
    assert conhecida["faixa"] and conhecida["faixa"][0] <= conhecida["faixa"][1]
    assert conhecida["valor_estimado"] is None and conhecida["carta_nome"] is None

    estudada = ei.public_intent(intent, "estudada", actors_by_id=actors)
    assert estudada["valor_estimado"] == estudada["faixa"][0]
    assert estudada["carta_nome"] == "Descarga do Instrumento"


def test_knowledge_level_from_revealed_cards():
    lobo = _enemy("lobo")
    assert ei.knowledge_level(lobo, "arc_descarga") == "desconhecida"
    lobo["revealed_resistances"] = ["igneo:resiste"]
    assert ei.knowledge_level(lobo, "arc_descarga") == "conhecida"
    lobo["revealed_cards"] = ["arc_descarga"]
    assert ei.knowledge_level(lobo, "arc_descarga") == "estudada"


def test_public_round_has_no_declaration_or_internal_fields():
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    frozen = ei.forecast_round(scene, actors, sides, random.Random(5))
    rows = ei.public_round(frozen, actors)
    assert rows and "declaration" not in rows[0] and "carta_id" not in rows[0]
    json.dumps(rows)


def test_sinais_catalog_covers_every_type_and_family():
    data = json.loads(
        (Path(__file__).resolve().parent.parent / "data/combat/pressagio_sinais.json").read_text(
            encoding="utf-8"
        )
    )
    for tipo in ei.TIPOS:
        assert len(data[tipo]["default"]) >= 2, tipo
    for tipo in ("ataque", "ataque_multiplo", "defesa", "enfraquecer"):
        for fam in ("fera", "morto_inquieto", "legiao", "culto", "ermo", "abissal"):
            assert len(data[tipo][fam]) == 2, (tipo, fam)
    assert ei.family_of({"id": "enemy_soldado_legiao_ferro"}) == "legiao"
    assert ei.family_of({"id": "enemy_mumia_de_po"}) == "morto_inquieto"
    assert ei.family_of({"id": "enemy_lobo"}) == "fera"


# --- R4/R5: execução e frustração ------------------------------------------------------
def test_on_executes_frozen_intent(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    frozen = ei.forecast_round(scene, actors, sides, random.Random(2))
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(2),
        pressagios=frozen,
    )
    assert out["pressagios_cumpridos"] == [
        {"actor_id": "lobo", "tipo": "ataque", "alvo_id": "player"}
    ]
    assert not out.get("pressagios_frustrados")


def test_frustrated_when_target_dies(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    scene, actors, sides = _world({"lobo": _enemy("lobo")}, ally_ids=("cao",))
    frozen = {
        "lobo": [
            {
                "actor_id": "lobo",
                "idx": 0,
                "tipo": "ataque",
                "alvo_id": "cao",
                "carta_id": None,
                "declaration": ct.TurnDeclaration(
                    actor_id="lobo", acao=ct.TurnStep(kind="attack", target_id="cao")
                ).model_dump(),
            }
        ]
    }
    actors["cao"]["dead"] = True
    actors["cao"]["status"] = "morto"
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(2),
        pressagios=frozen,
    )
    assert out["pressagios_frustrados"][0]["motivo"] == "impossivel"
    assert any("morreu no ar" in line or "já não é possível" in line for line in out["logs"])
    assert not out.get("pressagios_cumpridos")


def test_frustrated_when_enemy_gets_stunned(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    frozen = ei.forecast_round(scene, actors, sides, random.Random(2))
    actors["lobo"]["active_conditions"] = [{"name": "Atordoado", "control": "stun", "duration": 1}]
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(2),
        pressagios=frozen,
    )
    assert out["pressagios_frustrados"] == [
        {"actor_id": "lobo", "tipo": "ataque", "motivo": "atordoado"}
    ]


# --- R7: ações extras --------------------------------------------------------------------
def test_one_intent_per_action_for_boss():
    scene, actors, sides = _world({"chefe": _enemy("chefe", acoes_por_rodada=2)})
    frozen = ei.forecast_round(scene, actors, sides, random.Random(4))
    assert [i["idx"] for i in frozen["chefe"]] == [0, 1]


# --- R9: modos ------------------------------------------------------------------------------
def test_off_keeps_old_behavior_without_new_keys():
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(2),
    )
    assert not {"pressagios_cumpridos", "pressagios_frustrados", "intent_shadow"} & set(out)


def test_shadow_measures_without_changing_outcome(monkeypatch):
    def run(mode):
        if mode:
            monkeypatch.setenv("RPG_ENEMY_INTENT", mode)
        else:
            monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
        scene, actors, sides = _world({"lobo": _enemy("lobo")})
        out = orch.run_round(
            scene,
            actors,
            sides,
            {"player": actors["player"]},
            declarations={"player": _pass()},
            rng=random.Random(9),
        )
        return out, actors["player"]["vitalidade"]

    base_out, base_hp = run(None)
    shadow_out, shadow_hp = run("shadow")
    assert shadow_hp == base_hp and shadow_out["logs"] == base_out["logs"]
    assert shadow_out["intent_shadow"] == {"total": 1, "changed": 0}


def test_on_without_saved_pressagios_computes_at_round_start(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    scene, actors, sides = _world({"lobo": _enemy("lobo")})
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _pass()},
        rng=random.Random(2),
    )
    assert out["pressagios_cumpridos"]
