"""Contratos do laboratório de combate isolado.

Spec: specs/modo-simulacao-combate.md.
"""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

import agents.campaign_manager as campaign_manager
import agents.combat as combat_agent
import api
import character_creator
import persistence


def _request(**overrides) -> api.CombatSimulatorRequest:
    payload = {
        "class_name": "Sangromante",
        "level": 3,
        "enemy_id": "mon_cao_rebite",
        "quantity": 2,
    }
    payload.update(overrides)
    return api.CombatSimulatorRequest(**payload)


def test_opcoes_do_simulador_so_expoem_dados_canonicos():
    options = api.combat_simulator_options()

    assert set(options["classes"]) == set(api.gamedata.CLASSES)
    assert options["levels"] == [1, 3, 5, 10]
    assert options["quantities"] == [1, 2, 3]
    assert len(options["enemies"]) >= 100
    assert all(
        enemy["id"] in api.gamedata.BESTIARY
        and enemy["name"]
        and enemy["category"] in {"lacaio", "padrao", "elite", "chefe", "nomeado"}
        for enemy in options["enemies"]
    )
    assert all("cartas" not in enemy for enemy in options["enemies"])


def test_request_rejeita_nivel_quantidade_e_inimigo_invalidos():
    client = TestClient(api.app)

    assert client.post("/game/combat-simulator", json={
        "class_name": "Sangromante", "level": 2,
        "enemy_id": "mon_cao_rebite", "quantity": 1,
    }).status_code == 422
    assert client.post("/game/combat-simulator", json={
        "class_name": "Sangromante", "level": 3,
        "enemy_id": "nao_existe", "quantity": 1,
    }).status_code == 422
    assert client.post("/game/combat-simulator", json={
        "class_name": "Sangromante", "level": 3,
        "enemy_id": "mon_cao_rebite", "quantity": 4,
    }).status_code == 422


def test_builder_cria_ficha_inimigos_unicos_e_cena_congelada_sem_llm(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("simulador não pode chamar LLM/RAG")

    monkeypatch.setattr(character_creator, "get_llm", forbidden)
    monkeypatch.setattr(character_creator, "query_rag", forbidden)

    state = api._build_combat_simulator_state(_request())

    assert state["combat_simulation"] == {
        "enabled": True,
        "enemy_id": "mon_cao_rebite",
        "quantity": 2,
    }
    assert state["combat"]["active"] is True
    assert state["combat"]["round"] == 0
    assert state["player"]["class_name"] == "Sangromante"
    assert state["player"]["level"] == 3
    assert len(state["player"]["prepared_cards"]) >= 4
    assert [enemy["id"] for enemy in state["enemies"]] == [
        "mon_cao_rebite__sim_1", "mon_cao_rebite__sim_2",
    ]
    scene = state["combat"]["scene"]
    assert scene["frozen"] is True
    assert set(scene["positions"]) == {
        "player", "mon_cao_rebite__sim_1", "mon_cao_rebite__sim_2",
    }
    assert scene["zones"] == [
        {"id": "arena", "name": "Arena do Véu", "connections": []}
    ]


def test_endpoint_cria_e_turno_livre_usa_ataque_basico_sem_llm_ou_rag(monkeypatch):
    saved: dict[str, dict] = {}

    def save(state: dict) -> bool:
        saved[state["game_id"]] = deepcopy(state)
        return True

    def load(path: str | None = None):
        if not path:
            return None
        game_id = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(saved.get(game_id))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("simulador não pode chamar LLM/RAG")

    monkeypatch.setattr(api, "save_game_state", save)
    monkeypatch.setattr(api, "load_game_state", load)
    monkeypatch.setattr(character_creator, "get_llm", forbidden)
    monkeypatch.setattr(character_creator, "query_rag", forbidden)
    monkeypatch.setattr(campaign_manager, "get_llm", forbidden)
    monkeypatch.setattr(combat_agent, "get_llm", forbidden)
    monkeypatch.setattr(combat_agent, "build_context_pack", forbidden)
    monkeypatch.setattr("services.checkpoints.maybe_write", forbidden)

    client = TestClient(api.app)
    created = client.post("/game/combat-simulator", json=_request(quantity=1).model_dump())
    assert created.status_code == 200
    first = created.json()
    assert first["combat_simulation"]["enabled"] is True
    assert first["combat"]["active"] is True
    assert first["combat"]["round"] == 0

    acted = client.post("/game/action", json={
        "game_id": first["game_id"],
        "input_text": "qualquer texto livre vira ataque básico no laboratório",
    })
    assert acted.status_code == 200, acted.text
    body = acted.json()
    assert body["combat_simulation"]["enabled"] is True
    assert body["combat"]["round"] == 1 or body["combat"]["active"] is False
    state = saved[first["game_id"]]
    assert state["combat"]["last_player_action"]["kind"] == "attack"
    assert state.get("archivist_last_run", 0) == 0
    assert not state.get("consumed_conflict_ids")


def test_simulacao_persiste_marcador_e_arena_sem_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(character_creator, "get_llm", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("LLM proibida")
    ))
    state = api._build_combat_simulator_state(_request(quantity=1))

    assert persistence.save_game_state(state) is True
    loaded = persistence.load_game_state(persistence.save_path(state["game_id"]))

    assert loaded["combat_simulation"]["enabled"] is True
    assert loaded["combat"]["active"] is True
    assert loaded["combat"]["scene"]["frozen"] is True
    assert persistence.list_saves()[0]["combat_simulation"] is True
    assert not (tmp_path / f"{state['game_id']}.checkpoint.json").exists()


def test_action_request_monta_manobra_estruturada():
    state = {
        "combat": {"active": True},
        "enemies": [{"id": "alvo", "status": "ativo"}],
        "combat_simulation": {"enabled": True},
    }
    req = api.ActionRequest(
        input_text="Guardar",
        action_kind="maneuver",
        maneuver="guardar",
    )

    api._apply_action_options(state, req)

    assert state["combat_declaration"] == {
        "actor_id": "player",
        "acao": {
            "kind": "maneuver",
            "maneuver": "guardar",
            "target_id": "alvo",
        },
        "reaction_card_id": None,
    }
