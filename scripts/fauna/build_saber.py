"""SPEC-371 R6: compila o `contra_jogo` das fichas em `data/world/bestiario_saber.json`.

Deterministico (ordenado por id, LF, `ensure_ascii=False`, uma criatura por linha). O runtime
le so o JSON; nunca os YAMLs das fichas. Fichas `retro` (legado) e sem `contra_jogo` ficam fora.

Uso: `bash scripts/dev/py.sh scripts/fauna/build_saber.py [--check]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "world" / "bestiario_saber.json"
FICHAS_DIR = ROOT / "data" / "bestiario" / "fichas"


def build_doc() -> dict:
    import yaml

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    criaturas: dict[str, dict] = {}
    for path in sorted(FICHAS_DIR.glob("*.yaml")):
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=loader) or {}  # noqa: S506
        for ficha in doc.get("criaturas") or []:
            texto = str(ficha.get("contra_jogo") or "").strip()
            if ficha.get("status") == "retro" or not texto:
                continue
            criaturas[str(ficha["id"])] = {
                "contra_jogo": texto,
                "regiao": str(doc.get("regiao") or path.stem),
            }
    return {"version": 1, "criaturas": dict(sorted(criaturas.items()))}


def render(doc: dict) -> str:
    lines = ['{"version": ' + str(int(doc.get("version", 1))) + ', "criaturas": {']
    items = sorted((doc.get("criaturas") or {}).items())
    for i, (cid, e) in enumerate(items):
        body = json.dumps(e, ensure_ascii=False, sort_keys=True)
        lines.append(f"{json.dumps(cid)}: {body}{',' if i < len(items) - 1 else ''}")
    lines.append("}}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="falha se o JSON versionado estiver velho")
    args = ap.parse_args(argv)
    text = render(build_doc())
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("bestiario_saber.json fresco" if ok else "bestiario_saber.json DESATUALIZADO")
        return 0 if ok else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"{OUT.relative_to(ROOT)}: {len(json.loads(text)['criaturas'])} criaturas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
