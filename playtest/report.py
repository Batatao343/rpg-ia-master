"""playtest/report.py — agrega um run de playtest em métricas + Markdown (5.3).

`aggregate` cruza todas as campanhas de um diretório de run (os `*.summary.json`
+ `*.jsonl` que o telemetry.py escreveu) e `render_markdown` vira um relatório
estático legível no GitHub/editor. Comparação opcional com um run baseline
produz deltas de erros/violações/latência/custo. 100% offline; zero dep nova.
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class RunReport:
    run_id: str
    campaigns: List[dict]                 # summaries
    top_violations: List[Tuple[str, int]]
    top_errors: List[Tuple[str, int]]     # por rota do grafo
    deltas: Optional[dict]                # vs baseline (None sem baseline)
    mock_any: bool = False


def _load_summaries(run_dir: str) -> List[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(run_dir, "*.summary.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    return out


def _errors_by_route(run_dir: str) -> Counter:
    """Lê os JSONL do run e conta turnos com erro por rota do grafo."""
    c: Counter = Counter()
    for path in sorted(glob.glob(os.path.join(run_dir, "*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("error"):
                        c[rec.get("route") or "?"] += 1
        except Exception:
            continue
    return c


def _totais(summaries: List[dict]) -> dict:
    return {
        "campaigns": len(summaries),
        "errors": sum(int(s.get("errors", 0)) for s in summaries),
        "violations": sum(sum(s.get("violations", {}).values()) for s in summaries),
        "cost_usd": round(sum(float(s.get("cost_usd_total", 0.0)) for s in summaries), 6),
        "deaths": sum(int(s.get("deaths", 0)) for s in summaries),
        "latency_p95_max": max((int(s.get("latency_ms", {}).get("p95", 0)) for s in summaries), default=0),
    }


def aggregate(run_dir: str, baseline_dir: Optional[str] = None) -> RunReport:
    summaries = _load_summaries(run_dir)
    run_id = os.path.basename(os.path.normpath(run_dir))

    viol: Counter = Counter()
    for s in summaries:
        for cid, n in (s.get("violations") or {}).items():
            viol[cid] += int(n)

    errs = _errors_by_route(run_dir)

    deltas = None
    if baseline_dir:
        base = _load_summaries(baseline_dir)
        cur_t, base_t = _totais(summaries), _totais(base)
        deltas = {k: cur_t.get(k, 0) - base_t.get(k, 0)
                  for k in ("errors", "violations", "cost_usd", "deaths", "latency_p95_max")}
        deltas["baseline_id"] = os.path.basename(os.path.normpath(baseline_dir))

    return RunReport(
        run_id=run_id, campaigns=summaries,
        top_violations=viol.most_common(10),
        top_errors=errs.most_common(10),
        deltas=deltas,
        mock_any=any(s.get("mock") for s in summaries),
    )


def _fmt(n) -> str:
    return f"{n:+d}" if isinstance(n, int) else f"{n:+.4f}"


def render_markdown(report: RunReport) -> str:
    L: List[str] = []
    L.append(f"# Relatório de playtest — `{report.run_id}`")
    L.append("")
    if report.mock_any:
        L.append("> ⚠️ **Contém campanhas em MockLLM** (`mock: true`) — latência/rotas/custo "
                 "NÃO representam produção. Não compare mock × real.")
        L.append("")

    L.append("## Por perfil")
    L.append("")
    L.append("| perfil | seed | turnos | erros | mortes | nível | ouro | locais | "
             "p50 | p95 | custo USD | fallback | mock |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in report.campaigns:
        lat = s.get("latency_ms", {})
        L.append(
            f"| {s.get('profile','?')} | {s.get('seed',0)} | {s.get('turns_completed',0)} "
            f"| {s.get('errors',0)} | {s.get('deaths',0)} | {s.get('final_level',1)} "
            f"| {s.get('final_gold',0)} | {s.get('locations_visited',0)} "
            f"| {lat.get('p50',0)} | {lat.get('p95',0)} | {s.get('cost_usd_total',0.0):.4f} "
            f"| {s.get('fell_back_turns',0)} | {'sim' if s.get('mock') else 'não'} |")
    L.append("")

    L.append("## Violações")
    L.append("")
    if report.top_violations:
        L.append("| check_id | ocorrências |")
        L.append("|---|---|")
        for cid, n in report.top_violations:
            L.append(f"| {cid} | {n} |")
    else:
        L.append("_Nenhuma violação registrada._")
    L.append("")

    L.append("## Erros")
    L.append("")
    if report.top_errors:
        L.append("| rota | turnos com erro |")
        L.append("|---|---|")
        for route, n in report.top_errors:
            L.append(f"| {route} | {n} |")
    else:
        L.append("_Nenhum erro de turno registrado._")
    L.append("")

    L.append("## Custo por tier/provider")
    L.append("")
    prov: Counter = Counter()
    tiers: Counter = Counter()
    for s in report.campaigns:
        for p, n in (s.get("llm_requests_by_provider") or {}).items():
            prov[p] += int(n)
        for t, c in (s.get("cost_usd_by_tier") or {}).items():
            tiers[t] += float(c)
    if prov:
        L.append("Requests por provider: " + ", ".join(f"{p}={n}" for p, n in prov.most_common()))
    if tiers:
        L.append("")
        L.append("Custo por tier: " + ", ".join(f"{t}=${c:.4f}" for t, c in tiers.items()))
    if not prov and not tiers:
        L.append("_Sem invokes de LLM (MockLLM)._")
    L.append("")

    if report.deltas:
        L.append(f"## Deltas vs baseline `{report.deltas.get('baseline_id','?')}`")
        L.append("")
        L.append("| métrica | delta |")
        L.append("|---|---|")
        for k in ("errors", "violations", "deaths", "latency_p95_max", "cost_usd"):
            if k in report.deltas:
                L.append(f"| {k} | {_fmt(report.deltas[k])} |")
        L.append("")

    return "\n".join(L)
