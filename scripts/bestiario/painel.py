"""SPEC-349 R30: gera ``docs/bestiario/PAINEL.md`` a partir das fichas, da esteira e da arena.

Uso: ``bash scripts/dev/py.sh scripts/bestiario/painel.py``.

Por região: contagens por família, categoria, papel, arquétipo e status; cobertura de demônios
(crias por demônio, mínimo 2 ao fim da onda 12); slots genéricos pendentes (curadoria do
legado sem ficha reinventada/adotada) e inspirações registradas. Se existir
``docs/spec349/arena-<regiao>.json``, resume a faixa da arena (45-85 %).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import bestiary_lint as bl  # noqa: E402

OUT = ROOT / "docs" / "bestiario" / "PAINEL.md"


def _linha(cont: Counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(cont.items())) or "-"


def _arena(regiao: str) -> str:
    p = ROOT / "docs" / "spec349" / f"arena-{regiao}.json"
    if not p.exists():
        return "sem medição"
    cri = json.loads(p.read_text(encoding="utf-8")).get("criaturas") or {}
    ok = sum(1 for c in cri.values() if c.get("ok"))
    return f"{ok}/{len(cri)} dentro de 45-85 % (off e on)"


def gerar() -> str:
    fichas = bl.load_fichas()
    esteira = yaml.safe_load((ROOT / "data/bestiario/_esteira.yaml").read_text(encoding="utf-8"))
    cur = yaml.safe_load(
        (ROOT / "data/bestiario/curadoria_legado.yaml").read_text(encoding="utf-8")
    )
    por_regiao: dict[str, list[dict]] = defaultdict(list)
    for f in fichas.values():
        por_regiao[str(f["regiao"])].append(f)
    linhas = [
        "# Painel do Bestiário de Valoria (SPEC-349)",
        "",
        "Gerado por `scripts/bestiario/painel.py`; não edite à mão.",
        "",
        "| Região | Onda | Status | Novas | Reinv./adotadas | Chefes | Elites | Arena |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for reg in esteira["ordem"]:
        fs = [f for f in por_regiao.get(reg, []) if f.get("status") != "retro"]
        info = esteira["regioes"].get(reg, {})
        onda = fs[0].get("onda") if fs else "-"
        n_nova = sum(1 for f in fs if f["status"] == "nova")
        n_slot = len(fs) - n_nova
        cats = Counter(f["categoria"] for f in fs)
        linhas.append(
            f"| {reg} | {onda} | {info.get('status', '-')} | {n_nova} | {n_slot} | "
            f"{cats.get('chefe', 0)} | {cats.get('elite', 0)} | {_arena(reg)} |"
        )
    for reg in esteira["ordem"]:
        fs = [f for f in por_regiao.get(reg, []) if f.get("status") != "retro"]
        linhas += [
            "",
            f"## {reg}",
            "",
            f"- Família: {_linha(Counter(f['familia'] for f in fs))}",
            f"- Categoria: {_linha(Counter(f['categoria'] for f in fs))}",
            f"- Papel tático: {_linha(Counter(f['papel_tatico'] for f in fs))}",
            f"- Arquétipo: {_linha(Counter(f['arquetipo'] for f in fs))}",
            f"- Status: {_linha(Counter(f['status'] for f in fs))}",
        ]
    linhas += [
        "",
        "## Cobertura de demônios (crias por demônio)",
        "",
        "| Demônio | Crias | Ids |",
        "|---|---|---|",
    ]
    for dem, ids in sorted((esteira.get("demonios") or {}).items()):
        linhas.append(f"| {dem} | {len(ids)} | {', '.join(f'`{i}`' for i in ids)} |")
    pendentes = [
        cid
        for cid, c in cur.items()
        if c.get("classe") == "generico"
        and cid
        not in {f["id"] for f in fichas.values() if f.get("status") in ("reinventada", "adotada")}
    ]
    linhas += ["", "## Slots genéricos pendentes", ""]
    linhas += [f"- `{c}`" for c in sorted(pendentes)] or ["- nenhum"]
    insp = [
        (f["id"], i)
        for f in fichas.values()
        for i in (f.get("inspiracao") or [])
        if isinstance(i, dict)
    ]
    linhas += ["", "## Inspirações registradas", ""]
    linhas += [
        f"- `{cid}`: {i.get('fonte', '?')} - {i.get('referencia', '')}" for cid, i in insp
    ] or ["- nenhuma"]
    return "\n".join(linhas) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(gerar())
    print(OUT)
