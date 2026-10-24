"""SPEC-304 R31: simulador de calibração do mundo de NPCs (sem LLM, determinístico).

Uso (raiz do repo):  bash scripts/dev/py.sh docs/spec304/npc_world_sim.py [--seeds 20] [--days 120]

Elenco sintético de 60 NPCs (21 líderes + 36 `npc_mv_*` + 3 companheiros deixados num local de
perigo 3 por 10 dias) sobre o mundo da SPEC-302. O jogador fica em `nova_arcadia` e só PERCEBE
(sem intervir): mede o pior caso de letalidade. Imprime N1-N7 e retorna o dicionário.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.update(
    RPG_FORCE_MOCK="1", RPG_WORLD_ENGINE="on", RPG_NPC_WORLD="on", RPG_NPC_KNOWLEDGE="off"
)

COMPANIONS = (
    ("npc_mv_brunna_ponte_alta", "Brunna Ponte-Alta"),
    ("npc_mv_skek_eco_curto", "Skek Eco-Curto"),
    ("npc_mv_odrin_calcario", "Odrin Calcário"),
)
WAIT_FROM = 6  # depois da calma inicial do diretor (5 dias): so ai o perigo maior pode abrir
WAIT_DAYS = 10  # dias de espera dos companheiros a partir de WAIT_FROM


def _state(seed: int) -> dict:
    from services import companion_soul as cs
    from tests.spec304_helpers import comp, waiting_state

    st = waiting_state(game_id=f"cal-{seed}")
    party = []
    for cid, name in COMPANIONS:
        party.append(comp(id=cid, origin_npc=cid, name=name, active=True, waiting_at=""))
        st["npcs"][name] = {
            **st["npcs"]["Brunna Ponte-Alta"],
            "id": cid,
            "name": name,
            "faction": "ultimos_anoes_reino",
        }
    st["party"] = party
    st["companion_souls"] = {c["id"]: cs.ensure_soul(st, c) for c in party}
    return st


def run_seed(seed: int, days: int) -> dict:
    from tests.spec304_helpers import step

    st = _state(seed)
    log: dict[str, dict] = {}
    for day in range(2, days + 1):
        if day == WAIT_FROM:  # o grupo deixa os companheiros esperando num local de perigo 3
            st["party"] = [
                {**c, "active": False, "waiting_at": "ma_saidas_baixas"} for c in st["party"]
            ]
        if day == WAIT_FROM + WAIT_DAYS:  # fim da espera: o grupo os recolhe
            st["party"] = [{**c, "active": True, "waiting_at": ""} for c in st["party"]]
        step(st, day - 1, day)
        for p in st["npc_sim"]["perils"]:  # o simulador guarda TODOS (o estado poda em 30)
            log[p["peril_id"]] = dict(p)
    st["_peril_log"] = list(log.values())
    return st


def _stats(sts: list[dict], days: int) -> dict:
    from services import world_pressures as wp

    dc = wp.director_constants()
    perils, deaths = [], []
    gap_ok = True
    perceived_per_seed, max_active = [], 0
    comp_ids = {c[0] for c in COMPANIONS}
    comp_peril = comp_total = 0
    major_perceived = major_dead = 0
    n5 = n6 = 0
    for st in sts:
        seen = set(st["world_sim"].get("perceived_ids") or [])
        ps = list(st["_peril_log"])
        perils += ps
        perceived_per_seed.append(sum(1 for p in ps if p["warning_event_id"] in seen))
        for p in ps:
            if p["resolution"] == "morto":
                deaths.append(p)
                if p["danger"] < 3 and p["kind"] in ("emboscada",):
                    n5 += 1
                if p["resolved_day"] - p["opened_day"] < 2 or (
                    p["major"]
                    and not (
                        p["perceived_day"] is not None
                        and p["perceived_day"] <= p["deadline_day"] - 1
                    )
                ):
                    n6 += 1
            if (
                p["npc_id"] in comp_ids
                and p["resolution"] not in ("", "intervencao")
                and p["perceived_day"] is not None
            ):  # N4: o companheiro largado (os lideres tem a propria meta, N3)
                major_perceived += 1
                major_dead += p["resolution"] == "morto"
        ld = sorted(p["resolved_day"] for p in ps if p["resolution"] == "morto" and p.get("leader"))
        gap_ok = gap_ok and all(b - a >= 30 for a, b in zip(ld, ld[1:]))
        for cid in comp_ids:
            comp_total += 1
            comp_peril += any(
                p["npc_id"] == cid and WAIT_FROM <= p["opened_day"] < WAIT_FROM + WAIT_DAYS
                for p in ps
            )
        max_active = max([max_active] + [e.get("active", 0) for e in st["world_sim"]["tick_log"]])
    return {
        "N1_perceived_per_20d_median": statistics.median(x * 20 / days for x in perceived_per_seed),
        "N2_deaths_per_15d_median": statistics.median(
            sum(1 for p in sts[i]["_peril_log"] if p["resolution"] == "morto") * 15 / days
            for i in range(len(sts))
        ),
        "N2_any_death_in_horizon": sum(
            1 for st in sts if any(p["resolution"] == "morto" for p in st["_peril_log"])
        )
        / len(sts),
        "N3_leader_deaths_max": max(
            sum(1 for p in st["_peril_log"] if p["resolution"] == "morto" and p.get("leader"))
            for st in sts
        ),
        "N3_gap_30d_ok": gap_ok,
        "N4_p_peril_companion": comp_peril / comp_total,
        "N4_p_death_major_perceived": (major_dead / major_perceived) if major_perceived else None,
        "N5_deaths_danger_le2": n5,
        "N6_deaths_without_telegraph": n6,
        "N7_max_active_crises": max_active,
        "N7_cap": int(dc["MAX_ACTIVE_CRISES"]),
    }


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--days", type=int, default=120)
    args = ap.parse_args(argv)
    sts = [run_seed(s, args.days) for s in range(args.seeds)]
    out = _stats(sts, args.days)
    for k, v in out.items():
        print(f"{k:34s} {v}")
    return out


if __name__ == "__main__":
    main()
