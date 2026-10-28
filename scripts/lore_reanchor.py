"""lore_reanchor.py — reaponta as âncoras `arquivo.txt:N[-M]` dos dados de mundo.

Spec: SPEC-348 §3.5 (R4). Os arquivos de dados citam linhas de `lore_nova/*.txt`;
qualquer edição na lore desloca linhas. Este script lê, para cada `lore_nova/<f>.txt`
com diff, a versão do commit `--base` e a atual, monta o mapa linha velha → linha nova
(`difflib`) e reescreve as âncoras. Determinístico, sem LLM, sem decidir conteúdo.

Uso:
    lore_reanchor.py --base <commit> [--report <arquivo>]   # reescreve
    lore_reanchor.py --check                                  # sai != 0 se alguma âncora quebrou

Estados no relatório: `igual` (linha intacta), `linha alterada` (mapeada por
similaridade — conferir à mão), `linha removida` (erro: o executor escolhe a linha).
`data/world/rumor_seeds.json` é regenerado por `build_rumor_seeds.py` (não é reescrito
aqui, só checado).
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LORE_DIR = ROOT / "lore_nova"

REWRITE_FILES = [
    "data/npc_seed_tables.json",
    "data/race_attitudes.json",
    "data/world/festivals.json",
    "data/world/calendar.json",
    "data/world/world_quests.json",
    "data/world/lore_quests.json",
]
CHECK_ONLY_FILES = ["data/world/rumor_seeds.json"]

ANCHOR_RE = re.compile(r"(?P<pre>(?:lore_nova/)?)(?P<file>[a-z_]+\.txt):(?P<a>\d+)(?:-(?P<b>\d+))?")

IGUAL, ALTERADA, REMOVIDA = "igual", "linha alterada", "linha removida"


def _git_show(base: str, rel: str) -> list[str] | None:
    res = subprocess.run(
        ["git", "show", f"{base}:{rel}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        return None
    return res.stdout.splitlines()


def build_line_map(old: list[str], new: list[str]) -> dict[int, tuple[int | None, str]]:
    """linha velha (1-based) -> (linha nova | None, estado)."""
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    out: dict[int, tuple[int | None, str]] = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                out[i1 + k + 1] = (j1 + k + 1, IGUAL)
        elif tag == "delete":
            for i in range(i1, i2):
                out[i + 1] = (None, REMOVIDA)
        elif tag == "replace":
            block_new = new[j1:j2]
            used: set[int] = set()
            for i in range(i1, i2):
                if not old[i].strip():
                    out[i + 1] = (None, REMOVIDA)
                    continue
                best, best_r = None, 0.0
                for j, cand in enumerate(block_new):
                    if j in used or not cand.strip():
                        continue
                    r = difflib.SequenceMatcher(None, old[i], cand, autojunk=False).ratio()
                    if r > best_r:
                        best, best_r = j, r
                if best is not None and best_r >= 0.45:
                    used.add(best)
                    out[i + 1] = (j1 + best + 1, ALTERADA)
                else:
                    out[i + 1] = (None, REMOVIDA)
        # insert: nada a mapear
    return out


def _maps(base: str) -> dict[str, dict[int, tuple[int | None, str]]]:
    maps: dict[str, dict[int, tuple[int | None, str]]] = {}
    for path in sorted(LORE_DIR.glob("*.txt")):
        old = _git_show(base, f"lore_nova/{path.name}")
        if old is None:
            continue
        new = path.read_text(encoding="utf-8").splitlines()
        if old == new:
            continue
        maps[path.name] = build_line_map(old, new)
    return maps


def reanchor(base: str) -> tuple[list[str], int]:
    maps = _maps(base)
    report: list[str] = []
    errors = 0
    for rel in REWRITE_FILES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            nonlocal errors
            fname = m.group("file")
            lmap = maps.get(fname)
            if lmap is None:
                return m.group(0)
            a = int(m.group("a"))
            b = int(m.group("b")) if m.group("b") else None
            na, sa = lmap.get(a, (a, IGUAL))
            nb, sb = (None, IGUAL)
            if b is not None:
                nb, sb = lmap.get(b, (b, IGUAL))
                if nb is None:
                    # fim removido: usa o último mapeado antes dele
                    for k in range(b - 1, a - 1, -1):
                        cand = lmap.get(k, (k, IGUAL))[0]
                        if cand is not None:
                            nb, sb = cand, ALTERADA
                            break
            if na is None:
                errors += 1
                report.append(f"ERRO  {rel}: {fname}:{a} -> {REMOVIDA}")  # noqa: B023
                return m.group(0)
            if nb is not None and nb < na:
                nb = na
            new_ref = f"{m.group('pre')}{fname}:{na}" + (f"-{nb}" if b is not None else "")
            state = IGUAL if (sa == IGUAL and sb == IGUAL) else ALTERADA
            if new_ref != m.group(0) or state != IGUAL:
                report.append(f"{state:15s} {rel}: {m.group(0)} -> {new_ref}")  # noqa: B023
            return new_ref

        new_text = ANCHOR_RE.sub(repl, text)
        if new_text != text:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
    return report, errors


def check() -> list[str]:
    """Âncoras quebradas (linha inexistente ou vazia) em todos os arquivos de dados."""
    problems: list[str] = []
    cache: dict[str, list[str]] = {}
    for rel in REWRITE_FILES + CHECK_ONLY_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for m in ANCHOR_RE.finditer(text):
            fname = m.group("file")
            lines = cache.setdefault(
                fname, (LORE_DIR / fname).read_text(encoding="utf-8").splitlines()
            )
            a = int(m.group("a"))
            b = int(m.group("b")) if m.group("b") else a
            if not (1 <= a <= len(lines) and 1 <= b <= len(lines)) or not lines[a - 1].strip():
                problems.append(f"{rel}: {m.group(0)} aponta para linha vazia/inexistente")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", help="commit base (lore_nova antes das edições)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", help="grava o relatório neste arquivo")
    args = ap.parse_args(argv)

    if args.check:
        problems = check()
        for p in problems:
            print(p)
        print(f"{len(problems)} âncora(s) quebrada(s)")
        return 1 if problems else 0

    if not args.base:
        ap.error("--base é obrigatório sem --check")
    report, errors = reanchor(args.base)
    out = "\n".join(report) + f"\n{len(report)} linha(s) de relatório, {errors} erro(s)\n"
    if args.report:
        Path(args.report).write_text(out, encoding="utf-8")
    print(out)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
