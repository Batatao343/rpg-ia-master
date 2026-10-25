"""SPEC-312 Etapa 2: nascimento no motor (hook diario)."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from services import rumors
from services import world_engine as we
from services import world_pressures as wp
from tests.spec312_helpers import base_state, run_hook, walk


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _ids(cands):
    return {s["seed_id"] for s, _w in cands}


def test_frequented_regions_window():
    sim = {"region_presence": {"brekmar": 31, "nova_arcadia": 17, "skallgard": 10}}
    assert rumors.frequented_regions(sim, 31) == ["brekmar", "nova_arcadia"]
    assert "skallgard" not in rumors.frequented_regions(sim, 31)
    assert "skallgard" in rumors.frequented_regions(sim, 24)


def test_hook_records_presence_of_current_region():
    sim: dict = {}
    run_hook(sim, 7, loc="brekmar")
    assert sim["region_presence"]["brekmar"] == 7


def test_birth_rate_per_frequented_region():
    sim, items = walk(600)
    # heroi parado: 1 regiao frequentada -> ~0,5/dia (menos o esgotamento por cooldown)
    assert 0.38 <= len(items) / 600 <= 0.56


def test_rng_stream_independent_of_frequented_set():
    sim1: dict = {"region_presence": {"nova_arcadia": 5}}
    sim2: dict = {"region_presence": {"nova_arcadia": 5, "brekmar": 5, "skallgard": 4}}
    r1 = run_hook(sim1, 5)
    r2 = run_hook(sim2, 5)
    nova1 = [i for i in r1.digest if i["region_id"] == "nova_arcadia"]
    nova2 = [i for i in r2.digest if i["region_id"] == "nova_arcadia"]
    assert [i["subject_id"] for i in nova1] == [i["subject_id"] for i in nova2]


def test_candidates_exclude_active_perceived_cooldown_dead():
    lore = "rumor_os_navios_de_durrak_atraem_o_fundo"
    assert lore in _ids(rumors.candidates(base_state(), {}, "brekmar", 10))
    sim = {"rumors": [{"rumor_id": "x", "seed_id": lore, "expires_day": 15}]}
    assert lore not in _ids(rumors.candidates(base_state(), sim, "brekmar", 10))
    sim = {"rumor_seed_last_born": {lore: 0}}
    assert lore not in _ids(rumors.candidates(base_state(), sim, "brekmar", 20))
    assert lore in _ids(rumors.candidates(base_state(), sim, "brekmar", 40))
    sim = {"rumor_seed_last_born": {lore: rumors.NEVER_AGAIN}}
    assert lore not in _ids(rumors.candidates(base_state(), sim, "brekmar", 999))
    st = base_state(world_projection={"entities": {"npc_durrak": {"alive": False}}})
    assert lore not in _ids(rumors.candidates(st, {}, "brekmar", 10))


def test_secret_signature_blocks_candidate(monkeypatch):
    import services.memory_provenance as mp

    monkeypatch.setattr(
        mp,
        "find_strict_unrevealed",
        lambda text, state: "sec" if "estaleiro" in text.lower() else None,
    )
    got = _ids(rumors.candidates(base_state(), {}, "brekmar", 10))
    assert "rumor_os_navios_de_durrak_atraem_o_fundo" not in got


def test_avistamento_truth_regional():
    cands = rumors.candidates(base_state(), {}, "skallgard", 10)
    avist = [(s, w) for s, w in cands if s["family"] == "avistamento"]
    own = [s for s, _ in avist if "skallgard" in s["regions"]]
    adj = [s for s, _ in avist if "skallgard" not in s["regions"]]
    assert own and adj
    assert all(s["_truth"] is True for s in own)
    assert all(s["_truth"] is False for s in adj)
    w_adj = sum(w for s, w in avist if "skallgard" not in s["regions"])
    assert w_adj / sum(w for _s, w in avist) == pytest.approx(
        rumors.const("AVISTAMENTO_FALSE_P"), abs=0.01
    )


def test_instance_ids_deterministic_and_ttl():
    s1, i1 = walk(40, game_id="same")
    s2, i2 = walk(40, game_id="same")
    assert [r["rumor_id"] for r in s1["rumors"]] == [r["rumor_id"] for r in s2["rumors"]]
    assert i1 == i2
    for r in s1["rumors"]:
        assert r["expires_day"] == r["born_day"] + 10 and r["perceived_day"] == 0
        assert len(r["rumor_id"]) == 16
    item = i1[-1]
    assert item["kind"] == "rumor" and item["template_id"].startswith("rumor.")
    assert item["subject_id"] in {r["rumor_id"] for r in s1["rumors"]}


def _row(n, expires, perceived=0):
    return {
        "rumor_id": f"r{n}",
        "seed_id": f"s{n}",
        "born_day": n,
        "expires_day": expires,
        "perceived_day": perceived,
    }


def test_ledger_cap_never_drops_active_perceived():
    # 45 expirados recentes (idade 3 dias): o teto despeja primeiro os nao percebidos
    sim = {"rumors": [_row(n, 105, n if n % 2 else 0) for n in range(45)]}
    rumors._cap_ledger(sim, 108)
    assert len(sim["rumors"]) == 40
    assert sum(1 for r in sim["rumors"] if r["perceived_day"]) == 22  # nenhum percebido saiu
    # ativos (nao expirados) nunca saem, mesmo acima do teto
    sim2 = {"rumors": [_row(n, 999, 1) for n in range(45)]}
    rumors._cap_ledger(sim2, 100)
    assert len(sim2["rumors"]) == 45
    # velho demais sai e a semente percebida da lore nunca mais nasce
    old = _row(50, 3, 2)
    sim3 = {"rumors": [_row(1, 999, 1), old]}
    rumors._cap_ledger(sim3, 100)
    assert [r["rumor_id"] for r in sim3["rumors"]] == ["r1"]
    assert sim3["rumor_seed_last_born"]["s50"] == rumors.NEVER_AGAIN


def test_stale_unperceived_instance_and_old_cooldown_are_forgotten():
    sim = {
        "rumors": [_row(1, 50)],
        "rumor_seed_last_born": {"s1": 40, "velho": 1, "perceived": rumors.NEVER_AGAIN},
    }
    rumors._cap_ledger(sim, 60)
    assert sim["rumors"] == []
    assert (
        set(sim["rumor_seed_last_born"]) == {"s1", "perceived"}
        or "velho" not in sim["rumor_seed_last_born"]
    )


def test_independent_of_player_stats():
    def run(level):
        sim: dict = {}
        out = []
        for d in range(1, 30):
            st = base_state(d, player={"level": level, "gold": level * 1000, "name": "X"})
            st["world_sim"] = sim
            out += [i["subject_id"] for i in run_hook(sim, d, state=st).digest]
        return out

    assert run(1) == run(20)


def test_no_global_random_in_rumors():
    tree = ast.parse(Path(rumors.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name != "random" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "random"


FORBIDDEN = {"event_log", "pending_world_events", "world_projection", "memory_facts", "quests"}


def test_rumor_module_never_writes_event_log_projection_memory_quests():
    tree = ast.parse(Path(rumors.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            key = node.slice
            assert not (isinstance(key, ast.Constant) and key.value in FORBIDDEN)
        if isinstance(node, ast.Dict):
            for k in node.keys:
                assert not (isinstance(k, ast.Constant) and k.value in FORBIDDEN)
        if isinstance(node, ast.keyword):
            assert node.arg not in FORBIDDEN
    st = base_state()
    before = copy.deepcopy(st)
    sim: dict = {}
    res = run_hook(sim, 5, state=st)
    assert st == before and not res.events and not res.pressure_deltas and not res.state_patch


def test_shadow_writes_nothing(monkeypatch):
    monkeypatch.setenv("RPG_RUMORS", "shadow")
    sim: dict = {}
    for d in range(1, 40):
        assert run_hook(sim, d).digest == []
    assert not sim.get("rumors") and not sim.get("rumor_seed_last_born")


def test_requires_world_engine_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    assert rumors.mode() == "off"
    sim: dict = {}
    assert run_hook(sim, 3).digest == [] and not sim
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "off")
    assert rumors.mode() == "off"


def test_exhausted_region_gives_no_digest(monkeypatch):
    sim = {"region_presence": {"ophidia": 5}}
    monkeypatch.setattr(rumors, "candidates", lambda *a, **k: [])
    assert run_hook(sim, 5, loc="ophidia").digest == []


def test_trim_digest_drops_rumors_before_crisis():
    rum = [{"kind": "rumor", "item_id": f"r{i}"} for i in range(5)]
    cri = [{"kind": "crise", "item_id": f"c{i}"} for i in range(18)]
    out = rumors.trim_digest(rum + cri, 20)
    assert len(out) == 20
    assert sum(1 for i in out if i["kind"] == "crise") == 18


def test_birth_location_is_noninterior_in_region():
    locs = wp._map_index()[0]
    sim, _ = walk(60, route=lambda d: "brekmar")
    assert sim["rumors"]
    for r in sim["rumors"]:
        loc = locs[r["location_id"]]
        assert loc["region_id"] == r["region_id"] and not loc.get("parent_id")


def test_engine_registers_hook_and_ticks_rumors():
    # integracao: advance_days roda o hook e o digest guarda rumores
    from tests.spec312_helpers import world_at

    st = base_state(1)
    sim_key = "world_sim"
    digest: list = []
    for d in range(2, 25):
        res = we.advance_days(st, world_at(d - 1), world_at(d), [], {})
        st[sim_key] = res.world_sim
        st["world"] = res.world
        digest += res.digest
    sim = st[sim_key]
    assert sim["rumors"] and sim["region_presence"]["nova_arcadia"] == 24
    assert any(i["kind"] == "rumor" for i in digest)
