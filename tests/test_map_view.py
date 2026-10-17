"""SPEC-210 - view de mapa com fog server-side (offline)."""
from __future__ import annotations

import json

import gamedata
import world_utils
from services import map_view


def _all_locations() -> list:
    with open("data/world_map.json", encoding="utf-8") as fh:
        return json.load(fh)["locations"]


def _state(visited=None, current="nova_arcadia", **world_extra) -> dict:
    world = world_utils.starting_world("Nova Arcádia", 1)
    world["current_location_id"] = current
    world["current_location"] = gamedata.get_location(current)["name"]
    world["visited"] = list(visited or [current])
    world.update(world_extra)
    return {"game_id": "g", "world": world, "world_projection": {}, "event_log": [],
            "quests": [], "combat": None}


def _by_id(view):
    return {n["id"]: n for n in view["nodes"]}


def test_novo_jogo_so_visitado_e_adjacentes():
    view = map_view.build_map_view(_state())
    ids = set(_by_id(view))
    conns = {c["id"] for c in gamedata.get_connections("nova_arcadia")}
    assert ids == {"nova_arcadia"} | conns
    nodes = _by_id(view)
    assert nodes["nova_arcadia"]["state"] == "atual"
    for cid in conns:
        n = nodes[cid]
        assert n["state"] == "adjacente"
        assert set(n) <= {"id", "state", "name", "coords", "reachable", "reason"}
        assert "danger" not in n and "lore_seed" not in n and "art" not in n


def test_payload_nao_vaza_nomes_de_locais_nao_alcancados():
    view = map_view.build_map_view(_state())
    text = json.dumps(view, ensure_ascii=False)
    sent = set(_by_id(view))
    for loc in _all_locations():
        if loc["id"] in sent or loc.get("kind") == "interior":
            continue
        assert loc["name"] not in text, loc["name"]
        if loc.get("lore_seed"):
            assert loc["lore_seed"] not in text


def test_lore_e_perigo_so_de_visitados():
    view = map_view.build_map_view(_state())
    here = _by_id(view)["nova_arcadia"]
    assert here["lore_seed"] and here["region_id"] == "nova_arcadia" and "danger" in here
    assert here["art"] is not None


def test_travel_options_so_connections_e_custo_igual_travel_cost():
    state = _state()
    view = map_view.build_map_view(state)
    conns = gamedata.get_connections("nova_arcadia")
    opts = {o["location_id"]: o for o in view["travel_options"]}
    assert set(opts) == {c["id"] for c in conns}
    for c in conns:
        assert opts[c["id"]]["periods"] == world_utils.travel_cost(state["world"], c)
    assert opts["brekmar"]["periods"] == 2 and opts["na_anel_ferro"]["periods"] == 0


def test_assimetria_e_fallback_simetrico():
    state = _state(current="brekmar", visited=["nova_arcadia", "brekmar"])
    view = map_view.build_map_view(state)
    opt = {o["location_id"]: o for o in view["travel_options"]}["nova_arcadia"]
    assert opt["periods"] == world_utils.travel_cost(state["world"], gamedata.get_location("nova_arcadia"))


def test_botao_texto_reconhecido_por_find_travel_destination():
    state = _state()
    view = map_view.build_map_view(state)
    assert view["travel_options"]
    for opt in view["travel_options"]:
        dest = world_utils.find_travel_destination(state["world"], f"Viajo para {opt['name']}")
        assert dest and dest["id"] == opt["location_id"]


def test_visitado_nao_conectado_sem_rota_direta():
    state = _state(visited=["nova_arcadia", "floresta_sussurros"])
    assert "floresta_sussurros" not in {c["id"] for c in gamedata.get_connections("nova_arcadia")}
    view = map_view.build_map_view(state)
    n = _by_id(view)["floresta_sussurros"]
    assert n["state"] == "visitado" and n["reachable"] is False
    assert "sem rota direta" in n["reason"].lower()
    assert "floresta_sussurros" not in {o["location_id"] for o in view["travel_options"]}


