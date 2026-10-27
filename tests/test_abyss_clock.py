"""SPEC-331 R7 - Relógio do Abismo (a partir da rodada 5; conflito nunca passa de 12)."""

import random

from services import conflict_orchestrator as orch
from services import conflict_scene as cs

_V = {"forca": 3, "agilidade": 2, "corpo": 6, "mente": 3, "carisma": 2}


def _actor(aid, **kw):
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _arena(cartas=()):
    player = _actor("player", abyss_charge=0)
    e = _actor("e")
    scene = cs.new_scene()
    for i in ("player", "e"):
        cs.place(scene, i)
    cs.freeze(scene)
    scene["cartas_de_cena"] = list(cartas)
    return scene, {"player": player, "e": e}, {"hero": ["player"], "enemy": ["e"]}


def _round(scene, actors, sides, seed):
    return orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": {"actor_id": "player", "acao": {"kind": "pass"}}},
        rng=random.Random(seed),
    )


def test_off_nao_muda_entropia(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "off")
    scene, actors, sides = _arena()
    for r in range(7):
        out = _round(scene, actors, sides, r)
        assert "abyss_clock" not in out
    assert actors["player"]["abyss_charge"] == 0


def test_relogio_so_a_partir_da_rodada_5(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    scene, actors, sides = _arena()
    seen = []
    for r in range(1, 8):
        out = _round(scene, actors, sides, r)
        seen.append(out.get("abyss_clock"))
        if out["ended"]:
            break
    assert seen[:4] == [None, None, None, None]
    assert seen[4:] == list(range(5, 5 + len(seen[4:])))
    assert actors["player"]["abyss_charge"] == len(seen[4:])  # D-331-4: +1 Carga por rodada


def test_relogio_dispara_de_novo_a_carta_mais_forte(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    scene, actors, sides = _arena(["vigilia_dos_druidas_cinzentos", "nevoa_cinza_do_ermo"])
    from services import scene_cards as sc

    assert sc.strongest(scene)["id"] == "vigilia_dos_druidas_cinzentos"  # empate de peso: por id
    logs = []
    for r in range(1, 6):
        logs += _round(scene, actors, sides, r)["logs"]
    assert "O Abismo se aproxima." in logs


def test_conflito_nunca_passa_de_12_rodadas(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    scene, actors, sides = _arena()
    # trava a luta: ninguém causa dano (os dois só passam), nem o guard de impasse resolve
    rounds = 0
    for r in range(1, 40):
        out = _round(scene, actors, sides, r)
        actors["e"]["vitalidade"] = actors["e"].get("max_vitalidade", actors["e"]["vitalidade"])
        rounds = r
        if out["ended"]:
            break
    assert rounds <= 12
    assert out["ended"]
