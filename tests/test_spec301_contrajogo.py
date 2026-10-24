"""SPEC-301 Etapa 3 — contra-jogo no relógio das fações (R13-R15)."""

from __future__ import annotations

import random

import world_utils as wu
from services import event_processor
from services import faction_membership as fm
from tests.spec301_support import faction, joined, make_state, merge


def _legacy_advance(factions, periods=1):
    """Cópia literal da função pré-SPEC-301 (oráculo do 'influence 0 = legado')."""
    factions = wu.ensure_factions(factions)
    periods = max(0, int(periods))
    if periods == 0:
        return factions, []
    new_list, events = [], []
    for f in factions:
        f = dict(f)
        if not f.get("completed", False) and not f.get("defeated", False):
            f["progress"] = min(100, f.get("progress", 0) + f.get("pace", 3) * periods)
            if f["progress"] >= 100 and not f.get("completed", False):
                f["completed"] = True
                events.append(
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "goal": f.get("goal", ""),
                        "disposition": f.get("disposition", "neutro"),
                    }
                )
        new_list.append(f)
    return new_list, events


def test_influence_zero_identico_ao_legado():
    rng = random.Random(301)
    for _ in range(50):
        rows = [
            {
                "id": f"f{i}",
                "name": f"F{i}",
                "progress": rng.randint(0, 100),
                "pace": rng.randint(0, 6),
                "completed": rng.random() < 0.1,
                "defeated": rng.random() < 0.1,
            }
            for i in range(4)
        ]
        periods = rng.randint(0, 6)
        new, ev = wu.advance_factions([dict(r) for r in rows], periods)
        old, old_ev = _legacy_advance([dict(r) for r in rows], periods)
        strip = lambda lst: [  # noqa: E731
            {k: v for k, v in f.items() if k not in ("influence", "influence_periods")} for f in lst
        ]
        assert strip(new) == strip(old)
        assert ev == old_ev


def test_pace_efetivo_por_influence():
    base = {"pace": 3, "influence": 0}
    assert wu.effective_pace(base) == 3
    assert wu.effective_pace({"pace": 3, "influence": 9}) == 6
    assert wu.effective_pace({"pace": 3, "influence": -9}) == 0
    assert wu.effective_pace({"pace": 1, "influence": -9}) == 0  # piso 0
    assert wu.effective_pace({"pace": 3, "influence": 2}) == 3  # abaixo de 3 não muda
    assert wu.effective_pace({"pace": 3, "influence": -2}) == 3
    assert wu.effective_pace({"pace": 3, "influence": 99}) == 6  # clamp +-9


def test_advance_usa_pace_efetivo():
    rows = [{"id": "a", "name": "A", "progress": 0, "pace": 3, "influence": 3}]
    out, _ = wu.advance_factions(rows, 1)
    assert out[0]["progress"] == 4


def test_decadencia_a_cada_4_periodos():
    rows = [{"id": "a", "name": "A", "progress": 0, "pace": 3, "influence": 3}]
    out, _ = wu.advance_factions(rows, 3)
    assert out[0]["influence"] == 3 and out[0]["influence_periods"] == 3
    out, _ = wu.advance_factions(out, 1)
    assert out[0]["influence"] == 2 and out[0]["influence_periods"] == 0
    neg = [{"id": "b", "name": "B", "progress": 0, "pace": 3, "influence": -3}]
    out, _ = wu.advance_factions(neg, 8)
    assert out[0]["influence"] == -1
    # chega a 0 e para (sem cruzar o sinal), e o acumulador zera
    out, _ = wu.advance_factions([{"id": "c", "progress": 0, "pace": 3, "influence": 1}], 12)
    assert out[0]["influence"] == 0 and out[0]["influence_periods"] == 0


def test_ensure_factions_backfill_influence():
    out = wu.ensure_factions([{"id": "a", "name": "A"}])
    assert out[0]["influence"] == 0 and out[0]["influence_periods"] == 0
    # saves antigos (seed sem o campo) também
    st = make_state()
    assert all("influence" in f for f in wu.ensure_factions(st["factions"]))


def test_clamp_influence():
    assert wu.clamp_influence(99) == 9 and wu.clamp_influence(-99) == -9
    assert wu.clamp_influence("x") == 0


def _state_with_deed(direction="ajudou", fid="legiao_ferro"):
    st = make_state()
    st["faction_intel"][fid] = {"known": True}
    st["npcs"]["Thrace"] = {
        "id": "npc_comandante_thrace",
        "name": "Thrace",
        "in_scene": True,
        "relationship": 5,
        "faction_id": fid,
    }
    st["pending_world_events"] = [
        {
            "type": "faction_deed",
            "actor_id": "player",
            "target_id": fid,
            "payload": {
                "direction": direction,
                "magnitude": "menor",
                "location_id": "na_anel_ferro",
            },
            "source": "storyteller",
        }
    ]
    return st


def test_reputation_changed_move_influence_1():
    st = _state_with_deed("ajudou")
    out = event_processor.process_pending_events(st)
    assert faction(out, "legiao_ferro")["reputation"] > 0
    assert faction(out, "legiao_ferro")["influence"] == 1
    st = _state_with_deed("prejudicou")
    out = event_processor.process_pending_events(st)
    assert faction(out, "legiao_ferro")["influence"] == -1


def test_influencia_so_com_reputacao_aplicada():
    # Fação que não testemunhou (nenhum NPC em cena): proposta rejeitada/pendente,
    # reputação intacta => influência intacta.
    st = _state_with_deed("ajudou")
    st["npcs"] = {}
    st["world"]["current_location_id"] = "skallgard"
    out = event_processor.process_pending_events(st)
    f = faction({**st, **out}, "legiao_ferro")
    assert f["reputation"] == 0 and f.get("influence", 0) == 0


def test_bump_influence_clamp():
    rows = [{"id": "a", "influence": 9}, {"id": "b", "influence": -9}]
    assert fm.bump_influence(rows, "a", 1)[0]["influence"] == 9
    assert fm.bump_influence(rows, "b", -1)[1]["influence"] == -9


def test_prejudicar_a_propria_faccao_vira_ofensa():
    st = joined(_state_with_deed("prejudicou"))
    out = event_processor.process_pending_events(st)
    assert out["faction_membership"]["legiao_ferro"]["status"] == "suspeito"
    assert merge(st, out)["faction_membership"]["legiao_ferro"]["offenses"]
