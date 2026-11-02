"""SPEC-349 Etapa 7: calibra a arena por criatura com ajustes numéricos registrados.

Uso:
    bash scripts/dev/py.sh scripts/bestiario/calibrar.py --regioes nova_arcadia,brekmar \
        --seeds 20 --rodadas 6

Para cada criatura fora de 45-85 % (nos modos ``off`` e ``on``) move UM dial por rodada:
``corpo`` (Virtude Corpo, logo Vitalidade pela tabela) ou ``dano`` (dano_base do ataque básico e
da assinatura). Slots reinventados (R3) só aceitam ``dano``: Virtudes e Vitalidade do slot não
mudam. Cada ajuste fica em ``data/bestiario/mecanica/_ajustes.yaml`` com a leitura da arena que
o motivou (cumpre "cada ajuste é registrado"). Nada aqui toca evaluator, expected ou baseline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gerar_mecanica as gm  # noqa: E402

LO, HI = 0.45, 0.85
AJ_PATH = ROOT / "data" / "bestiario" / "mecanica" / "_ajustes.yaml"
BASE_PATH = ROOT / "docs" / "spec349" / "arena-slots-baseline.json"
LIMITE = 7
LIMITE_DANO = 7
ALVO = 0.65


def _ler() -> dict:
    if AJ_PATH.exists():
        return yaml.safe_load(AJ_PATH.read_text(encoding="utf-8")).get("ajustes") or {}
    return {}


def _gravar(aj: dict) -> None:
    head = (
        "# SPEC-349 Etapa 7: ajustes numéricos da arena (scripts/bestiario/calibrar.py).\n"
        "# corpo: soma na Virtude Corpo (Vitalidade pela tabela); dano: soma no dano_base do\n"
        "# ataque básico e da assinatura; forca: soma na Virtude Força (acerto); sig: só a assinatura. `arena` = leitura (L3/L5, off | on) que motivou o último passo.\n"
    )
    body = yaml.safe_dump({"ajustes": aj}, allow_unicode=True, sort_keys=True, width=100)
    with open(AJ_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + body)


def _arena(ids: list[str], seeds: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = tmp.name
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "bestiario" / "arena.py"),
        "--regiao",
        "nova_arcadia",
        "--seeds",
        str(seeds),
        "--ids",
        ",".join(ids),
        "--json",
        out,
    ]
    subprocess.run(cmd, cwd=ROOT, check=False, stdout=subprocess.DEVNULL)
    return json.loads(Path(out).read_text(encoding="utf-8"))["criaturas"]


def _fora(cells: dict, base: dict | None) -> float:
    """0 = dentro da faixa e do delta; senão a maior violação (positiva: fácil demais)."""
    viol: list[float] = []
    for key, w in cells.items():
        if w > HI:
            viol.append(w - HI)
        elif w < LO:
            viol.append(w - LO)
        if base and key in base and LO <= base[key] <= HI and abs(w - base[key]) > 0.08:
            viol.append(w - base[key])
    return max(viol, key=abs) if viol else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regioes", required=True)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--rodadas", type=int, default=6)
    ap.add_argument("--ids", default="", help="restringe a estas criaturas")
    a = ap.parse_args()

    regs = a.regioes.split(",")
    fichas: dict[str, dict] = {}
    for r in regs:
        doc = gm._load_yaml(ROOT / "data" / "bestiario" / "fichas" / f"{r}.yaml")
        for f in doc["criaturas"]:
            if f.get("status") != "retro":
                fichas[f["id"]] = f
    if a.ids:
        fichas = {k: v for k, v in fichas.items() if k in a.ids.split(",")}
    base_all = (
        json.loads(BASE_PATH.read_text(encoding="utf-8"))["criaturas"] if BASE_PATH.exists() else {}
    )
    best = {i: (9.0, {}, "") for i in fichas}  # (distância, ajuste, leitura)
    pend = sorted(fichas)
    for rodada in range(a.rodadas + 1):
        for r in regs:
            gm.gerar(r)
        res = _arena(pend, a.seeds)
        aj = _ler()
        nxt = []
        for cid in pend:
            cells = res[cid]["cells"]
            slot = fichas[cid]["status"] != "nova"
            d = _fora(cells, (base_all.get(cid) or {}).get("cells") if slot else None)
            cur = aj.get(cid) or {}
            if abs(d) < best[cid][0]:
                best[cid] = (
                    abs(d),
                    {k: cur.get(k, 0) for k in ("corpo", "dano", "sig", "forca")},
                    " | ".join(f"{k} {v:.0%}" for k, v in sorted(cells.items())),
                )
            leitura = " | ".join(f"{k} {v:.0%}" for k, v in sorted(cells.items()))
            if d == 0:
                aj.setdefault(cid, {})["arena"] = leitura
                continue
            if rodada == a.rodadas:  # esgotou: fica com o melhor visto
                aj.setdefault(cid, {}).update(best[cid][1])
                aj[cid]["arena"] = f"{best[cid][2]} (melhor de {a.rodadas} rodadas)"
                continue
            # vitória alta = criatura fraca demais -> reforça; vitória baixa -> enfraquece
            media = sum(cells.values()) / len(cells)
            alvo = ALVO
            base_cells = (base_all.get(cid) or {}).get("cells") if slot else None
            if base_cells and all(LO <= v <= HI for v in base_cells.values()):
                # slot que já estava na faixa: o alvo é a dificuldade de antes (delta <= 8 pp)
                alvo = sum(base_cells.values()) / len(base_cells)
            sentido = 1 if media > alvo else -1
            k = max(1, min(5, round(abs(media - alvo) / 0.12)))
            comps = (
                ["dano"]
                if slot
                else (
                    ["dano", "forca"]
                    if fichas[cid]["categoria"] == "chefe"
                    else ["corpo", "dano", "forca"]
                )
            )
            novo = {c: int(cur.get(c, 0)) for c in (*comps, "sig")}
            for _ in range(k):
                comp = min(comps, key=lambda c: (abs(novo[c]), comps.index(c)))
                lim = LIMITE_DANO if comp == "dano" else LIMITE
                novo[comp] = max(-lim, min(lim, novo[comp] + sentido))
            if (
                len(cells) == 2
                and abs(
                    cells.get("L3|on", cells.get("L5|on", 0))
                    - cells.get("L3|off", cells.get("L5|off", 0))
                )
                > 0.15
            ):
                on = next(v for k, v in cells.items() if k.endswith("|on"))
                off = next(v for k, v in cells.items() if k.endswith("|off"))
                novo["sig"] = max(
                    -LIMITE_DANO, min(LIMITE_DANO, novo["sig"] + (1 if on > off else -1))
                )
            aj.setdefault(cid, {}).update(novo)
            aj[cid]["arena"] = leitura
            nxt.append(cid)
        _gravar(aj)
        print(f"rodada {rodada}: {len(pend)} medidas, {len(nxt)} seguem", flush=True)
        pend = nxt
        if not pend:
            break
    for r in regs:
        gm.gerar(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
