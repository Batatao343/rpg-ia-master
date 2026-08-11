"""Regressões de fiação das 5 Posturas no runtime de Cartas v4.

Os helpers de ``combat_mechanics`` isolados não bastam: estes testes atravessam
o orquestrador/economia reais para impedir novo corte de fios em futuros cutovers.
"""
import random

import combat_mechanics as cm
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


def _scene(*actor_ids: str) -> dict:
    scene = cs.new_scene()
    for actor_id in actor_ids:
        cs.place(scene, actor_id)
    cs.freeze(scene)
    return scene


def _player(class_name: str, card_id: str | None = None, **overrides) -> dict:
    player = orch.ensure_combat_sheet({
        "id": "player",
        "name": class_name,
        "is_player": True,
        "class_name": class_name,
        "virtudes": {
            "forca": 20, "agilidade": 20, "corpo": 5,
            "mente": 20, "carisma": 20,
        },
        "entropy": 0,
        "max_entropy": 30,
        "abyss_charge": 0,
        "known_cards": [card_id] if card_id else [],
        "prepared_cards": [card_id] if card_id else [],
    }, is_player=True)
    player.update(overrides)
    # Mantém os ataques inimigos determinísticos sem acoplar o teste a uma seed
    # específica do 2d10; ataques de Carta usam Mente/Carisma nos casos abaixo.
    player["virtudes"]["agilidade"] = -10
    return player


def _enemy(enemy_id: str = "enemy", **overrides) -> dict:
    enemy = orch.ensure_combat_sheet({
        "id": enemy_id,
        "name": "Carrasco",
        "categoria": "chefe",
        "virtudes": {
            "forca": 20, "agilidade": 0, "corpo": 5,
            "mente": 0, "carisma": 0,
        },
        "vitalidade": 80,
        "max_vitalidade": 80,
        "dano_base_arma": 8,
    })
    enemy.update(overrides)
    return enemy


def _card_declaration(card_id: str, target_id: str = "enemy") -> ct.TurnDeclaration:
    return ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="card", card_id=card_id, target_id=target_id),
    )


def _pass() -> ct.TurnDeclaration:
    return ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))


def _run(player: dict, enemy: dict, declaration: ct.TurnDeclaration) -> dict:
    actors = {"player": player, "enemy": enemy}
    declarations = {"player": declaration}
    if not enemy.get("surrendered"):
        declarations["enemy"] = ct.TurnDeclaration(
            actor_id="enemy",
            acao=ct.TurnStep(kind="attack", target_id="player"),
        )
    return orch.run_round(
        _scene(*actors), actors, {"hero": ["player"], "enemy": ["enemy"]},
        {"player": player}, declarations=declarations,
        initiator="heroes", rng=random.Random(4),
    )


def test_devoto_recebe_entropia_e_carga_pelo_dano_real_da_rodada():
    player = _player("Devoto do Abismo", vitalidade=60, max_vitalidade=60)

    out = _run(player, _enemy(), _pass())

    assert any(a.get("actor_id") == "enemy" and a.get("acerto") for a in out["attacks"])
    assert player["entropy"] >= 1
    assert player["abyss_charge"] == 1
    assert any(e["kind"] == "entropy:on_damage_taken" for e in out["class_mechanics"])


def test_sangromante_carta_v4_paga_auto_dano_e_dispara_cicatriz_de_pico():
    card_id = "san_exp_credencial"
    player = _player(
        "Sangromante", card_id, subclass="exposto", entropy=10,
        vitalidade=40, max_vitalidade=40,
    )
    enemy = _enemy(surrendered=True)

    out = _run(player, enemy, _card_declaration(card_id))

    assert player["vitalidade"] < 40
    assert player["abyss_charge"] >= 2  # gatilho de sangue + Cicatriz
    assert player.get("vitalidade_max_penalty", 0) == 3
    kinds = {e["kind"] for e in out["class_mechanics"]}
    assert {"self_harm", "entropy:on_self_harm", "consequence:cicatriz"} <= kinds


def test_sangromante_vaza_entropia_de_sangue_quando_inimigo_acerta():
    player = _player(
        "Sangromante", entropy=8, max_entropy=30, _blood_entropy=8,
        vitalidade=60, max_vitalidade=60,
    )

    out = _run(player, _enemy(), _pass())

    assert player["entropy"] == 6
    assert player["_blood_entropy"] == 6
    assert any(e["kind"] == "special:blood_leak" for e in out["class_mechanics"])


