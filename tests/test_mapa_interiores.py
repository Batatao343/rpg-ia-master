"""Spec mapa-sublocais — travel_times por conexão + camada interior.

Spec: specs/SPEC-027-mapa-sublocais-viagem-variavel.md.
"""

from __future__ import annotations

import json
import os

import gamedata
import world_utils as wu
from world_utils import apply_travel, find_travel_destination, travel_cost


# ---------------------------------------------------------------------------
# Helpers — mapa fixture injetado em gamedata._LOCATIONS_BY_ID
# ---------------------------------------------------------------------------

def _fixture_map(monkeypatch):
    locs = {
        "cidade": {"id": "cidade", "name": "Cidade", "region_id": "r1", "danger": 1,
                   "connections": ["bairro", "ermo", "longe", "taverna"],
                   "travel_times": {"bairro": 0, "longe": 3},
                   "tags": ["cidade"]},
        "bairro": {"id": "bairro", "name": "Bairro", "region_id": "r1", "danger": 1,
                   "connections": ["cidade"], "tags": []},
        "ermo": {"id": "ermo", "name": "Ermo", "region_id": "r2", "danger": 3,
                 "connections": ["cidade"], "tags": []},
        "longe": {"id": "longe", "name": "Longe", "region_id": "r3", "danger": 2,
                  "connections": ["cidade"], "tags": []},
        "taverna": {"id": "taverna", "name": "Taverna do Teste", "kind": "interior",
                    "parent_id": "cidade", "region_id": "r1", "danger": 0,
                    "connections": ["cidade"], "tags": ["taverna", "abrigo"]},
    }
    monkeypatch.setattr(gamedata, "_LOCATIONS_BY_ID", locs)
    return locs


def _world(loc_id: str = "cidade") -> dict:
    return {
        "current_location_id": loc_id, "current_location": loc_id.title(),
        "visited": [loc_id], "world_clock": {"day": 1, "period": "Manhã"},
        "danger_level": 1, "turn_count": 1,
    }


# ---------------------------------------------------------------------------
# Etapa 1 — travel_cost + apply_travel
# ---------------------------------------------------------------------------

def test_custo_default_1(monkeypatch):
    locs = _fixture_map(monkeypatch)
    assert travel_cost(_world("cidade"), locs["ermo"]) == 1


def test_custo_declarado_e_usado(monkeypatch):
    locs = _fixture_map(monkeypatch)
    world = _world("cidade")
    assert travel_cost(world, locs["longe"]) == 3
    antes = dict(world["world_clock"])
    novo = apply_travel(world, locs["longe"])
    # relógio andou 3 períodos (Manhã -> +3)
    periodos = wu.PERIODS
    idx_antes = periodos.index(antes["period"])
    total = idx_antes + 3
    assert novo["world_clock"]["day"] == antes["day"] + total // len(periodos)


def test_custo_simetrico_fallback(monkeypatch):
    locs = _fixture_map(monkeypatch)
    # "longe" não declara travel_times; cidade declara longe: 3 -> simétrico
    assert travel_cost(_world("longe"), locs["cidade"]) == 3


def test_custo_zero_nao_vira_relogio(monkeypatch):
    locs = _fixture_map(monkeypatch)
    world = _world("cidade")
    clock_antes = dict(world["world_clock"])
    weather_antes = world.get("weather_state")
    novo = apply_travel(world, locs["bairro"])
    assert novo["world_clock"] == clock_antes
    assert novo.get("weather_state") == weather_antes
    assert "bairro" in novo["visited"]          # fog of war revela mesmo assim
    assert novo["current_location_id"] == "bairro"


def test_interior_custa_zero(monkeypatch):
    locs = _fixture_map(monkeypatch)
    world = _world("cidade")
    assert travel_cost(world, locs["taverna"]) == 0
    novo = apply_travel(world, locs["taverna"])
    assert novo["world_clock"] == {"day": 1, "period": "Manhã"}
    assert novo["danger_level"] == 0


def test_sair_do_interior_para_o_pai_custa_zero(monkeypatch):
    locs = _fixture_map(monkeypatch)
    assert travel_cost(_world("taverna"), locs["cidade"]) == 0


# ---------------------------------------------------------------------------
# Etapa 2 — camada interior
# ---------------------------------------------------------------------------

def test_interior_so_alcancavel_do_pai(monkeypatch):
    _fixture_map(monkeypatch)
    # do pai: acha
    dest = find_travel_destination(_world("cidade"), "entro na taverna do teste")
    assert dest and dest["id"] == "taverna"
    # de outra região: não acha (não conectado)
    assert find_travel_destination(_world("ermo"), "vou para a taverna do teste") is None


