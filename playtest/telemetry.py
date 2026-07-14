"""playtest/telemetry.py — rastro estruturado por campanha (Fase 5.3).

Grava, por campanha de playtest, 1 JSONL (uma linha por turno, shape do logger
`rpg.turn` da Fase 10 + campos de playtest e de roteamento) e um `summary.json`
com métricas agregadas. Tudo em `playtest_runs/{run_id}/` (gitignored). Funções
puras sobre `CampaignResult` + `TurnRecord`; zero dependência nova.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List

from playtest import pricing
from playtest.runner import CampaignResult, TurnRecord

PLAYTEST_RUNS_DIR = os.getenv("RPG_PLAYTEST_RUNS_DIR", "playtest_runs")


def new_run_id() -> str:
    """Id de run = timestamp que ordena sozinho."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def run_dir(run_id: str) -> str:
    return os.path.join(PLAYTEST_RUNS_DIR, run_id)


def report_path(run_id: str) -> str:
    return os.path.join(run_dir(run_id), "report.md")


# --- registros por turno ----------------------------------------------------

def turn_to_record(rec: TurnRecord) -> dict:
    """TurnRecord -> dict serializável (1 linha do JSONL)."""
    return {
        "turn": rec.turn,
        "action": rec.action,
        "narrative": rec.narrative,
        "route": rec.route,
        "latency_ms": rec.latency_ms,
        "events_applied": rec.events_applied,
        "events_rejected": rec.events_rejected,
        "error": rec.error,
        "location_id": rec.location_id,
        "player_hp": rec.player_hp,
        "player_max_hp": rec.player_max_hp,
        "player_level": rec.player_level,
        "gold": rec.gold,
        "combat_active": rec.combat_active,
        "replanned": rec.replanned,
        "violations": list(rec.violations),
        "provider": rec.provider,
        "model": rec.model,
        "tier": rec.tier,
        "fell_back": rec.fell_back,
        "cost_usd": round(pricing.turn_cost(rec.llm_events), 6),
    }


def write_turn(fp, record: dict) -> None:
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1))))
    return int(s[idx])


def build_summary(result: CampaignResult, turn_records: List[dict]) -> dict:
    """Métricas agregadas da campanha (spec 5.3 R2)."""
    routes: dict = {}
    violations: dict = {}
    providers: dict = {}
    cost_by_tier: dict = {}
    latencies: List[int] = []
    fell_back_turns = 0
    cost_total = 0.0

    for r in turn_records:
        if r.get("route"):
            routes[r["route"]] = routes.get(r["route"], 0) + 1
        for cid in r.get("violations", []):
            violations[cid] = violations.get(cid, 0) + 1
        latencies.append(int(r.get("latency_ms", 0)))
        if r.get("fell_back"):
            fell_back_turns += 1
        cost_total += float(r.get("cost_usd", 0.0))

    # Requests e custo por tier vêm dos llm_events crus (todos os invokes).
    for rec in result.history:
        for e in rec.llm_events:
            prov = e.get("provider") or "?"
            providers[prov] = providers.get(prov, 0) + 1
            tier = e.get("tier") or "?"
            cost_by_tier[tier] = round(
                cost_by_tier.get(tier, 0.0) + pricing.estimate_cost(e.get("model", "")), 6)

    final = result.final_state or {}
    world = final.get("world", {}) or {}
    player = final.get("player", {}) or {}
    quests = [q for q in (final.get("quests") or []) if isinstance(q, dict)]

    # spec balanceamento-early-game (R5): métricas de balanço da campanha.
    first_death_turn = next(
        (r["turn"] for r in turn_records
         if int(r.get("player_max_hp", 0) or 0) > 0 and int(r.get("player_hp", 1) or 0) <= 0),
        None)
    downed_count = len([ev for ev in (final.get("event_log") or [])
                        if isinstance(ev, dict) and ev.get("type") == "player_downed"])
    replan_count = len([r for r in turn_records if r.get("replanned")])
    combat_end_hp_pcts: List[float] = []
    prev_combat = False
    for r in turn_records:
        now_combat = bool(r.get("combat_active"))
        ended = (not now_combat) and (prev_combat or r.get("route") == "combat_agent")
        mx = int(r.get("player_max_hp", 0) or 0)
        if ended and mx > 0:
            combat_end_hp_pcts.append(100.0 * int(r.get("player_hp", 0) or 0) / mx)
        prev_combat = now_combat
    avg_hp_pct_after_combat = (
        round(sum(combat_end_hp_pcts) / len(combat_end_hp_pcts), 1)
        if combat_end_hp_pcts else None)

    return {
        "profile": result.profile,
        "seed": result.seed,
        "turns_completed": result.turns_completed,
        "errors": len(result.errors),
        "violations": violations,
        "routes": routes,
        "latency_ms": {"p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95)},
        "deaths": 1 if final.get("game_over") else 0,
        "first_death_turn": first_death_turn,
        "downed_count": downed_count,
        "avg_hp_pct_after_combat": avg_hp_pct_after_combat,
        "replan_count": replan_count,
        "final_level": int(player.get("level", 1) or 1),
        "final_gold": int(player.get("gold", 0) or 0),
        "locations_visited": len(world.get("visited", []) or []),
        "quests": {
            "created": len(quests),
            "completed": len([q for q in quests if q.get("status") != "active"]),
        },
        "llm_requests_by_provider": providers,
        "cost_usd_total": round(cost_total, 6),
        "cost_usd_by_tier": cost_by_tier,
        "fell_back_turns": fell_back_turns,
        "mock": result.mock,
        "aborted_reason": result.aborted_reason,
    }


def persist_campaign(run_id: str, result: CampaignResult) -> dict:
    """Escreve `{profile}_{seed}.jsonl` + `{profile}_{seed}.summary.json` no run.
    Devolve o summary."""
    d = run_dir(run_id)
    os.makedirs(d, exist_ok=True)
    stem = f"{result.profile}_{result.seed}"
    turn_records = [turn_to_record(r) for r in result.history]

    with open(os.path.join(d, f"{stem}.jsonl"), "w", encoding="utf-8") as f:
        for rec in turn_records:
            write_turn(f, rec)

    summary = build_summary(result, turn_records)
    with open(os.path.join(d, f"{stem}.summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary
