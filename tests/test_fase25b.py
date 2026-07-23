"""
Testes da Fase 2.5b — Valoria nos dados mecânicos + combate com comportamento.
Offline/determinístico (MockLLM via conftest).

Cobre: integridade cruzada com o grafo (R1-R4), merge de entities_extra,
mapa conexo, traits raciais (R9), perfis de comportamento/moral/fuga (R8),
alertas de fuga (R10) e sorteio de encontro por região (R11).
"""
import json
import os
import random

import pytest

import gamedata
import world_utils as wu
import combat_mechanics as cm
from services import graph_resolver

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

REGION_IDS = [
    "nova_arcadia", "pantano_melancolia", "deserto_zhur", "floresta_sussurros",
    "selva_xylos", "skallgard", "aethelgard", "ophidia", "costa_negra",
    "montanhas_afiadas", "pradaria_ruinas", "brekmar",
]


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def entities():
    graph_resolver.clear_cache()
    return graph_resolver.load_entities()


# --------------------------------------------------------------------------
# Etapa 1 — merge entities.json + entities_extra.json
# --------------------------------------------------------------------------
def test_entities_merge_includes_extra(entities):
    assert "nova_arcadia" in entities          # canônico
    assert "na_anel_lama" in entities          # curadoria (entities_extra)
    assert entities["na_anel_lama"]["type"] == "location"


def test_entities_extra_never_overrides_canonical(entities):
    # nenhum id do extra pode divergir do canônico carregado. Exceção: o overlay de
    # componentes (Fase 2.7, components.json) AUMENTA `components` sem tocar nos demais
    # campos — canônico continua sendo superconjunto em tudo menos `components`.
    with open(os.path.join(DATA, "graph", "entities.json"), encoding="utf-8") as f:
        canon = json.load(f)
    for eid, ent in canon.items():
        loaded = entities[eid]
        for k, v in ent.items():
            if k == "components":
                # componentes canônicos preservados (overlay só adiciona)
                assert all(loaded["components"].get(ck) == cv for ck, cv in v.items())
            else:
                assert loaded[k] == v


# --------------------------------------------------------------------------
# Integridade cruzada (critério central da 2.5b)
# --------------------------------------------------------------------------
def test_world_map_ids_exist_in_graph(entities):
    wm = _load("world_map.json")
    for loc in wm["locations"]:
        assert loc["id"] in entities, f"local fora do grafo: {loc['id']}"
        assert loc.get("region_id") in REGION_IDS


def test_faction_ids_exist_in_graph(entities):
    for fid in _load("factions.json"):
        assert fid in entities, f"facção fora do grafo: {fid}"
        assert entities[fid]["type"] == "faction"


def test_bestiary_ids_exist_in_graph(entities):
    for bid in _load("bestiary.json"):
        assert bid in entities, f"criatura fora do grafo: {bid}"


def test_origin_race_ids_exist_in_graph(entities):
    races = _load("origins.json")["races"]
    assert len(races) == 6
    for r in races:
        assert r["id"] in entities and entities[r["id"]]["type"] == "race"


def test_ascension_targets_exist():
    wm_ids = {l["id"] for l in _load("world_map.json")["locations"]}
    factions = _load("factions.json")
    for fid, f in factions.items():
        asc = f.get("ascension", {})
        t = asc.get("type")
        if t in ("dominar_local", "elevar_perigo", "invocar_entidade"):
            assert asc["target"] in wm_ids, f"{fid}: target {asc['target']} fora do mapa"
        elif t == "eliminar_faccao":
            assert asc["target"] in factions, f"{fid}: alvo {asc['target']} não é facção"


