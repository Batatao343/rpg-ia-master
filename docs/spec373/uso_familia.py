"""SPEC-373 R7/R14: uso de cada inf_* (max por semente 0-11, ids de instancia) e Cartas que faltam.

Grava docs/spec373/uso-familia.json. So importa; nao modifica nada.
"""

from __future__ import annotations

import collections
import json
import math
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["RPG_FORCE_MOCK"] = "1"
os.environ["RPG_ENEMY_DECKS"] = "on"

TETO = 15


def _uses(bestiary: dict, edk) -> list[collections.Counter]:
    runs: list[collections.Counter] = []
    for seed in range(12):
        c: collections.Counter = collections.Counter()
        for bid, entry in bestiary.items():
            c.update(x for x in edk.build_enemy_deck({**entry, "id": f"{bid}_1"}, seed) if x.startswith("inf_"))
        runs.append(c)
    c = collections.Counter()
    for bid, entry in bestiary.items():
        seed = zlib.crc32(f"game-x|3|{bid}".encode())
        c.update(x for x in edk.build_enemy_deck({**entry, "id": f"{bid}_1"}, seed) if x.startswith("inf_"))
    runs.append(c)
    return runs


def main() -> None:
    from agents.bestiary import load_bestiary
    from services import enemy_decks as edk

    best = load_bestiary()
    pools = edk._pools()
    meta = edk._meta()["familias"]
    runs = _uses(best, edk)
    peak: dict[str, int] = {}
    for c in runs:
        for k, v in c.items():
            peak[k] = max(peak.get(k, 0), v)
    fam_n: collections.Counter = collections.Counter()
    fam_m: collections.Counter = collections.Counter()
    for bid, entry in best.items():
        fam = edk.family_key({**entry, "id": bid})
        if fam:
            (fam_m if edk._autoral({**entry, "id": bid}) else fam_n)[fam] += 1
    out: dict = {"teto": TETO, "familias": {}, "faccoes": {}}
    for fam in edk.FAMILIAS:
        sigs = {str(s["carta"]) for s in meta[fam]["assinaturas"]}
        commons = [c for c in pools["familias"][fam] if c not in sigs]
        n, m = fam_n[fam], fam_m[fam]
        s_need = max(2, math.ceil(n / 8))
        p_need = math.ceil((3 * n + 1.5 * m) / 8)
        out["familias"][fam] = {
            "N": n,
            "M": m,
            "assinaturas": len(sigs),
            "comuns": len(commons),
            "S_min": s_need,
            "P_min": p_need,
            "faltam_assinaturas": max(0, s_need - len(sigs)),
            "faltam_comuns": max(0, p_need - len(commons)),
            "pico_assinatura": max((peak.get(c, 0) for c in sigs), default=0),
            "pico_comum": max((peak.get(c, 0) for c in commons), default=0),
        }
    fac_cards = {c for ids in pools["faccoes"].values() for c in ids}
    out["faccoes"] = {"pico": max((peak.get(c, 0) for c in fac_cards), default=0)}
    out["acima_do_teto"] = {k: v for k, v in sorted(peak.items()) if v > TETO}
    out["faltam_total"] = sum(
        f["faltam_assinaturas"] + f["faltam_comuns"] for f in out["familias"].values()
    )
    (ROOT / "docs/spec373/uso-familia.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), "utf-8"
    )
    for fam, f in out["familias"].items():
        print(fam, f)
    print("acima do teto:", len(out["acima_do_teto"]), "faltam:", out["faltam_total"])


if __name__ == "__main__":
    main()
