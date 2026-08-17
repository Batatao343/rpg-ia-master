"""Regressões dos blockers de revisão em NPCs e preparação de encontros."""

import random
from types import SimpleNamespace

import gamedata
from langchain_core.messages import HumanMessage
from agents import npc as npc_mod
from agents import storyteller
from services import conflict_scene as cs
from services import encounter_preparation as prep
from services import conflict_turn as ct
from services import tactical_profile as tactical


def test_with_new_npc_preserves_complete_v4_sheet_and_tactical_profile(monkeypatch):
    generated = {
        "id": "npc_iria",
        "name": "Iria",
        "role": "Batedora",
        "persona": "Atenta e direta.",
        "initial_relationship": 7,
        "attributes": {"dex": 14},
        "combat_stats": {"hp": 8, "ac": 13, "attacks": []},
        "virtudes": {
            "forca": 1, "agilidade": 3, "corpo": 2, "mente": 2, "carisma": 1,
        },
        "vitalidade": 8,
        "max_vitalidade": 8,
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "esquiva": 13,
        "categoria": "padrao",
        "active_conditions": ["alerta"],
        "status": "ativo",
        "tactical_profile": {
            "priorities": [
                {"action": "protect", "when": {"ally_in_danger": True}, "weight": 9},
            ],
        },
        "known_cards": ["passo_veloz"],
    }
    monkeypatch.setattr(storyteller, "generate_new_npc", lambda *_args, **_kwargs: generated)

    result = storyteller._with_new_npc(
        {}, "Iria", "Ponte Velha", "Iria surge entre as ruínas.",
        game_id="game-1", home_id="ponte_velha", turn=4,
    )["Iria"]

    for field in (
        "id", "virtudes", "vitalidade", "max_vitalidade", "ferimento_espacos",
        "ferimentos", "esquiva", "categoria", "active_conditions", "status",
        "tactical_profile", "known_cards",
    ):
        assert result[field] == generated[field]
    assert result["location"] == "Ponte Velha"
    assert result["relationship"] == 7
    assert result["in_scene"] is True


def test_normalize_prepared_object_without_uses_gets_one_finite_use():
    source = {
        "objects": [{
            "id": "alavanca",
            "name": "Alavanca",
            "base_narrativa": "Uma alavanca enferrujada está na parede.",
            "interactions": [{
                "label": "puxar",
                "effect": {"kind": "block_route", "params": {}},
            }],
        }],
    }

    scene = prep.normalize_prepared_scene(source, encounter_level=2)

    assert "uses_remaining" not in source["objects"][0]
    assert scene["objects"][0]["uses_remaining"] == 1
    first = cs.apply_object_interaction(scene, "alavanca", "puxar", "player")
    second = cs.apply_object_interaction(scene, "alavanca", "puxar", "player")
    assert first["ok"] is True
    assert second["ok"] is False


def test_position_id_is_not_a_canonical_effect_target():
    scene = {
        "positions": {
            "player": {"zone_id": "z0"},
            "npc_inventado": {"zone_id": "z0"},
            "enemy_1": {"zone_id": "z0"},
        },
        "enemies": [{"id": "enemy_1", "name": "Salteador"}],
        "npcs": [],
        "objects": [{
            "id": "braseiro",
            "base_narrativa": "Um braseiro arde junto à passagem.",
            "interactions": [{
                "label": "derrubar",
                "effect": {
                    "kind": "damage",
                    "potency": "moderado",
                    "params": {"target": "npc_inventado"},
                },
            }],
        }],
    }

    rejected = prep.normalize_prepared_scene(scene, encounter_level=2)
    assert prep.validate_preparation(rejected)["ok"] is False
    assert rejected["_normalization_errors"]

    scene["objects"][0]["interactions"][0]["effect"]["params"]["target"] = "enemy_1"
    accepted = prep.normalize_prepared_scene(scene, encounter_level=2)
    assert prep.validate_preparation(accepted)["ok"] is True
    assert accepted["objects"][0]["interactions"][0]["effect"]["params"]["target"] == "enemy_1"


