"""Contratos da interface tática de Cartas (spec conflito-16)."""
from random import Random

from services import conflict_orchestrator as orch
from services import conflict_scene as scene_mod
from services.conflict_turn import TurnDeclaration, TurnStep

import api


def _player() -> dict:
    return orch.ensure_combat_sheet({
        "id": "player",
        "name": "Iria",
        "is_player": True,
        "class_name": "Devoto do Abismo",
        "level": 4,
        "virtudes": {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 2},
        "vitalidade": 12,
        "max_vitalidade": 18,
        "ferimentos": {"leve": [{"regiao": "braço", "detail": "corte"}],
                        "grave": [], "critico": []},
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "entropy": 8,
        "max_entropy": 10,
        "abyss_charge": 1,
        "known_cards": ["golpe_devoto", "muralha_viva", "dev_encaixe"],
        "prepared_cards": ["golpe_devoto", "muralha_viva", "dev_encaixe"],
        "card_usage": {"muralha_viva": {"used_this_scene": 1}},
        "active_conditions": [],
    }, is_player=True)


def _enemy() -> dict:
    return orch.ensure_combat_sheet({
        "id": "lobo_1", "archetype_id": "lobo_cinzento", "name": "Lobo Cinzento",
        "categoria": "padrao", "virtudes": {"forca": 2, "agilidade": 3,
        "corpo": 1, "mente": 0, "carisma": 0}, "vitalidade": 9,
        "max_vitalidade": 9, "active_conditions": [],
        "cartas": ["bst_defesa_instintiva", "carta_secreta"],
        "revealed_cards": ["bst_defesa_instintiva"],
        "resist_tipos": ["cortante", "fogo"],
        "revealed_resistances": ["cortante"],
        "tactical_profile": {"pursuit_policy": "persegue"},
    })


def _scene() -> dict:
    scene = scene_mod.new_scene([
        {"id": "ponte", "name": "Ponte partida", "connections": ["margem"]},
        {"id": "margem", "name": "Margem", "connections": ["ponte"]},
    ])
    scene_mod.place(scene, "player", zone_id="ponte", postura="protegido")
    scene_mod.place(scene, "lobo_1", zone_id="margem", distance_state="distante")
    scene_mod.freeze(scene)
    return scene


def test_combat_block_expoe_cartas_cena_ferimentos_e_conhecimento_progressivo():
    player, enemy, scene = _player(), _enemy(), _scene()
    block = api._combat_block({
        "player": player,
        "enemies": [enemy],
        "combat": {"active": True, "round": 2, "scene": scene,
                   "chase": {"trilha": "afastado", "escapou": False}},
    })

    assert block["scene"]["zones"][0]["name"] == "Ponte partida"
    assert block["scene"]["positions"][0]["participant_name"]
    cards = {card["id"]: card for card in block["cards"]}
    assert cards["golpe_devoto"]["ready"] is True
    assert cards["muralha_viva"]["spent"] is True
    assert cards["muralha_viva"]["has_rupture"] is True
    assert cards["dev_encaixe"]["type"] == "reacao"
    assert block["wounds"]["slots"]["leve"] == 3
    assert block["chase"]["track"] == "afastado"

    panel = block["enemies"][0]
    assert panel["revealed_cards"] == [
        {"id": "bst_defesa_instintiva", "name": "Defesa Instintiva"}
    ]
    assert panel["revealed_resistances"] == ["cortante"]
    assert "cartas" not in panel and "resist_tipos" not in panel


def test_action_request_aceita_escolhas_taticas_estruturadas():
    req = api.ActionRequest(
        input_text="Uso Muralha Viva.", game_id=None,
        card_id="muralha_viva", target_id="lobo_1", ruptura=True,
        reaction_card_id="dev_encaixe",
    )
    assert req.ruptura is True
    assert req.reaction_card_id == "dev_encaixe"
    state = {"combat": {"active": True}}
    api._apply_action_options(state, req)
    assert state["combat_declaration"]["acao"]["params"]["ruptura"] is True
    assert state["combat_declaration"]["reaction_card_id"] == "dev_encaixe"


def test_reacao_escolhida_pelo_jogador_e_consumida_quando_ele_e_alvo():
    player, enemy, scene = _player(), _enemy(), _scene()
    player["card_usage"] = {}
    before = player["entropy"]
    sides = {"hero": ["player"], "ally": [], "enemy": ["lobo_1"]}
    declarations = {
        "player": TurnDeclaration(
            actor_id="player", acao=TurnStep(kind="pass"),
            reaction_card_id="dev_encaixe",
        ),
        "lobo_1": TurnDeclaration(
            actor_id="lobo_1", acao=TurnStep(kind="attack", target_id="player"),
        ),
    }

    out = orch.run_round(
        scene, {"player": player, "lobo_1": enemy}, sides,
        {"player": player}, declarations=declarations,
        initiator="enemy", rng=Random(7),
    )

    assert any(r["participant"] == "player" and r["card_id"] == "dev_encaixe"
               for r in out["reactions"])
    assert player["entropy"] == before - 1
    assert player["card_usage"]["dev_encaixe"]["used_this_turn"] == 1


def test_death_block_preserva_ultima_acao_terminal_e_estabilizacao():
    block = api._death_block({
        "death_pending": True,
        "player": {"dead": True, "estado_terminal": False,
                   "stabilization_attempts": 2, "name": "Iria"},
        "combat": {
            "last_player_action": {"kind": "card", "card_id": "muralha_viva",
                                   "result": "hit"},
            "death_context": {"entered_terminal": True,
                              "stabilization": "duas falhas de estabilização",
                              "killer": "Lobo Cinzento"},
        },
    })
    assert block["pending"] is True
    assert block["last_action"]["card_id"] == "muralha_viva"
    assert block["entered_terminal"] is True
    assert block["stabilization_attempts"] == 2
