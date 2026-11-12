"""SPEC-415 R1-R9: pre-checagens do pouso num lugar so (`scripts/dev/land_check.sh NNN`).

Saida: uma linha por check, `OK|WARN|FAIL <check>: <detalhe>`; rc 0 sem FAIL, 1 com FAIL,
2 para uso errado. Checks (nessa ordem): collision, format, ram, review, measure, ci.

    land_check.sh NNN [--only collision,ram]

Env: RPG_LAND_MIN_RAM_GB (3.0), RPG_LAND_SKIP (`ram`, `ci`), RPG_WT_PUSH (=1 liga o check ci).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ("collision", "format", "ram", "review", "measure", "ci")
SKIPPABLE = frozenset({"ram", "ci"})
Runner = Callable[[list[str], str | None], tuple[int, str]]
Result = tuple[str, str]  # (OK|WARN|FAIL, detalhe)

_VERDICT_RE = re.compile(r"APPROVED_WITH_FOLLOWUPS|APPROVED|CHANGES_REQUIRED")
_RISK_RE = re.compile(r"^>\s*\*\*Risco:\*\*\s*`([^`]+)`(?!\s*\|\s*`)", re.MULTILINE)
_RISKS = ("baixo", "médio", "alto")
_MEASURE_RE = re.compile(r"(?<!`)<MEDIR:")
_RAM_RE = re.compile(r"RAM livre:\s*(\d+(?:[.,]\d+)?)\s*GB")
_ORPHAN_RE = re.compile(r"^\s*(\d+)\s+\d+\s*MB\s", re.MULTILINE)


def default_run(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    out = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return out.returncode, out.stdout + (out.stderr if out.returncode else "")


# --------------------------------------------------------------------------- puras


def dirty_paths(porcelain_z: str) -> list[str]:
    """Caminhos de `git status --porcelain -z` (renames/copias: os dois lados)."""
    parts = porcelain_z.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if entry[0] in "RC" or entry[1] in "RC":
            if i < len(parts) and parts[i]:
                paths.append(parts[i])
            i += 1
    return paths


def collisions(branch: list[str], dirty: list[str]) -> list[str]:
    hit = []
    for path in branch:
        for d in dirty:
            if path == d or (d.endswith("/") and path.startswith(d)):
                hit.append(path)
                break
    return hit


def parse_risk(spec_text: str) -> str | None:
    m = _RISK_RE.search(spec_text)
    if not m:
        return None
    value = m.group(1).strip()
    return value if value in _RISKS else None


def last_verdict(handoff_text: str) -> str | None:
    found = _VERDICT_RE.findall(handoff_text)
    return found[-1] if found else None


def _evidence_filled(text: str) -> bool:
    m = re.search(r"^## Evid[êe]ncia verificada\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return bool(m and m.group(1).strip())


def _handoff_role(name: str) -> str:
    m = re.match(r"^SPEC-\d{3}(?:-(sol|astra|terra|luna))?-", name)
    return (m.group(1) or "") if m else ""


def _name_ok(name: str) -> bool:
    path = ROOT / "scripts" / "check_handoff_names.py"
    spec = importlib.util.spec_from_file_location("_chn", path)
    if spec is None or spec.loader is None:
        return True
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bool(mod.PATTERN.match(name))


def review_problems(risk: str | None, handoffs: Mapping[str, str]) -> list[str]:
    """`handoffs`: nome do arquivo -> texto. Regras do R7."""
    if risk is None:
        return ["campo Risco nao preenchido no cabecalho da spec"]
    if risk == "baixo":
        return []
    valid = {n: t for n, t in handoffs.items() if _name_ok(n)}
    if risk == "alto":
        valid = {n: t for n, t in valid.items() if _handoff_role(n) in ("sol", "astra")}
        if not valid:
            return ["Risco alto exige handoff de revisor Opus (-sol- ou -astra-)"]
    if not valid:
        return [f"Risco {risk} exige handoffs/SPEC-NNN-<papel>-review.md aceito pelo lint de nomes"]
    problems: list[str] = []
    for name, text in sorted(valid.items()):
        if last_verdict(text) == "CHANGES_REQUIRED":
            problems.append(f"{name}: ultimo veredito CHANGES_REQUIRED")
        elif not _evidence_filled(text):
            problems.append(f"{name}: falta '## Evidencia verificada' preenchida")
    return problems if len(problems) == len(valid) else []


def pending_measures(spec_text: str) -> list[str]:
    return [
        f"linha {n}: {line.strip()[:80]}"
        for n, line in enumerate(spec_text.splitlines(), 1)
        if _MEASURE_RE.search(line)
    ]


def parse_free_ram_gb(ram_output: str) -> float | None:
    m = _RAM_RE.search(ram_output)
    return float(m.group(1).replace(",", ".")) if m else None


def ci_problem(runs: list[dict], head_sha: str) -> str | None:
    mine = [r for r in runs if r.get("headSha") == head_sha]
    if not mine:
        return f"nenhum run do audit-local para {head_sha[:8]}: rode `wt.sh ci NNN`"
    for r in mine:
        if r.get("event") == "workflow_dispatch" and r.get("conclusion") == "success":
            return None
    r = mine[0]
    return (
        f"run de {head_sha[:8]} nao passou (event={r.get('event')}, "
        f"status={r.get('status')}, conclusion={r.get('conclusion')}): rode `wt.sh ci NNN`"
    )


# --------------------------------------------------------------------------- contexto


@dataclass
class Ctx:
    nnn: str
    branch: str
    wt: str
    main: str
    spec_path: Path | None
    run: Runner
    env: Mapping[str, str]

    def git(self, *args: str, cwd: str | None = None) -> tuple[int, str]:
        return self.run(["git", *args], cwd or self.wt)

    def spec_text(self) -> str:
        return self.spec_path.read_text(encoding="utf-8") if self.spec_path else ""


def worktrees(porcelain: str) -> list[tuple[str, str]]:
    """[(path, branch)] de `git worktree list --porcelain`; 1a entrada = principal."""
    out: list[tuple[str, str]] = []
    for block in porcelain.strip().split("\n\n"):
        path = branch = ""
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = line[9:]
            elif line.startswith("branch refs/heads/"):
                branch = line[18:]
        if path:
            out.append((path, branch))
    return out


def build_ctx(nnn: str, run: Runner, env: Mapping[str, str]) -> Ctx | None:
    branch = f"spec-{nnn}"
    rc, text = run(["git", "worktree", "list", "--porcelain"], None)
    if rc != 0:
        return None
    wts = worktrees(text)
    mine = next((p for p, b in wts if b == branch), None)
    if mine is None or run(["git", "rev-parse", "--verify", "-q", branch], mine)[0] != 0:
        return None
    specs = sorted((Path(mine) / "specs").glob(f"SPEC-{nnn}-*.md"))
    return Ctx(nnn, branch, mine, wts[0][0], specs[0] if specs else None, run, env)


# --------------------------------------------------------------------------- checks


def check_collision(ctx: Ctx) -> Result:
    rc, out = ctx.git("diff", "--name-only", "-z", f"main...{ctx.branch}")
    if rc != 0:
        return "FAIL", f"git diff main...{ctx.branch} falhou: {out.strip()[:120]}"
    branch_files = [p for p in out.split("\0") if p]
    rc, out = ctx.git("status", "--porcelain", "-z", "--untracked-files=normal", cwd=ctx.main)
    if rc != 0:
        return "FAIL", f"git status no principal falhou: {out.strip()[:120]}"
    hit = collisions(branch_files, dirty_paths(out))
    if not hit:
        return "OK", "principal sem edicao nao commitada em arquivo da branch"
    return "FAIL", (
        f"{', '.join(hit)} sujo(s) no principal; o ff da main vai recusar: "
        "commite/descarte no principal ou tire da branch"
    )


def format_command(files: list[str]) -> list[str]:
    return [sys.executable, "-m", "ruff", "format", "--check", "--force-exclude", *files]


def check_format(ctx: Ctx) -> Result:
    rc, out = ctx.git("diff", "--name-only", "--diff-filter=d", "-z", f"main...{ctx.branch}")
    files = [p for p in out.split("\0") if p.endswith(".py") and (Path(ctx.wt) / p).exists()]
    if not files:
        return "OK", "nada a checar"
    rc, out = ctx.run(format_command(files), ctx.wt)
    if rc == 0:
        return "OK", f"{len(files)} arquivo(s) .py formatados"
    bad = [ln[len("Would reformat: ") :] for ln in out.splitlines() if ln.startswith("Would")]
    return (
        "FAIL",
        f"ruff format --check reprovou {', '.join(bad) or out.strip()[:120]}; rode ruff format",
    )


def check_ram(ctx: Ctx) -> Result:
    floor = float(ctx.env.get("RPG_LAND_MIN_RAM_GB", "3.0").replace(",", "."))
    rc, out = ctx.run(["bash", "scripts/dev/ram.sh"], ctx.wt)
    free = parse_free_ram_gb(out) if rc == 0 else None
    if free is None:
        return "WARN", "nao consegui ler a RAM livre (ram.sh)"
    pids = _ORPHAN_RE.findall(out)
    if free < floor:
        if "ram" in ctx.env.get("RPG_LAND_SKIP", "").split(","):
            return "WARN", f"ram ignorada (RPG_LAND_SKIP): {free:.1f} GB < {floor:.1f} GB"
        return "FAIL", f"{free:.1f} GB livres < piso {floor:.1f} GB"
    if pids:
        return "WARN", f"{free:.1f} GB livres; pytest/python orfao PID {', '.join(pids)}"
    return "OK", f"{free:.1f} GB livres"


def check_review(ctx: Ctx) -> Result:
    risk = parse_risk(ctx.spec_text())
    handoffs = {
        p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in sorted((Path(ctx.wt) / "handoffs").glob(f"SPEC-{ctx.nnn}-*.md"))
    }
    problems = review_problems(risk, handoffs)
    if problems:
        return "FAIL", "; ".join(problems)
    if risk == "baixo":
        return "OK", "Risco baixo: sem revisor obrigatorio"
    return "OK", f"Risco {risk}: revisao aprovada com evidencia"


def check_measure(ctx: Ctx) -> Result:
    found = pending_measures(ctx.spec_text())
    if found:
        return "FAIL", "marcador <MEDIR: pendente em " + "; ".join(found[:5])
    return "OK", "nenhuma medicao pendente"


def check_ci(ctx: Ctx) -> Result:
    if parse_risk(ctx.spec_text()) != "alto":
        return "OK", "nao exigido"
    if ctx.env.get("RPG_WT_PUSH") != "1":
        return "WARN", (
            "CI pre-pouso desligado (aguarda autorizacao do dono para push de branch); "
            "registre em 'Nao rodou e por que'"
        )
    if "ci" in ctx.env.get("RPG_LAND_SKIP", "").split(","):
        return "WARN", "ci ignorado (RPG_LAND_SKIP)"
    rc, out = ctx.run(
        ["gh", "run", "list", "--workflow", "audit-local.yml", "--branch", ctx.branch,
         "--json", "headSha,conclusion,status,event", "--limit", "10"],
        ctx.wt,
    )  # fmt: skip
    if rc != 0:
        return "FAIL", f"gh run list falhou: {out.strip()[:120]}"
    try:
        runs = json.loads(out or "[]")
    except json.JSONDecodeError:
        return "FAIL", "saida do gh nao e JSON"
    head = ctx.git("rev-parse", ctx.branch)[1].strip()
    problem = ci_problem(runs, head)
    return ("FAIL", problem) if problem else ("OK", f"audit-local verde em {head[:8]}")


_FUNCS: dict[str, Callable[[Ctx], Result]] = {
    "collision": check_collision,
    "format": check_format,
    "ram": check_ram,
    "review": check_review,
    "measure": check_measure,
    "ci": check_ci,
}


def _parse_args(argv: list[str]) -> tuple[str, list[str]] | None:
    if not argv or not re.fullmatch(r"\d{3}", argv[0]):
        return None
    only = list(CHECKS)
    rest = argv[1:]
    if rest:
        if rest[0] != "--only" or len(rest) != 2:
            return None
        only = [c for c in rest[1].split(",") if c]
        if not only or any(c not in CHECKS for c in only):
            return None
        only = [c for c in CHECKS if c in only]
    return argv[0], only


def main(
    argv: list[str] | None = None, run: Runner | None = None, env: Mapping[str, str] | None = None
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    parsed = _parse_args(argv)
    skip = [s for s in env.get("RPG_LAND_SKIP", "").split(",") if s]
    if parsed is None or any(s not in SKIPPABLE for s in skip):
        print(
            "uso: land_check.sh NNN [--only <check>[,...]]; RPG_LAND_SKIP so aceita ram,ci",
            file=sys.stderr,
        )
        return 2
    nnn, only = parsed
    ctx = build_ctx(nnn, run or default_run, env)
    if ctx is None:
        print(f"spec-{nnn}: branch/worktree inexistente", file=sys.stderr)
        return 2
    if ctx.spec_path is None:
        print(f"specs/SPEC-{nnn}-*.md inexistente", file=sys.stderr)
        return 2
    failed = False
    for name in only:
        level, detail = _FUNCS[name](ctx)
        failed = failed or level == "FAIL"
        print(f"{level} {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