def test_corruptor_carta_de_decadencia_dispara_recurso_da_classe():
    card_id = "cor_bio_gangrena"
    player = _player("Corruptor", card_id, subclass="biologia", entropy=1)

    out = _run(player, _enemy(surrendered=True), _card_declaration(card_id))

    assert player["entropy"] == 1
    assert player["abyss_charge"] == 1
    assert any(e["kind"] == "entropy:on_decay_nearby" for e in out["class_mechanics"])


def test_arcanista_canaliza_arma_e_resfria_caldeira_com_cartas_v4():
    player = _player("Arcanista Cinzento", "arc_faisca", entropy=0)
    out = _run(player, _enemy(surrendered=True), _card_declaration("arc_faisca"))

    assert player["entropy"] == 2
    assert player["abyss_charge"] == 1
    assert player["_cool_deadline"] == 3
    assert any(e["kind"] == "special:boiler_armed" for e in out["class_mechanics"])

    player["prepared_cards"] = ["arc_descarga"]
    player["known_cards"] = ["arc_descarga"]
    cards.reset_card_usage({"player": player}, "turno")
    out = _run(player, _enemy(surrendered=True), _card_declaration("arc_descarga"))

    assert "_cool_deadline" not in player
    assert any(e["kind"] == "special:boiler_cooled" for e in out["class_mechanics"])


def test_dependencia_altera_custo_real_da_carta_no_motor_de_economia():
    player = _player(
        "Arcanista Cinzento", "arc_descarga", entropy=10,
        abyss_charge=4, equipment={},
    )
    state = {"player": player}

    result = cards.use_card(state, "arc_descarga")

    assert result["ok"] is True
    assert player["entropy"] == 8
    assert "-2 Entropia" in result["log"]


def test_medico_ganha_recurso_quando_aliado_sofre_na_rodada_real():
    player = _player("Médico de Campo", entropy=0)
    ally = orch.ensure_combat_sheet({
        "id": "ally", "name": "Batedor", "categoria": "nomeado",
        "virtudes": {"forca": 1, "agilidade": 30, "corpo": 5, "mente": 1, "carisma": 1},
        "vitalidade": 60, "max_vitalidade": 60,
    })
    ally["virtudes"]["agilidade"] = -10
    enemy = _enemy()
    actors = {"player": player, "ally": ally, "enemy": enemy}

    out = orch.run_round(
        _scene(*actors), actors,
        {"hero": ["player"], "ally": ["ally"], "enemy": ["enemy"]},
        {"player": player}, declarations={
            "player": _pass(),
            "ally": ct.TurnDeclaration(actor_id="ally", acao=ct.TurnStep(kind="pass")),
            "enemy": ct.TurnDeclaration(
                actor_id="enemy", acao=ct.TurnStep(kind="attack", target_id="ally")),
        },
        initiator="heroes", rng=random.Random(4),
    )

    assert player["entropy"] == 1
    assert player["abyss_charge"] == 1
    assert any(e["kind"] == "entropy:on_ally_suffer" for e in out["class_mechanics"])


class _AlwaysTaunt:
    def random(self) -> float:
        return 0.0


def test_provocacao_do_devoto_redireciona_alvo_inimigo():
    devoto = _player("Devoto do Abismo", entropy=10)
    ally = _player("Médico de Campo", vitalidade=30, max_vitalidade=30)
    ally["id"] = "ally"
    ally["is_player"] = False
    enemy = _enemy()
    enemy["active_conditions"] = [{
        "name": "Provocação do Abismo", "duration": 2, "dot": 0,
        "control": "taunt", "source_actor_id": "player",
    }]
    actors = {"player": devoto, "ally": ally, "enemy": enemy}

    declaration = orch.enemy_declaration(
        _scene(*actors), "enemy", actors,
        {"hero": ["player"], "ally": ["ally"], "enemy": ["enemy"]},
        rng=_AlwaysTaunt(),
    )

    assert declaration.acao.target_id == "player"


def test_todas_as_cartas_v4_usam_apenas_marcadores_de_classe_fechados():
    for card in cards.all_cards().values():
        assert cards.valid_class_mechanics(card.get("mecanica_classe"))
    assert not cards.valid_class_mechanics({"regra_livre": "não"})
    assert not cards.valid_class_mechanics({"decadencia": "conceito_do_llm"})