def test_prepared_object_damage_is_applied_to_target_vitality():
    target = {
        "id": "enemy_1",
        "name": "Salteador",
        "categoria": "padrao",
        "virtudes": {
            "forca": 2, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1,
        },
        "vitalidade": gamedata.vitalidade_para_corpo(3),
        "max_vitalidade": gamedata.vitalidade_para_corpo(3),
        "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(3),
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "active_conditions": [],
    }
    player = {
        "id": "player",
        "name": "Heroína",
        "virtudes": {
            "forca": 2, "agilidade": 2, "corpo": 2, "mente": 2, "carisma": 2,
        },
    }
    raw_scene = {
        "positions": {
            "player": {"zone_id": "z0"},
            "enemy_1": {"zone_id": "z0"},
        },
        "enemies": [target],
        "objects": [{
            "id": "braseiro",
            "name": "Braseiro",
            "base_narrativa": "Um braseiro pesado domina a passagem.",
            "interactions": [{
                "label": "derrubar",
                "effect": {
                    "kind": "damage",
                    "potency": "moderado",
                    "params": {"target": "enemy_1"},
                },
            }],
        }],
    }
    scene = prep.normalize_prepared_scene(raw_scene, encounter_level=2)
    # Mesmo uma adulteração posterior não atravessa como número livre: o
    # executor do orquestrador materializa novamente pela categoria.
    scene["objects"][0]["interactions"][0]["effect"]["params"]["amount"] = 9999
    before = target["vitalidade"]
    expected_damage = prep.potency_value("moderado", 2, "dano")

    result = ct.resolve_turn(
        scene,
        {"player": player, "enemy_1": target},
        {
            "actor_id": "player",
            "acao": {
                "kind": "object",
                "object_id": "braseiro",
                "interaction": "derrubar",
            },
        },
        rng=random.Random(4),
    )

    assert result["ok"] is True
    assert target["vitalidade"] == before - expected_damage
    assert scene["objects"][0]["destroyed"] is True


def test_npc_tactical_archetype_explicit_wins_and_materializes_specific_profile():
    sheet = prep.build_npc_combat_sheet({
        "name": "Serena",
        "role": "Oráculo",
        "persona": "Decifra presságios.",
        "tactical_archetype": "guardiao",
    })

    assert sheet["tactical_archetype"] == "guardiao"
    assert "protege" in sheet["tactical_profile"]["priorities"][0]["action_hint"].lower()
    assert sheet["tactical_profile"] != tactical._default_profile()


def test_npc_tactical_archetype_derives_from_role_and_has_closed_fallback():
    support = prep.build_npc_combat_sheet({
        "name": "Mara",
        "role": "Curandeira de campanha",
        "persona": "Cuida primeiro dos feridos.",
    })
    fallback = prep.build_npc_combat_sheet({
        "name": "Nulo",
        "role": "Guardião",
        "persona": "Sem descrição.",
        "tactical_archetype": "deus_onisciente",
    })

    assert support["tactical_archetype"] == "suporte"
    assert support["tactical_profile"] == tactical.npc_profile_for_archetype("suporte")
    assert fallback["tactical_archetype"] == tactical.NPC_TACTICAL_FALLBACK
    assert fallback["tactical_profile"] == tactical.npc_profile_for_archetype(
        tactical.NPC_TACTICAL_FALLBACK)


class _DialogueLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return npc_mod.NPCResponse(
            dialogue="Ouvi boatos, mas não posso confirmá-los.",
            action_description="baixa a voz",
            memory_update="Um rumor livre que não deve virar fato global.",
        )