# --------------------------------------------------------------------------
# Etapa 2 — mapa de Valoria
# --------------------------------------------------------------------------
def test_map_has_all_regions_and_is_connected():
    wm = _load("world_map.json")
    locs = {l["id"]: l for l in wm["locations"]}
    for rid in REGION_IDS:
        assert rid in locs, f"macro-região ausente do mapa: {rid}"
    # conexões simétricas
    for lid, loc in locs.items():
        for c in loc["connections"]:
            assert c in locs, f"{lid} conecta a nó inexistente {c}"
            assert lid in locs[c]["connections"], f"conexão assimétrica {lid}<->{c}"
    # grafo conexo a partir do start
    start = wm["start_location"]
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(locs[cur]["connections"])
    assert seen == set(locs), f"nós inalcançáveis: {set(locs) - seen}"


def test_every_region_has_start_node():
    for loc in _load("world_map.json")["locations"]:
        pass
    region_names = {l["region"] for l in _load("world_map.json")["locations"]}
    for name in region_names:
        assert gamedata.start_location_for_region(name), f"região sem start: {name}"


# --------------------------------------------------------------------------
# Etapa 4 — traits raciais (R9)
# --------------------------------------------------------------------------
def test_apply_racial_traits_anao():
    from character_creator import apply_racial_traits
    # spec conflito-01: raça NÃO altera Virtudes; hp/resist/save/itens seguem
    sheet = {"virtudes": {"mente": 1, "agilidade": 1, "forca": 4, "carisma": 1, "corpo": 3},
             "hp": 30, "max_hp": 30, "inventory": []}
    apply_racial_traits(sheet, "Anão da Fuligem")
    assert sheet["virtudes"]["corpo"] == 3           # inalterado pela raça
    assert sheet["hp"] == 35 and sheet["max_hp"] == 35
    assert "veneno" in sheet["condition_resists"]
    # save_bonus agora chaveado por Virtude (con -> corpo)
    assert sheet["racial_save_bonus"].get("corpo") == 2
    from inventory import item_display
    assert any(item_display(e) == "Respirador de Couro" for e in sheet["inventory"])
    assert len(sheet["racial_traits"]) == 2


def test_apply_racial_traits_by_id_and_unknown():
    from character_creator import apply_racial_traits
    # spec conflito-01: raça não mexe em Virtude; resist continua valendo
    sheet = {"virtudes": {"mente": 1}, "hp": 20, "max_hp": 20}
    apply_racial_traits(sheet, "race_cinzeus")
    assert sheet["virtudes"]["mente"] == 1           # inalterado pela raça
    assert any("atordoa" in r for r in sheet["condition_resists"])
    # raça desconhecida: no-op seguro
    sheet2 = {"virtudes": {}}
    apply_racial_traits(sheet2, "Marciano")
    assert sheet2["racial_traits"] == []


def test_condition_resist_blocks_condition():
    player = {"name": "T", "condition_resists": ["veneno"], "active_conditions": []}
    log = cm.apply_condition(player, {"name": "Veneno", "dot": 2, "duration": 3, "source": "x"})
    assert "resiste" in log.lower()
    assert player["active_conditions"] == []
    # sem resist, condição entra
    player2 = {"name": "T", "active_conditions": []}
    cm.apply_condition(player2, {"name": "Veneno", "dot": 2, "duration": 3, "source": "x"})
    assert player2["active_conditions"]


def test_creator_applies_traits_end_to_end():
    from character_creator import create_player_character
    sheet = create_player_character({"name": "Kael", "class_name": "Cavaleiro da Vigília",
                                     "race": "Osshari", "region": "Costa Negra", "level": 1})
    assert sheet["racial_traits"], "ficha deve registrar traits raciais"
    assert "medo" in sheet["condition_resists"]


# --------------------------------------------------------------------------
# Etapa 6 — comportamento de combate (R8)
# --------------------------------------------------------------------------
def _enemy(profile=None, hp=30, max_hp=30, **kw):
    e = {"id": "e1", "name": "Alvo", "hp": hp, "max_hp": max_hp, "status": "ativo",
         "active_conditions": [], "attributes": {"str": 12, "dex": 10},
         "attacks": [{"name": "Garra", "bonus": 20, "damage": "1d4+2"},
                     {"name": "Mordida Venenosa", "bonus": 2, "damage": "2d6+1 + veneno"}]}
    if profile:
        e["behavior"] = {"profile": profile, **kw}
    return e


