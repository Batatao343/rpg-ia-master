"""
Fase 6.3 — Migração de monstros: população reage à caça e ao poder.
Spec: specs/fase-6.3-migracao-de-monstros.md. 100% offline, zero estado novo.
"""
import random

import pytest

import world_utils as wu
from gamedata import BESTIARY
from services import ecology as eco3
from services import graph_resolver as gr

RATO = "enemy_rato_peste_anel_lama"  # minion de nova_arcadia (bestiário real)


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


def _bk(kills, last_turn):
    return {RATO: {"seen": kills, "fought": kills, "defeated": kills,
                   "first_seen_turn": 1, "last_update_turn": last_turn}}


# ---------------------------------------------------------------------------
# Etapa 1 — ecology puro
# ---------------------------------------------------------------------------

def test_pressure_faixas():
    assert eco3.hunt_pressure(RATO, _bk(0, 10), 10) == 1.0
    assert eco3.hunt_pressure(RATO, _bk(2, 10), 10) == 0.6
    assert eco3.hunt_pressure(RATO, _bk(4, 10), 10) == 0.3
    assert eco3.hunt_pressure(RATO, _bk(7, 10), 10) == 0.1
    assert eco3.hunt_pressure(RATO, None, 10) == 1.0


def test_decay_janela():
    # kills quentes (mesmo turno) contam cheio
    assert eco3.hunt_pressure(RATO, _bk(6, 30), 30) == 0.1
    # 11-20 turnos atrás: metade (6*0.5=3 -> 0.3)
    assert eco3.hunt_pressure(RATO, _bk(6, 15), 30) == 0.3
    # >20 turnos: população voltou
    assert eco3.hunt_pressure(RATO, _bk(6, 5), 30) == 1.0


def test_faction_boost():
    enemy = {"id": "x", "faction": "mao_sombria"}
    proj = {"dynamic_edges": [{"id": "d", "source": "mao_sombria",
                               "type": "controls", "target": "na_anel_lama",
                               "created_by_event": "e"}]}
    assert eco3.faction_boost(enemy, "na_anel_lama", proj) == eco3.FACTION_BOOST
    assert eco3.faction_boost(enemy, "na_anel_lama", {}) in (1.0, eco3.FACTION_BOOST)
    assert eco3.faction_boost({"id": "y"}, "na_anel_lama", proj) == 1.0


def test_weighted_pick_rng_semeado():
    rng = random.Random(42)
    a, b = {"id": "a"}, {"id": "b"}
    picks = [eco3.weighted_pick([a, b], [0.1, 1.0], rng)["id"] for _ in range(200)]
    assert picks.count("b") > picks.count("a") * 3
    assert eco3.weighted_pick([a], [0], rng) is None


# ---------------------------------------------------------------------------
# Etapa 2 — sorteio integrado
# ---------------------------------------------------------------------------

def _loc_nova():
    from gamedata import get_location
    return get_location("na_anel_lama") or get_location("nova_arcadia")


def test_sem_dados_comportamento_legado():
    loc = _loc_nova()
    e1 = wu.pick_encounter_enemy(loc, 1, turn=3)
    e2 = wu.pick_encounter_enemy(loc, 1, turn=3)
    assert e1 == e2  # determinístico round-robin


def test_pick_respeita_pressao():
    loc = _loc_nova()
    bk = _bk(7, 20)  # rato quase extinto
    rng = random.Random(7)
    picks = [wu.pick_encounter_enemy(loc, 1, turn=20, bestiary_knowledge=bk,
                                     projection={}, rng=rng)
             for _ in range(200)]
    ids = [p["id"] for p in picks if p]
    assert ids, "sorteio vazio"
    ratio = ids.count(RATO) / len(ids)
    assert ratio < 0.25, f"rato caçado demais ainda domina ({ratio:.0%})"


def test_migrante_de_regiao_conectada():
    loc = _loc_nova()
    migrants = eco3.migrant_candidates(loc, BESTIARY, {})
    for m in migrants:
        assert loc.get("region_id") not in (m.get("regions") or [])
        assert "BOSS" not in str(m.get("type", "")).upper()


def test_rota_bloqueada_barra_migrante():
    from gamedata import get_location
    loc = _loc_nova()
    conns = loc.get("connections") or []
    proj = {"blocked_routes": [{"a": loc["id"], "b": c, "blocked_by_event": "e"}
                               for c in conns]}
    assert eco3.migrant_candidates(loc, BESTIARY, proj) == []


# ---------------------------------------------------------------------------
# Etapa 3 — loot suprimido
# ---------------------------------------------------------------------------

def test_loot_some_com_extincao_local_e_volta():
    from services import economy as eco
    # criatura com loot na região: acha uma no bestiário real
    alvo = next((e for e in BESTIARY.values()
                 if e.get("loot") and e.get("regions")), None)
    assert alvo, "bestiário sem criatura com loot"
    region = alvo["regions"][0]
    bk = {alvo["id"]: {"defeated": 7, "last_update_turn": 50}}
    supp = eco3.suppressed_loot(region, BESTIARY, bk, 50)
    assert set(alvo["loot"]) <= supp
    # decay -> volta
    assert eco3.suppressed_loot(region, BESTIARY, bk, 100) == set()


# ---------------------------------------------------------------------------
# Etapa 4 — visibilidade (Codex 3.2)
# ---------------------------------------------------------------------------

def test_codex_mostra_raridade():
    from services.discovery import bestiary_view
    bk = _bk(7, 20)
    view = bestiary_view(bk, turn=20)
    entry = next(v for v in view if v["id"] == RATO)
    assert "rarity_note" in entry
    # sem pressão -> sem nota
    view2 = bestiary_view(_bk(1, 1), turn=50)
    entry2 = next(v for v in view2 if v["id"] == RATO)
    assert "rarity_note" not in entry2


def test_rotulo_faixas():
    assert eco3.regional_rarity_label(RATO, _bk(7, 20), 20) == "quase não se vê mais por aqui"
    assert eco3.regional_rarity_label(RATO, _bk(4, 20), 20) == "cada vez mais rara na região"
    assert eco3.regional_rarity_label(RATO, None, 20) == ""
