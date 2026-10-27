"""SPEC-339 R15 — arena antes/depois da correcao do tick de controle.

    bash scripts/dev/py.sh docs/spec339/arena_spec339.py run  <antes|depois> [--out arquivo.json]
    bash scripts/dev/py.sh docs/spec339/arena_spec339.py report antes.json depois.json > RELATORIO.md

`run` mede, com o motor que estiver no checkout (as mesmas sementes nos dois lados):
  1. cartas: protocolo de lote (cada Carta isolada, level_req, 20 sementes, padrao) em cada
     arquivo de Postura com taunt/marca/fear/silence; default (niveis 1,3,5) nos arquivos legados;
  2. posturas: taxa de vitoria por Postura e por subclasse (baralho completo, L1/L3/L5, padrao+elite);
  3. inimigos (D5): taxa do heroi contra TODAS as categorias de criatura (baralhos de inimigo com
     taunt/marca entram em jogo), Devoto e Sangromante, L3.
Rode a partir da raiz do repo.
"""

from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "cards"))
sys.path.insert(0, os.path.join(ROOT, "docs", "spec335"))
import arena_posturas as AP  # noqa: E402
import sim  # noqa: E402

from services import card_lint  # noqa: E402

POSTURA_FILES = [
    "devoto_consagrado",
    "devoto_zeloso",
    "sangromante_avaro",
    "sangromante_exposto",
    "sangromante_silencioso",
    "corruptor_alma",
    "corruptor_biologia",
    "corruptor_inorganica",
    "corruptor_tronco",
    "arcanista_cinzento_descoberto",
    "arcanista_cinzento_improvisador",
    "medico_boticario",
]
LEGACY_FILES = ["devoto", "sangromante", "corruptor", "medico", "arcanista"]
CONTROL_KINDS = {"taunt", "marca", "marca_do_abismo", "fear", "silence"}


def _cards_with_control(batch: list[dict]) -> list[dict]:
    from services import card_effects as fx

    out = []
    for c in batch:
        kinds = {str(e.get("kind")) for e in fx.normalize(c)}
        conds = {str(e.get("condicao", "")).lower() for e in fx.normalize(c)}
        if kinds & CONTROL_KINDS or conds & {"medo", "silenciado", "enraizado"}:
            out.append(c)
    return out


def run_cards() -> dict:
    res: dict = {}
    for name in POSTURA_FILES:
        batch = card_lint.load_batch(f"data/cards/posturas/{name}.json")
        print(f"[cards] {name}: {len(batch)} cartas", flush=True)
        res.update(sim.simulate_protocolo_lote(batch))
    for name in LEGACY_FILES:
        batch = _cards_with_control(card_lint.load_batch(f"data/cards/{name}.json"))
        print(f"[cards] legado {name}: {len(batch)} cartas com controle", flush=True)
        if batch:
            res.update(sim.simulate_batch(batch, [1, 3, 5], ["padrao"], 4, list(range(4))))
    return res


def run_posturas(seeds: int = 20) -> dict:
    res: dict = {}
    for cls, subs in AP.POSTURAS.items():
        res[cls] = {}
        for sub in ["", *subs]:
            arm = AP.run_arm(cls, range(seeds), [1, 3, 5], ["padrao", "elite"], 4, sub)
            res[cls][sub or "todas"] = {
                "celulas": arm,
                "total": AP.rate(arm),
                "padrao": AP.rate(arm, ("padrao",)),
                "elite": AP.rate(arm, ("elite",)),
            }
            print(f"[posturas] {cls}/{sub or 'todas'}: {AP.rate(arm):.1%}", flush=True)
    return res


def run_inimigos(seeds: int = 10) -> dict:
    pool = sim.A.creatures_by_category()
    res: dict = {}
    for cls in ("Devoto do Abismo", "Sangromante"):
        res[cls] = {}
        deck = sim.full_deck(cls, 3, "")
        for cat, ids in pool.items():
            if not ids:
                continue
            n = sim.A.group_size(cat, 3)
            wins = fights = 0
            for bid in sim.pick(ids, 4):
                for seed in range(seeds):
                    outcome, _ = sim.fight(bid, n, cls, 3, seed, deck, "inim")
                    wins += outcome == "win"
                    fights += 1
            res[cls][cat] = [wins, fights]
            print(f"[inimigos] {cls}/{cat}: {wins}/{fights}", flush=True)
    return res


