"""SPEC-212 gate de gameplay do beta desktop (stack real + MockLLM, zero provider real).

  uv run python scripts/beta_gameplay_gate.py --strict            # gate completo (sobe API+Vite, roda Playwright)
  uv run python scripts/beta_gameplay_gate.py --strict --reuse    # reaproveita relatorios ja gerados em web/test-results

Escreve docs/spec212/evidence/gameplay-gate-<sha12>.{json,md} no estilo de
scripts/release/checklist.py (`schema`, `sha`, `ok`, `failing`, `results[]`). `ok` exige
`dirty_files == 0`, todo check bloqueante `pass` e, em `--strict`, nenhum `not_provisioned`/`skip`.
Exit 1 quando `ok` e falso. Nao edita SPEC-197/198 nem scripts/release/checklist.py.

Fluxo `run` (padrao): valida o Supabase local (portas 55321-55324), sobe
`scripts/audit_local_server.py` (perfil `local`, RPG_FORCE_MOCK=1, RPG_CLIENT_LATENCY_REPORT=1)
e o Vite, roda F01-F40 nos projetos desktop-1440/desktop-1280 + J-V1 (V01-V09), le os traces
`web/test-results/vertical/vertical-trace-<viewport>.json`, aplica os oraculos da regua e
confere `docs/spec212/known-issues.md` (R17).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVIDENCE = ROOT / "docs" / "spec212" / "evidence"
KNOWN_ISSUES = ROOT / "docs" / "spec212" / "known-issues.md"
WEB = ROOT / "web"
RESULTS = WEB / "test-results"
# Playwright apaga `test-results/` a cada execucao; os relatorios JSON do gate vivem fora dele.
REPORTS = WEB / "playwright-report" / "gate"
VIEWPORTS = {"desktop-1440": "1440x900", "desktop-1280": "1280x800"}
NPX = shutil.which("npx") or "npx"   # Windows: npx.cmd
GATE = "beta-gameplay-desktop"
SCHEMA = 1


@dataclass
class Result:
    name: str
    status: str  # pass | fail | skip | not_provisioned
    detail: Any = None
    blocking: bool = True

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "blocking": self.blocking, "detail": self.detail}


def _run(args: list[str], *, cwd: Path = ROOT, env: dict | None = None, timeout: int = 1800) -> tuple[int, str]:
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,  # noqa: S603
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


@dataclass
class Deps:
    """Seams de efeito colateral: os testes rodam offline."""
    run: Callable[..., tuple[int, str]] = field(default=_run)
    read_text: Callable[[Path], str] = field(default=lambda p: p.read_text(encoding="utf-8"))
    exists: Callable[[Path], bool] = field(default=lambda p: p.exists())


# --- identidade da arvore --------------------------------------------------------------------------------

def git_sha(deps: Deps) -> str:
    code, out = deps.run(["git", "rev-parse", "HEAD"])
    return out.strip().splitlines()[0] if code == 0 and out.strip() else "unknown"


def dirty_files(deps: Deps) -> list[str]:
    """Arquivos modificados/nao rastreados (ignorados nao contam: test-results, dist, .venv)."""
    code, out = deps.run(["git", "status", "--porcelain"])
    if code != 0:
        return ["<git status failed>"]
    return [line[3:].strip() for line in out.splitlines() if line.strip()]


# --- checks puros ----------------------------------------------------------------------------------------

def check_journeys(summaries: dict[str, dict | None]) -> Result:
    """F01-F40 por viewport desktop (R14). `summaries[projeto]` = saida de `frontend_eval_report.summarize`."""
    detail: dict[str, Any] = {}
    missing = [p for p in VIEWPORTS if not summaries.get(p)]
    for project, summary in summaries.items():
        if summary:
            journeys = summary["journeys"]
            detail[project] = {"passed": journeys["passed"], "executed": journeys["executed"],
                               "registered": journeys["registered"], "hard_gates": summary["hard_gates_passed"]}
    if missing:
        return Result("journeys_f01_f40", "not_provisioned", {**detail, "missing_viewports": missing})
    ok = all(s and s["hard_gates_passed"] for s in summaries.values())
    return Result("journeys_f01_f40", "pass" if ok else "fail", detail)


def check_vertical(summary: dict | None) -> Result:
    if not summary:
        return Result("vertical_v01_v09", "not_provisioned", {"reason": "sem relatorio do J-V1"})
    journeys = summary["journeys"]
    detail = {"steps": 9, "passed": journeys["passed"], "registered": journeys["registered"],
              "per_viewport": {p: sum(v.values()) for p, v in journeys["results"].items()}}
    return Result("vertical_v01_v09", "pass" if summary["hard_gates_passed"] else "fail", detail)


_ORACLE_CHECKS = (
    ("console_clean", ("console",)),
    ("no_duplicate_turns", ("turns",)),
    ("no_secret_leak", ("secrets",)),
    ("latency_present", ("latency",)),
    ("a11y_serious_critical", ("a11y",)),
    ("xp_speaker_roster_gesture", ("xp", "speaker", "roster", "gesture")),
)


def check_oracles(traces: dict[str, dict | None], scan: Callable[[dict], dict]) -> list[Result]:
    """Aplica `scan_trace` da regua a cada viewport; um Result por oraculo (R10-R13, R15)."""
    present = {vp: t for vp, t in traces.items() if t}
    if len(present) < len(VIEWPORTS):
        reason = {"missing_viewports": [p for p in VIEWPORTS if p not in present]}
        return [Result(name, "not_provisioned", reason) for name, _ in _ORACLE_CHECKS]
    verdicts = {vp: scan(trace) for vp, trace in present.items()}
    results = []
    for name, operations in _ORACLE_CHECKS:
        problems = {vp: {op: v["problems"][op] for op in operations if op in v["problems"]}
                    for vp, v in verdicts.items()}
        problems = {vp: p for vp, p in problems.items() if p}
        detail: dict[str, Any] = {"problems": problems}
        if name == "no_duplicate_turns":
            ids = {r.get("action_id") for t in present.values() for r in (t.get("turns") or {}).get("turns", [])}
            detail.update(action_ids=len([i for i in ids if i]), duplicates=sum(len(p) for p in problems.values()))
        elif name == "no_secret_leak":
            detail.update(surfaces_scanned=sum(len((t.get("secrets") or {}).get("surfaces") or {})
                                               for t in present.values()),
                          matches=sum(len(p) for p in problems.values()))
        elif name == "latency_present":
            detail.update(
                turns={vp: len((t.get("latency") or {}).get("turns") or []) for vp, t in present.items()},
                baseline={vp: v["baseline"] for vp, v in verdicts.items()},
                baseline_only=True, indicative=True)
        elif name == "a11y_serious_critical":
            detail["tabs_scanned"] = sum(len((t.get("a11y") or {}).get("tabs") or []) for t in present.values())
        elif name == "console_clean":
            detail["errors"] = sum(len(p) for p in problems.values())
        results.append(Result(name, "fail" if problems else "pass", detail))
    return results


_ROW = re.compile(r"^\|\s*(KI-\d+)\s*\|(.+)\|\s*$")


def parse_known_issues(text: str) -> list[dict[str, str]]:
    """Tabela `| KI-n | descricao | prioridade | impacto | classificacao | status |`."""
    rows = []
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 5:
            continue
        rows.append({"id": m.group(1), "desc": cells[0], "priority": cells[1], "impact": cells[2],
                     "class": cells[3], "status": cells[4]})
    return rows


def check_known_issues(text: str | None) -> Result:
    """R17: item aberto classificado `bloqueia beta` (ou P0/P1 com impacto em R1-R9) reprova."""
    if text is None:
        return Result("known_issues_no_blockers", "not_provisioned", {"reason": "known-issues.md ausente"})
    rows = parse_known_issues(text)
    if not rows:
        return Result("known_issues_no_blockers", "fail", {"reason": "nenhuma linha KI-n na tabela"})
    blocking = []
    for row in rows:
        is_open = row["status"].lower().startswith("aberto")
        hits_core = bool(re.search(r"\bR[1-9]\b", row["impact"])) and row["priority"].upper() in ("P0", "P1")
        if is_open and ("bloqueia" in row["class"].lower() or hits_core):
            blocking.append(row["id"])
    return Result("known_issues_no_blockers", "fail" if blocking else "pass",
                  {"issues": len(rows), "blocking_open": len(blocking), "ids": blocking})


# --- relatorio -------------------------------------------------------------------------------------------

def build_report(results: list[Result], *, sha: str, dirty: list[str], strict: bool) -> dict:
    failing = []
    for r in results:
        if not r.blocking:
            continue
        if r.status == "fail" or (strict and r.status in ("skip", "not_provisioned")):
            failing.append(r.name)
    if dirty:
        failing.append("clean_tree")
    return {
        "schema": SCHEMA, "gate": GATE, "sha": sha, "dirty_files": len(dirty),
        "ok": not failing, "failing": failing, "strict": strict,
        "viewports": list(VIEWPORTS.values()),
        "results": [r.as_dict() for r in results] + (
            [Result("clean_tree", "fail", {"dirty_files": dirty[:20]}).as_dict()] if dirty else []),
    }


def to_markdown(report: dict) -> str:
    lines = [f"# Gate de gameplay do beta desktop — {report['sha'][:12]}", "",
             f"- ok: **{report['ok']}** · dirty_files: {report['dirty_files']} · strict: {report['strict']}",
             f"- viewports: {', '.join(report['viewports'])}",
             f"- failing: {', '.join(report['failing']) or '—'}", "",
             "| check | status | bloqueante |", "|---|---|---|"]
    for r in report["results"]:
        lines.append(f"| {r['name']} | {r['status']} | {r['blocking']} |")
    lat = next((r for r in report["results"] if r["name"] == "latency_present"), None)
    if lat and isinstance(lat.get("detail"), dict) and lat["detail"].get("baseline"):
        lines += ["", "## Baseline de latencia (cliente, nearest-rank, sem meta)", ""]
        for vp, base in lat["detail"]["baseline"].items():
            lines.append(f"- {vp}: n={base['turns']} TTFMC p50/p95 {base['ttfmc_ms']['p50']}/{base['ttfmc_ms']['p95']} ms · "
                         f"TTLT p50/p95 {base['ttlt_ms']['p50']}/{base['ttlt_ms']['p95']} ms (indicativo: n<20)")
    return "\n".join(lines) + "\n"


def write_report(report: dict, directory: Path = EVIDENCE) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"gameplay-gate-{report['sha'][:12]}"
    js, md = directory / f"{stem}.json", directory / f"{stem}.md"
    js.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md.write_text(to_markdown(report), encoding="utf-8")
    return js, md


# --- execucao --------------------------------------------------------------------------------------------

def _load_json(path: Path, deps: Deps) -> dict | None:
    if not deps.exists(path):
        return None
    try:
        return json.loads(deps.read_text(path))
    except ValueError:
        return None


def collect(deps: Deps, reports_dir: Path | None = None,
            results_dir: Path | None = None) -> tuple[dict, dict | None, dict]:
    """Le relatorios ja gerados: (F por projeto, vertical, traces por viewport)."""
    from scripts.frontend_eval_report import summarize, summarize_vertical
    reports_dir, results_dir = reports_dir or REPORTS, results_dir or RESULTS
    f_summaries = {}
    for project in VIEWPORTS:
        raw = _load_json(reports_dir / f"gate-f-{project}.json", deps)
        f_summaries[project] = summarize(raw) if raw else None
    raw_v = _load_json(reports_dir / "gate-vertical.json", deps)
    vertical = summarize_vertical(raw_v) if raw_v else None
    traces = {project: _load_json(results_dir / "vertical" / f"vertical-trace-{vp}.json", deps)
              for project, vp in VIEWPORTS.items()}
    return f_summaries, vertical, traces


_CONFIG = """import {{ defineConfig, devices }} from "@playwright/test";
import base from "./playwright.config";
export default defineConfig({{
  ...base, workers: 1, timeout: {timeout}, reporter: [["json", {{ outputFile: "playwright-report/gate/{out}" }}]],
  testMatch: {match}, use: {{ ...base.use, baseURL: "http://127.0.0.1:{port}" }},
  webServer: {server},
  projects: [{projects}],
}});
"""


def _projects(names: list[str]) -> str:
    sizes = {"desktop-1440": (1440, 900), "desktop-1280": (1280, 800)}
    return ", ".join(
        f'{{ name: "{n}", use: {{ ...devices["Desktop Chrome"], viewport: {{ width: {sizes[n][0]}, height: {sizes[n][1]} }} }} }}'
        for n in names)


def run_playwright(deps: Deps, *, vite_port: int, api_port: int, env: dict[str, str]) -> None:
    """Gera configs temporarias (apagadas ao fim), roda F por viewport e o J-V1 (workers=1)."""
    configs: list[Path] = []
    try:
        for project in VIEWPORTS:
            cfg = WEB / f"pw.gate.f.{project}.config.ts"
            cfg.write_text(_CONFIG.format(
                timeout=60_000, out=f"gate-f-{project}.json", match=r"/critical-journeys\.spec\.ts/",
                port=vite_port,
                server=json.dumps({"command": f"node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port {vite_port}",
                                   "url": f"http://127.0.0.1:{vite_port}", "reuseExistingServer": True,
                                   "timeout": 120_000}),
                projects=_projects([project])), encoding="utf-8")
            configs.append(cfg)
            deps.run([NPX, "playwright", "test", "-c", cfg.name], cwd=WEB, env=env)
        vcfg = WEB / "pw.gate.vertical.config.ts"
        vcfg.write_text(_CONFIG.format(
            timeout=240_000, out="gate-vertical.json", match=r"/vertical-journey\.spec\.ts/",
            port=api_port, server="undefined", projects=_projects(list(VIEWPORTS))), encoding="utf-8")
        configs.append(vcfg)
        deps.run([NPX, "playwright", "test", "-c", vcfg.name], cwd=WEB, env=env)
    finally:
        for cfg in configs:
            cfg.unlink(missing_ok=True)


def provision(api_port: int, log_path: Path) -> tuple[subprocess.Popen | None, dict[str, str], str | None]:
    """Sobe a API local (perfil local + MockLLM) e devolve o env da jornada. Falha -> motivo."""
    try:
        from scripts.start_local_api import _supabase_status
        status = _supabase_status()
    except Exception as exc:  # Supabase local fora do ar
        return None, {}, f"supabase local indisponivel: {type(exc).__name__}"
    env = {**os.environ, "RPG_CLIENT_LATENCY_REPORT": "1", "PYTHONUTF8": "1"}
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "scripts/audit_local_server.py", "--port", str(api_port)],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    import httpx
    for _ in range(60):
        try:
            if httpx.get(f"http://127.0.0.1:{api_port}/health", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        proc.terminate()
        return None, {}, "API local nao respondeu em 60s"
    return proc, {
        **os.environ,
        "RPG_VJ_BASE_URL": f"http://127.0.0.1:{api_port}",
        "RPG_VJ_SERVICE_KEY": status["SERVICE_ROLE_KEY"],
        "RPG_VJ_API_LOG": str(log_path),
        "RPG_VJ_PYTHON": sys.executable,
    }, None


def main(argv: list[str] | None = None, deps: Deps | None = None) -> int:
    deps = deps or Deps()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="skip/not_provisioned tambem reprovam")
    parser.add_argument("--reuse", action="store_true", help="nao executa Playwright; le web/test-results")
    parser.add_argument("--api-port", type=int, default=8204)
    parser.add_argument("--vite-port", type=int, default=4204)
    parser.add_argument("--evidence-dir", type=Path, default=EVIDENCE)
    parser.add_argument("--known-issues", type=Path, default=KNOWN_ISSUES)
    args = parser.parse_args(argv)

    sha, dirty = git_sha(deps), dirty_files(deps)   # antes de qualquer arquivo temporario
    proc = None
    results: list[Result] = []
    try:
        if not args.reuse:
            REPORTS.mkdir(parents=True, exist_ok=True)
            proc, env, reason = provision(args.api_port, REPORTS / "gate-api.log")
            if reason:
                results.append(Result("stack_provisioned", "not_provisioned", {"reason": reason}))
            else:
                run_playwright(deps, vite_port=args.vite_port, api_port=args.api_port, env=env)
        from evals.evaluators.gameplay_gate import scan_trace
        f_summaries, vertical, traces = collect(deps)
        results += [check_journeys(f_summaries), check_vertical(vertical), *check_oracles(traces, scan_trace),
                    check_known_issues(deps.read_text(args.known_issues) if deps.exists(args.known_issues) else None)]
    finally:
        if proc is not None:
            proc.terminate()
    report = build_report(results, sha=sha, dirty=dirty, strict=args.strict)
    js, md = write_report(report, args.evidence_dir)
    print(json.dumps({"ok": report["ok"], "failing": report["failing"], "json": str(js), "md": str(md)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
