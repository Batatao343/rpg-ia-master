"""SPEC-358 R13: equivalência completa do protocolo v1 (``sim.py`` da main × o novo).

    bash scripts/dev/py.sh docs/spec358/equivalencia_v1.py [--ref main] [--only <substr>]

Extrai ``git show <ref>:scripts/cards/sim.py`` para um arquivo temporário ao lado do sim.py
(para o ``ROOT`` do módulo resolver igual), importa os dois e roda ``simulate_protocolo_lote``
(v1, sementes 0-19) nos 15 arquivos ``data/cards/posturas/<postura>_<subclasse>.json``
(os ``*_tronco.json`` ficam de fora). Afirma igualdade EXATA dos dicts e grava
``docs/spec358/equivalencia-v1.json``. Qualquer diferença: exit 1 (bloqueia o pouso).
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "spec358", "equivalencia-v1.json")


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="main")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    src = subprocess.run(
        ["git", "show", f"{args.ref}:scripts/cards/sim.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    sha = subprocess.run(
        ["git", "rev-parse", args.ref], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    tmp = os.path.join(ROOT, "scripts", "cards", "_sim_ref_358.py")
    with open(tmp, "wb") as f:
        f.write(src)
    try:
        old = _load(tmp, "sim_ref_358")
        new = _load(os.path.join(ROOT, "scripts", "cards", "sim.py"), "sim_new_358")
        from services import card_lint

        files = sorted(
            p
            for p in glob.glob(os.path.join(ROOT, "data", "cards", "posturas", "*.json"))
            if not p.endswith("_tronco.json") and args.only in p
        )
        result: dict = {"_meta": {"ref": args.ref, "sha": sha, "sementes": "0-19"}}
        todos_iguais = True
        for path in files:
            batch = card_lint.load_batch(path)
            a = old.simulate_protocolo_lote(json.loads(json.dumps(batch)))
            b = new.simulate_protocolo_lote(json.loads(json.dumps(batch)))
            iguais = a == b
            todos_iguais &= iguais
            result[os.path.basename(path)] = {"cartas": len(batch), "iguais": iguais}
            print(
                os.path.basename(path), len(batch), "iguais" if iguais else "DIFERENTE", flush=True
            )
    finally:
        os.remove(tmp)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return 0 if todos_iguais else 1


if __name__ == "__main__":
    sys.exit(main())