def cmd_run(label: str, out: str | None) -> None:
    t0 = time.time()
    res = {
        "label": label,
        "cards": run_cards(),
        "posturas": run_posturas(),
        "inimigos": run_inimigos(),
    }
    res["elapsed_s"] = round(time.time() - t0, 1)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(res, ensure_ascii=False, indent=1) + "\n")


def _pct(x: float) -> str:
    return f"{x * 100:.1f}"


def cmd_report(antes: str, depois: str) -> None:
    a = json.load(open(antes, encoding="utf-8"))
    d = json.load(open(depois, encoding="utf-8"))
    print("# SPEC-339 — Arena antes/depois da correção do tick de controle\n")
    print(
        "Mesmas sementes nos dois lados; só o motor muda. Nenhum número de Carta foi alterado (R16).\n"
    )
    print("## Variação de vitória por Postura/subclasse (baralho completo, L1/L3/L5)\n")
    print(
        "| Postura / subclasse | padrão antes | padrão depois | Δ pp | total antes | total depois | Δ pp |"
    )
    print("|---|---|---|---|---|---|---|")
    for cls, subs in d["posturas"].items():
        for sub, v in subs.items():
            b = a["posturas"][cls][sub]
            print(
                f"| {cls} / {sub} | {_pct(b['padrao'])} | {_pct(v['padrao'])} | "
                f"{(v['padrao'] - b['padrao']) * 100:+.1f} | {_pct(b['total'])} | {_pct(v['total'])} | "
                f"{(v['total'] - b['total']) * 100:+.1f} |"
            )
    print("\n## Cartas com maior variação (|Δ| >= 3 pp no delta de vitória) e bandeiras\n")
    print(
        "| Carta | classe | delta antes (pp) | delta depois (pp) | variação | uso antes→depois | bandeiras antes → depois |"
    )
    print("|---|---|---|---|---|---|---|")
    novas, sumiram = [], []
    for cid, v in d["cards"].items():
        b = a["cards"].get(cid)
        if not b:
            continue
        var = v["delta_pp"] - b["delta_pp"]
        fb, fd = set(b["bandeiras"]), set(v["bandeiras"])
        if "dominante" in fd - fb:
            novas.append(cid)
        if "dominante" in fb - fd:
            sumiram.append(cid)
        if abs(var) >= 3 or fb != fd:
            print(
                f"| `{cid}` | {v['classe']} | {b['delta_pp']:+.1f} | {v['delta_pp']:+.1f} | {var:+.1f} | "
                f"{b['taxa_uso']:.0%}→{v['taxa_uso']:.0%} | {','.join(sorted(fb)) or '-'} → {','.join(sorted(fd)) or '-'} |"
            )
    print(
        f"\n**Bandeira `dominante` NOVA ({len(novas)}):** "
        + (", ".join(f"`{c}`" for c in novas) or "nenhuma")
    )
    print(
        f"\n**Bandeira `dominante` que SUMIU ({len(sumiram)}):** "
        + (", ".join(f"`{c}`" for c in sumiram) or "nenhuma")
    )
    print("\n## Encontros contra baralhos de inimigo (D5, só medir) — herói L3, baralho completo\n")
    print("| Postura | categoria | antes | depois | Δ pp |")
    print("|---|---|---|---|---|")
    for cls, cats in d["inimigos"].items():
        for cat, (w, n) in cats.items():
            wb, nb = a["inimigos"][cls][cat]
            print(
                f"| {cls} | {cat} | {_pct(wb / nb)} | {_pct(w / n)} | {(w / n - wb / nb) * 100:+.1f} |"
            )


if __name__ == "__main__":
    if sys.argv[1] == "run":
        outp = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        cmd_run(sys.argv[2], outp)
    else:
        cmd_report(sys.argv[2], sys.argv[3])
