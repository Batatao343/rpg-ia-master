"""SPEC-360 R3: compila `data/bestiario/fauna/*.yaml` em `data/world/fauna.json`.

Deterministico (ordenado por id, LF, `ensure_ascii=False`, uma criatura por linha). O
territorio sai resolvido (default = habitat da ficha / nos da regiao no legado) e os
`predadores` sao derivados das `presas` de todas as regioes. O runtime le so o JSON.

Uso: `bash scripts/dev/py.sh scripts/fauna/build.py [--check]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "world" / "fauna.json"
DEFAULT_PERMANENCIA = [3, 6]


def build_doc() -> dict:
    import yaml

    from services import fauna_lint as fl
    from services.fauna_lint_tramas import normalize_tramas

    criaturas: dict[str, dict] = {}
    for region in fl.covered_regions():
        doc = yaml.safe_load((fl.FAUNA_DIR / f"{region}.yaml").read_text(encoding="utf-8")) or {}
        refs = fl.load_refs(region, exclude_other=True)
        for cid, e in sorted((doc.get("criaturas") or {}).items()):
            eco = dict(e.get("ecologia") or {})
            sinais = {k: v for k, v in (e.get("sinais") or {}).items() if v}
            criaturas[cid] = {
                "regiao": region,
                "ecologia": {
                    "horario": list(eco.get("horario") or []),
                    "estacoes": {
                        k: float(v) for k, v in sorted((eco.get("estacoes") or {}).items())
                    },
                    "territorio": sorted(fl.effective_territory(cid, eco, refs)),
                    "permanencia": list(eco.get("permanencia") or DEFAULT_PERMANENCIA),
                    "presas": sorted(eco.get("presas") or []),
                    "foge_de": sorted(eco.get("foge_de") or []),
                    "reage": [
                        {"quando": str(r["quando"]), "efeito": str(r["efeito"])}
                        for r in eco.get("reage") or []
                    ],
                },
                "sinais": sinais,
                "contra_jogo": str(e.get("contra_jogo") or "").strip(),
                "tramas": normalize_tramas(e.get("tramas")),
                "predadores": [],
            }
            if eco.get("suprime"):  # SPEC-370 R11: so emite quando ha (diff minimo)
                criaturas[cid]["ecologia"]["suprime"] = sorted(eco["suprime"])
    for cid, e in criaturas.items():
        for prey in e["ecologia"]["presas"]:
            if prey in criaturas:
                criaturas[prey]["predadores"].append(cid)
    for cid, e in list(criaturas.items()):
        for target in e["ecologia"].get("suprime") or []:
            if target in criaturas:
                criaturas[target].setdefault("suprimidos_por", []).append(cid)
    for e in criaturas.values():
        e["predadores"] = sorted(set(e["predadores"]))
        if e.get("suprimidos_por"):
            e["suprimidos_por"] = sorted(set(e["suprimidos_por"]))
    return {"version": 1, "criaturas": dict(sorted(criaturas.items()))}


def render(doc: dict) -> str:
    lines = ['{"version": ' + str(int(doc.get("version", 1))) + ', "criaturas": {']
    items = sorted((doc.get("criaturas") or {}).items())
    for i, (cid, e) in enumerate(items):
        body = json.dumps(e, ensure_ascii=False, sort_keys=True)
        lines.append(f"{json.dumps(cid)}: {body}{',' if i < len(items) - 1 else ''}")
    lines.append("}}")
    return "\n".join(lines) + "\n"


def is_fresh() -> bool:
    if not OUT.exists():
        return False
    return OUT.read_text(encoding="utf-8") == render(build_doc())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="falha se o JSON versionado estiver velho")
    args = ap.parse_args(argv)
    text = render(build_doc())
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("fauna.json fresco" if ok else "fauna.json DESATUALIZADO")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"{OUT.relative_to(ROOT)}: {len(json.loads(text)['criaturas'])} criaturas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
