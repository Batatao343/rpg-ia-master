"""SPEC-418: gate de tipos (basedpyright) com baseline que so encolhe.

    type_gate.py [--check]                  erro novo ou baseline folgada => rc 1
    type_gate.py --tighten                  regrava a baseline so descendo (livre p/ executor)
    type_gate.py --update --reason TEXTO    unica operacao que acrescenta entrada (coordenador)
    type_gate.py --land --base main         uma linha `OK|WARN|FAIL types: ...` (land_check)
    type_gate.py --files ARQ...             checa so os arquivos dados, sem baseline

O checador roda com `--writebaseline` numa copia temporaria da baseline: o JSON de saida traz so os
erros novos e a copia passa a refletir o estado atual (entradas consertadas somem). O arquivo
versionado nunca muda num check.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_REL = ".basedpyright/baseline.json"
TRIGGERS = frozenset({"pyproject.toml", "uv.lock", BASELINE_REL})
TIMEOUT_S = 600
MAX_LINES = 40
Diag = tuple[str, int, str, str]  # arquivo posix relativo, linha, regra, mensagem
Entries = Counter  # Counter[tuple[str, str]]: (arquivo, regra) -> n


def land_line(status: str, detail: str) -> str:
    return f"{status} types: {detail}"


def needs_check(changed: list[str]) -> bool:
    """Qualquer .py (mesmo fora do escopo, que importa llm_setup etc.) ou config/lock/baseline."""
    return any(p.endswith(".py") or p in TRIGGERS for p in changed)


def entries(baseline_json: dict) -> Entries:
    out: Entries = Counter()
    for fname, items in (baseline_json.get("files") or {}).items():
        key = fname.removeprefix("./")
        for item in items:
            out[(key, str(item.get("code")))] += 1
    return out


def slack(base: Entries, current: Entries) -> list[str]:
    """R10: entradas da baseline que o estado atual nao precisa mais."""
    return [
        f"baseline folgada: {f} {r} {n} -> {current.get((f, r), 0)}; rode type_gate.py --tighten"
        for (f, r), n in sorted(base.items())
        if current.get((f, r), 0) < n
    ]


def is_shrink_only(old: Entries, new: Entries) -> bool:
    return all(old.get(k, 0) >= n for k, n in new.items())


def growth(base_ref: Entries, head: Entries) -> list[str]:
    """R12.1: a baseline do branch nao pode ter entrada que a base nao tem."""
    return [
        f"baseline cresceu: {f} {r} {base_ref.get((f, r), 0)} -> {n}"
        for (f, r), n in sorted(head.items())
        if n > base_ref.get((f, r), 0)
    ]


def checker_installed() -> bool:
    return importlib.util.find_spec("basedpyright") is not None


def _rel(path: str, repo: Path) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def run_checker(paths: list[str] | None, baseline: Path | None, repo: Path = ROOT) -> list[Diag]:
    """Unico ponto que chama o subprocesso. Com `baseline`: `--writebaseline` nessa copia."""
    cmd = [sys.executable, "-m", "basedpyright", "--outputjson"]
    if baseline is not None:
        cmd += ["--writebaseline", "--baselinefile", str(baseline)]
    out = subprocess.run(
        [*cmd, *(paths or [])],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    try:
        # --writebaseline imprime "updated <arq> with N errors" antes do JSON
        data = json.loads(
            out.stdout[out.stdout.find("\n{") + 1 :] if "\n{" in out.stdout else out.stdout
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"basedpyright sem JSON (rc {out.returncode}): {(out.stderr or out.stdout)[:300]}"
        ) from exc
    return [
        (
            _rel(d["file"], repo),
            d["range"]["start"]["line"] + 1,
            d.get("rule") or "-",
            d["message"].splitlines()[0],
        )
        for d in data.get("generalDiagnostics", [])
        if d.get("severity") == "error"
    ]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_base(repo: Path, base: str) -> dict | None:
    out = subprocess.run(
        ["git", "show", f"{base}:{BASELINE_REL}"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None


def evaluate(repo: Path) -> tuple[list[Diag], list[str], Entries, Entries, Path]:
    """Roda uma vez contra copia da baseline. Retorna (novos, folgas, antes, depois, copia)."""
    versioned = repo / BASELINE_REL
    tmpdir = Path(tempfile.mkdtemp(prefix="type_gate_"))
    tmp = tmpdir / "baseline.json"
    if versioned.exists():
        shutil.copyfile(versioned, tmp)
    new = run_checker(None, tmp, repo)
    before, after = entries(_load(versioned)), entries(_load(tmp))
    return new, slack(before, after), before, after, tmp


def _fmt(diags: list[Diag]) -> list[str]:
    lines = [f"{f}:{ln} {rule} {msg}" for f, ln, rule, msg in diags[:MAX_LINES]]
    if len(diags) > MAX_LINES:
        lines.append(f"... e mais {len(diags) - MAX_LINES}")
    return lines + [f"total: {len(diags)} erro(s) novo(s)"]


def cmd_check(repo: Path) -> int:
    new, slacks, *_ = evaluate(repo)
    if new:
        print("\n".join(_fmt(new)))
    print("\n".join(slacks[:MAX_LINES]))
    if not new and not slacks:
        print("OK types: nenhum erro novo, baseline justa")
    return 1 if new or slacks else 0


def cmd_tighten(repo: Path) -> int:
    new, _, before, after, tmp = evaluate(repo)
    if new:
        print("\n".join(_fmt(new)))
        print("conserte ou peça `--update` ao coordenador")
        return 1
    if not is_shrink_only(before, after):
        print("recusado: o resultado nao e sub-multiconjunto da baseline", file=sys.stderr)
        return 1
    for (f, r), n in sorted((before - after).items()):
        print(f"removida: {f} {r} (-{n})")
    if before != after:
        shutil.copyfile(tmp, repo / BASELINE_REL)
    return 0


def cmd_update(repo: Path, reason: str) -> int:
    if not reason.strip():
        print("--update exige --reason nao vazio", file=sys.stderr)
        return 2
    _, _, before, after, tmp = evaluate(repo)
    target = repo / BASELINE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tmp, target)
    log = repo / "docs" / "spec418" / "baseline_log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    added = sum((after - before).values())
    with log.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{date.today().isoformat()} · +{added} entradas · {reason.strip()}\n")
    print(f"baseline gravada: {sum(after.values())} entradas (+{added})")
    return 0


def cmd_land(repo: Path, base: str) -> int:
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8",
    )  # fmt: skip
    changed = [ln.strip() for ln in diff.stdout.splitlines() if ln.strip()]
    if not needs_check(changed):
        print(land_line("OK", "nada a checar"))
        return 0
    if not checker_installed():
        print(land_line("WARN", "basedpyright nao instalado neste venv (uv sync --all-extras)"))
        return 0
    head = entries(_load(repo / BASELINE_REL))
    base_json = _read_base(repo, base)
    grew = growth(entries(base_json), head) if base_json is not None else []
    if grew:
        print(land_line("FAIL", f"{len(grew)} entrada(s): " + "; ".join(grew[:3])))
        return 1
    new, slacks, *_ = evaluate(repo)
    if new:
        top = ", ".join(f"{f}:{ln} {rule}" for f, ln, rule, _ in new[:3])
        print(land_line("FAIL", f"{len(new)} erros novos ({top})"))
        return 1
    if slacks:
        print(land_line("FAIL", f"{len(slacks)} folga(s): " + "; ".join(slacks[:2])))
        return 1
    print(land_line("OK", f"nenhum erro novo, baseline com {sum(head.values())} entradas"))
    return 0


def cmd_files(repo: Path, files: list[str]) -> int:
    diags = run_checker([str(Path(f).resolve()) for f in files], None, repo)
    for f, ln, rule, msg in diags:
        print(f"{f}:{ln} {rule} {msg}")
    return 1 if diags else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--tighten", action="store_true")
    mode.add_argument("--update", action="store_true")
    mode.add_argument("--land", action="store_true")
    mode.add_argument("--files", nargs="+", metavar="ARQ")
    ap.add_argument("--reason", default="")
    ap.add_argument("--base", default="main")
    ap.add_argument("--repo", default=str(ROOT))
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    if a.land:
        return cmd_land(repo, a.base)
    if not checker_installed():
        print("basedpyright nao instalado: rode `uv sync --all-extras`", file=sys.stderr)
        return 2
    try:
        if a.files:
            return cmd_files(repo, a.files)
        if a.tighten:
            return cmd_tighten(repo)
        if a.update:
            return cmd_update(repo, a.reason)
        return cmd_check(repo)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"type_gate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