def test_estado_bloqueado_e_edge():
    state = _state()
    state["world_projection"] = {"blocked_routes": [{"a": "nova_arcadia", "b": "brekmar"}]}
    view = map_view.build_map_view(state)
    assert _by_id(view)["brekmar"]["state"] == "bloqueado"
    opt = {o["location_id"]: o for o in view["travel_options"]}["brekmar"]
    assert opt["blocked"] is True and opt["reachable"] is False and opt["reason"]
    edge = [e for e in view["edges"] if {e["a"], e["b"]} == {"nova_arcadia", "brekmar"}][0]
    assert edge["blocked"] is True


def test_estados_exclusivos():
    view = map_view.build_map_view(_state(visited=["nova_arcadia", "brekmar"]))
    for n in view["nodes"]:
        assert n["state"] in {"atual", "visitado", "adjacente", "bloqueado"}
    assert sum(1 for n in view["nodes"] if n["state"] == "atual") == 1


def test_override_de_perigo_e_quest_so_em_visitados():
    state = _state(visited=["nova_arcadia", "brekmar"], danger_overrides={"brekmar": 4})
    state["quests"] = [
        {"id": "q1", "status": "active", "location_id": "brekmar"},
        {"id": "q2", "status": "active", "location_id": "na_anel_ferro"},  # adjacente
    ]
    view = map_view.build_map_view(state)
    nodes = _by_id(view)
    assert nodes["brekmar"]["danger"] == 4
    assert nodes["brekmar"]["quest_target"] is True
    assert "quest_target" not in nodes["na_anel_ferro"]


def test_interior_ancora_no_pai_e_nunca_vira_no():
    interior = next(l for l in _all_locations() if l.get("kind") == "interior")
    state = _state(current=interior["id"], visited=[interior["parent_id"], interior["id"]])
    view = map_view.build_map_view(state)
    assert interior["id"] not in set(_by_id(view))
    assert _by_id(view)[interior["parent_id"]]["state"] == "atual"
    opts = {o["location_id"]: o for o in view["travel_options"]}
    assert opts[interior["parent_id"]]["periods"] == 0
    assert view["interiors"]["exit_to"]["id"] == interior["parent_id"]


def test_arte_exata_ou_regional_ou_placeholder():
    view = map_view.build_map_view(_state(visited=["nova_arcadia", "pantano_melancolia"]))
    assert _by_id(view)["nova_arcadia"]["art"]["scope"] == "exact"
    assert _by_id(view)["pantano_melancolia"]["art"]["scope"] in {"exact", "regional", "placeholder"}


def test_map_version_estavel_e_muda():
    a = map_view.build_map_view(_state())
    b = map_view.build_map_view(_state())
    assert a["map_version"] == b["map_version"]
    c = map_view.build_map_view(_state(visited=["nova_arcadia", "brekmar"]))
    assert c["map_version"] != a["map_version"]


def test_gate_de_viagem():
    s = _state()
    assert map_view.build_map_view(s)["travel_gate"]["blocked"] is False
    s["combat"] = {"active": True}
    gate = map_view.build_map_view(s)["travel_gate"]
    assert gate["blocked"] and "fuga" in gate["reason"]
    s["combat"] = None
    s["death_pending"] = True
    assert map_view.build_map_view(s)["travel_gate"]["blocked"]
    s["death_pending"], s["game_over"] = False, True
    assert map_view.build_map_view(s)["travel_gate"]["blocked"]
    s["game_over"], s["archived"] = False, True
    assert map_view.build_map_view(s)["travel_gate"]["blocked"]


def test_save_antigo_sem_campos():
    view = map_view.build_map_view({"world": {"current_location_id": "nova_arcadia"}})
    assert view["current_id"] == "nova_arcadia" and view["nodes"]


def test_legado_filtrado_por_jogo():
    legacy = map_view.legacy_filtered_map(_state())
    ids = {loc["id"] for loc in legacy["locations"]}
    assert ids == set(_by_id(map_view.build_map_view(_state())))
    adj = [loc for loc in legacy["locations"] if loc["id"] == "brekmar"][0]
    assert adj["lore_seed"] == "" and adj["connections"] == []


