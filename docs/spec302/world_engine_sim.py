"""SPEC-302 R33: simulador offline de calibracao do motor de mundo (sem LLM).

Roda o MESMO `services.world_engine.advance_days` (modo `on`) por N dias x M seeds num
estado sintetico (heroi inerte: R5), devolve os eventos ao `event_log`/projection como o
arquivista faria (validando cada um) e mede as metas C1-C6.

Uso:  bash scripts/dev/py.sh docs/spec302/world_engine_sim.py [--days 120] [--seeds 20]
                                                         [--calendar on|off] [--s303]

SPEC-303 R28: `--calendar on|off` liga/desliga o calendario (estacoes, festas, offsets de
baseline; default `on`, o modo de producao) e `--s303` imprime as metas S2-S4.
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
    festivals: dict[str, dict] = {}
    season_digest_days: list[int] = []
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
        season_digest_days += [i["day"] for i in res.digest if i["kind"] == "estacao"]
        for rec in (res.world_sim or {}).get("festivals", []):
            festivals[rec["festa_id"]] = dict(rec)
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
        "festivals": festivals,
        "season_digest_days": season_digest_days,
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


def evaluate_s303(seeds: int = 20, days: int = 120) -> dict:
    """SPEC-303 R28: S2 (estacao sozinha nao abre crise), S3 (1a virada em anchor+4..8),
    S4 (cada festa ocorre ou e cancelada 1x por ano; taxa de cancelamento por festa)."""
    from services import world_calendar as wcal
    from services import world_pressures as wp

    # S2: sem surtos e sem causas por evento, a unica diferenca e o calendario
    cfg = wp.get_config()
    saved = (cfg["constants"]["surge_p"], cfg["causes"])
    cfg["constants"]["surge_p"], cfg["causes"] = 0.0, []
    offset_kinds = {"fome", "praga"}
    try:
        s2_extra = []
        for seed in range(1, seeds + 1):
            os.environ["RPG_CALENDAR"] = "on"
            on = run_campaign(seed, days)
            os.environ["RPG_CALENDAR"] = "off"
            off = run_campaign(seed, days)
            key = lambda c: (c["region_id"], c["kind"])  # noqa: E731
            base = {key(c) for c in off["crises"]}
            s2_extra += [
                f"seed{seed}:{c['region_id']}:{c['kind']}"
                for c in on["crises"]
                if c["kind"] in offset_kinds and key(c) not in base
            ]
    finally:
        cfg["constants"]["surge_p"], cfg["causes"] = saved
        os.environ["RPG_CALENDAR"] = "on"
    s3_ok, s3_days = True, []
    per_year: dict[tuple[str, str, int], int] = {}
    outcome: dict[str, dict[str, int]] = {}
    for seed in range(1, seeds + 1):
        out = run_campaign(seed, days)
        cal = out["sim"].get("calendar") or {}
        first = (out["season_digest_days"] or [None])[0]
        anchor = int(cal.get("anchor_day", 1))
        s3_days.append(None if first is None else first - anchor)
        s3_ok &= first is not None and 4 <= first - anchor <= 8 and first == cal["first_turn_day"]
        for rec in out["festivals"].values():
            if rec["status"] in ("encerrada", "cancelada", "ativa"):
                tag = "cancelada" if rec["status"] == "cancelada" else "ocorreu"
                k = (f"sim-{seed}", rec["festival_id"], rec["year"])
                per_year[k] = per_year.get(k, 0) + 1
                row = outcome.setdefault(rec["festival_id"], {"ocorreu": 0, "cancelada": 0})
                row[tag] += 1
    s4_ok = all(v == 1 for v in per_year.values())
    cancel_rate = {
        f: round(r["cancelada"] / max(1, r["ocorreu"] + r["cancelada"]), 3)
        for f, r in sorted(outcome.items())
    }
    return {
        "S2_extra_crises_from_season": s2_extra,
        "S3_ok": s3_ok,
        "S3_first_turn_offsets": sorted(set(x for x in s3_days if x is not None)),
        "S4_ok": s4_ok,
        "S4_cancel_rate_by_festival": cancel_rate,
        "festival_years_observed": len(per_year),
        "festivals_in_catalog": len(wcal.festivals_catalog()),
    }


PROFILES_S312 = {
    "parado": lambda day: "nova_arcadia",
    "viajante": lambda day: ("brekmar", "pradaria_ruinas", "nova_arcadia")[(day // 3) % 3],
}


def run_s312(seed: int, days: int, route) -> dict:
    """SPEC-312 Etapa 7: campanha com percepcao REAL (`storyteller._perceive_world`)."""
    from types import SimpleNamespace

    import gamedata
    from agents import storyteller as stt
    from services import rumors
    from services import world_engine as we

    state = {
        "game_id": f"sim312-{seed}",
        "event_log": [],
        "world_projection": {},
        "factions": gamedata.seed_factions(),
        "quests": [],
    }
    world = {"world_clock": {"day": 1, "period": "Manhã"}, "turn_count": 0}
    factions = state["factions"]
    perceived_by_day: dict[int, int] = {}
    seen_seeds: list[str] = []
    news_over_cap = news_expired = presence_days = born_total = 0
    max_bytes = 0
    for day in range(2, days + 2):
        before = copy.deepcopy(world)
        world = copy.deepcopy(world)
        loc = route(day)
        world.update(current_location_id=loc, current_location=loc, turn_count=day)
        world["world_clock"] = {"day": day, "period": "Manhã"}
        state["world"] = world
        res = we.advance_days(state, before, world, factions, {})
        world, factions = res.world, res.factions
        state["factions"], state["world"] = factions, world
        sim = res.world_sim or {}
        state[res.sim_key] = sim
        tick = SimpleNamespace(sim_key=res.sim_key, days_ticked=res.days_ticked, world_sim=sim)
        world, seen = stt._perceive_world(state, world, factions, {}, tick)
        state["world"] = world
        for it in seen:
            if rumors.is_rumor_item(it):
                perceived_by_day[day] = perceived_by_day.get(day, 0) + 1
                inst = rumors.instance(state, it["subject_id"]) or {}
                seen_seeds.append(f"{inst.get('seed_id')}|{inst.get('truth')}")
        presence_days += len(rumors.frequented_regions(sim, day))
        born_total += sum(1 for r in sim.get("rumors") or [] if r.get("born_day") == day)
        news = [n for n in world.get("news", []) if n.get("kind") == "rumor"]
        news_over_cap += len(news) > rumors.const("RUMOR_NEWS_MAX")
        news_expired += sum(1 for n in news if n["expires_day"] < day)
        max_bytes = max(max_bytes, len(repr(sim)))
    return {
        "perceived_by_day": perceived_by_day,
        "seen": seen_seeds,
        "news_over_cap": news_over_cap,
        "news_expired": news_expired,
        "max_sim_bytes": max_bytes,
        "born": born_total,
        "presence_days": presence_days,
    }


def evaluate_s312(seeds: int = 60, days: int = 120) -> dict:
    """SPEC-312 S1-S6 (S7 informativo) para os dois perfis de heroi."""
    out: dict = {}
    base_bytes: dict[str, dict[int, int]] = {}
    os.environ["RPG_RUMORS"] = (
        "off"  # baseline POR PERFIL e POR SEED (mesma trajetoria sem rumores)
    )
    for name, route in PROFILES_S312.items():
        base_bytes[name] = {
            seed: run_s312(seed, days, route)["max_sim_bytes"] for seed in range(1, seeds + 1)
        }
    os.environ["RPG_RUMORS"] = "on"
    for name, route in PROFILES_S312.items():
        runs = [run_s312(seed, days, route) for seed in range(1, seeds + 1)]
        born = sum(r["born"] for r in runs)
        presence = sum(r["presence_days"] for r in runs)
        total_days = seeds * days
        new_days = sum(len(r["perceived_by_day"]) for r in runs)
        seen = [x for r in runs for x in r["seen"]]
        false = sum(1 for x in seen if x.endswith("|False"))
        lore_dupes = 0
        for r in runs:
            lore = [x.split("|")[0] for x in r["seen"] if "avist" not in x and "narrador" not in x]
            lore_dupes += len(lore) - len(set(lore))
        out[name] = {
            "S1_births_per_frequented_region_day": round(born / max(1, presence), 3),
            "S2_days_with_new_rumor_perceived": round(new_days / total_days, 3),
            "S3_false_fraction_perceived": round(false / max(1, len(seen)), 3),
            "S4_lore_seed_perceived_twice": lore_dupes,
            "S5_news_violations": sum(r["news_over_cap"] + r["news_expired"] for r in runs),
            "S6_sim_bytes_growth": max(
                r["max_sim_bytes"] - base_bytes[name][i] for i, r in enumerate(runs, 1)
            ),
            "perceived_total": len(seen),
            "over_daily_cap": sum(1 for r in runs for v in r["perceived_by_day"].values() if v > 1),
        }
    out["S7_note"] = "esgotamento da familia lore: ver S4/S2 (avistamento cobre as regioes pobres)"
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--calendar", choices=("on", "off"), default="on")
    ap.add_argument("--s303", action="store_true", help="imprime S2-S4 da SPEC-303")
    ap.add_argument("--s312", action="store_true", help="imprime S1-S7 da SPEC-312 (rumores)")
    args = ap.parse_args()
    import json

    if args.s312:
        print(
            json.dumps(
                evaluate_s312(args.seeds, args.days), indent=2, ensure_ascii=False, default=str
            )
        )
        raise SystemExit(0)

    os.environ["RPG_CALENDAR"] = args.calendar
    result = evaluate(args.seeds, args.days)
    if args.s303:
        result = {"S1": result, **evaluate_s303(args.seeds, args.days)}
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
