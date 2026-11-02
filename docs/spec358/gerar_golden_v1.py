"""SPEC-358 R12: gera o golden do protocolo v1 do ``scripts/cards/sim.py``.

    bash scripts/dev/py.sh docs/spec358/gerar_golden_v1.py [--sim <caminho do sim.py>]

Rodado com o ``sim.py`` INTOCADO (commit anterior a qualquer edição dele). O ``compute``
é reusado por ``tests/test_card_sim_v2.py::test_v1_reproduz_golden`` para recomputar e
comparar com igualdade exata. Pool de Cartas congelado (monkeypatch de
``cards.cards_for_class``): o golden não quebra quando a esteira promove Cartas novas.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "spec358_sim_v1_golden.json")
CLASSE = "Médico de Campo"


def _card(i: int, **over) -> dict:
    c = {
        "id": f"med_lote_{i}",
        "name": f"Fio {i}",
        "tipo": "ativa",
        "origem": "onda-1",
        "classe": CLASSE,
        "subclasse": "boticario",
        "patamar": "inicial",
        "raridade": "comum",
        "custo_entropia": 0,
        "frequencia": "livre",
        "virtude_permitida": ["mente"],
        "efeitos": [{"kind": "cura", "valor": 3}],
        "descricao": "Cinza de fornalha fecha a ferida.",
        "momento": f"Melhor jogada quando o caso {i} pede calma e o inimigo hesita.",
        "tier": 1,
        "level_req": 1,
        "apex": False,
        "onda": 1,
        "versao": 1,
    }
    c.update(over)
    return c


def synthetic_batch() -> list[dict]:
    """Mesmo lote de ``tests/test_card_sim.py::_synthetic_batch``."""
    return [
        _card(1, efeitos=[{"kind": "dano", "dano_base": 40, "categoria_arma": "leve"}]),
        _card(2, tipo="reacao", efeitos=[{"kind": "contra_ataque", "dano_base": 4}]),
        _card(3, efeitos=[{"kind": "protecao", "valor": 2}]),
    ]


def lote_protocolo() -> list[dict]:
    return [
        _card(11, efeitos=[{"kind": "dano", "dano_base": 5, "categoria_arma": "leve"}]),
        _card(12, efeitos=[{"kind": "protecao", "valor": 3}]),
    ]


def pool_congelado() -> list[dict]:
    return [
        _card(
            91,
            origem="pool-358",
            efeitos=[{"kind": "dano", "dano_base": 4, "categoria_arma": "leve"}],
        ),
        _card(92, origem="pool-358", efeitos=[{"kind": "protecao", "valor": 2}]),
        _card(93, origem="pool-358", efeitos=[{"kind": "cura", "valor": 3}]),
    ]


def load_sim(path: str | None = None, name: str = "sim358"):
    path = path or os.path.join(ROOT, "scripts", "cards", "sim.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def pool_frozen(sim):
    """cards_for_class devolve só o pool fixo (e ele entra no catálogo)."""
    from services import card_effects as fx
    from services import cards

    pool = [fx.materialize(copy.deepcopy(c)) for c in pool_congelado()]
    orig = cards.cards_for_class
    base = cards._load_cards()
    saved = dict(base)
    cards.cards_for_class = lambda class_name, subclass="": [
        c for c in pool if c.get("classe") in (class_name, "")
    ]
    try:
        for c in pool:
            base[c["id"]] = c
        yield
    finally:
        cards.cards_for_class = orig
        base.clear()
        base.update(saved)


def compute(sim) -> dict:
    out: dict = {}
    with pool_frozen(sim):
        out["simulate_batch"] = sim.simulate_batch(
            copy.deepcopy(synthetic_batch()), [1, 3], ["padrao"], 2, [0, 1]
        )
        out["simulate_protocolo_lote"] = sim.simulate_protocolo_lote(
            copy.deepcopy(lote_protocolo())
        )
        with tempfile.TemporaryDirectory() as tmp:
            lote = os.path.join(tmp, "lote.json")
            outp = os.path.join(tmp, "out.json")
            with open(lote, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"cards": lote_protocolo()}, f, ensure_ascii=False)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = sim.main(["--lote", lote, "--protocolo", "lote", "--out", outp])
            with open(outp, encoding="utf-8") as f:
                out_file = f.read()
        out["main"] = {"stdout": buf.getvalue(), "codigo": code, "out_arquivo": out_file}
    return json.loads(json.dumps(out, ensure_ascii=False))  # normaliza p/ tipos JSON


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", default=None)
    args = ap.parse_args()
    sha = subprocess.run(
        ["git", "rev-parse", "main"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    sim = load_sim(args.sim)
    golden = {
        "_meta": {
            "gerado_de": sha,
            "sim_fonte": args.sim or "scripts/cards/sim.py (worktree)",
            "comando": "bash scripts/dev/py.sh docs/spec358/gerar_golden_v1.py",
            "pool_congelado": pool_congelado(),
        },
        **compute(sim),
    }
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(golden, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("golden gravado:", GOLDEN)


if __name__ == "__main__":
    main()
