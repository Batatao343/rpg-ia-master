"""Regressões do smoke real: a LLM escolhe categorias, nunca números mecânicos."""

import pytest
from pydantic import ValidationError

import gamedata
import party as party_mod
from agents.bestiary import EnemySchema, materialize_enemy_concept
from services import encounter_preparation as prep


def _canonical_v4_npc(extreme: int = 9999) -> dict:
    return {
        "id": "npc_iria",
        "name": "Iria",
        "role": "Guardiã veterana",
        "persona": "Protege os seus.",
        "relationship": 9,
        "in_scene": True,
        # Campos legados conflitantes não são autoridade.
        "attributes": {
            "str": extreme,
            "dex": extreme,
            "con": extreme,
        },
        "combat_stats": {
            "hp": extreme,
            "ac": extreme,
            "attacks": [{
                "name": "Golpe adulterado",
                "bonus": extreme,
                "damage": f"{extreme}d{extreme}",
            }],
        },
        # Ficha v4 canônica e já danificada.
        "virtudes": {
            "forca": 2,
            "agilidade": 3,
            "corpo": 2,
            "mente": 1,
            "carisma": 2,
        },
        "vitalidade": 4,
        "max_vitalidade": 10,
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {
            "leve": [{"regiao": "braco", "categoria": "leve"}],
            "grave": [{"regiao": "torso", "categoria": "grave"}],
            "critico": [],
        },
        "esquiva": 13,
        "categoria": "companheiro",
        "active_conditions": [{"name": "sangrando", "duration": 2}],
        "conscious": True,
        "status": "ativo",
        "tactical_archetype": "guardiao",
        "tactical_profile": {
            "priorities": [{
                "trigger": "aliado_em_perigo",
                "tipo": "obrigatorio",
                "action_key": "protect",
                "action_hint": "Protege o aliado em perigo.",
                "resistance": "flexivel",
                "blocks": [],
            }],
        },
        "known_cards": ["interpor_escudo"],
    }


@pytest.mark.parametrize("extreme", [9999, -9999])
def test_companion_copia_ficha_v4_e_ignora_extremos_legados(extreme):
    npc = _canonical_v4_npc(extreme)

    companion = party_mod.make_companion_from_npc(npc, npc["name"])

    for field in (
        "virtudes",
        "vitalidade",
        "max_vitalidade",
        "ferimento_espacos",
        "ferimentos",
        "esquiva",
        "tactical_profile",
    ):
        assert companion[field] == npc[field]
    assert companion["hp"] == 4
    assert companion["max_hp"] == 10
    assert companion["defense"] == npc["esquiva"]
    assert companion["attributes"] != npc["attributes"]
    assert companion["attacks"] != npc["combat_stats"]["attacks"]

    # A ficha do aliado é cópia viva independente; materializá-lo não cura,
    # apaga Ferimentos nem compartilha estruturas com o NPC persistido.
    companion["ferimentos"]["leve"].append({"regiao": "perna"})
    companion["tactical_profile"]["priorities"][0]["action_key"] = "flee"
    assert len(npc["ferimentos"]["leve"]) == 1
    assert (
        npc["tactical_profile"]["priorities"][0]["action_key"]
        == "protect"
    )


def test_recrutamento_e_aliado_transitorio_preservam_ficha_v4_danificada():
    npc = _canonical_v4_npc()
    state = {
        "npcs": {"Iria": npc},
        "party": [],
        "factions": [],
    }

    recruited, reason = party_mod.recruit(state, "Iria")
    transient = party_mod.scene_allies(state)

    assert reason == ""
    assert recruited is not None
    assert len(transient) == 1
    for companion in (recruited[0], transient[0]):
        assert companion["virtudes"] == npc["virtudes"]
        assert companion["vitalidade"] == 4
        assert companion["max_vitalidade"] == 10
        assert companion["ferimentos"] == npc["ferimentos"]
        assert companion["esquiva"] == 13
        assert companion["tactical_profile"] == npc["tactical_profile"]
    assert transient[0]["transient"] is True


def test_companion_legado_ignora_numeros_livres_e_materializa_ficha_segura():
    def materialize(extreme):
        return party_mod.make_companion_from_npc({
            "id": f"npc_legacy_{extreme}",
            "role": "Curandeira de campanha",
            "persona": "Cuida dos feridos.",
            "attributes": {
                "str": extreme,
                "dex": extreme,
                "con": extreme,
            },
            "combat_stats": {
                "hp": extreme,
                "ac": extreme,
                "attacks": [{"bonus": extreme, "damage": "9999d9999"}],
            },
        }, "Mara")

    positive = materialize(9999)
    negative = materialize(-9999)

    for field in (
        "virtudes",
        "vitalidade",
        "max_vitalidade",
        "ferimento_espacos",
        "esquiva",
        "tactical_profile",
    ):
        assert positive[field] == negative[field]
    assert positive["virtudes"] == {
        "forca": 1,
        "agilidade": 1,
        "corpo": 1,
        "mente": 1,
        "carisma": 1,
    }
    assert positive["max_vitalidade"] == gamedata.vitalidade_para_corpo(1)
    assert positive["vitalidade"] == positive["max_vitalidade"]
    assert positive["defense"] == positive["esquiva"]
    assert positive["tactical_profile"]["priorities"]
    assert positive["attributes"] != {
        "str": 9999,
        "dex": 9999,
        "con": 9999,
    }
    assert all(
        attack.get("damage") != "9999d9999"
        for attack in positive["attacks"]
    )