def test_api_endpoint_fog_e_404(monkeypatch):
    import api
    from fastapi.testclient import TestClient
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    r = client.post("/game/new", json={"name": "Mapa", "race": "Humano", "class_name": "Sangromante",
                                       "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    gid = r.json()["game_id"]
    m = client.get("/game/map", params={"game_id": gid})
    assert m.status_code == 200
    body = m.json()
    assert body["game_id"] == gid and body["current_id"]
    sent = {n["id"] for n in body["nodes"]}
    full = client.get("/data/map").json()["locations"]
    text = json.dumps(body, ensure_ascii=False)
    for loc in full:
        if loc["id"] not in sent:
            assert loc["name"] not in text
    legacy = client.get("/data/map", params={"game_id": gid}).json()
    assert {loc["id"] for loc in legacy["locations"]} == sent
    assert client.get("/game/map", params={"game_id": "00000000-0000-4000-8000-000000000000"}).status_code == 404
    assert client.get("/game/map", params={"game_id": "x"}).status_code == 400
    assert len(client.get("/data/map").json()["locations"]) == len(full)  # global intacto


# --- Revisao independente (Sol) ---

def test_legado_filtrado_nao_vaza_tesouro_nem_ids_por_travel_times():
    """Visitado nao-ancora: `travel_times`/`treasure` do JSON cru nao podem sair
    (travel_times de brekmar cita costa_negra/ophidia, nao alcancados daqui)."""
    for visited, current in ((["nova_arcadia", "brekmar"], "nova_arcadia"),
                             (["pantano_melancolia", "pm_profundezas"], "pantano_melancolia")):
        legacy = map_view.legacy_filtered_map(_state(current=current, visited=visited))
        sent = {loc["id"] for loc in legacy["locations"]}
        text = json.dumps(legacy, ensure_ascii=False)
        assert "treasure" not in text
        for loc in _all_locations():
            if loc["id"] not in sent:
                assert f'"{loc["id"]}"' not in text, loc["id"]
                assert loc["name"] not in text, loc["name"]


def test_view_nao_cita_ids_de_locais_nao_alcancados():
    for visited, current in ((["nova_arcadia", "brekmar"], "nova_arcadia"),
                             (["pantano_melancolia", "pm_profundezas"], "pantano_melancolia")):
        view = map_view.build_map_view(_state(current=current, visited=visited))
        sent = set(_by_id(view)) | {o["location_id"] for o in view["travel_options"]}
        sent |= {i["id"] for i in view["interiors"]["here"]}
        text = json.dumps(view, ensure_ascii=False)
        assert "treasure" not in text
        for loc in _all_locations():
            if loc["id"] not in sent:
                assert f'"{loc["id"]}"' not in text, loc["id"]


def test_saida_do_interior_reconhecida_pelo_router_de_viagem():
    interior = next(l for l in _all_locations() if l.get("kind") == "interior")
    state = _state(current=interior["id"], visited=[interior["parent_id"], interior["id"]])
    view = map_view.build_map_view(state)
    parent = {o["location_id"]: o for o in view["travel_options"]}[interior["parent_id"]]
    dest = world_utils.find_travel_destination(state["world"], f"Viajo para {parent['name']}")
    assert dest and dest["id"] == interior["parent_id"]


def test_data_map_por_jogo_entra_na_fronteira_de_sessao_e_no_store(monkeypatch):
    import api
    from fastapi.testclient import TestClient
    assert api._session_scoped_path("/data/map", {"game_id": "x"}) is True
    assert api._session_scoped_path("/data/map", {}) is False
    assert api._session_scoped_path("/game/map", {}) is True
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    client = TestClient(api.app)
    r = client.post("/game/new", json={"name": "Mapa", "race": "Humano", "class_name": "Sangromante",
                                       "region": "Nova Arcádia", "level": 1, "backstory": ""})
    gid = r.json()["game_id"]
    assert client.get("/data/map", params={"game_id": gid}).headers.get("cache-control") == "no-store"
    assert client.get("/game/map", params={"game_id": gid}).headers.get("cache-control") == "no-store"
