"""SPEC-347 R14: registro estruturado da rodada (`turn_spans` + `round_log` + view)."""

from __future__ import annotations

import random

from services import combat_preview as cpv
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

ACTORS = [
    {"id": "player", "name": "Herói", "is_player": True},
    {"id": "enemy_1", "name": "Saqueador"},
]


def _atk(actor, target, **extra):
    return {
        "actor_id": actor,
        "target_id": target,
        "acerto": True,
        "resultado": "acerto",
        "dano_final": 4,
        **extra,
    }


def test_order_follows_turn_spans_and_reaction_is_marked():
    out = {
        "attacks": [
            _atk(
                "enemy_1",
                "player",
                fora_de_turno="Contra-ataque",
                resultado="erro",
                acerto=False,
                dano_final=None,
            ),
            _atk("player", "enemy_1"),
        ],
        "cards_used": [],
        "turn_spans": [{"actor_id": "player", "attacks": [0, 2], "cards": [0, 0]}],
    }
    log = cpv.round_board(out, ACTORS, {"enemy_1"})
    assert [e["ator_id"] for e in log] == ["enemy_1", "player"]
    assert (
        log[0]["origem"] == "reacao"
        and log[0]["rotulo"] == "Contra-ataque"
        and log[0]["resultado"] == "erro"
    )
    assert log[0]["lado"] == "inimigo" and log[1]["lado"] == "heroi"
    assert log[1]["dano"] == 4 and log[1]["origem"] == "turno"


def test_defense_card_without_attack_appears():
    card = {"id": "guarda", "name": "Guarda Alta", "efeito": {"kind": "protecao", "valor": 2}}
    out = {
        "attacks": [],
        "cards_used": [{"actor_id": "player", "card_id": "guarda", "card": card}],
        "turn_spans": [{"actor_id": "player", "attacks": [0, 0], "cards": [0, 1]}],
    }
    [entry] = cpv.round_board(out, ACTORS, {"enemy_1"})
    assert (
        entry["resultado"] == "efeito"
        and entry["efeito"] == "+2 Proteção"
        and entry["carta_nome"] == "Guarda Alta"
    )


def test_denied_turn_generates_no_entry():
    out = {
        "attacks": [],
        "cards_used": [],
        "turn_spans": [{"actor_id": "enemy_1", "attacks": [0, 0], "cards": [0, 0], "negado": True}],
    }
    assert cpv.round_board(out, ACTORS, {"enemy_1"}) == []


def test_order_matches_resolved_turns_in_real_round():
    scene = cs.new_scene()
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        },
        is_player=True,
    )
    enemy = orch.ensure_combat_sheet(
        {
            "id": "enemy_1",
            "name": "Saqueador",
            "categoria": "padrao",
            "max_vitalidade": 12,
            "vitalidade": 12,
            "virtudes": {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
        }
    )
    for i in ("player", "enemy_1"):
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": player, "enemy_1": enemy}
    sides = {"hero": ["player"], "ally": [], "enemy": ["enemy_1"]}
    decl = {
        "player": ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id="enemy_1")
        )
    }
    out = orch.run_round(scene, actors, sides, {}, declarations=decl, rng=random.Random(5))
    spans = out["turn_spans"]
    assert [s["actor_id"] for s in spans] == out["resolved_turns"]
    log = cpv.round_board(out, [player, enemy], {"enemy_1"})
    assert log and log[0]["ator_id"] in out["resolved_turns"]


def test_deck_off_has_no_last_round_board(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    meta: dict = {}
    cpv.store_mech_log(meta, {"attacks": [], "cards_used": []}, ACTORS)
    assert "last_round_board" not in meta and "last_mech_log" not in meta


def test_passive_counter_attack_comes_after_the_blow_that_caused_it():
    """Contra-ataque passivo (depois de levar o golpe): o golpe do inimigo vem antes do revide (P2-4)."""
    out = {
        "attacks": [
            _atk("enemy_1", "player", card_id=None),
            _atk("player", "enemy_1", fora_de_turno="Contra-ataque"),
        ],
        "cards_used": [],
        "turn_spans": [{"actor_id": "enemy_1", "attacks": [0, 2], "cards": [0, 0]}],
    }
    log = cpv.round_board(out, ACTORS, {"enemy_1"})
    assert [(e["ator_id"], e["origem"]) for e in log] == [
        ("enemy_1", "turno"),
        ("player", "reacao"),
    ]


def test_reaction_window_attack_still_precedes_the_actors_blow():
    out = {
        "attacks": [
            _atk("enemy_1", "player", fora_de_turno="Contra-ataque"),
            _atk("player", "enemy_1"),
        ],
        "cards_used": [],
        "turn_spans": [{"actor_id": "player", "attacks": [0, 2], "cards": [0, 0]}],
    }
    log = cpv.round_board(out, ACTORS, {"enemy_1"})
    assert [e["ator_id"] for e in log] == ["enemy_1", "player"]


def test_dot_ticks_and_heals_enter_the_board():
    """SPEC-346 R7/R10 (P1-2): o DoT vira entrada `efeito` no turno de quem sofre; a cura mostra o valor real."""
    heal_card = {"id": "bencao", "name": "Bênção Curta", "efeito": {"kind": "cura", "valor": 3}}
    out = {
        "attacks": [],
        "cards_used": [{"actor_id": "player", "card_id": "bencao", "card": heal_card}],
        "heals": [{"actor_id": "player", "card": "Bênção Curta", "amount": 2}],
        "ticks": [{"actor_id": "enemy_1", "condition": "Sangramento", "dano_final": 2}],
        "turn_spans": [
            {"actor_id": "enemy_1", "attacks": [0, 0], "cards": [0, 0]},
            {"actor_id": "player", "attacks": [0, 0], "cards": [0, 1]},
        ],
    }
    # SPEC-353 R51: fonte desconhecida -> ator_id None, lado "efeito"; a vítima vai em alvo_id.
    log = cpv.round_board(out, ACTORS, {"enemy_1"})
    assert [e["ator_id"] for e in log] == [None, "player"]
    assert log[0]["alvo_id"] == "enemy_1" and log[0]["tipo"] == "dano_continuo"
    assert (
        log[0]["rotulo"] == "Dano contínuo"
        and log[0]["efeito"] == "−2 Vitalidade"
        and log[0]["lado"] == "efeito"
    )
    assert log[1]["efeito"] == "+2 Vitalidade"


def test_mech_log_label_and_last_stand_coexist():
    atk = {
        "actor_id": "enemy_1",
        "target_id": "player",
        "dice_rolled": [3, 4],
        "dice_kept": [3, 4],
        "virtude": 0,
        "modificador": 0,
        "total": 7,
        "esquiva_alvo": 5,
        "resultado": "acerto",
        "acerto": True,
        "dano_final": 2,
    }
    last = cpv.mech_log([{**atk, "label": "Última Ação", "fora_de_turno": "Última Ação"}], ACTORS)[
        0
    ]
    assert last.startswith("Última Ação: Saqueador → Você")  # a forma da 346 vale
    counter = cpv.mech_log([{**atk, "fora_de_turno": "Contra-ataque"}], ACTORS)[0]
    assert counter.startswith("Saqueador · Contra-ataque → Você")
