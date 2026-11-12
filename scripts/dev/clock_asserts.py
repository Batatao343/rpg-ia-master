"""Catraca de relógio real em testes (SPEC-416 Bloco C).

Conta, por função em `tests/**/*.py`, os `assert` que dependem do relógio real
(`time.time`, `perf_counter`, `monotonic`, `datetime.now`, ...), direta ou por nome contaminado.
O baseline `tests/clock_asserts.json` só encolhe (contagem exata, folga 0).

    bash scripts/dev/py.sh scripts/dev/clock_asserts.py            # confere (rc 1 se divergiu)
    bash scripts/dev/py.sh scripts/dev/clock_asserts.py --tighten  # só desce e remove órfãs
    bash scripts/dev/py.sh scripts/dev/clock_asserts.py --update   # regrava (coordenador)

Teste novo com relógio real: use relógio fixo (`monkeypatch` do `time`/`datetime` do módulo sob
teste) ou peça `--update` ao coordenador com o motivo.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests" / "clock_asserts.json"
CLOCKS = frozenset(
    {
        "time.time",
        "time.time_ns",
        "time.perf_counter",
        "time.perf_counter_ns",
        "time.monotonic",
        "time.monotonic_ns",
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.today",
        "datetime.date.today",
    }
)
_FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)


def tracked_tests(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", "tests/*.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return sorted(p for p in out.splitlines() if p)


def _aliases(nodes: list[ast.AST]) -> dict[str, str]:
    """Nome local -> nome canônico, a partir de `import`/`from ... import`."""
    found: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.Import):
            for a in node.names:
                found[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for a in node.names:
                found[a.asname or a.name] = f"{node.module}.{a.name}"
    return found


def _dotted(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _has_clock(expr: ast.AST, aliases: dict[str, str], tainted: set[str]) -> bool:
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Call):
            name = _dotted(sub.func)
            if name:
                head, _, rest = name.partition(".")
                canon = aliases.get(head, head) + (f".{rest}" if rest else "")
                if canon in CLOCKS:
                    return True
        elif isinstance(sub, ast.Name) and sub.id in tainted:
            return True
    return False


def _own_nodes(func: ast.AST) -> list[ast.AST]:
    """Nós da função sem descer em funções/classes aninhadas (elas contam à parte)."""
    out: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        out.append(node)
        if not isinstance(node, (*_FUNC, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))
    return sorted(out, key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))


def _targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Assign):
        raw = node.targets
    elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
        raw = [node.target]
    else:
        return []
    return [n.id for t in raw for n in ast.walk(t) if isinstance(n, ast.Name)]


def count_in_function(func: ast.AST, module_aliases: dict[str, str]) -> int:
    nodes = _own_nodes(func)
    aliases = {**module_aliases, **_aliases(nodes)}
    tainted: set[str] = set()
    count = 0
    for node in nodes:
        if isinstance(node, ast.Assert):
            count += _has_clock(node.test, aliases, tainted)
        elif isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
            if node.value is not None and _has_clock(node.value, aliases, tainted):
                tainted.update(_targets(node))
    return count


def _functions(tree: ast.AST, prefix: str = ""):
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, _FUNC):
            name = f"{prefix}{node.name}"
            yield name, node
            yield from _functions(node, f"{name}.")
        elif isinstance(node, ast.ClassDef):
            yield from _functions(node, f"{prefix}{node.name}.")


def measure(root: Path, files: list[str]) -> dict[str, int]:
    """{"arquivo::qualificado": n} só das funções com n > 0."""
    found: dict[str, int] = {}
    for rel in files:
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        module_aliases = _aliases([n for n in tree.body])
        for name, func in _functions(tree):
            n = count_in_function(func, module_aliases)
            if n:
                found[f"{rel}::{name}"] = n
    return found


def problems(current: dict[str, int], baseline: dict[str, int]) -> list[str]:
    found = []
    for key, n in sorted(current.items()):
        if key not in baseline:
            found.append(f"assert com relógio real novo: {key} ({n})")
        elif n > baseline[key]:
            found.append(f"assert com relógio real cresceu: {key} {baseline[key]} -> {n}")
    for key, base in sorted(baseline.items()):
        n = current.get(key)
        if n is None:
            found.append(
                f"entrada órfã na baseline: {key} ({base}); rode clock_asserts.py --tighten"
            )
        elif n < base:
            found.append(f"baseline folgada: {key} {base} -> {n}; rode clock_asserts.py --tighten")
    return found


def tightened(current: dict[str, int], baseline: dict[str, int]) -> dict[str, int]:
    return {k: min(b, current[k]) for k, b in baseline.items() if k in current}


def load_baseline(path: Path = BASELINE) -> dict[str, int]:
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("functions", {}))


def write_baseline(functions: dict[str, int], path: Path = BASELINE) -> None:
    data = {
        "_doc": "Gerado por scripts/dev/clock_asserts.py --update (SPEC-416). Só encolhe; "
        "--tighten desce, --update sobe (coordenador, com motivo no commit).",
        "functions": dict(sorted(functions.items())),
    }
    path.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def run_tighten(current: dict[str, int], path: Path = BASELINE) -> int:
    baseline = load_baseline(path)
    blocked = [
        m
        for m in problems(current, baseline)
        if not m.startswith(("entrada órfã", "baseline folgada"))
    ]
    if blocked:
        print("\n".join(blocked))
        print("--tighten recusado: use relógio fixo ou peça --update ao coordenador.")
        return 1
    new = tightened(current, baseline)
    if new != baseline:
        write_baseline(new, path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--update", action="store_true")
    group.add_argument("--tighten", action="store_true")
    args = parser.parse_args(argv)
    current = measure(ROOT, tracked_tests(ROOT))
    if args.tighten:
        return run_tighten(current)
    if args.update:
        write_baseline(current)
        print(f"{len(current)} funções na baseline ({sum(current.values())} asserts)")
        return 0
    found = problems(current, load_baseline())
    print("\n".join(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
