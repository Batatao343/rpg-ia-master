"""SPEC-298 Etapa 2 — raça/origem: ids, tabela curada, relação inicial, recusa."""

import json
from pathlib import Path

from services import reputation as rep


def _state(race="Elfo", region_id=""):
    return {
        "player": {
            "race": race,
            "race_id": rep.resolve_race_id(race),
            "origin_region_id": region_id,
        },
        "world": {"current_location_id": "skallgard"},
    }


def test_race_id_por_nome_em_save_antigo():
    for name in ("Humano", "humano", "  HUMANO "):
        assert rep.resolve_race_id(name) == "race_humanos"
    assert rep.resolve_race_id("Anão da Fuligem") == "race_anoes_fuligem"
    assert rep.resolve_race_id("Anao da Fuligem") == "race_anoes_fuligem"
    assert rep.resolve_race_id("Goblin") == ""
    assert rep.resolve_region_id("Skallgard") == "skallgard"
    assert rep.resolve_region_id("") == ""


def test_npc_grafo_raca_por_tag():
    assert rep.npc_race_id({"id": "npc_mestre_albrecht_o_cartografo"}) == "race_humanos"
    assert rep.npc_race_id({"id": "inexistente"}) == ""
    assert rep.npc_race_id({"id": "x", "race_id": "race_elfos"}) == "race_elfos"
    assert rep.npc_race_id({"id": "x", "race_id": "race_invalida"}) == ""


def test_npc_schema_race_id_invalido_vira_vazio():
    from agents.npc import _valid_race_id

    assert _valid_race_id("race_vrel") == "race_vrel"
    assert _valid_race_id("orc") == ""
    assert _valid_race_id(None) == ""


def test_cultura_humana_por_regiao():
    npc = {"id": "n", "race_id": "race_humanos", "home_location_id": "skallgard"}
    assert rep.race_attitude(_state("Elfo"), npc) == -1  # Nascidos do Gelo x elfo
    urbano = {"id": "n", "race_id": "race_humanos", "home_location_id": "nova_arcadia"}
    assert rep.race_attitude(_state("Elfo"), urbano) == 0
    assert rep.race_attitude(_state("Osshari"), npc) == 1


def test_regra_local_vrel_skallgard():
    npc = {"id": "n", "race_id": "race_humanos", "home_location_id": "skallgard"}
    assert rep.race_attitude(_state("Vrel"), npc) == 1
    fora = {"id": "n", "race_id": "race_humanos", "home_location_id": "nova_arcadia"}
    assert rep.race_attitude(_state("Vrel"), fora) == 0


def test_initial_relationship_soma_e_clamp_2_8():
    npc = {"id": "n", "race_id": "race_humanos", "home_location_id": "skallgard"}
    value, basis = rep.initial_relationship(_state("Elfo"), npc)
    assert value == 4 and basis == {"race": -1, "origin": 0, "fame": 0, "faction": 0}
    st = _state("Osshari")
    st["location_fame"] = {"skallgard": {"renown": 70, "infamy": 0}}
    st["player"]["origin_region_id"] = "skallgard"
    elfo = {"id": "n", "race_id": "race_elfos", "home_location_id": "skallgard"}
    # elfo -> osshari = +1 ; origem +1 ; fama +2 => 9 -> teto 8
    assert rep.initial_relationship(st, elfo)[0] == 8
    st = _state("Anão da Fuligem")
    st["location_fame"] = {"skallgard": {"renown": 0, "infamy": 90}}
    # elfo -> anao = -2 ; fama -2 => 1 -> piso 2
    assert rep.initial_relationship(st, elfo)[0] == 2


def test_conterraneo_mais_um():
    npc = {"id": "n", "race_id": "", "home_location_id": "skallgard"}
    assert rep.initial_relationship(_state("Elfo", "skallgard"), npc)[1]["origin"] == 1
    assert rep.initial_relationship(_state("Elfo", "brekmar"), npc)[1]["origin"] == 0


def test_recusa_so_com_menos_dois_e_rel_ate_2():
    npc = {"id": "n", "race_id": "race_elfos", "relationship": 2}
    st = _state("Anão da Fuligem")
    assert rep.refuses(st, npc, "comercio") and rep.refuses(st, npc, "favor")
    assert not rep.refuses(st, npc, "conversa")
    assert not rep.refuses(st, {**npc, "relationship": 3}, "comercio")
    assert not rep.refuses(_state("Humano"), npc, "comercio")  # atitude +1


def test_relacao_pessoal_supera_preconceito():
    npc = {"id": "n", "race_id": "race_elfos", "home_location_id": ""}
    st = _state("Anão da Fuligem")
    value, basis = rep.initial_relationship(st, npc)
    assert basis["race"] == -2 and value == 3
    assert not rep.refuses(st, {**npc, "relationship": value}, "comercio")


def test_lint_race_attitudes_exige_source():
    from services.content_validator import lint_race_attitudes

    data = json.loads(Path("data/race_attitudes.json").read_text(encoding="utf-8"))
    assert lint_race_attitudes(data) == []
    broken = json.loads(json.dumps(data))
    broken["races"]["race_elfos"]["race_humanos"].pop("source")
    broken["races"]["race_elfos"]["race_vrel"]["value"] = 9
    broken["races"]["race_inventada"] = {}
    assert len(lint_race_attitudes(broken)) == 3
