"""SPEC-325 Fase C / R14 - objetos de cena (via `combat_node` real, MockLLM)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

import api
from agents import combat as cbt
from services import conflict_scene as cs
from services import encounter_preparation as prep
from tests.spec325_chase_helpers import first_state, narration_spy, step
from tests.spec325_helpers import run_node

SECRET_COND = "Maldição Rubra"


def _effect(kind="damage", target="e1", **params):
    raw = {"kind": kind, "potency": "fraco", "params": {"target": target, **params}}
    return prep.materialize_effect(raw, 1, valid_targets={"player", "e1"})


def _pilar(target="e1", **over):
    return {
        "id": "pilar",
        "name": "Pilar Rachado",
        "base_narrativa": "no centro da sala",
        "uses_remaining": 1,
        "interactions": [{"label": "derrubar", "cost": "acao", "effect": _effect(target=target)}],
        **over,
    }


def _hidden_obj():
    return {
        "id": "alcapao",
        "name": "Alçapão Velho",
        "base_narrativa": "sob o tapete",
        "secret": True,
        "uses_remaining": 1,
        "interactions": [
            {
                "label": "abrir",
                "cost": "acao",
                "effect": _effect("apply_condition", condition=SECRET_COND),
            }
        ],
    }


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_OBJECTS", "on")


def _scene_round(monkeypatch, objects=None):
    """Rodada 1 (cria a cena) + objetos injetados na cena já congelada."""
    state = first_state()
    out = run_node(state, monkeypatch)
    out["combat"]["scene"]["objects"] = list(objects if objects is not None else [_pilar()])
    return state, out


def _enemy(out):
    return out["enemies"][0]


def _api_payload(merged, out):
    state = {**merged, **{k: v for k, v in out.items() if k != "next"}}
    state["world"] = {**state["world"], "current_location": "Montanhas Afiadas"}
    state["messages"] = [*state["messages"], AIMessage(content="Fim.")]
    return api.format_response(state).model_dump()


def test_api_objects_hide_effect_and_secret(monkeypatch):
    state, out = _scene_round(monkeypatch, [_pilar(), _hidden_obj()])
    scene = _api_payload(state, out)["combat"]["scene"]
    assert [o["id"] for o in scene["objects"]] == ["pilar"]
    obj = scene["objects"][0]
    assert obj["interactions"] == [{"label": "derrubar", "cost": "acao"}]
    dumped = json.dumps(scene, default=str)
    assert "effect" not in dumped and SECRET_COND not in dumped and "alcapao" not in dumped
    cs.discover_object(out["combat"]["scene"], "alcapao")
    after = _api_payload(state, out)["combat"]["scene"]
    assert {o["id"] for o in after["objects"]} == {"pilar", "alcapao"}
    assert SECRET_COND not in json.dumps(after, default=str)  # efeito segue oculto


def test_api_objects_only_with_flag_on(monkeypatch):
    state, out = _scene_round(monkeypatch)
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_COMBAT_OBJECTS", mode)
        assert "objects" not in _api_payload(state, out)["combat"]["scene"]


def test_fallback_scene_has_no_objects_no_chip(monkeypatch):
    state = first_state()
    out = run_node(state, monkeypatch)
    assert out["combat"]["scene"]["objects"] == []
    assert _api_payload(state, out)["combat"]["scene"]["objects"] == []


def test_chip_name_resolves_object_step_without_llm(monkeypatch):
    state, out = _scene_round(monkeypatch)

    def boom(*a, **k):
        raise AssertionError("o chip de objeto nao pode gastar CLASSIFY")

    monkeypatch.setattr(cbt, "get_llm", boom)
    before = _enemy(out)["vitalidade"]
    merged, out2 = step(state, out, monkeypatch, "Derrubar Pilar Rachado.")
    assert out2["combat"]["last_player_action"]["kind"] == "object"
    assert _enemy(out2)["vitalidade"] < before  # o efeito do objeto foi aplicado


def test_free_text_conjugated_verb_resolves(monkeypatch):
    state, out = _scene_round(monkeypatch)
    _m, out2 = step(state, out, monkeypatch, "derrubo o pilar rachado em cima deles")
    assert out2["combat"]["last_player_action"]["kind"] == "object"


def test_object_use_consumes_single_use(monkeypatch):
    state, out = _scene_round(monkeypatch)
    merged, out2 = step(state, out, monkeypatch, "Derrubar Pilar Rachado.")
    obj = out2["combat"]["scene"]["objects"][0]
    assert obj["uses_remaining"] == 0 and obj["destroyed"] is True
    # sem usos: o chip nao resolve mais para objeto (cai no fluxo normal)
    _m, out3 = step(merged, out2, monkeypatch, "Derrubar Pilar Rachado.")
    assert out3["combat"]["last_player_action"]["kind"] != "object"


class _FakeLLM:
    def __init__(self, move):
        self.move = move

    def with_structured_output(self, model):
        outer = self

        class _Bound:
            def invoke(self, _msgs):
                return model(**outer.move)

        return _Bound()


def _classify(monkeypatch, move):
    monkeypatch.setattr(cbt, "get_llm", lambda *a, **k: _FakeLLM(move))


def test_classify_object_invalid_falls_back_to_attack(monkeypatch):
    state, out = _scene_round(monkeypatch)
    _classify(monkeypatch, {"kind": "object", "object_id": "fantasma", "interaction": "x"})
    _m, out2 = step(state, out, monkeypatch, "faço algo estranho com a sala")
    assert out2["combat"]["last_player_action"]["kind"] == "attack"
    assert out2["combat"]["scene"]["objects"][0]["uses_remaining"] == 1  # nada consumido


def test_classify_object_valid_is_used(monkeypatch):
    state, out = _scene_round(monkeypatch)
    _classify(monkeypatch, {"kind": "object", "object_id": "pilar", "interaction": "derrubar"})
    _m, out2 = step(state, out, monkeypatch, "faço algo estranho com a sala")
    assert out2["combat"]["last_player_action"]["kind"] == "object"
    assert out2["combat"]["scene"]["objects"][0]["uses_remaining"] == 0


def test_classify_prompt_lists_visible_objects_without_effect(monkeypatch):
    state, out = _scene_round(monkeypatch, [_pilar(), _hidden_obj()])
    seen: list[str] = []

    class _Spy(_FakeLLM):
        def with_structured_output(self, model):
            class _Bound:
                def invoke(_self, msgs):
                    seen.append(" ".join(str(m.content) for m in msgs))
                    return model(kind="attack")

            return _Bound()

    monkeypatch.setattr(cbt, "get_llm", lambda *a, **k: _Spy({}))
    step(state, out, monkeypatch, "faço algo estranho com a sala")
    prompt = seen[-1]
    assert "pilar" in prompt and "derrubar" in prompt
    assert "alcapao" not in prompt and SECRET_COND not in prompt and "damage" not in prompt


def test_offensive_object_self_side_refused(monkeypatch):
    state, out = _scene_round(monkeypatch, [_pilar(target="player")])
    round_before = out["combat"]["round"]
    vit_before = out["player"]["vitalidade"]
    logs_seen: list[list[str]] = []

    def narrate(player, enemies, logs, *a, **k):
        logs_seen.append(list(logs))
        return "Fim."

    _m, out2 = step(state, out, monkeypatch, "Derrubar Pilar Rachado.", narrate=narrate)
    assert out2["combat"]["round"] == round_before  # nao gastou a rodada
    assert out2["player"]["vitalidade"] == vit_before
    obj = out2["combat"]["scene"]["objects"][0]
    assert obj["uses_remaining"] == 1 and not obj.get("destroyed")
    text = " ".join(logs_seen[-1])
    assert "assim agora" in text and "dano" not in text.lower() and "damage" not in text


def test_unused_effect_never_reaches_narrator_or_api(monkeypatch):
    """Oraculo do R5: o efeito do objeto so aparece DEPOIS do uso."""
    state, out = _scene_round(monkeypatch, [_pilar(), _hidden_obj()])
    narrate, seen = narration_spy()
    merged, out2 = step(state, out, monkeypatch, "ataco o inimigo", narrate=narrate)
    blob = seen[-1] + json.dumps(_api_payload(merged, out2)["combat"], default=str)
    assert SECRET_COND not in blob and "potency" not in blob and "_mechanical_origin" not in blob


def test_procurar_discovers_secret(monkeypatch):
    decl = {
        "actor_id": "player",
        "acao": {"kind": "maneuver", "maneuver": "procurar", "target_id": "e1"},
    }
    state, out = _scene_round(monkeypatch, [_pilar(), _hidden_obj()])
    _m, out2 = step(state, out, monkeypatch, "procuro", declaration=decl)
    objs = {o["id"]: o for o in out2["combat"]["scene"]["objects"]}
    assert objs["alcapao"]["discovered"] is True
    visible = [o["id"] for o in cs.visible_objects(out2["combat"]["scene"])]
    assert "alcapao" in visible


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_procurar_does_not_discover_unless_on(monkeypatch, mode):
    monkeypatch.setenv("RPG_COMBAT_OBJECTS", mode)
    decl = {
        "actor_id": "player",
        "acao": {"kind": "maneuver", "maneuver": "procurar", "target_id": "e1"},
    }
    state, out = _scene_round(monkeypatch, [_pilar(), _hidden_obj()])
    _m, out2 = step(state, out, monkeypatch, "procuro", declaration=decl)
    objs = {o["id"]: o for o in out2["combat"]["scene"]["objects"]}
    assert not objs["alcapao"].get("discovered")


def test_procurar_skips_when_participant_hidden(monkeypatch):
    decl = {
        "actor_id": "player",
        "acao": {"kind": "maneuver", "maneuver": "procurar", "target_id": "e1"},
    }
    state, out = _scene_round(monkeypatch, [_hidden_obj()])
    out["combat"]["scene"]["positions"]["e1"]["hidden_from"] = ["player"]
    _m, out2 = step(state, out, monkeypatch, "procuro", declaration=decl)
    assert not out2["combat"]["scene"]["objects"][0].get("discovered")


def _norm(out):
    res = {k: v for k, v in out.items() if k != "messages"}
    res["narr"] = [m.content for m in out.get("messages", [])]
    return json.dumps(res, default=str, sort_keys=True)


def test_shadow_no_state_change(monkeypatch):
    """`shadow` = `off` com a mesma seed, mesmo com o chip de objeto no texto."""
    results = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_COMBAT_OBJECTS", mode)
        state, out = _scene_round(monkeypatch)
        _m, out2 = step(state, out, monkeypatch, "Derrubar Pilar Rachado.")
        results[mode] = _norm(out2)
    assert results["off"] == results["shadow"]


def test_off_harness_object_decl_untouched(monkeypatch):
    """Com a flag `off`, uma declaração estruturada `object` segue o caminho anterior."""
    monkeypatch.setenv("RPG_COMBAT_OBJECTS", "off")
    decl = {
        "actor_id": "player",
        "acao": {"kind": "object", "object_id": "pilar", "interaction": "derrubar"},
    }
    state, out = _scene_round(monkeypatch)
    _m, out2 = step(state, out, monkeypatch, "x", declaration=decl)
    assert out2["combat"]["scene"]["objects"][0]["uses_remaining"] == 0
