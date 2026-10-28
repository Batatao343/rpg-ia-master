"""SPEC-355 - arena do bloco A (so IMPORTA o avaliador congelado da SPEC-341; nao o altera).

    bash scripts/dev/py.sh docs/spec355/arena_spec355.py base --seeds 0:20 --out f.json \
        [--classes "Sangromante" "Corruptor:alma"] [--versoes id ...] [--cartas id ...]
    bash scripts/dev/py.sh docs/spec355/arena_spec355.py emboscada --seeds 0:20 --out f.json \
        [--base arena-pos-b-0-19.json]

R16: ``p_emb(Postura, nivel)`` = media, em perigo 1..4, de P(d20 + wis + perc < 8 + 2*perigo)
(``world_utils.detection_check``, perception_mod 0, f_viagem = 1: cota superior); taxa realista de
cada celula = ``p_emb * emboscada + (1 - p_emb) * base``. Variante "com contrapartida": na celula
cujo ``full_deck`` tem Carta ``buff_iniciativa`` a parcela de emboscada vale a de base.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "docs", "spec341"))
import arena_spec341 as B  # noqa: E402

import combat_mechanics as cm  # noqa: E402
from services import card_effects as fx  # noqa: E402
from services import cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402

_orig_run_round = orch.run_round


def _ambush_round(scene, actors, sides, state=None, **kw):
    if cs.tactical_round(scene) == 0:
        kw["initiator"] = "enemy"
    return _orig_run_round(scene, actors, sides, state, **kw)


def p_emb(cls: str, level: int) -> float:
    """P(falhar na deteccao) media em perigo 1..4, com a ficha que a arena usa."""
    hero = B.sim.A.hero(cls, level)
    wis = cm.actor_mods(hero).get("wis", 0)
    save_b = hero.get("racial_save_bonus") or {}
    wis += int(save_b.get("mente", save_b.get("wis", 0)) or 0)
    perc = sum(
        int(pe.get("delta", 0) or 0)
        for pe in cm.player_passives(hero)
        if pe.get("trigger") == "perception"
    )
    probs = []
    for danger in (1, 2, 3, 4):
        dc = 8 + 2 * danger
        probs.append(sum(1 for r in range(1, 21) if r + wis + perc < dc) / 20)
    return sum(probs) / len(probs)


def has_initiative_card(cls: str, level: int, sub: str) -> bool:
    for cid in B.sim.full_deck(cls, level, sub):
        card = cards.get_card(cid) or {}
        if any(e.get("kind") == "buff_iniciativa" for e in fx.normalize(card)):
            return True
    return False


def _rate(cells: dict[str, list[float]]) -> float:
    w = sum(v[0] for v in cells.values())
    n = sum(v[1] for v in cells.values())
    return round(w / n, 4) if n else 0.0


def mix(base: dict, amb: dict) -> dict:
    """Mistura R16 por celula. ``base``/``amb``: saida de ``B.posturas``."""
    out: dict = {}
    for cls, subs in base.items():
        out[cls] = {}
        for sub, cell in subs.items():
            real: dict[str, list[float]] = {}
            real_c: dict[str, list[float]] = {}
            pe: dict[str, float] = {}
            real_sub = "" if sub == "todas" else sub
            for key, (bw, bn) in cell["celulas"].items():
                level = int(key.split(" ")[0][1:])
                p = pe.setdefault(str(level), round(p_emb(cls, level), 4))
                aw = amb[cls][sub]["celulas"][key][0]
                real[key] = [p * aw + (1 - p) * bw, bn]
                counter = has_initiative_card(cls, level, real_sub)
                real_c[key] = [bw if counter else p * aw + (1 - p) * bw, bn]
            pad = lambda d: _rate({k: v for k, v in d.items() if k.endswith("padrao")})  # noqa: E731
            eli = lambda d: _rate({k: v for k, v in d.items() if k.endswith("elite")})  # noqa: E731
            out[cls][sub] = {
                "p_emb": pe,
                "base_total": cell["total"],
                "emboscada_total": amb[cls][sub]["total"],
                "realista": {"total": _rate(real), "padrao": pad(real), "elite": eli(real)},
                "realista_com_contrapartida": {
                    "total": _rate(real_c),
                    "padrao": pad(real_c),
                    "elite": eli(real_c),
                },
            }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("base")
    b.add_argument("--seeds", default="0:20")
    b.add_argument("--classes", nargs="*")
    b.add_argument("--versoes", nargs="*", default=[])
    b.add_argument("--cartas", nargs="*", default=[])
    b.add_argument("--out")
    e = sp.add_parser("emboscada")
    e.add_argument("--seeds", default="0:20")
    e.add_argument("--classes", nargs="*")
    e.add_argument("--base")
    e.add_argument("--out")
    args = ap.parse_args(argv)
    rng = B._seeds(args.seeds)
    res: dict = {"seeds": [rng.start, rng.stop]}
    if args.cmd == "base":
        res["versoes"] = B.versoes(args.versoes)
        res["posturas"] = B.posturas(rng, B._classes_arg(args.classes))
        if args.cartas:
            res["cartas"] = B.cartas(rng, args.cartas)
            res["versoes"].update(B.versoes(args.cartas))
    else:
        if args.base:
            base = json.load(open(args.base, encoding="utf-8"))["posturas"]
        else:
            base = B.posturas(rng, B._classes_arg(args.classes))
        orch.run_round = _ambush_round
        try:
            amb = B.posturas(rng, B._classes_arg(args.classes))
        finally:
            orch.run_round = _orig_run_round
        res["cenario"] = "emboscada realista (f_viagem = 1) sobre o avaliador congelado"
        res["posturas"] = mix(base, amb)
    B._write(args.out, res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
