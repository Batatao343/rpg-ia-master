"""SPEC-331 (revisão Sol): ambiente neutro, shadow puro, forecast do Relógio, registro temporário."""

import random

import pytest

from services import card_effects as fx
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import encounter_preparation as prep
from services import scene_cards as sc

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}


def _actor(aid, **kw):
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _scene(cartas=()):
    scene = cs.new_scene([{"id": "z0", "name": "Campo", "connections": ["z1"]}])
    for i in ("player", "e"):
        cs.place(scene, i)
    cs.freeze(scene)
    scene["cartas_de_cena"] = list(cartas)
    return scene


def _ctx(scene, actors):
    return fx.Ctx(
        scene=scene,
        actors_by_id=actors,
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
    )


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")


def test_carga_so_para_quem_tem_carga(on):
    player = _actor("player", abyss_charge=1)
    actors = {"player": player, "e": _actor("e")}
    actors["e"].pop("abyss_charge", None)
    scene = _scene(["vigilia_dos_druidas_cinzentos"])
    out = {"logs": [], "terminal": [], "deaths": []}
    sc.tick(_ctx(scene, actors), 1, "fim_rodada", out)
    sc.tick(_ctx(scene, actors), 2, "fim_rodada", out)
    assert player["abyss_charge"] == 3
    assert "abyss_charge" not in actors["e"]
    assert player.get("entropy", 0) == 0  # D-331-4: pressão, não recurso


def test_dano_de_ambiente_tem_fonte_neutra(on):
    player = _actor("player")
    player["active_conditions"] = [
        {
            "name": "Marca do Abismo",
            "keyword": "marca_do_abismo",
            "control": "marca",
            "abismo_bonus": 5,
            "duration": 3,
            "dot": 0,
        }
    ]
    actors = {"player": player, "e": _actor("e")}
    scene = _scene(["vento_de_vidro_de_zhur"])
    out = {"logs": [], "terminal": [], "deaths": []}
    before = player["vitalidade"]
    sc.tick(_ctx(scene, actors), 2, "fim_rodada", out)
    assert player["vitalidade"] < before
    assert before - player["vitalidade"] <= 2  # não somou os 5 da Marca
    assert [c["keyword"] for c in player["active_conditions"]] == ["marca_do_abismo"]
    assert not out.get("extra_hits")


def test_shadow_nao_grava_cena_estado_nem_forecast(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "shadow")
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene(["telhado_que_cede"])
    sc.tick(_ctx(scene, actors), 3, "inicio_rodada", {})
    assert "cena_estado" not in scene
    assert sc.forecast(scene, 3) == []


def test_forecast_inclui_redisparo_do_relogio(on):
    scene = _scene(["sinos_de_nova_arcadia"])
    got = sc.forecast(scene, 5)  # sinos só nas rodadas 3, 6...: na 5 só o Relógio
    assert [(g["id"], g["quando"]) for g in got] == [("sinos_de_nova_arcadia", "relogio")]
    assert sc.forecast(scene, 4) == []


def test_carta_temporaria_fora_da_progressao_e_do_catalogo(on, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    scene = _scene()
    cs.add_object(
        scene,
        {
            "id": "barril",
            "name": "Barril",
            "zone_id": "z0",
            "uses_remaining": 1,
            "interactions": [
                {
                    "label": "derrubar",
                    "effect": {"kind": "damage", "params": {"amount": 3, "target": "e"}},
                }
            ],
        },
        from_trigger=True,
    )
    piles = {"compra": [], "mao": ["a"], "descarte": [], "exaurida": []}
    ids = sc.sync_hand(scene, piles, "player")
    assert ids and ids[0] not in cards.all_cards()
    assert all(not c["id"].startswith("cena_") for c in cards.cards_for_class(""))
    assert cards.get_card(ids[0])
    cards.reload_cards()
    assert cards.get_card(ids[0]) is None  # processo novo: recriada no sync


def test_in_hand_aceita_so_cena_na_mao():
    assert sc.in_hand({"mao": ["cena_x_1"]}, "cena_x_1")
    assert not sc.in_hand({"mao": ["cena_x_1"]}, "outra")
    assert not sc.in_hand({"mao": ["abc"]}, "abc")
    assert not sc.in_hand(None, "cena_x_1")


def test_public_objective_por_nome(on):
    scene = _scene()
    scene["objetivo"] = {"tipo": "alcancar_zona", "alvo": "z1"}
    scene["zones"].append({"id": "z1", "name": "A ponte"})
    view = sc.public_objective(scene)
    assert view["alvo_nome"] == "A ponte" and view["tipo"] == "alcancar_zona"
    assert sc.public_objective({"zones": []}) is None


def test_prompt_lista_alvos_validos(on):
    ctx = {"location": "Skallgard", "enemies": [{"id": "bandido_1"}], "allies": ["ana"]}
    text = prep._scene_cards_prompt(ctx)
    assert "ana" in text and "bandido_1" in text and "zona criada" in text
