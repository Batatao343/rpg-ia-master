"""CLI do gate de unicidade do bestiário (SPEC-349). Uso: lint.py [--regiao R] [--sem-revisao]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import bestiary_lint as bl  # noqa: E402
from services.content_validator import CODEX_DIR, _parse_codex  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regiao", help="só esta região (default: todas)")
    ap.add_argument("--sem-revisao", action="store_true", help="não exige U11 (rascunho)")
    ap.add_argument("--vagas", action="store_true", help="só o tabuleiro (R8)")
    args = ap.parse_args(argv)

    best = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
    docs = [
        {
            "id": str(fm.get("id") or ""),
            "name": str(fm.get("name") or ""),
            "tags": list(fm.get("tags") or []),
            "body": body,
        }
        for _, fm, body in _parse_codex(CODEX_DIR)
        if fm.get("type") == "monster"
    ]
    fichas = bl.load_fichas(args.regiao)
    por_regiao: dict[str, list[dict]] = {}
    for f in fichas.values():
        por_regiao.setdefault(str(f.get("regiao")), []).append(f)

    issues = []
    for regiao, fs in por_regiao.items():
        cotas = bl.COTAS_ONDA.get(regiao, bl.COTAS_PADRAO)
        if args.vagas:
            issues += bl.lint_vagas(bl.load_vagas(regiao), cotas)
            continue
        for f in fs:
            issues += bl.lint_ficha(f, exigir_revisao=not args.sem_revisao)
        issues += bl.lint_regiao(regiao, fs, bestiary=best, codex_docs=docs, cotas=cotas)
    if not args.regiao and not args.vagas:
        esteira_path = ROOT / "data" / "bestiario" / "_esteira.yaml"
        esteira = (
            yaml.safe_load(esteira_path.read_text(encoding="utf-8"))
            if esteira_path.exists()
            else None
        )
        issues += bl.lint_global(por_regiao, esteira=esteira)
    for i in issues:
        print(i)
    n_err = sum(1 for i in issues if i.level == "error")
    print(f"{len(fichas)} fichas · {n_err} erro(s) · {len(issues) - n_err} aviso(s)")
    return 1 if n_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
