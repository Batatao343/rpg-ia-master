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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class RunReport:
    run_id: str
    campaigns: List[dict]                 # summaries
    top_violations: List[Tuple[str, int]]
    top_errors: List[Tuple[str, int]]     # por rota do grafo
    deltas: Optional[dict]                # vs baseline (None sem baseline)
    mock_any: bool = False
    status: str = "legacy"
    complete: bool = True
    completeness: dict = field(default_factory=dict)
    violation_samples: Dict[str, dict] = field(default_factory=dict)


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
        # spec balanceamento-early-game (R5)
        "replans": sum(int(s.get("replan_count", 0) or 0) for s in summaries),
        "downed": sum(int(s.get("downed_count", 0) or 0) for s in summaries),
    }


def aggregate(run_dir: str, baseline_dir: Optional[str] = None) -> RunReport:
    summaries = _load_summaries(run_dir)
    run_id = os.path.basename(os.path.normpath(run_dir))

    viol: Counter = Counter()
    violation_samples: Dict[str, dict] = {}
    for s in summaries:
        for cid, n in (s.get("violations") or {}).items():
            viol[cid] += int(n)
        for cid, sample in (s.get("violation_samples") or {}).items():
            if cid not in violation_samples and isinstance(sample, dict):
                violation_samples[cid] = sample

    errs = _errors_by_route(run_dir)

    deltas = None
    if baseline_dir:
        base = _load_summaries(baseline_dir)
        cur_t, base_t = _totais(summaries), _totais(base)
        deltas = {k: cur_t.get(k, 0) - base_t.get(k, 0)
                  for k in ("errors", "violations", "cost_usd", "deaths",
                            "latency_p95_max", "replans", "downed")}
        deltas["baseline_id"] = os.path.basename(os.path.normpath(baseline_dir))

    from playtest import telemetry
    completeness = telemetry.inspect_run(run_dir)
    return RunReport(
        run_id=run_id, campaigns=summaries,
        top_violations=viol.most_common(10),
        top_errors=errs.most_common(10),
        deltas=deltas,
        mock_any=any(s.get("mock") for s in summaries),
        status=str(completeness.get("status") or "unknown"),
        complete=bool(completeness.get("complete")),
        completeness=completeness,
        violation_samples=violation_samples,
    )


def render_transcript(run_dir: str) -> str:
    """Transcrito QUALITATIVO por turno (ação do jogador → rota → narração do
    LLM) de todas as campanhas do run. Serve p/ julgar o PROMPT: coerência,
    repetição, se o narrador ignora estado, se falta algo. Legível no editor."""
    L: List[str] = [f"# Transcrito de playtest — `{os.path.basename(os.path.normpath(run_dir))}`", ""]
    for path in sorted(glob.glob(os.path.join(run_dir, "*.jsonl"))):
        stem = os.path.basename(path)[:-6]  # tira .jsonl
        L.append(f"## Campanha `{stem}`")
        L.append("")
        try:
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
        except Exception as e:
            L.append(f"_erro ao ler: {e}_")
            continue
        for r in rows:
            prov = r.get("provider")
            tag = f" · {prov}/{r.get('model','')}" if prov else " · mock"
            L.append(f"### Turno {r.get('turn')} — rota `{r.get('route','')}`{tag}")
            L.append(f"**Ação:** {r.get('action','')}")
            err = r.get("error")
            if err:
                L.append(f"**ERRO:** `{err}`")
            narr = (r.get("narrative") or "").strip()
            L.append("")
            L.append(narr if narr else "_(sem narração capturada)_")
            viol = r.get("violations") or []
            if viol:
                L.append("")
                L.append(f"⚠️ violações: {', '.join(viol)}")
            L.append("")
    return "\n".join(L)


def _fmt(n) -> str:
    return f"{n:+d}" if isinstance(n, int) else f"{n:+.4f}"


def render_markdown(report: RunReport) -> str:
    L: List[str] = []
    L.append(f"# Relatório de playtest — `{report.run_id}`")
    L.append("")
    if not report.complete:
        details = report.completeness or {}
        L.append(
            f"> ⛔ **RUN INCOMPLETA** — status `{report.status}`; "
            f"campanhas {details.get('persisted_campaigns', '?')}/"
            f"{details.get('expected_campaigns', '?')}."
        )
        missing = details.get("missing_profiles") or []
        if missing:
            L.append(f"> Perfis ausentes: {', '.join(map(str, missing))}.")
        incomplete = details.get("incomplete_campaigns") or []
        if incomplete:
            rendered = ", ".join(
                f"{item.get('profile')} "
                f"({item.get('turns_completed')}/{item.get('turns_expected')})"
                for item in incomplete
            )
            L.append(f"> Campanhas incompletas: {rendered}.")
        missing_summaries = details.get("missing_summaries") or []
        if missing_summaries:
            L.append(
                "> Summaries ausentes: "
                + ", ".join(map(str, missing_summaries))
                + "."
            )
        for label, key in (
            ("Summaries inválidos", "invalid_summaries"),
            ("JSONLs ausentes", "missing_jsonls"),
            ("JSONLs inválidos", "invalid_jsonls"),
            ("Saves ausentes", "missing_saves"),
            ("Saves inválidos", "invalid_saves"),
            ("Divergências de artefato", "artifact_mismatches"),
            ("Erros de configuração", "configuration_errors"),
        ):
            values = details.get(key) or []
            if values:
                rendered_values = ", ".join(
                    str(value.get("file") or value.get("field") or value)
                    if isinstance(value, dict) else str(value)
                    for value in values[:10]
                )
                L.append(f"> {label}: {rendered_values}.")
        L.append("")
    if report.mock_any:
        L.append("> ⚠️ **Contém campanhas em MockLLM** (`mock: true`) — latência/rotas/custo "
                 "NÃO representam produção. Não compare mock × real.")
        L.append("")
    warning_total = sum(
        int(summary.get("warning_violations", 0) or 0)
        for summary in report.campaigns
    )
    if warning_total:
        L.append(
            f"> ⚠️ **{warning_total} warning(s) não bloqueante(s)** — "
            "revise a seção de violações antes do aceite funcional."
        )
        L.append("")

    L.append("## Por perfil")
    L.append("")
    L.append("| perfil | seed | turnos | erros | mortes | 1ª morte | downed | "
             "hp% pós-comb | replans | nível | ouro | locais | "
             "p50 | p95 | custo USD | fallback | mock |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in report.campaigns:
        lat = s.get("latency_ms", {})
        hp_pct = s.get("avg_hp_pct_after_combat")
        L.append(
            f"| {s.get('profile','?')} | {s.get('seed',0)} | {s.get('turns_completed',0)} "
            f"| {s.get('errors',0)} | {s.get('deaths',0)} "
            f"| {s.get('first_death_turn') if s.get('first_death_turn') is not None else '—'} "
            f"| {s.get('downed_count',0)} "
            f"| {f'{hp_pct:.0f}%' if hp_pct is not None else '—'} "
            f"| {s.get('replan_count',0)} | {s.get('final_level',1)} "
            f"| {s.get('final_gold',0)} | {s.get('locations_visited',0)} "
            f"| {lat.get('p50',0)} | {lat.get('p95',0)} | {s.get('cost_usd_total',0.0):.4f} "
            f"| {s.get('fell_back_turns',0)} | {'sim' if s.get('mock') else 'não'} |")
    L.append("")

    L.append("## Cobertura mecânica")
    L.append("")
    L.append("| perfil | turnos combat | conflitos iniciados | encerrados | reações | táticas |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for summary in report.campaigns:
        coverage = summary.get("combat_coverage") or {}
        L.append(
            f"| {summary.get('profile','?')} "
            f"| {coverage.get('executed_turns', 0)} "
            f"| {coverage.get('started', 0)} "
            f"| {coverage.get('ended', 0)} "
            f"| {coverage.get('reactions', 0)} "
            f"| {coverage.get('tactics', 0)} |"
        )
    L.append("")

    # spec balanceamento-classes-pos-playtest (R3): matriz por classe.
    with_class = [s for s in report.campaigns if s.get("class_name")]
    if with_class:
        L.append("## Classes")
        L.append("")
        # spec playtest-agente-curioso-entropia (R5): colunas de GASTO real
        # (%ativa, gasto/turno) no lugar do snapshot degenerado.
        L.append("| perfil | classe | turnos | mortes | nível | %ativa | "
                 "gasto/turno | starvation | flooding | Carga pico | Carga final | patamar |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s in with_class:
            ent = s.get("entropy") or {}

            def _p(v):
                return f"{v:.0f}%" if isinstance(v, (int, float)) else "—"

            def _n(v):
                return f"{v:.2f}" if isinstance(v, (int, float)) else "—"
            L.append(
                f"| {s.get('profile','?')} | {s.get('class_name','?')} "
                f"| {s.get('turns_completed',0)} | {s.get('deaths',0)} "
                f"| {s.get('final_level',1)} "
                f"| {_p(ent.get('pct_combat_turns_ability_used'))} "
                f"| {_n(ent.get('spent_per_combat_turn'))} "
                f"| {_p(ent.get('starvation_pct_combat'))} "
                f"| {_p(ent.get('flooding_pct_combat'))} "
                f"| {ent.get('peak_abyss_charge',0)} | {ent.get('final_abyss_charge',0)} "
                f"| {ent.get('final_abyss_tier') or '—'} |")
        L.append("")

    # spec playtest-stop-gameover (R4): morte como linha própria (turno/local/causa).
    deaths = [s for s in report.campaigns if int(s.get("deaths", 0))]
    if deaths:
        L.append("## Mortes")
        L.append("")
        L.append("| perfil | seed | turno | local | causa |")
        L.append("|---|---|---|---|---|")
        for s in deaths:
            L.append(
                f"| {s.get('profile','?')} | {s.get('seed',0)} "
                f"| {s.get('first_death_turn') if s.get('first_death_turn') is not None else '—'} "
                f"| {s.get('death_location') or '—'} | {s.get('death_cause') or '—'} |")
        L.append("")

    L.append("## Violações")
    L.append("")
    if report.top_violations:
        L.append("| check_id | ocorrências | severidade | amostra |")
        L.append("|---|---|---|---|")
        for cid, n in report.top_violations:
            sample = report.violation_samples.get(cid) or {}
            severity = sample.get("severity") or "—"
            message = str(sample.get("message") or "—").replace("|", "\\|")
            L.append(f"| {cid} | {n} | {severity} | {message} |")
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
        for k in ("errors", "violations", "deaths", "downed", "replans",
                  "latency_p95_max", "cost_usd"):
            if k in report.deltas:
                L.append(f"| {k} | {_fmt(report.deltas[k])} |")
        L.append("")

    return "\n".join(L)
