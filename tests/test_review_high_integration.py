"""Regressões de integração encontradas na revisão pós-smoke."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from agents import combat, loot
from services import conflict_orchestrator as orch
from services import conflict_summary as summary_service
from services import encounter_preparation as prep


def _player() -> dict:
    return {
        "id": "player",
        "name": "Herói",
        "level": 1,
        "gold": 0,
        "inventory": [],
        "virtudes": {
            "forca": 2,
            "agilidade": 2,
            "corpo": 2,
            "mente": 1,
            "carisma": 1,
        },
        "vitalidade": 8,
        "max_vitalidade": 8,
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "esquiva": 11,
        "active_conditions": [],
        "status": "ativo",
    }


def _conflict_summary() -> dict:
    return summary_service.build_summary([
        _player(),
        {
            "id": "brutamontes",
            "name": "Brutamontes",
            "dead": True,
            "conscious": False,
            "ferimentos": {"leve": [], "grave": [], "critico": []},
        },
    ])


class _HallucinatingLootLLM:
    is_fallback = False

    def __init__(self):
        self.human_context = ""

    def invoke(self, messages):
        self.human_context = str(messages[-1].content)
        return AIMessage(
            content="Você encontra a Espada Solar e recolhe 9999 moedas de ouro."
        )


def test_loot_enriquece_summary_antes_da_narracao_e_rejeita_extra(monkeypatch):
    llm = _HallucinatingLootLLM()
    monkeypatch.setattr(loot, "get_llm", lambda **_kwargs: llm)
    monkeypatch.setattr(
        loot,
        "get_location",
        lambda _location_id: {
            "id": "ponte",
            "name": "Ponte Velha",
            "region_id": "planicie",
        },
    )
    monkeypatch.setattr(
        loot.economy,
        "roll_loot",
        lambda *_args, **_kwargs: {
            "gold": 7,
            "item_id": None,
            "rarity": "common",
        },
    )

    out = loot.loot_node({
        "player": _player(),
        "world": {
            "current_location_id": "ponte",
            "danger_level": 1,
            "turn_count": 3,
        },
        "combat": {"encounter_level": 4},
        "conflict_summary": _conflict_summary(),
        "loot_source": "TREASURE",
        "messages": [HumanMessage(content="Vasculho os corpos.")],
        "world_projection": {},
        "bestiary_knowledge": {},
    })

    assert out["conflict_summary"]["loot_obtido"] == [
        {"kind": "gold", "amount": 7}
    ]
    # O prompt já recebeu o resultado aplicado, não o summary pré-loot.
    assert "Espólio: 7 ouro." in llm.human_context
    rendered = out["messages"][0].content
    assert "Espada Solar" not in rendered
    assert "9999" not in rendered
    assert "Espólio: 7 ouro." in rendered
    assert "[SISTEMA] +7 de ouro" in rendered


def test_combat_sem_inimigo_ativo_produz_summary_antes_do_loot():
    dead_enemy = {
        "id": "brutamontes_1",
        "name": "Brutamontes",
        "dead": True,
        "conscious": False,
        "status": "morto",
        "virtudes": {
            "forca": 3,
            "agilidade": 1,
            "corpo": 3,
            "mente": 1,
            "carisma": 1,
        },
        "vitalidade": 0,
        "max_vitalidade": 10,
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "esquiva": 10,
        "active_conditions": [],
    }
    scene = {
        "encounter_level": 4,
        "zones": [{"id": "z0", "name": "Ponte", "connections": []}],
        "positions": {},
        "objects": [],
        "enemies": [dead_enemy],
        "npcs": [],
    }

    out = combat.combat_node({
        "messages": [HumanMessage(content="O combate já terminou.")],
        "player": _player(),
        "enemies": [dead_enemy],
        "combat": {
            "active": True,
            "round": 3,
            "scene": scene,
            "encounter_level": 4,
        },
        "world": {
            "turn_count": 5,
            "current_location": "Ponte",
            "current_location_id": "ponte",
        },
        "party": [],
        "npcs": {},
    })

    assert out["next"] == "loot"
    assert out["combat"]["active"] is False
    assert out["conflict_summary"]["mortos"] == ["Brutamontes"]
    assert "Brutamontes" in out["conflict_summary"]["participantes"]


class _AdversarialScannerLLM:
    def __init__(self, result):
        self.result = result

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return self.result


def test_scanner_clampa_antes_da_factory_e_ids_sao_unicos(monkeypatch):
    huge = 1_000_000
    # model_construct simula uma fronteira/provider defeituoso que furou o schema.
    scan = combat.EncounterScanner.model_construct(
        detected_enemies=[
            combat.EnemyIdentification.model_construct(name="Goblin", count=huge),
            combat.EnemyIdentification.model_construct(name="  goblin  ", count=huge),
            combat.EnemyIdentification.model_construct(name="Orc", count=huge),
            combat.EnemyIdentification.model_construct(name="Troll", count=huge),
        ],
        flavor_text="Uma horda avança.",
    )
    factory_calls: list[str] = []

    def factory(name, **_kwargs):
        factory_calls.append(name)
        # Dois conceitos diferentes podem inclusive resolver para o mesmo template.
        return {
            "id": "enemy_shared",
            "name": name.strip(),
            "virtudes": {
                "forca": 2,
                "agilidade": 2,
                "corpo": 2,
                "mente": 1,
                "carisma": 1,
            },
        }

    monkeypatch.setattr(
        combat,
        "get_llm",
        lambda **_kwargs: _AdversarialScannerLLM(scan),
    )
    monkeypatch.setattr(combat, "generate_new_enemy", factory)

    enemies, _flavor = combat._spawn_v4_enemies([], "horda", None)

    # Duplicata case/whitespace conta como um tipo; o teto total é decidido antes
    # de chamar a factory. Troll nunca chega a ser materializado.
    assert factory_calls == ["Goblin", "Orc"]
    assert len(enemies) == 24
    ids = [enemy["id"] for enemy in enemies]
    assert len(ids) == len(set(ids))


def test_orchestrator_rematerializa_amount_antes_de_aplicar(monkeypatch):
    seen = {}

    def fake_damage(target, *, damage_base, damage_type, directed_region, rng):
        seen.update(
            target=target["id"],
            damage_base=damage_base,
            damage_type=damage_type,
            directed_region=directed_region,
        )
        return {"log": []}

    monkeypatch.setattr(orch, "resolve_damage_and_wounds", fake_damage)
    player = _player()
    scene = {"encounter_level": 3}
    out = {"logs": [], "terminal": [], "deaths": []}

    orch.apply_effect_spec(
        scene,
        {"player": player},
        {
            "kind": "damage",
            "potency": "forte",
            "params": {"target": "player", "amount": 9999},
        },
        out,
    )

    assert seen["damage_base"] == prep.potency_value("forte", 3, "dano")
    assert seen["damage_base"] != 9999
