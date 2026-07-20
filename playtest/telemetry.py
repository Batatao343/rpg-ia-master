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
        # spec balanceamento-classes-pos-playtest (R2)
        "entropy": rec.entropy,
        "max_entropy": rec.max_entropy,
        "abyss_charge": rec.abyss_charge,
        "abyss_tier": rec.abyss_tier,
        # spec playtest-agente-curioso-entropia (R3): gasto real de Entropia
        "entropy_spent": rec.entropy_spent,
        "used_active_ability": rec.used_active_ability,
        "ability_id": rec.ability_id,
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


def _min_active_entropy_cost(player: dict) -> int:
    """Menor custo de Entropia entre as habilidades ATIVAS conhecidas do jogador
    (spec playtest-agente-curioso-entropia R4). 0 se a classe não tem ativa de
    Entropia (starvation não se aplica)."""
    try:
        from gamedata import ABILITIES
        from combat_mechanics import _resource_field
    except Exception:
        return 0
    costs: List[int] = []
    for aid in (player.get("known_abilities") or []):
        ab = ABILITIES.get(str(aid))
        if not isinstance(ab, dict):
            continue
        if ab.get("ability_kind", "active") != "active":
            continue
        cost = int(ab.get("cost", 0) or 0)
        if cost > 0 and _resource_field(ab.get("resource_type", "")) == "entropy":
            costs.append(cost)
    return min(costs) if costs else 0


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

    # spec playtest-stop-gameover (R4): local/causa da morte, do event_log.
    death_ev = next(
        (ev for ev in reversed(final.get("event_log") or [])
         if isinstance(ev, dict) and ev.get("type") == "player_died"), None)
    death_payload = (death_ev or {}).get("payload", {}) or {}
    death_location = death_payload.get("location") or None
    death_cause = death_payload.get("killer") or None

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

    # spec playtest-agente-curioso-entropia (R4): economia de Entropia medida por
    # GASTO, não por snapshot. Turno de combate = rota combat_agent (o gasto só é
    # fiel aí; ver runner._fill_state_metrics). O snapshot antigo era degenerado
    # (o gatilho reenche ao teto → flooding 100% / starvation 0% sempre).
    combat_rows = [r for r in turn_records if r.get("route") == "combat_agent"]

    def _pct(n: int, d: int):
        return round(100.0 * n / d, 1) if d else None

    n_combat = len(combat_rows)
    ability_turns = [r for r in combat_rows if r.get("used_active_ability")]
    basic_turns = [r for r in combat_rows if not r.get("used_active_ability")]
    spent_total = sum(int(r.get("entropy_spent", 0) or 0) for r in combat_rows)
    spent_per_combat_turn = round(spent_total / n_combat, 2) if n_combat else None
    pct_ability_used = _pct(len(ability_turns), n_combat)
    pct_basic_only = _pct(len(basic_turns), n_combat)
    # starvation REDEFINIDO: turno de combate que NÃO usou ativa E tinha Entropia
    # abaixo do menor custo de ativa conhecida (recurso faltou p/ agir).
    min_active_cost = _min_active_entropy_cost(player)
    starvation = _pct(
        len([r for r in basic_turns
             if int(r.get("max_entropy", 0) or 0) > 0
             and int(r.get("entropy", 0) or 0) < min_active_cost]),
        n_combat) if min_active_cost > 0 else None
    # flooding REDEFINIDO: turno que terminou com ataque básico E Entropia cheia
    # (recurso sobrou e não foi usado — gatilho/pool irrelevante).
    flooding = _pct(
        len([r for r in basic_turns
             if int(r.get("max_entropy", 0) or 0) > 0
             and int(r.get("entropy", 0) or 0) == int(r.get("max_entropy", 0) or 0)]),
        n_combat)
    peak_charge = max((int(r.get("abyss_charge", 0) or 0) for r in turn_records), default=0)
    try:
        from combat_mechanics import abyss_tier
        final_tier = abyss_tier(player)
    except Exception:
        final_tier = ""

    return {
        "profile": result.profile,
        "seed": result.seed,
        "class_name": player.get("class_name") or None,
        "entropy": {
            "spent_total": spent_total,
            "spent_per_combat_turn": spent_per_combat_turn,
            "pct_combat_turns_ability_used": pct_ability_used,
            "pct_combat_turns_basic_only": pct_basic_only,
            "starvation_pct_combat": starvation,
            "flooding_pct_combat": flooding,
            "peak_abyss_charge": peak_charge,
            "final_abyss_charge": int(player.get("abyss_charge", 0) or 0),
            "final_abyss_tier": final_tier,
        },
        "turns_completed": result.turns_completed,
        "errors": len(result.errors),
        "violations": violations,
        "routes": routes,
        "latency_ms": {"p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95)},
        "deaths": 1 if final.get("game_over") else 0,
        "first_death_turn": first_death_turn,
        "death_location": death_location,
        "death_cause": death_cause,
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


def persist_campaign(run_id: str, result: CampaignResult,
                     stem: str | None = None) -> dict:
    """Escreve `{stem}.jsonl` + `{stem}.summary.json` no run (default
    `{profile}_{seed}`; runs por CLASSE passam stem próprio p/ não colidir —
    spec balanceamento-classes-pos-playtest). Devolve o summary."""
    d = run_dir(run_id)
    os.makedirs(d, exist_ok=True)
    stem = stem or f"{result.profile}_{result.seed}"
    turn_records = [turn_to_record(r) for r in result.history]

    with open(os.path.join(d, f"{stem}.jsonl"), "w", encoding="utf-8") as f:
        for rec in turn_records:
            write_turn(f, rec)

    summary = build_summary(result, turn_records)
    with open(os.path.join(d, f"{stem}.summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary
