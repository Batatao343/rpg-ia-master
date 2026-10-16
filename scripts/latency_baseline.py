"""SPEC-200: baseline de latencia percebida (ack, TTFMC, TTLT) e decomposicao por fase.

Uso (a partir da raiz do repo)::

    uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 \
        --profile typical --mode virtual
    uv run python scripts/latency_baseline.py report <run_id>
    uv run python scripts/latency_baseline.py compare <run_a> <run_b>

O modo offline NAO mede latencia de rede: usa MockLLM com latencia injetada
deterministica (``playtest/latency_llm.py``) e um relogio virtual. Mede a
ESTRUTURA do turno (decomposicao, ordem, contagens). Valores absolutos de p95 so
sao interpretaveis no modo ``real`` (opt-in, com teto de requests/custo).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observability import latency as lat  # noqa: E402
from observability.latency import PHASES, percentile  # noqa: E402

RUNS_DIR = ROOT / "latency_runs"
SCHEMA_VERSION = 1
INDICATIVE_BELOW = 20
METRICS = ("ack_server_ms", "ttfmc_server_ms", "ttlt_server_ms", "state_server_ms", "total_ms")
METRIC_LABEL = {"ack_server_ms": "ack", "ttfmc_server_ms": "ttfmc", "ttlt_server_ms": "ttlt",
                "state_server_ms": "state", "total_ms": "total"}
REAL_ENV = "RPG_LATENCY_REAL_AUTHORIZED"
REAL_COMMAND_HINT = (
    "RPG_LATENCY_REAL_AUTHORIZED=1 uv run python scripts/latency_baseline.py run --real "
    "--journeys J1,J2,J3 --reps 5 --max-requests 40 --max-cost 0.20")


# --------------------------------------------------------------------------- util
def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def fingerprint(mode: str, profile: str, journeys: List[str]) -> Dict[str, Any]:
    from scripts import latency_journeys as lj
    return {
        "git_sha": _git_sha(),
        "mode": mode,                                   # offline-virtual|offline-scaled|real
        "profile": profile,
        "execution_mode": os.getenv("RPG_TURN_EXECUTION", "sequential").strip().lower(),
        "python": ".".join(platform.python_version_tuple()[:2]),
        "pseudo_streaming": lat.PSEUDO_STREAMING,
        "journeys": sorted(journeys),
        "journeys_version": lj.JOURNEYS_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


# Campos que tornam duas runs INCOMPARAVEIS (git_sha e informativo: e a variavel do A/B).
_COMPARABLE_KEYS = ("mode", "profile", "execution_mode", "python", "pseudo_streaming",
                    "journeys", "journeys_version", "schema_version")


def fingerprint_mismatch(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    return [k for k in _COMPARABLE_KEYS if a.get(k) != b.get(k)]


def _stats(values: List[int]) -> Dict[str, Any]:
    vals = [int(v) for v in values if v is not None]
    return {"n": len(vals), "p50": percentile(vals, 50), "p95": percentile(vals, 95),
            "max": max(vals, default=0)}


# ------------------------------------------------------------------- agregacao
def aggregate(records: List[Dict[str, Any]], fp: Dict[str, Any]) -> Dict[str, Any]:
    by_journey: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        by_journey.setdefault(rec["journey"], []).append(rec)

    def block(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {"n": len(rows), "indicative": len(rows) < INDICATIVE_BELOW}
        for key in METRICS:
            out[METRIC_LABEL[key]] = _stats([r.get(key) for r in rows])
        out["phases"] = lat.summarize_phases(rows)
        sizes: Dict[str, Any] = {}
        for size in ("short", "medium", "long"):
            sub = [r for r in rows if r.get("input_size") == size]
            if sub:
                sizes[size] = {"n": len(sub), "ttfmc": _stats([r.get("ttfmc_server_ms") for r in sub]),
                               "total": _stats([r.get("total_ms") for r in sub])}
        out["by_input_size"] = sizes
        out["llm_attempts_mean"] = round(
            sum(int(r.get("llm_attempts", 0) or 0) for r in rows) / max(1, len(rows)), 3)
        out["llm_fallbacks_total"] = sum(int(r.get("llm_fallbacks", 0) or 0) for r in rows)
        out["routes"] = {}
        for r in rows:
            route = str(r.get("route_next") or "?")
            out["routes"][route] = out["routes"].get(route, 0) + 1
        out["routes"] = dict(sorted(out["routes"].items()))
        return out

    return {"fingerprint": fp,
            "overall": block(records),
            "journeys": {name: block(rows) for name, rows in sorted(by_journey.items())}}


def _dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


# ------------------------------------------------------------------- execucao
@contextlib.contextmanager
def _isolated_env(work: Path, *, offline: bool):
    """Saves/memoria/cache em diretorio descartavel; embeddings e LLM offline."""
    import persistence
    import rag
    from playtest import runner as pr

    saves, memory = work / "saves", work / "memory"
    saves.mkdir(parents=True, exist_ok=True)
    memory.mkdir(parents=True, exist_ok=True)
    env_keys = ("RPG_RATE_LIMIT", "RPG_RUNTIME_CACHE_DIR")
    prev_env = {k: os.environ.get(k) for k in env_keys}
    prev_paths = (persistence.SAVES_DIR, persistence.SESSION_MEMORY_DIR, rag.SAVES_DIR)
    os.environ["RPG_RATE_LIMIT"] = "0"
    os.environ["RPG_RUNTIME_CACHE_DIR"] = str(work / "runtime")
    persistence.SAVES_DIR, persistence.SESSION_MEMORY_DIR, rag.SAVES_DIR = (
        str(saves), str(memory), str(memory))
    try:
        with pr._force_mock(active=offline), pr._offline_embeddings(active=offline):
            pr._clear_caches()
            yield
    finally:
        persistence.SAVES_DIR, persistence.SESSION_MEMORY_DIR, rag.SAVES_DIR = prev_paths
        for key, value in prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _read_stream(client, game_id: str, text: str, action_id: str) -> List[str]:
    events: List[str] = []
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": text, "game_id": game_id,
                             "action_id": action_id}) as response:
        if response.status_code != 200:
            raise RuntimeError(f"stream HTTP {response.status_code}")
        name = None
        for line in response.iter_lines():
            line = line.decode() if isinstance(line, bytes) else line
            if line.startswith("event: "):
                name = line[7:].strip()
                events.append(name)
    return events


def _wait_record(sink: List[Dict[str, Any]], count: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while len(sink) < count and time.monotonic() < deadline:
        time.sleep(0.005)
    if len(sink) < count:
        raise RuntimeError("registro de latencia nao publicado a tempo")


def execute(journeys, reps: int, seed: int, profile: str, mode: str, scale: float,
            work: Path, *, real: bool = False, max_requests: Optional[int] = None,
            max_cost: Optional[float] = None, progress=None) -> List[Dict[str, Any]]:
    """Roda as jornadas in-process (TestClient, SSE real) e devolve os registros."""
    import random
    from fastapi.testclient import TestClient

    from playtest.latency_llm import LatencyContext, install, uninstall

    records: List[Dict[str, Any]] = []
    sink: List[Dict[str, Any]] = []
    clock = lat.FakeClock() if (mode == "virtual" and not real) else None
    ctx = None if real else LatencyContext(profile=profile, seed=seed, mode=mode,
                                          scale=scale, clock=clock)
    with _isolated_env(work, offline=not real):
        import api
        if clock is not None:
            lat.set_clock(clock)
        if ctx is not None:
            install(ctx)
        lat.add_sink(sink.append)
        spent_requests, spent_cost = 0, 0.0
        try:
            with TestClient(api.app) as client:
                for journey in journeys:
                    for rep in range(reps):
                        random.seed(f"{seed}|{journey.name}|{rep}")
                        if ctx is not None:
                            ctx.start_turn(journey.name, rep)
                        created = client.post("/game/new", json={
                            "name": "Latencia", "race": "Humano",
                            "class_name": "Sangromante", "region": "Nova Arcádia",
                            "level": 1, "backstory": ""})
                        if created.status_code != 200:
                            raise RuntimeError(f"/game/new HTTP {created.status_code}")
                        game_id = created.json()["game_id"]
                        plan = [(t, False) for t in journey.warmup] + [
                            (t, True) for t in journey.measured_turns()]
                        for turn_index, (text, measured) in enumerate(plan):
                            if ctx is not None:
                                ctx.start_turn(journey.name, rep * 1000 + turn_index)
                            before = len(sink)
                            _read_stream(client, game_id, text, str(uuid.uuid4()))
                            _wait_record(sink, before + 1)
                            rec = dict(sink[-1])
                            if real:
                                spent_requests += int(rec.get("llm_attempts", 0) or 0)
                                spent_cost += float(rec.get("cost_usd") or 0.0)
                            if not measured:
                                continue
                            rec.update({
                                "journey": journey.name, "rep": rep, "seed": seed,
                                "profile": "real" if real else profile,
                                "mode": "real" if real else f"offline-{mode}",
                                "turn_index": turn_index,
                                "expected_route": journey.expected_route,
                                "pseudo_streaming": lat.PSEUDO_STREAMING,
                            })
                            records.append(rec)
                            if real and (
                                    (max_requests is not None and spent_requests >= max_requests)
                                    or (max_cost is not None and spent_cost >= max_cost)):
                                raise SystemExit(
                                    f"teto atingido (requests={spent_requests}, "
                                    f"custo={spent_cost:.4f}): run abortada")
                    if progress:
                        progress(journey.name)
        finally:
            lat.remove_sink(sink.append)
            uninstall()
            lat.set_clock(None)
    return records


# -------------------------------------------------------------------- relatorio
def _row(label: str, st: Dict[str, Any]) -> str:
    return f"| {label} | {st['n']} | {st['p50']} | {st['p95']} | {st['max']} |"


def render_report(summary: Dict[str, Any]) -> str:
    fp = summary["fingerprint"]
    lines = ["# Baseline de latencia percebida (SPEC-200)", "",
             "## Fingerprint de ambiente", ""]
    for key in ("git_sha", "mode", "profile", "execution_mode", "python",
                "pseudo_streaming", "journeys_version"):
        lines.append(f"- `{key}`: `{fp.get(key)}`")
    lines += ["", "> `pseudo_streaming=true`: o servidor fatia uma mensagem JA pronta; "
              "**TTFT = TTFMC (pseudo_streaming)** — nao ha token real.", ""]
    if fp.get("mode") != "real":
        lines += ["> Modo offline mede a ESTRUTURA do turno (decomposicao, ordem, contagens) "
                  "com latencia injetada; nao e latencia de rede. p95 absoluto so e "
                  "interpretavel no modo `real`.", ""]
    for name, block in [("TODAS", summary["overall"])] + list(summary["journeys"].items()):
        tag = " (p95 indicativo: n < 20)" if block["indicative"] else ""
        lines += [f"## {name} — n={block['n']}{tag}", "",
                  "| metrica (ms) | n | p50 | p95 | max |", "|---|---|---|---|---|"]
        for key in METRICS:
            label = METRIC_LABEL[key]
            lines.append(_row(label if label != "ttfmc" else "ttfmc (= TTFT)", block[label]))
        lines += ["", "| fase | p50 | p95 | participacao |", "|---|---|---|---|"]
        for phase in PHASES:
            ph = block["phases"][phase]
            lines.append(f"| {phase} | {ph['p50']} | {ph['p95']} | {ph['share'] * 100:.1f}% |")
        if block["by_input_size"]:
            lines += ["", "| entrada | n | ttfmc p50 | ttfmc p95 |", "|---|---|---|---|"]
            for size, sub in block["by_input_size"].items():
                lines.append(f"| {size} | {sub['n']} | {sub['ttfmc']['p50']} | {sub['ttfmc']['p95']} |")
        lines += ["", f"- tentativas LLM/turno (media): {block['llm_attempts_mean']} · "
                      f"fallbacks: {block['llm_fallbacks_total']} · rotas: {block['routes']}", ""]
    return "\n".join(lines) + "\n"


def compare_runs(a: Dict[str, Any], b: Dict[str, Any], *, allow_mismatch: bool) -> str:
    bad = fingerprint_mismatch(a["fingerprint"], b["fingerprint"])
    if bad and not allow_mismatch:
        raise SystemExit("fingerprints incompativeis (" + ", ".join(bad) +
                         "): recuso comparar; use --allow-env-mismatch para forcar")
    lines = ["# Comparacao de baselines (SPEC-200)", ""]
    if bad:
        lines += [f"> **RESSALVA:** fingerprints diferem em {', '.join(bad)} — "
                  "comparacao nao e A/B limpa.", ""]
    lines += [f"- A: `{a['fingerprint']['git_sha']}` · B: `{b['fingerprint']['git_sha']}`", "",
              "| jornada | metrica | A p50 | B p50 | delta | A p95 | B p95 | delta |",
              "|---|---|---|---|---|---|---|---|"]
    for name in sorted(set(a["journeys"]) & set(b["journeys"])):
        for key in ("ttfmc", "ttlt", "total"):
            sa, sb = a["journeys"][name][key], b["journeys"][name][key]
            lines.append(f"| {name} | {key} | {sa['p50']} | {sb['p50']} | {sb['p50'] - sa['p50']:+d} "
                         f"| {sa['p95']} | {sb['p95']} | {sb['p95'] - sa['p95']:+d} |")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------------- CLI
def _real_guard(args) -> None:
    """R15: falha ANTES de construir qualquer LLM quando faltar autorizacao/teto."""
    problems = []
    if os.environ.get(REAL_ENV) != "1":
        problems.append(f"defina {REAL_ENV}=1")
    if args.max_requests is None:
        problems.append("--max-requests e obrigatorio")
    if args.max_cost is None:
        problems.append("--max-cost e obrigatorio")
    if problems:
        raise SystemExit("modo --real recusado: " + "; ".join(problems) +
                         f"\ncomando previsto: {REAL_COMMAND_HINT}")


def cmd_run(args) -> int:
    if args.real:
        _real_guard(args)
    from scripts import latency_journeys as lj
    journeys = lj.select(args.journeys)
    mode = "real" if args.real else args.mode
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S") + f"-{uuid.uuid4().hex[:6]}"
    out_root = Path(args.out_dir) if args.out_dir else RUNS_DIR
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="latency-work-"))
    try:
        records = execute(journeys, args.reps, args.seed, args.profile, args.mode, args.scale,
                          work, real=args.real, max_requests=args.max_requests,
                          max_cost=args.max_cost, progress=lambda n: print(f"  {n} ok"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    fp_mode = "real" if args.real else f"offline-{mode}"
    fp = fingerprint(fp_mode, "real" if args.real else args.profile, [j.name for j in journeys])
    with open(run_dir / "records.jsonl", "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    summary = aggregate(records, fp)
    _dump(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(f"run_id={run_id} registros={len(records)} dir={run_dir}")
    return 0


def _load_summary(run: str, out_dir: Optional[str]) -> Dict[str, Any]:
    root = Path(out_dir) if out_dir else RUNS_DIR
    path = Path(run) / "summary.json" if Path(run).is_dir() else root / run / "summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_report(args) -> int:
    text = render_report(_load_summary(args.run_id, args.out_dir))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_compare(args) -> int:
    print(compare_runs(_load_summary(args.run_a, args.out_dir), _load_summary(args.run_b, args.out_dir),
                       allow_mismatch=args.allow_env_mismatch))
    return 0


def cmd_serve(args) -> int:
    """API local com latencia injetada em tempo REAL escalado (smoke de browser)."""
    import uvicorn

    from playtest.latency_llm import LatencyContext, install
    os.environ.setdefault("RPG_FORCE_MOCK", "1")
    os.environ.setdefault("RPG_RATE_LIMIT", "0")
    work = Path(tempfile.mkdtemp(prefix="latency-serve-"))
    import persistence
    persistence.SAVES_DIR = str(work / "saves")
    persistence.SESSION_MEMORY_DIR = str(work / "memory")
    os.makedirs(persistence.SAVES_DIR, exist_ok=True)
    import api
    install(LatencyContext(profile=args.profile, seed=args.seed, mode="scaled", scale=args.scale))
    uvicorn.run(api.app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--journeys", default="all")
    run.add_argument("--reps", type=int, default=30)
    run.add_argument("--seed", type=int, default=200)
    run.add_argument("--profile", default="typical",
                     choices=["flat-fast", "typical", "slow-tail", "fallback-once"])
    run.add_argument("--mode", default="virtual", choices=["virtual", "scaled"])
    run.add_argument("--scale", type=float, default=0.01)
    run.add_argument("--run-id")
    run.add_argument("--out-dir")
    run.add_argument("--real", action="store_true")
    run.add_argument("--max-requests", type=int)
    run.add_argument("--max-cost", type=float)
    run.set_defaults(fn=cmd_run)
    report = sub.add_parser("report")
    report.add_argument("run_id")
    report.add_argument("--out-dir")
    report.add_argument("--out")
    report.set_defaults(fn=cmd_report)
    compare = sub.add_parser("compare")
    compare.add_argument("run_a")
    compare.add_argument("run_b")
    compare.add_argument("--out-dir")
    compare.add_argument("--allow-env-mismatch", action="store_true")
    compare.set_defaults(fn=cmd_compare)
    serve = sub.add_parser("serve")
    serve.add_argument("--profile", default="typical")
    serve.add_argument("--scale", type=float, default=0.02)
    serve.add_argument("--seed", type=int, default=200)
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(fn=cmd_serve)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
