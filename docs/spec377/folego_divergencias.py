"""SPEC-377 Etapa 0 (R10): divergencias entre os dois ``custo_folego``. So importa e le.

Modos: (i) bruto (JSON em disco), (ii) catalogo (``cards.all_cards``), (iii) ``effective_card``
com Ruptura e evolucao A/B. ``--lote-v2 ARQ`` roda o protocolo lote-v2 das divergentes com a
funcao em vigor (``--jogo`` troca ``fx.custo_folego`` pela do jogo, em memoria).
Uso: bash scripts/dev/py.sh docs/spec377/folego_divergencias.py [--out X.json] [--lote-v2 Y.json [--jogo]]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import card_effects as fx  # noqa: E402
from services import cards  # noqa: E402

_JOGO = cards.custo_folego
_LINT = fx.custo_folego


def _par(card: dict) -> tuple[object, object]:
    try:
        lint: object = _LINT(card)
    except (ValueError, TypeError) as exc:
        lint = f"erro:{type(exc).__name__}"
    return _JOGO(card), lint


def _bruto() -> list[dict]:
    out = []
    for path in cards._card_files():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for c in data.get("cards") or []:
            if isinstance(c, dict) and c.get("id"):
                j, li = _par(c)
                if j != li:
                    out.append({"id": c["id"], "arquivo": Path(path).name, "jogo": j, "lint": li})
    return out


def _catalogo() -> tuple[int, list[dict]]:
    allc = cards.all_cards()
    out = []
    for cid, c in allc.items():
        j, li = _par(c)
        if j != li:
            out.append({"id": cid, "jogo": j, "lint": li})
    return len(allc), out


def _efetivas() -> tuple[int, list[dict]]:
    out, n = [], 0
    for cid, c in cards.all_cards().items():
        if not (c.get("ruptura") or c.get("evolucao")):
            continue
        n += 1
        variantes = [("base", {}, False), ("ruptura", {}, True)]
        for cam in ("A", "B"):
            variantes += [(cam, {"evolved_cards": {cid: cam}}, False)]
            variantes += [(cam + "+ruptura", {"evolved_cards": {cid: cam}}, True)]
        for nome, player, rup in variantes:
            eff = cards.effective_card(copy.deepcopy(player), cid, ruptura=rup)
            if eff is None:
                continue
            j, li = _par(eff)
            if j != li:
                out.append({"id": cid, "variante": nome, "jogo": j, "lint": li})
    return n, out


def _lote_v2(ids: list[str]) -> dict:
    from scripts.cards import sim

    batch = [fx.materialize(copy.deepcopy(cards.all_cards()[i])) for i in ids]
    rep = sim.simulate_protocolo_lote(batch, protocolo="v2")
    keep = (
        "vitoria_sem",
        "vitoria_ref",
        "vitoria_com",
        "delta_pp",
        "delta_base",
        "bandeiras",
        "avisos",
    )
    return {
        cid: {k: r.get(k) for k in keep} | {"ref_custo_folego": (r.get("referencia") or {})}
        for cid, r in rep.items()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--lote-v2")
    ap.add_argument("--jogo", action="store_true")
    args = ap.parse_args()
    if args.lote_v2:
        if args.jogo:
            fx.custo_folego = _JOGO
        rep = _lote_v2(["cor_toque", "toque_corrosivo"])
        Path(args.lote_v2).write_text(
            json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    bruto = _bruto()
    n_cat, cat = _catalogo()
    n_eff, eff = _efetivas()
    res = {
        "bruto": bruto,
        "catalogo": {"cartas": n_cat, "divergentes": cat},
        "efetivas": {"cartas_com_ruptura_ou_evolucao": n_eff, "divergentes": eff},
    }
    txt = json.dumps(res, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(txt, encoding="utf-8", newline="\n")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
