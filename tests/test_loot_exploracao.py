"""Suíte da spec loot-exploracao — explorar recompensa (escada de raridade + baús).

Offline/determinístico. Reusa a engine de loot da Fase 6. Ver
specs/loot-exploracao.md.
"""
import random

from services import exploration as ex


def _world(visited=None, looted=None, danger=3):
    return {"current_location_id": "pm_profundezas", "danger_level": danger,
            "visited": visited or [], "looted_locations": looted or [],
            "turn_count": 5}


def _loc(danger=3, region="pantano_melancolia", treasure=None):
    d = {"id": "pm_profundezas", "name": "Profundezas", "danger": danger,
         "region_id": region}
    if treasure is not None:
        d["treasure"] = treasure
    return d


# --- R1/R2: achado ambiental na 1ª visita -----------------------------------

def test_chance_escala_com_perigo():
    assert ex.discovery_chance(1) < ex.discovery_chance(4)
    assert ex.discovery_chance(4) <= 0.5   # teto


def test_roll_discovery_pode_dar_loot():
    # com seed favorável, alguma delas concede algo em local perigoso.
    achou = False
    for s in range(30):
        d = ex.roll_discovery(_world(), _loc(danger=4), 3, random.Random(s))
        if d:
            achou = True
            assert d["gold"] >= 0
            assert d["rarity"] in ("comum", "incomum", "raro")
            break
    assert achou


def test_roll_discovery_passivo_nunca_unico():
    from inventory import is_unique
    for s in range(60):
        d = ex.roll_discovery(_world(), _loc(danger=4), 3, random.Random(s))
        if d and d.get("item_id"):
            assert not is_unique(d["item_id"]), d["item_id"]


def test_rng_de_chegada_e_estavel():
    a = ex.arrival_rng("game", "loc", 7).random()
    b = ex.arrival_rng("game", "loc", 7).random()
    assert a == b


# --- R3/R4: baú curado one-shot ---------------------------------------------

def test_bau_curado_concede_uma_vez():
    player = {"inventory": [], "gold": 0, "level": 2}
    world = _world()
    loc = _loc(treasure={"gold": 40, "items": ["pocao_cura_maior"]})
    note, _ = ex.discover_on_arrival(player, world, loc, 2, random.Random(0))
    assert note and "baú" in note.lower() or "esconderijo" in note.lower()
    assert player["gold"] == 40
    assert any((i.get("id") if isinstance(i, dict) else i) == "pocao_cura_maior"
               for i in player["inventory"])
    assert "pm_profundezas" in world["looted_locations"]
    # 2ª chegada → nada (já saqueado)
    p2 = {"inventory": [], "gold": 0, "level": 2}
    note2, _ = ex.discover_on_arrival(p2, world, loc, 2, random.Random(0))
    assert note2 == "" or "baú" not in note2.lower()
    assert p2["gold"] == 0


def test_resolve_treasure_ja_saqueado_none():
    world = _world(looted=["pm_profundezas"])
    loc = _loc(treasure={"gold": 40, "items": []})
    assert ex.resolve_treasure(world, loc) is None


def test_unico_escondido_respeita_claim():
    unique = "art_adaga_vidro_dragao"
    projection = {"unique_items": {unique: {"holder": "player"}}}
    player = {"inventory": [], "gold": 0}
    world = _world()
    loc = _loc(treasure={"gold": 0, "items": [unique]})
    _, events = ex.discover_on_arrival(
        player, world, loc, 2, random.Random(0), projection=projection)
    assert player["inventory"] == []
    assert events == []
    assert "pm_profundezas" in world["looted_locations"]


def test_unico_escondido_livre_gera_claim():
    unique = "art_adaga_vidro_dragao"
    player = {"inventory": [], "gold": 0}
    world = _world()
    loc = _loc(treasure={"gold": 0, "items": [unique]})
    _, events = ex.discover_on_arrival(player, world, loc, 2, random.Random(0))
    assert any(item.get("id") == unique for item in player["inventory"])
    assert events and events[0]["type"] == "unique_item_claimed"


def test_sem_treasure_none():
    assert ex.resolve_treasure(_world(), _loc()) is None


# --- R5: item entra pelo caminho canônico (sem item fantasma) ----------------

def test_item_entra_no_inventario_do_estado():
    player = {"inventory": [], "gold": 0}
    world = _world()
    loc = _loc(treasure={"gold": 0, "items": ["espada_curta"]})
    ex.discover_on_arrival(player, world, loc, 1, random.Random(0))
    ids = [(i.get("id") if isinstance(i, dict) else i) for i in player["inventory"]]
    assert "espada_curta" in ids