def test_companion_legado_incompleto_preserva_dano_e_ferimentos_existentes():
    wounds = {
        "leve": [{"regiao": "ombro", "categoria": "leve"}],
        "grave": [],
        "critico": [],
    }
    companion = party_mod.make_companion_from_npc({
        "id": "npc_legacy_hurt",
        "role": "Guarda",
        "vitalidade": 3,
        "ferimentos": wounds,
        "attributes": {"con": 9999, "dex": 9999},
        "combat_stats": {"hp": 9999, "ac": 9999},
    }, "Bors")

    assert companion["vitalidade"] == 3
    assert companion["hp"] == 3
    assert companion["max_vitalidade"] == gamedata.vitalidade_para_corpo(1)
    assert companion["ferimentos"] == wounds
    assert companion["ferimentos"] is not wounds


def test_enemy_schema_rejeita_hp_ac_atributos_e_dano_livres():
    with pytest.raises(ValidationError):
        EnemySchema.model_validate({
            "name": "Colosso",
            "description": "ameaça",
            "categoria": "elite",
            "arquetipo": "bruto",
            "estilo_ataque": "corpo_a_corpo",
            "nome_ataque": "Punho",
            "hp": 9999,
            "ac": 9999,
            "attributes": {"str": 9999},
            "damage": "9999d9999",
        })


def test_factory_ignora_numeros_livres_e_materializa_por_categoria():
    base = {
        "name": "Colosso",
        "description": "ameaça",
        "categoria": "elite",
        "arquetipo": "bruto",
        "estilo_ataque": "corpo_a_corpo",
        "hp": 9999,
        "max_hp": 9999,
        "ac": 9999,
        "attributes": {"str": 9999},
        "attacks": [{"damage": "9999d9999"}],
    }
    a = materialize_enemy_concept(base, encounter_level=3)
    b = materialize_enemy_concept({**base, "hp": -50, "ac": -50}, encounter_level=3)
    assert a["virtudes"] == b["virtudes"]
    assert a["vitalidade"] == b["vitalidade"] == a["max_vitalidade"]
    assert a["hp"] != 9999 and a["ac"] != 9999
    assert a["tactical_profile"]["priorities"]
    assert "damage" not in a["attacks"][0]


def test_effect_numbers_are_recomputed_from_potency_table():
    effect = {
        "kind": "damage",
        "potency": "forte",
        "params": {"target": "player", "amount": 9999, "duration": 9999},
    }
    result = prep.materialize_effect(effect, 3, valid_targets={"player"})
    assert result is not None
    assert result["params"]["amount"] == prep.potency_value("forte", 3, "dano")
    assert result["params"]["amount"] != 9999
    assert "duration" not in result["params"]


def test_effect_target_outside_scene_is_rejected():
    effect = {
        "kind": "apply_condition",
        "potency": "moderado",
        "params": {"target": "npc_fantasma", "condition": "exposto", "duration": 9999},
    }
    assert prep.materialize_effect(effect, 2, valid_targets={"player", "enemy_1"}) is None


def test_validate_rejects_numeric_effect_that_skipped_materialization():
    scene = {
        "encounter_level": 2,
        "objects": [{
            "id": "braseiro",
            "base_narrativa": "braseiro citado",
            "interactions": [{
                "label": "derrubar",
                "effect": {"kind": "damage",
                           "params": {"target": "player", "amount": 9999}},
            }],
        }],
        "abyss_events": [],
    }
    result = prep.validate_preparation(scene)
    assert result["ok"] is False
    assert any("não materializado" in error for error in result["errors"])


class _PreparedLLM:
    def __init__(self, scene: prep.PreparedScene):
        self.scene = scene

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return self.scene


def test_prepare_encounter_neutralizes_numeric_input_from_llm():
    proposed = prep.PreparedScene(
        zones=[{"id": "z0", "name": "Ponte", "connections": []}],
        objects=[{
            "id": "braseiro",
            "base_narrativa": "braseiro citado na ponte",
            "interactions": [{
                "label": "derrubar",
                "effect": {
                    "kind": "damage",
                    "potency": "fraco",
                    "params": {"target": "player", "amount": 9999},
                },
            }],
        }],
    )
    scene = prep.prepare_encounter(
        {"location": "Ponte", "encounter_level": 4, "enemies": [], "npcs": []},
        _PreparedLLM(proposed),
    )
    effect = scene["objects"][0]["interactions"][0]["effect"]
    assert effect["params"]["amount"] == prep.potency_value("fraco", 4, "dano")
    assert effect["_mechanical_origin"] == "potency_by_level"


def test_prepare_encounter_invalid_target_falls_back_safely():
    proposed = prep.PreparedScene(
        zones=[{"id": "z0", "name": "Ponte", "connections": []}],
        objects=[{
            "id": "braseiro",
            "base_narrativa": "braseiro citado na ponte",
            "interactions": [{
                "label": "derrubar",
                "effect": {
                    "kind": "damage",
                    "potency": "forte",
                    "params": {"target": "npc_inventado", "amount": 9999},
                },
            }],
        }],
    )
    scene = prep.prepare_encounter(
        {"location": "Ponte", "encounter_level": 2, "enemies": [], "npcs": []},
        _PreparedLLM(proposed),
    )
    assert scene["safe_fallback"] is True
    assert scene["objects"] == []
