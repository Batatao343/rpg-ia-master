"""SPEC-340: registro de feature flags ``RPG_*`` com validade.

O registro (``config/flags.yaml``) é só documentação verificada; o runtime
continua lendo ``os.getenv``. Comandos::

    check                    exit 1 com a lista de erros
    list [--kind K]          lista as flags registradas
    expiring --days N        flags ``release`` que vencem em até N dias
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "flags.yaml"
KINDS = {"release", "ops", "kill_switch", "config", "dev"}
NAME_RE = re.compile(r"RPG_[A-Z0-9_]+")
SPEC_RE = re.compile(r"^SPEC-\d+$")
EXTRA_SOURCES = ("scripts/staging/staging_flags.json", ".env.example")


def load(path: Path = REGISTRY) -> dict[str, dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(k): (v or {}) for k, v in data.items()}


def _is_product_source(rel: str) -> bool:
    if rel.startswith("tests/") or rel.startswith("."):
        return rel.startswith(".github/workflows/") and rel.endswith(".yml")
    return rel.endswith(".py")


def scan_sources(root: Path = ROOT) -> dict[str, set[str]]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout.splitlines()
    files = [f for f in out if _is_product_source(f) or f in EXTRA_SOURCES]
    found: dict[str, set[str]] = {}
    for rel in files:
        p = Path(root) / rel
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in NAME_RE.findall(text):
            found.setdefault(name, set()).add(rel)
    return found


def _as_date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            return None
    return None


def validate(registry: dict[str, dict], found: dict[str, set[str]], today: dt.date) -> list[str]:
    errs: list[str] = []
    patterns = {n: re.compile(n) for n, e in registry.items() if e.get("pattern")}
    exact = {n for n, e in registry.items() if not e.get("pattern")}

    for name, e in registry.items():
        kind = e.get("kind")
        if kind not in KINDS:
            errs.append(f"{name}: kind inválido {kind!r} (use {sorted(KINDS)})")
        spec = e.get("spec")
        if spec is not None and not (isinstance(spec, str) and SPEC_RE.match(spec)):
            errs.append(f"{name}: spec deve ser 'SPEC-NNN' ou null, veio {spec!r}")
        d = e.get("default")
        if d is not None and not isinstance(d, str):
            errs.append(f"{name}: default deve ser string ou null, veio {d!r}")
        exp = e.get("expires")
        if kind == "release":
            if exp is None:
                errs.append(f"{name}: kind release exige `expires` (AAAA-MM-DD)")
            else:
                ed = _as_date(exp)
                if ed is None:
                    errs.append(f"{name}: `expires` inválido {exp!r}")
                elif ed < today:
                    errs.append(
                        f"{name}: flag release vencida em {ed} - remova a flag ou renove "
                        "`expires` com justificativa no `note`"
                    )
        elif exp is not None:
            errs.append(f"{name}: `expires` é proibido em kind {kind!r}")

    for name in sorted(found):
        if name in exact or any(p.fullmatch(name) for p in patterns.values()):
            continue
        files = ", ".join(sorted(found[name])[:3])
        errs.append(f"{name}: lida no código mas sem registro em config/flags.yaml ({files})")

    for name in sorted(exact):
        if name not in found:
            errs.append(f"{name}: entrada órfã - não aparece em nenhuma fonte")
    for name, p in patterns.items():
        if not any(p.fullmatch(f) for f in found):
            errs.append(f"{name}: padrão órfão - nenhum nome casa")
    return errs


def check(root: Path = ROOT, today: dt.date | None = None) -> int:
    root = Path(root)
    errs = validate(load(root / "config" / "flags.yaml"), scan_sources(root), today or dt.date.today())
    for e in errs:
        print(e, file=sys.stderr)
    return 1 if errs else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    lp = sub.add_parser("list")
    lp.add_argument("--kind", choices=sorted(KINDS))
    ep = sub.add_parser("expiring")
    ep.add_argument("--days", type=int, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return check()
    reg = load()
    if a.cmd == "list":
        for n, e in sorted(reg.items()):
            if a.kind and e.get("kind") != a.kind:
                continue
            print(f"{n}\t{e.get('kind')}\t{e.get('spec')}\t{e.get('expires') or ''}")
        return 0
    limit = dt.date.today() + dt.timedelta(days=a.days)
    for n, e in sorted(reg.items()):
        ed = _as_date(e.get("expires"))
        if e.get("kind") == "release" and ed and ed <= limit:
            print(f"{n}\t{ed}\t{e.get('spec')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