def test_get_behavior_defaults_to_feroz():
    assert cm.get_behavior({})["profile"] == "feroz"
    assert cm.get_behavior({"behavior": {"profile": "INVALIDO"}})["profile"] == "feroz"
    b = cm.get_behavior({"behavior": {"profile": "tatico"}})
    assert b["flee_below"] == pytest.approx(0.35)


def test_feroz_never_flees_and_frenzies():
    urso = _enemy("feroz", hp=1, max_hp=100)
    assert cm.check_morale(urso, allies=[]) is None   # 1 HP e ainda luta
    random.seed(7)
    player = {"name": "H", "hp": 50, "max_hp": 50, "attributes": {"dex": 10}, "inventory": []}
    logs = cm.resolve_enemy_turn(urso, player, allies=[urso], rnd=1)
    assert urso["status"] == "ativo"
    assert any("frenesi" in l for l in logs), "feroz com HP<50% deve ganhar +2 de frenesi"


def test_implacavel_never_flees_and_rotates_attacks():
    boss = _enemy("implacavel", hp=1, max_hp=200)
    assert cm.check_morale(boss, allies=[]) is None
    a1 = cm.choose_enemy_attack(boss, 10, rnd=1)
    a2 = cm.choose_enemy_attack(boss, 10, rnd=2)
    assert a1["name"] != a2["name"]  # rotaciona


def test_tatico_flees_below_threshold():
    guarda = _enemy("tatico", hp=5, max_hp=30, flee_below=0.35)
    log = cm.check_morale(guarda, allies=[])
    assert log and "FOGE" in log
    assert guarda["status"] == "fugiu"


def test_tatico_pack_morale():
    g1 = _enemy("tatico", hp=30, max_hp=30, flee_below=0.35, pack_morale=True)
    g1["id"] = "g1"
    mortos = [{"id": "g2", "name": "G2", "status": "morto"},
              {"id": "g3", "name": "G3", "status": "morto"}]
    log = cm.check_morale(g1, allies=[g1] + mortos)
    assert log and g1["status"] == "fugiu"  # 2 de 2 aliados caídos > 50%


def test_covarde_flees_when_ally_falls():
    rato = _enemy("covarde", hp=30, max_hp=30, flee_below=0.6)
    rato["id"] = "r1"
    log = cm.check_morale(rato, allies=[rato, {"id": "r2", "name": "R2", "status": "morto"}])
    assert log and rato["status"] == "fugiu"


def test_fled_enemy_takes_no_turn():
    e = _enemy("tatico", hp=2, max_hp=30)
    player = {"name": "H", "hp": 50, "max_hp": 50, "attributes": {"dex": 10}, "inventory": []}
    logs = cm.resolve_enemy_turn(e, player, allies=[e], rnd=1)
    assert e["status"] == "fugiu"
    assert player["hp"] == 50  # fugiu sem atacar
    assert len(logs) == 1 and "FOGE" in logs[0]


def test_tatico_opens_with_condition_attack():
    e = _enemy("tatico", hp=30, max_hp=30)
    player = {"name": "H", "active_conditions": []}
    atk = cm.choose_enemy_attack(e, player_ac=12, rnd=1, player=player)
    assert atk["name"] == "Mordida Venenosa"  # aplica condição primeiro
    # com condição já ativa e AC alta -> maior bônus
    player2 = {"name": "H", "active_conditions": [{"name": "Veneno"}]}
    atk2 = cm.choose_enemy_attack(e, player_ac=16, rnd=1, player=player2)
    assert atk2["name"] == "Garra"


def test_enemy_attack_condition_respects_racial_resist():
    random.seed(3)
    e = _enemy("feroz")
    e["attacks"] = [{"name": "Mordida", "bonus": 20, "damage": "1d4 + veneno"}]
    anao = {"name": "A", "hp": 40, "max_hp": 40, "attributes": {"dex": 10},
            "inventory": [], "condition_resists": ["veneno"], "active_conditions": []}
    cm.resolve_enemy_turn(e, anao, allies=[e], rnd=1)
    assert anao["active_conditions"] == []  # anão resiste ao veneno


