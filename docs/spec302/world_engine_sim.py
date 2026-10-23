"""SPEC-302 R33: simulador offline de calibracao do motor de mundo (sem LLM).

Roda o MESMO `services.world_engine.advance_days` (modo `on`) por N dias x M seeds num
estado sintetico (heroi inerte: R5), devolve os eventos ao `event_log`/projection como o
arquivista faria (validando cada um) e mede as metas C1-C6.

Uso:  bash scripts/dev/py.sh docs/spec302/world_engine_sim.py [--days 120] [--seeds 20]
"""

from __future__ import annotations

import argparse
import copy
import os
import statistics
import sys

os.environ["RPG_WORLD_ENGINE"] = "on"
os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

EVAL_REGIONS = ("nova_arcadia", "brekmar", "pradaria_ruinas", "pantano_melancolia")


def run_campaign(seed: int, days: int = 120, *, check_validator: bool = True) -> dict:
    """Uma campanha sintetica. Devolve metricas brutas por dia."""
    import gamedata
    from services import world_engine as we
    from services import world_pressures as wp
    from services.event_processor import _build_event, apply_event
    from services.world_validators import validate_proposal

    state = {
        "game_id": f"sim-{seed}",
        "event_log": [],
        "world_projection": {},
        "factions": gamedata.seed_factions(),
        "quests": [],
        "world": {"world_clock": {"day": 1, "period": "Manhã"}, "turn_count": 0},
    }
    world = {"world_clock": {"day": 1, "period": "Manhã"}, "turn_count": 0}
    factions = state["factions"]
    started: dict[str, dict] = {}
    digest_days: list[dict] = []
    active_per_day: list[list[dict]] = []
    invalid: list[tuple[str, str]] = []
    max_sim_bytes = 0
    for day in range(2, days + 2):
        before = copy.deepcopy(world)
        world = copy.deepcopy(world)
        world["world_clock"] = {"day": day, "period": "Manhã"}
        world["turn_count"] = day
        state["world"] = world
        res = we.advance_days(state, before, world, factions, {})
        world, factions = res.world, res.factions
        state["factions"] = factions
        state["world"] = world
        state[res.sim_key] = res.world_sim
        digest_days += res.digest
        for ev in res.pending_events:
            if check_validator:
                v = validate_proposal(ev, state)
                if not v.ok:
                    invalid.append((ev["type"], v.reason))
                    continue
            built = _build_event(ev, day)
            state["event_log"].append(built)
            state["world_projection"] = apply_event(built, state["world_projection"])
        sim = res.world_sim or {}
        for c in sim.get("crises", []):
            if c.get("start_day") is not None:
                started.setdefault(c["crisis_id"], dict(c))
                started[c["crisis_id"]].update(c)
        act = [
            c
            for c in sim.get("crises", [])
            if c.get("start_day") is not None and c.get("end_day") is None
        ]
        active_per_day.append([{"region_id": c["region_id"], "kind": c["kind"]} for c in act])
        max_sim_bytes = max(max_sim_bytes, len(repr(sim)))
    return {
        "days": days,
        "crises": list(started.values()),
        "digest": digest_days,
        "active_per_day": active_per_day,
        "invalid_events": invalid,
        "projection": state["world_projection"],
        "sim": state.get("world_sim") or {},
        "max_sim_bytes": max_sim_bytes,
        "adjacency": wp.region_adjacency(),
    }


def _intervals(days_sorted: list[int]) -> list[int]:
    return [b - a for a, b in zip(days_sorted, days_sorted[1:], strict=False)]


def evaluate(seeds: int = 20, days: int = 120) -> dict:
    from services import world_pressures as wp

    cfg = wp.get_config()
    maxc = int(cfg["director"]["MAX_ACTIVE_CRISES"])
    minw = int(cfg["director"]["MIN_WARNING_DAYS"])
    c1: dict[str, list[int]] = {r: [] for r in EVAL_REGIONS}
    c2: dict[str, list[int]] = {r: [] for r in EVAL_REGIONS}
    c3_ok = True
    c4_world: list[float] = []
    c4_region_max: list[float] = []
    c5_ok = True
    c6_bad: list[str] = []
    invalid: list = []
    max_bytes = 0
    for seed in range(1, seeds + 1):
        out = run_campaign(seed, days)
        adj = out["adjacency"]
        invalid += out["invalid_events"]
        max_bytes = max(max_bytes, out["max_sim_bytes"])
        for r in EVAL_REGIONS:
            near = {r, *adj.get(r, [])}
            starts = sorted(c["start_day"] for c in out["crises"] if c["region_id"] in near)
            c1[r] += _intervals(starts)
            sig_days = sorted({d["day"] for d in out["digest"] if d["region_id"] == r})
            c2[r] += _intervals(sig_days)
        apd = out["active_per_day"]
        c3_ok &= all(len(a) <= maxc for a in apd)
        c4_world.append(sum(1 for a in apd if a) / len(apd))
        reg_frac = {}
        for a in apd:
            for reg in {x["region_id"] for x in a}:
                reg_frac[reg] = reg_frac.get(reg, 0) + 1
        c4_region_max.append(max(reg_frac.values(), default=0) / len(apd))
        c5_ok &= all(int(c["start_day"]) - int(c["warned_day"]) >= minw for c in out["crises"])
        # C6: toda ruina recupera dentro do horizonte, ou e jovem, ou a pressao a sustenta
        for loc, row in (out["projection"].get("location_states") or {}).items():
            if row.get("state") != "ruina":
                continue
            age = days + 1 - int(row.get("since_day", 0))
            region = wp.region_of(loc)
            sustained = any(
                v >= cfg["constants"]["SINAL"]
                for v in (out["sim"].get("pressures", {}).get(region) or {}).values()
            )
            if age >= cfg["director"]["RUIN_RECOVERY_DAYS"] and not sustained:
                c6_bad.append(f"seed{seed}:{loc}")
    med = lambda xs: statistics.median(xs) if xs else None  # noqa: E731
    return {
        "C1": {r: med(v) for r, v in c1.items()},
        "C2": {r: med(v) for r, v in c2.items()},
        "C3": c3_ok,
        "C4_world_max": max(c4_world),
        "C4_world_mean": statistics.mean(c4_world),
        "C4_world_p90": sorted(c4_world)[int(0.9 * (len(c4_world) - 1))],
        "C4_region_max": max(c4_region_max),
        "C5": c5_ok,
        "C6_bad": c6_bad,
        "invalid_events": invalid,
        "max_sim_bytes": max_bytes,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()
    import json

    print(json.dumps(evaluate(args.seeds, args.days), indent=2, ensure_ascii=False, default=str))
