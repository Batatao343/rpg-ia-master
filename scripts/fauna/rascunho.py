"""SPEC-360 §3.7 passo 1: rascunho deterministico do bloco de fauna de uma regiao (sem LLM).

Pre-preenche so o que sai da ficha: `territorio` = habitat, `horario` por palavras da prosa
(`comportamento`/`gancho`), `antecedencia: imediato` sugerida para `papel_tatico: emboscador`
e `revisao: pendente`. Sinais, presas, reacoes e estacoes ficam para o autor.

Uso: `bash scripts/dev/py.sh scripts/fauna/rascunho.py --regiao nova_arcadia [--out PATH]`.
Nao sobrescreve um arquivo existente sem `--force`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_NOITE = ("noite", "madrugada", "escuro", "anoitecer", "lua")
_DIA = ("dia claro", "sol", "manha", "meio-dia", "tarde")


def guess_horario(text: str) -> list[str]:
    from services.fauna_lint import fold
    from world_utils import PERIODS

    t = fold(text)
    night = any(w in t for w in _NOITE)
    day = any(w in t for w in _DIA)
    if night and not day:
        return ["Anoitecer", "Noite"]
    if day and not night:
        return ["Manhã", "Tarde"]
    return list(PERIODS)


def draft(region: str) -> dict:
    from services import fauna_lint as fl

    refs = fl.load_refs(region, exclude_other=True)
    out: dict[str, dict] = {}
    for cid in sorted(set(refs.fichas) | set(refs.legacy)):
        ficha = refs.fichas.get(cid)
        prose = " ".join(str((ficha or {}).get(k) or "") for k in ("comportamento", "gancho"))
        out[cid] = {
            "fonte": "ficha" if ficha else "legado",
            "ecologia": {
                "horario": guess_horario(prose),
                "territorio": fl.effective_territory(cid, {}, refs),
                "presas": [],
                "suprime": [],
                "foge_de": [],
                "reage": [],
            },
            "sinais": {
                "antecedencia": "imediato"
                if (ficha or {}).get("papel_tatico") == "emboscador"
                else "cedo",
                "rastro": None,
                "resto": None,
                "som": None,
                "cheiro": None,
                "marca": None,
                "aproximacao": None,
                "rumor": None,
            },
            "contra_jogo": str((ficha or {}).get("contra_jogo") or ""),
            "tramas": [],
            "autor": "",
            "revisao": "pendente",
        }
    return {"regiao": region, "criaturas": out}


def main(argv: list[str] | None = None) -> int:
    import yaml

    from services import fauna_lint as fl

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--regiao", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else fl.FAUNA_DIR / f"{args.regiao}.yaml"
    if out.exists() and not args.force:
        print(f"{out} ja existe (use --force ou --out)")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(draft(args.regiao), allow_unicode=True, sort_keys=False, width=100)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"rascunho em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
