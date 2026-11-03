"""SPEC-371 P2-3 (sonda informativa, NAO e avaliador): balanco das Posturas com a reacao armada.

    bash scripts/dev/py.sh docs/spec371/arena_posturas_reacao_armada.py [--seeds 180:260] [--out f.json]

Reusa `docs/spec335/arena_posturas.py::run_arm` (mesmo herói, mesmos encontros, bot de baralho
completo). O bot oficial nunca joga reações. Dois braços por Postura (`todas` as subclasses):
- `antes`: baralho SEM as Cartas `reacao_inicial` e bot oficial (a referência da 341/371);
- `depois_sem_armar`: a Carta de reação inicial da Postura garantida no baralho (`extra`: o herói
  real a tem Preparada), bot oficial;
- `depois_armada`: o mesmo baralho + reação armada: se há Carta de reação na mão, ela vai em
  `reaction_card_id` (o motor decide se o gatilho casa e se há Fôlego).
Faixa de aceitação: 45–85 %. Nada aqui recalibra Carta.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "cards"))
sys.path.insert(0, os.path.join(os.getcwd(), "docs", "spec335"))
import arena_posturas as AP  # noqa: E402
import sim  # noqa: E402

from services import cards  # noqa: E402

_full_deck, _decl = sim.full_deck, sim.full_deck_decl


def _sem_novas(*a, **k):
    """Tira as 3 Cartas novas de SPEC-371 (`*1_ini_*`); `cor_membrana` ja existia."""
    novas = {cid for cid in cards.all_cards() if "1_ini_" in cid}
    return [c for c in _full_deck(*a, **k) if c not in novas]


REACAO = {
    "Arcanista Cinzento": "arc1_ini_cinza_nos_olhos",
    "Médico de Campo": "med1_ini_pinca_no_tendao",
    "Devoto do Abismo": "dev1_ini_dor_devolvida",
    "Corruptor": "cor_membrana",
    "Sangromante": "san_esquiva",
}


def _com_reacao(cls, level, sub="", **k):
    return _full_deck(cls, level, sub, extra=[REACAO[cls]], **k)


def _armada(player, piles, target_id, seen=None):
    decl = _decl(player, piles, target_id, seen)
    for cid in piles["mao"]:
        if (cards.get_card(cid) or {}).get("tipo") == "reacao":
            decl.reaction_card_id = cid
            break
    return decl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="180:260")
    ap.add_argument("--out")
    ap.add_argument("--classes", nargs="*")
    args = ap.parse_args()
    a, b = args.seeds.split(":")
    seeds = range(int(a), int(b))
    res: dict = {}
    for cls in args.classes or list(AP.POSTURAS):
        row = {}
        for arm, deck_fn, decl_fn in (
            ("antes", _sem_novas, _decl),
            ("depois_sem_armar", _com_reacao, _decl),
            ("depois_armada", _com_reacao, _armada),
        ):
            sim.full_deck, sim.full_deck_decl = deck_fn, decl_fn
            cells = AP.run_arm(cls, seeds, [1, 3, 5], ["padrao", "elite"], 4, "")
            row[arm] = {
                "total": AP.rate(cells),
                "padrao": AP.rate(cells, ("padrao",)),
                "elite": AP.rate(cells, ("elite",)),
                "celulas": cells,
            }
            print(f"[{cls}] {arm}: {row[arm]['total']:.1%}", flush=True)
        res[cls] = row
    sim.full_deck, sim.full_deck_decl = _full_deck, _decl
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"seeds": [int(a), int(b)], "posturas": res}, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