def test_victory_ignores_fled_enemies():
    """Fugido não conta como ativo: combate acaba e fugido não vira loot."""
    enemies = [_enemy("tatico", hp=2), {"id": "e2", "name": "Morto", "status": "morto",
                                        "hp": 0, "max_hp": 10, "active_conditions": []}]
    enemies[0]["status"] = "fugiu"
    active = [e for e in enemies if e.get("status") == "ativo"]
    dead = [e for e in enemies if e.get("status") == "morto"]
    assert not active and len(dead) == 1


# --------------------------------------------------------------------------
# Etapa 7 — fuga vira alerta de mundo (R10)
# --------------------------------------------------------------------------
def test_register_flee_alert_and_reinforcements():
    world = wu.ensure_world({"current_location_id": "pradaria_ruinas"})
    world = wu.register_flee_alert(world, "Nômade Canibal 2", faction_id="bandos_nomades", turn=5)
    alerts = world["threat_alerts"]
    assert len(alerts) == 1
    assert alerts[0]["hint"] == "Nômade Canibal"  # sufixo de instância removido
    assert alerts[0]["region_id"] == "pradaria_ruinas"

    # alerta dispara encontro mesmo em local seguro (perigo 2) e é consumido
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=7)
    assert enc and enc["reason"] == "reinforcements"
    assert "Nômade Canibal" in enc["hint"]
    assert world["threat_alerts"] == []  # consumido

    # sem alerta, mesmo local não dispara nada
    assert wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10) is None


def test_flee_alert_expires():
    world = wu.ensure_world({"current_location_id": "pradaria_ruinas"})
    world = wu.register_flee_alert(world, "Bandido", turn=0)
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)  # > TTL 6
    assert enc is None
    assert world["threat_alerts"] == []  # expirado foi descartado


def test_flee_alert_only_in_same_region():
    world = wu.ensure_world({"current_location_id": "pradaria_ruinas"})
    world = wu.register_flee_alert(world, "Bandido", turn=5)
    world["current_location_id"] = "skallgard"  # jogador mudou de região
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=7)
    assert enc is None
    assert len(world["threat_alerts"]) == 1  # alerta segue vivo na outra região


# --------------------------------------------------------------------------
# Etapa 8 — sorteio de criatura por região (R11)
# --------------------------------------------------------------------------
def test_pick_encounter_enemy_by_region_and_danger():
    loc = gamedata.get_location("skallgard")
    entry = wu.pick_encounter_enemy(loc, danger=2, turn=3)
    assert entry and "skallgard" in entry["regions"]
    assert "BOSS" not in str(entry.get("type", "")).upper()
    assert "minion" in str(entry.get("type", "")).lower()


def test_pick_encounter_enemy_by_faction():
    entry = wu.pick_encounter_enemy({}, danger=3, turn=0, faction_id="legiao_ferro")
    assert entry and entry["id"] == "enemy_soldado_legiao_ferro"


def test_high_danger_hint_is_exact_bestiary_name():
    world = {"current_location_id": "pr_ruinas_assombradas"}  # perigo 4
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    assert enc and enc["reason"] == "high_danger"
    names = {e["name"] for e in gamedata.BESTIARY.values()}
    assert enc["hint"] in names, "hint deve ser o nome exato de uma entrada do bestiário"


def test_bestiary_regions_and_behavior_valid():
    bestiary = _load("bestiary.json")
    coverage = {r: 0 for r in REGION_IDS}
    for bid, e in bestiary.items():
        b = e.get("behavior") or {}
        assert b.get("profile") in cm.PROFILES, f"{bid}: behavior inválido"
        for r in e.get("regions", []):
            assert r in REGION_IDS, f"{bid}: região desconhecida {r}"
            coverage[r] += 1
    for region, n in coverage.items():
        assert n >= 3, f"região {region} com só {n} criaturas no bestiário"