def _dialogue_state():
    return {
        "game_id": "memory-policy",
        "active_npc_name": "Grum",
        "npcs": {
            "Grum": {
                "id": "npc_grum",
                "name": "Grum",
                "role": "Guarda",
                "persona": "Desconfiado",
                "location": "Nova Arcádia",
                "relationship": 5,
                "memory": [],
                "in_scene": True,
            },
        },
        "messages": [HumanMessage(content="Que rumores correm pela cidade?")],
        "world": {
            "turn_count": 3,
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
        },
        "party": [],
        "factions": [],
        "faction_intel": {},
        "quests": [],
    }


def test_npc_dialogue_marks_memory_as_canonical_only(monkeypatch):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc_mod, "add_npc_memory", lambda *_args, **_kwargs: True)
    state = _dialogue_state()

    result = npc_mod.npc_actor_node(state)

    assert result["memory_fact_policy"] == "canonical_only"
    assert result["pending_npc_memory"] == []
    assert result["rag_persistence_error"] is None
    assert len(result["memory_facts"]) == 1
    assert result["memory_facts"][0]["provenance"] == "npc_claim"
    assert result["memory_facts"][0]["confidence"] == "reported"
    assert result["memory_facts"][0]["source_id"] == "npc:npc_grum"


def test_npc_dialogue_success_is_idempotent_in_global_ledger(monkeypatch):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    writes = []
    monkeypatch.setattr(
        npc_mod,
        "add_npc_memory",
        lambda *_args, **_kwargs: writes.append(1) or True,
    )
    state = _dialogue_state()

    first = npc_mod.npc_actor_node(state)
    state.update(first)
    # Reproduz a mesma fala observável no mesmo turno: o vetor pode receber a
    # chamada normal, mas o ledger global continua com um único registro.
    state["messages"] = [HumanMessage(content="Que rumores correm pela cidade?")]
    second = npc_mod.npc_actor_node(state)

    assert len(writes) == 2
    assert len(second["memory_facts"]) == 1


def test_npc_dialogue_promotes_same_text_from_inference_to_reported(monkeypatch):
    from services.memory_provenance import make_memory_fact

    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc_mod, "add_npc_memory", lambda *_args, **_kwargs: True)
    baseline = npc_mod.npc_actor_node(_dialogue_state())
    state = _dialogue_state()
    state["memory_facts"] = [make_memory_fact(
        baseline["memory_facts"][0]["text"],
        provenance="inference",
        source_id="archivist:summary",
        source_turn=3,
    )]

    result = npc_mod.npc_actor_node(state)

    assert result["memory_facts"][0]["confidence"] == "reported"
    assert result["memory_promotions"][-1] == {
        "turn": 3, "count": 1, "reason": "npc_claim_direct_write",
    }


def test_npc_dialogue_failure_enqueues_operation_scoped_retry(monkeypatch):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc_mod, "add_npc_memory", lambda *_args, **_kwargs: False)

    result = npc_mod.npc_actor_node(_dialogue_state())

    assert result["rag_persistence_error"]
    assert result["archive_due"] is True
    assert result["memory_fact_policy"] == "canonical_only"
    assert len(result["pending_npc_memory"]) == 1
    pending = result["pending_npc_memory"][0]
    assert pending["operation"] == "add_npc_memory"
    assert pending["npc_id"] == "npc_grum"
    assert "Turno 3" in pending["facts"][0]
    assert "memory_update" not in pending["facts"][0]


def test_npc_dialogue_success_does_not_erase_old_retry(monkeypatch):
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _DialogueLLM())
    monkeypatch.setattr(
        npc_mod,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc_mod, "add_npc_memory", lambda *_args, **_kwargs: True)
    state = _dialogue_state()
    state["pending_npc_memory"] = [{
        "operation": "add_npc_memory",
        "npc_id": "npc_antigo",
        "facts": ["Uma memória antiga ainda aguarda retry."],
    }]
    state["rag_persistence_error"] = "falha antiga"

    result = npc_mod.npc_actor_node(state)

    assert result["pending_npc_memory"] == state["pending_npc_memory"]
    assert result["rag_persistence_error"] == "falha antiga"