def test_interior_conta_como_abrigo(monkeypatch):
    locs = _fixture_map(monkeypatch)
    world = _world("taverna")
    world["weather_state"] = "qualquer"
    # rest_block/dot_outdoor anulados por tag de abrigo
    eff = wu.weather_effects(world, locs["taverna"])
    assert eff["rest_block"] is False
    assert eff["dot_outdoor"] == 0


def test_interiors_of(monkeypatch):
    _fixture_map(monkeypatch)
    filhos = gamedata.interiors_of("cidade")
    assert [f["id"] for f in filhos] == ["taverna"]
    assert gamedata.interiors_of("ermo") == []


# ---------------------------------------------------------------------------
# Etapa 3 — dados reais do repo (R8)
# ---------------------------------------------------------------------------

def _mapa_real() -> list:
    with open(os.path.join("data", "world_map.json"), encoding="utf-8") as f:
        return json.load(f)["locations"]


def test_mapa_real_valido():
    locs = _mapa_real()
    by_id = {l["id"]: l for l in locs}

    for loc in locs:
        # conexões apontam para nós existentes
        for c in loc.get("connections", []):
            assert c in by_id, f"{loc['id']}: conexão órfã '{c}'"
        # travel_times só referencia conexões existentes
        for dest, cost in (loc.get("travel_times") or {}).items():
            assert dest in loc.get("connections", []), \
                f"{loc['id']}: travel_time para '{dest}' que não é conexão"
            assert isinstance(cost, int) and cost >= 0
            # custo 0 fora de interior só entre nós da mesma região
            if cost == 0 and by_id[dest].get("kind") != "interior":
                assert loc.get("region_id") == by_id[dest].get("region_id"), \
                    f"{loc['id']}->{dest}: custo 0 entre regiões diferentes"
        # interior bem formado
        if loc.get("kind") == "interior":
            parent = by_id.get(loc.get("parent_id", ""))
            assert parent and parent.get("kind") != "interior", \
                f"{loc['id']}: parent_id inválido"
            assert "abrigo" in (loc.get("tags") or []), f"{loc['id']}: interior sem tag abrigo"
            for c in loc.get("connections", []):
                ok = c == loc.get("parent_id") or \
                    (by_id[c].get("kind") == "interior" and
                     by_id[c].get("parent_id") == loc.get("parent_id"))
                assert ok, f"{loc['id']}: interior conecta fora do pai ({c})"

    # grafo não-interior é conexo
    exterior = {l["id"] for l in locs if l.get("kind") != "interior"}
    start = next(iter(exterior))
    fila, vistos = [start], {start}
    while fila:
        cur = fila.pop()
        for c in by_id[cur].get("connections", []):
            if c in exterior and c not in vistos:
                vistos.add(c)
                fila.append(c)
    assert vistos == exterior, f"grafo exterior desconexo: faltam {exterior - vistos}"

    # interiores curados existem
    assert sum(1 for l in locs if l.get("kind") == "interior") >= 4


def test_mapa_real_custos_curados():
    locs = {l["id"]: l for l in _mapa_real()}
    assert locs["na_anel_lama"]["travel_times"]["na_anel_ferro"] == 0
    assert locs["skallgard"]["travel_times"]["montanhas_afiadas"] == 2
    assert locs["brekmar"]["travel_times"]["ophidia"] == 3


# ---------------------------------------------------------------------------
# Etapa 4 — API
# ---------------------------------------------------------------------------

def test_data_map_sem_interiores():
    from fastapi.testclient import TestClient
    import api

    client = TestClient(api.app)
    body = client.get("/data/map").json()
    kinds = {l.get("kind") for l in body["locations"]}
    assert "interior" not in kinds
    ids = {l["id"] for l in body["locations"]}
    assert "na_taverna_javali" not in ids
    assert "nova_arcadia" in ids


def test_world_block_lista_interiores():
    import api

    bloco = api._world_block({"current_location_id": "na_anel_lama",
                              "current_location": "Anel de Lama"})
    assert any(i["id"] == "na_taverna_javali" for i in bloco["interiors"]["here"])
    assert bloco["interiors"]["exit_to"] is None

    dentro = api._world_block({"current_location_id": "na_taverna_javali",
                               "current_location": "Taverna do Javali Dourado"})
    assert dentro["interiors"]["exit_to"]["id"] == "na_anel_lama"
