"""Revisão em lote (Opus) das criaturas do pool que passaram no gate (SPEC-361 R26/R27).

Uso (coordenador):
    bash scripts/dev/py.sh scripts/bestiario/pool_revisao.py export [--regiao R] [--max 40] \
        [--out handoffs/pool-review/AAAA-MM-DD.yaml]
    # o spec-reviewer (Opus) preenche `veredito: aprovada | rejeitada` e `motivo` (<= 200)
    bash scripts/dev/py.sh scripts/bestiario/pool_revisao.py import --arquivo <yaml> \
        [--revisor opus-spec-reviewer] [--arte-dir docs/arte/bestiario-runtime]

`import` chama ``shared_pool.apply_curator_verdicts`` (único escritor de PROMOTED para criatura
com ficha) e acrescenta cada aprovada ao doc de arte da região, idempotente por ``entry_id``.
O revisor não edita texto gerado em jogo: "ajustes" = ``rejeitada`` (D5).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import bestiary_lint as bl  # noqa: E402
from services import creature_gen as cg  # noqa: E402
from services import shared_pool as sp  # noqa: E402
from services.shared_pool_models import PoolNamespace, PoolStatus  # noqa: E402

CHECKLIST = [
    "Criatura física de Valoria: corpo concreto com partes nomeadas, nada conceitual (U9).",
    "Família coerente com a lore (Reescrito, Besta Torta, Cobrado, Cria de Apetite) e com a região.",
    "Não repete nenhum vizinho listado: corpo, papel, silhueta, telegrafo e gancho próprios.",
    "Nome de 2-4 palavras, sem monstro de manual, sem marcador de variante (U1/U4/U5/U8).",
    "Zero número, dado ou jargão de sistema em qualquer texto (R20).",
    "Sem PII, sem nome de pessoa real, sem instrução ao narrador, sem segredo da lore.",
    "Arte: visual legível e evitar com o clichê certo; nada que copie criatura de outra obra.",
]
_FAMILIA_EM_JOGO = {
    "corpo_reescrito": "Reescrito",
    "besta_entropia": "Besta Torta",
    "humanoide_preco": "Cobrado",
    "demonio_encarnado": "Cria de Apetite",
}


def _pendentes(store, regiao: str | None, maximo: int) -> list:
    out = []
    for e in store.select(namespace=PoolNamespace.CREATURE, statuses=[PoolStatus.HELD]):
        if not sp._awaiting_curator(e) or not isinstance(e.document.get("ficha"), dict):
            continue
        if regiao and e.region_id != regiao:
            continue
        out.append(e)
    return sorted(out, key=lambda e: e.entry_id)[:maximo]


def _vizinhos(ficha: dict, regiao: str) -> tuple[list[dict], list[str]]:
    fichas = cg.fichas_da_regiao(regiao)
    scored = sorted(
        ((bl.eixos_iguais(ficha, f), str(f.get("id")), f) for f in fichas),
        key=lambda t: (-t[0], t[1]),
    )
    viz = [{"id": fid, "nome": f.get("nome"), "eixos_iguais": n} for n, fid, f in scored[:3]]
    avisos = [f"{fid}: {n} de 6 eixos iguais (limite 3)" for n, fid, _f in scored if n == 3]
    return viz, avisos


def exportar(regiao: str | None, maximo: int, out: Path, *, store=None) -> int:
    store = store or sp.get_store()
    entradas = []
    for e in _pendentes(store, regiao, maximo):
        ficha = dict(e.document["ficha"])
        viz, avisos = _vizinhos(ficha, e.region_id)
        entradas.append(
            {
                "entry_id": e.entry_id,
                "regiao": e.region_id,
                "nome": e.name,
                "ficha": ficha,
                "vizinhos": viz,
                "avisos": avisos,
                "veredito": "",
                "motivo": "",
            }
        )
    doc = {
        "spec": "SPEC-361",
        "gerado_em": dt.date.today().isoformat(),
        "revisor": "opus-spec-reviewer",
        "checklist": CHECKLIST,
        "instrucao": "Preencha veredito (aprovada | rejeitada) e motivo (<= 200). "
        "Não edite a ficha: ajuste = rejeitada.",
        "entradas": entradas,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )
    return len(entradas)


_LUGAR = re.compile(
    r"\b(?:no fundo d[aeo]s?|dentro d[aeo]s?|em|na|no|sob|entre)\s+(?:(?:uma?|o|a|os|as)\s+)?"
    r"([a-zà-ú]+(?:\s+(?:de|da|do|dos|das)\s+[a-zà-ú]+)*)",
    re.IGNORECASE,
)


# Lista FECHADA de substantivos de lugar (raiz dobrada, sem acento): só estes valem como "lugar do
# texto". O núcleo é a 1ª palavra do sintagma ("cisterna de pedra" -> "cisterna").
SUBSTANTIVOS_DE_LUGAR = frozenset(
    """cisterna poco gruta caverna galeria mina margem praia poca pantano brejo ruina ruinas cripta
    porao esgoto doca docas cais ponte estrada floresta mata duna dunas deserto campo campos forja
    oficina torre farol camara tunel salao beco igreja catedral templo capela cemiterio fosso vale
    colina serra montanha penhasco canyon rio lago mar costa porto vila cidade aldeia taverna
    estalagem mercado praca rua viela telhado muralha castelo fortaleza celeiro estabulo curral
    moinho fabrica fundicao armazem deposito biblioteca mausoleu tumulo ossuario catacumba labirinto
    corredor patio jardim horta pomar bosque clareira trilha encruzilhada passagem desfiladeiro
    abismo cratera vulcao geleira tundra savana selva jungla charco lodacal manguezal recife ilha
    ilhota farol cabana choupana casebre abrigo toca ninho covil salina areal planicie pradaria
    descampado barranco falesia gruta mirante""".split()
)


def _fold(texto: str) -> str:
    return cg.bl._fold(texto)


def lugar_do_texto(ficha: dict) -> str:
    """O lugar que a PRÓPRIA ficha descreve (arte, silhueta, descrição), ou vazio.

    Só vale quando o substantivo núcleo está em ``SUBSTANTIVOS_DE_LUGAR``; "azul", "lábios",
    "que" e afins NÃO são lugar e voltam para o habitat do mapa."""
    arte = ficha.get("arte") or {}
    for texto in (arte.get("visual"), ficha.get("silhueta"), ficha.get("description")):
        for m in _LUGAR.finditer(str(texto or "")):
            lugar = m.group(1).strip()
            if _fold(lugar.split()[0]) in SUBSTANTIVOS_DE_LUGAR:
                return lugar
    return ""


def _composicao(ficha: dict, regiao: str) -> str:
    # SPEC-374: o lugar vem do texto da ficha; o 1º habitat do mapa só quando o texto não diz
    doc = cg._regiao_doc(regiao)
    habitat = (ficha.get("habitat") or [regiao])[0]
    nome_regiao = doc.get("nome_regiao") or regiao
    lugar = lugar_do_texto(ficha)
    lugar = (
        f"{lugar[:1].upper()}{lugar[1:]} ({nome_regiao})"
        if lugar
        else ((doc.get("habitat_nome") or {}).get(habitat) or nome_regiao)
    )
    return (
        f"{lugar}, luz baixa; a criatura em primeiro plano, de três-quartos, no gesto do "
        "telegrafo; uma figura humana, uma ferramenta ou uma porta ao lado dá a escala."
    )


def _bloco_arte(entry, ficha: dict) -> str:
    regiao = entry.region_id
    doc = cg._regiao_doc(regiao)
    arte = ficha.get("arte") or {}
    fam = _FAMILIA_EM_JOGO.get(str(ficha.get("familia")), str(ficha.get("familia")))
    return (
        f"### {entry.name}\n"
        f"`{fam} · {ficha.get('categoria')} · {doc.get('nome_regiao') or regiao} · runtime` "
        f"<!-- entry_id: {entry.entry_id} -->\n\n"
        f"**Visual:** {arte.get('visual') or ficha.get('aparencia') or ''}\n"
        f"**Composição:** {_composicao(ficha, regiao)}\n"
        f"**Evitar:** {arte.get('evitar') or ''}\n"
    )


def acrescentar_arte(entry, arte_dir: Path) -> bool:
    """Idempotente por ``entry_id``. Devolve True se escreveu."""
    ficha = entry.document.get("ficha") or {}
    path = arte_dir / f"{entry.region_id}.md"
    atual = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"entry_id: {entry.entry_id} " in atual:
        return False
    if not atual:
        nome = cg._regiao_doc(entry.region_id).get("nome_regiao") or entry.region_id
        atual = (
            f"# Bestiário runtime — {nome} (SPEC-361)\n\n"
            "> Criaturas geradas em jogo, aprovadas pelo curador (revisão Opus em lote) e "
            "promovidas ao pool.\n> Gerado por `scripts/bestiario/pool_revisao.py import`. "
            "Estilo e exclusões globais: `docs/arte/bestiario-349/` §0.\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        atual.rstrip("\n") + "\n\n" + _bloco_arte(entry, ficha), encoding="utf-8", newline="\n"
    )
    return True


def importar(arquivo: Path, revisor: str | None, arte_dir: Path, *, store=None) -> dict:
    store = store or sp.get_store()
    doc = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    revisor = revisor or str(doc.get("revisor") or "")
    vereditos = [
        {"entry_id": e.get("entry_id"), "veredito": e.get("veredito"), "motivo": e.get("motivo")}
        for e in doc.get("entradas") or []
    ]
    counts = sp.apply_curator_verdicts(store, vereditos, revisor=revisor)
    counts["arte"] = 0
    for v in vereditos:
        if str(v.get("veredito") or "").strip().lower() != "aprovada":
            continue
        entry = store.get(str(v.get("entry_id") or ""))
        if entry is not None and entry.status == PoolStatus.PROMOTED:
            counts["arte"] += int(acrescentar_arte(entry, arte_dir))
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--regiao")
    ex.add_argument("--max", type=int, default=40)
    ex.add_argument("--out", default=f"handoffs/pool-review/{dt.date.today().isoformat()}.yaml")
    im = sub.add_parser("import")
    im.add_argument("--arquivo", required=True)
    im.add_argument("--revisor")
    im.add_argument("--arte-dir", default="docs/arte/bestiario-runtime")
    args = ap.parse_args(argv)
    if args.cmd == "export":
        n = exportar(args.regiao, args.max, ROOT / args.out)
        print(json.dumps({"exportadas": n, "arquivo": args.out}))
    else:
        print(json.dumps(importar(Path(args.arquivo), args.revisor, ROOT / args.arte_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
