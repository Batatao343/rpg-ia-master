"""SPEC-358 R14/R15 - reprocessa a arena v1 x v2 (substituicao). Offline, MockLLM, seeded.

    bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 1     # sementes 0-19, todo o conjunto
    bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 2     # sementes 20-99: dominantes e divergentes
    bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase 3     # controle sintetico da 335 (R15), 20-99
    bash scripts/dev/py.sh docs/spec358/arena_v2.py --fase relatorio

Fase 1 roda UMA vez o v2 por Carta; o delta por remocao do v1 e a taxa de uso saem do mesmo
relatorio (``delta_pp_remocao``, ``avisos``) e as bandeiras do v1 sao derivadas por regra
(``v1_bandeiras``). A regra e conferida contra o v1 de verdade num arquivo (``verificacao_v1``).
Nada do catalogo muda; os arquivos da 335 so sao importados (``BARALHOS``, ``variante``,
``SUBCLASSES``, ``controle``).
"""

from __future__ import annotations

import argparse
import copy
import glob
import importlib.util
import json
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "cards"))
import sim  # noqa: E402

from services import card_lint, cards  # noqa: E402

D = os.path.join("docs", "spec358")
F1 = os.path.join(D, "arena-v2.json")
F2 = os.path.join(D, "arena-v2-confirmacao-sementes20-99.json")
F3 = os.path.join(D, "arena-v2-controle-r15.json")
REL = os.path.join(D, "RELATORIO-arena-v2.md")
CONTROLES = [
    "dev1_con_bencao_do_aco",
    "san1_sil_corte_sem_aviso",
    "cor1_alm_culpa_antiga",
    "med1_bot_agulha_envenenada",
    "med1_fer_cotovelo_de_aco",
    "med1_fer_pinca_de_aco",
    "arc1_tro_centelha_ressoante",
]


def _imp(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join("docs", "spec335", rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def v1_bandeiras(r: dict) -> list[str]:
    """Bandeiras que o v1 poria, a partir do relatorio v2 (mesmas regras de ``simulate_batch``)."""
    av = r["avisos"]
    f: list[str] = []
    if "uso_nao_medido" in av:
        f.append("uso_nao_medido")
    elif "amostra_insuficiente" in av:
        f.append("amostra_insuficiente")
    else:
        if "uso_baixo" in av:
            f.append("em_branco")
        if "uso_alto" in av:
            f.append("dominante")
    if (
        r["lutas_por_braco"] >= sim.MIN_LUTAS_DELTA
        and r["delta_pp_remocao"] > sim.LIMIAR_DOMINANTE_DELTA_PP
        and "dominante" not in f
    ):
        f.append("dominante")
    return f


def veredito(bandeiras: list[str]) -> str:
    return "recusa" if set(bandeiras) - sim.SEM_BANDEIRA else "passa"


def _save(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _load(path: str):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


# ------------------------------------------------------------------------------------------
# Unidades (grupo, id, variante) -> (carta, ids a isolar)
# ------------------------------------------------------------------------------------------
def unidades() -> list[tuple[str, str, str, dict, set[str]]]:
    tronco = _imp("confirmar_tronco_358", "confirmar_tronco_lote6.py")
    neu = _imp("neutras_358", "arena_neutras_lote6.py")
    out: list[tuple[str, str, str, dict, set[str]]] = []
    for path in sorted(glob.glob("data/cards/posturas/*.json")):
        if path.endswith("_tronco.json"):
            continue
        batch = card_lint.load_batch(path)
        ids = {c["id"] for c in batch}
        arq = os.path.basename(path)
        for c in batch:
            out.append((f"arquivo:{arq}", c["id"], "", c, ids))
    for path in sorted(glob.glob("data/cards/posturas/*_tronco.json")):
        for c in card_lint.load_batch(path):
            for sub in tronco.SUBCLASSES[c["classe"]]:
                v = copy.deepcopy(c)
                v["subclasse"] = sub
                out.append(("tronco", c["id"], sub, v, set()))
    for c in card_lint.load_batch("data/cards/valoria_neutras.json"):
        for key, (classe, sub) in neu.BARALHOS.items():
            out.append(("neutras", c["id"], key, neu.variante(c, classe, sub), set()))
    return out


def rodar(card: dict, outros: set[str], seeds: list[int], protocolo: str = "v2") -> dict:
    base = cards._load_cards()
    saved = {i: base.pop(i) for i in outros - {card["id"]} if i in base}
    try:
        level = max(int(card.get("level_req", 1) or 1), 1)
        return sim.simulate_batch(
            [card],
            [level],
            sim.PROTOCOLO_LOTE["categories"],
            sim.PROTOCOLO_LOTE["per_cat"],
            seeds,
            protocolo=protocolo,
        )[card["id"]]
    finally:
        base.update(saved)


def chave(g: str, cid: str, var: str) -> str:
    return f"{g}|{cid}|{var}"


# ------------------------------------------------------------------------------------------
def fase1() -> None:
    res = _load(F1) or {"_meta": {"sementes": "0-19", "protocolo": "lote-v2"}, "itens": {}}
    todos = unidades()
    feitos = 0
    for g, cid, var, card, outros in todos:
        k = chave(g, cid, var)
        if k in res["itens"]:
            continue
        res["itens"][k] = rodar(card, outros, list(range(20)))
        feitos += 1
        if feitos % 10 == 0:
            _save(F1, res)
            print(f"{len(res['itens'])}/{len(todos)}", flush=True)
    _save(F1, res)
    # conferencia: v1 de verdade num arquivo vs o derivado do v2
    if "verificacao_v1" not in res["_meta"]:
        arq = "sangromante_avaro.json"
        batch = card_lint.load_batch(os.path.join("data", "cards", "posturas", arq))
        v1 = sim.simulate_protocolo_lote(batch)
        ok = True
        for cid, r1 in v1.items():
            r2 = res["itens"][chave(f"arquivo:{arq}", cid, "")]
            ok &= (
                r1["delta_pp"] == r2["delta_pp_remocao"]
                and r1["vitoria_sem"] == r2["vitoria_sem"]
                and r1["vitoria_com"] == r2["vitoria_com"]
                and r1["taxa_uso"] == r2["taxa_uso"]
                and r1["bandeiras"] == v1_bandeiras(r2)
            )
        res["_meta"]["verificacao_v1"] = {"arquivo": arq, "cartas": len(v1), "iguais": bool(ok)}
        _save(F1, res)
    print("fase 1 ok", res["_meta"]["verificacao_v1"], flush=True)


def selecionar(res: dict) -> list[str]:
    sel = []
    for k, r in res["itens"].items():
        v1 = veredito(v1_bandeiras(r))
        v2 = veredito(r["bandeiras"])
        if "dominante" in r["bandeiras"] or v1 != v2:
            sel.append(k)
    return sel


def fase2() -> None:
    res = _load(F1)
    conf = _load(F2) or {"_meta": {"sementes": "20-99"}, "itens": {}}
    por_chave = {chave(g, cid, var): (card, outros) for g, cid, var, card, outros in unidades()}
    sel = selecionar(res)
    print(f"{len(sel)} itens a confirmar", flush=True)
    for i, k in enumerate(sel, 1):
        if k in conf["itens"]:
            continue
        card, outros = por_chave[k]
        conf["itens"][k] = rodar(card, outros, list(range(20, 100)))
        _save(F2, conf)
        print(f"{i}/{len(sel)} {k}", flush=True)
    conf["_meta"]["selecionados"] = sel
    _save(F2, conf)


def fase3() -> None:
    lote5 = _imp("confirmar_lote5_358", "confirmar_lote5.py")
    todas = {i for i in cards._load_cards() if i.startswith("med1_")}
    ctl = lote5.controle("ctl_ferro_dano4_marcial", 4, "cirurgiao_ferro", "marcial")
    base = cards._load_cards()
    saved = {i: base.pop(i) for i in todas if i in base}
    try:
        r = sim.simulate_batch([ctl], [4], ["padrao"], 4, list(range(20, 100)), protocolo="v2")[
            ctl["id"]
        ]
    finally:
        base.update(saved)
    _save(F3, {"ctl_ferro_dano4_marcial": r})
    print(json.dumps(r, ensure_ascii=False)[:400], flush=True)


# ------------------------------------------------------------------------------------------
def _linha(k: str, r: dict) -> str:
    _g, cid, var = k.split("|")
    nome = cid + (f" [{var}]" if var else "")
    ref = r["referencia"]
    refs = f"{ref['efeito'].get('dano_base', ref['efeito'].get('valor'))}" if ref else "-"
    vr = "-" if r["vitoria_ref"] is None else f"{r['vitoria_ref']:.3f}"
    b1 = ",".join(v1_bandeiras(r)) or "-"
    b2 = ",".join(r["bandeiras"]) or "-"
    av = ",".join(r["avisos"]) or "-"
    return (
        f"| {nome} | {r['taxa_uso']:.0%} | {r['delta_pp_remocao']:+.1f} | {r['delta_pp']:+.1f} "
        f"({r['delta_base'][:3]}) | {refs} | {r['vitoria_sem']:.3f} | {vr} | {b1} -> {b2} | {av} |"
    )


CAB = (
    "| Carta | uso | delta v1 (remocao) | delta v2 | X ref | vitoria_base | vitoria_ref | "
    "bandeiras v1 -> v2 | avisos v2 |\n|---|---|---|---|---|---|---|---|---|"
)


def relatorio() -> None:
    res = _load(F1)
    conf = _load(F2) or {"itens": {}}
    ctl = _load(F3)
    it = res["itens"]
    L: list[str] = []
    L.append("# SPEC-358 - Reprocessamento da arena: v1 (remocao) x v2 (substituicao)\n")
    L.append(
        "Sementes 0-19, protocolo de lote (padrao, `level_req`, 20 sementes). Nenhuma Carta, "
        "limiar ou relatorio antigo foi alterado. `[F]` = fato medido; `[H]` = hipotese.\n"
    )
    ver = res["_meta"].get("verificacao_v1")
    L.append(
        f"Bandeiras v1 derivadas do mesmo relatorio v2 (mesmas regras do `sim.py`). Conferencia "
        f"contra o v1 de verdade: {ver}.\n"
    )

    # contagens
    def cont(fn):
        n = {"uso": 0, "delta": 0}
        for r in it.values():
            for b in fn(r):
                if b in ("em_branco",) or (b == "dominante" and False):
                    n["uso"] += 1
        return n

    tot1 = tot2 = rec1 = rec2 = 0
    motivos1 = {"em_branco": 0, "dominante_uso": 0, "dominante_delta": 0}
    for r in it.values():
        f1 = v1_bandeiras(r)
        tot1 += len(set(f1) - sim.SEM_BANDEIRA)
        tot2 += len(r["bandeiras"])
        rec1 += veredito(f1) == "recusa"
        rec2 += veredito(r["bandeiras"]) == "recusa"
        if "em_branco" in f1:
            motivos1["em_branco"] += 1
        if "uso_alto" in r["avisos"]:
            motivos1["dominante_uso"] += 1
        if (
            r["lutas_por_braco"] >= sim.MIN_LUTAS_DELTA
            and r["delta_pp_remocao"] > sim.LIMIAR_DOMINANTE_DELTA_PP
        ):
            motivos1["dominante_delta"] += 1
    L.append("## 1. Contagem de bandeiras\n")
    L.append(f"Itens (Carta x variante): {len(it)}.\n")
    L.append("| | v1 | v2 |\n|---|---|---|")
    L.append(f"| bandeiras (total) | {tot1} | {tot2} |")
    L.append(f"| itens recusados | {rec1} | {rec2} |")
    L.append(
        f"| por uso (em_branco / dominante por uso) | {motivos1['em_branco']} / {motivos1['dominante_uso']} | 0 (viram aviso) |"
    )
    L.append(
        f"| por delta (dominante) | {motivos1['dominante_delta']} | {sum('dominante' in r['bandeiras'] for r in it.values())} |"
    )
    sem_ref = sum(r["referencia"] is None for r in it.values())
    L.append(f"\nItens sem referencia (reacao/passiva/etc.): {sem_ref}.\n")
    # divergencias
    L.append("## 2. Divergencias de veredito (v1 x v2)\n")
    div = [k for k, r in it.items() if veredito(v1_bandeiras(r)) != veredito(r["bandeiras"])]
    L.append(
        f"{len(div)} itens. Liberados pelo v2: "
        f"{sum(veredito(v1_bandeiras(it[k])) == 'recusa' for k in div)}; "
        f"recusados so no v2: {sum(veredito(v1_bandeiras(it[k])) == 'passa' for k in div)}.\n"
    )
    L.append(CAB)
    for k in div:
        L.append(_linha(k, it[k]))
    # confirmacao
    L.append("\n## 3. Confirmacao com sementes 20-99 (320 lutas por braco, uma vez)\n")
    L.append(
        "Itens com `dominante` no v2 ou com veredito v1 != v2. `delta v1` = remocao, `delta v2` = substituicao.\n"
    )
    L.append(
        "| Carta | delta v1 0-19 | delta v2 0-19 | delta v1 20-99 | delta v2 20-99 | bandeiras v1 -> v2 (20-99) |\n|---|---|---|---|---|---|"
    )
    for k, r in conf["itens"].items():
        a = it[k]
        _g, cid, var = k.split("|")
        L.append(
            f"| {cid}{' [' + var + ']' if var else ''} | {a['delta_pp_remocao']:+.1f} | {a['delta_pp']:+.1f} | "
            f"{r['delta_pp_remocao']:+.1f} | {r['delta_pp']:+.1f} | "
            f"{','.join(v1_bandeiras(r)) or '-'} -> {','.join(r['bandeiras']) or '-'} |"
        )
    # controles
    L.append("\n## 4. Casos de controle\n")
    L.append(CAB)
    for cid in CONTROLES:
        ks = [k for k in it if k.split("|")[1] == cid]
        for k in ks:
            L.append(_linha(k, it[k]))
    if ctl:
        r = ctl["ctl_ferro_dano4_marcial"]
        L.append("\n### R15 - controle sintetico `ctl_ferro_dano4_marcial` (sementes 20-99)\n")
        L.append(
            f"delta por remocao {r['delta_pp_remocao']:+.1f} pp; delta por substituicao "
            f"{r['delta_pp']:+.1f} pp; `vitoria_sem` {r['vitoria_sem']}, `vitoria_ref` "
            f"{r['vitoria_ref']}, `vitoria_com` {r['vitoria_com']}; ref {r['referencia']}.\n"
        )
        ok = abs(r["delta_pp"]) < abs(r["delta_pp_remocao"])
        L.append(
            f"[F] |delta v2| {'<' if ok else '>='} |delta v1|: a hipotese R15 "
            f"{'se confirmou' if ok else 'NAO se confirmou (D6: o v2 nao e recomendado como default sem decisao do dono)'}.\n"
        )
    L.append("## 5. Tabelas por conjunto\n")
    grupos: dict[str, list[str]] = {}
    for k in it:
        grupos.setdefault(k.split("|")[0], []).append(k)
    for g, ks in grupos.items():
        L.append(f"\n### {g}\n")
        L.append(CAB)
        for k in ks:
            L.append(_linha(k, it[k]))
    L.append("\n## 6. Limitacoes\n")
    L.append(
        "- [F] Reacoes, passivas, virtudes e utilitarias nao tem referencia: ficam com delta por "
        "remocao e aviso `sem_referencia` (o bot nao as declara).\n"
        '- [F] "Outro suporte" (purga, ganhar Folego etc.) usa referencia de `protecao` (D3): o delta '
        "dessas Cartas mede suporte contra protecao, nao contra um efeito equivalente.\n"
        "- [F] A referencia e uma Carta de efeito unico no ponto medio da faixa; Cartas com varios "
        "efeitos (area, Chamado, Torpor...) so tem o efeito principal comparado.\n"
        "- [H] Uma Carta no topo da faixa de orcamento tera delta positivo legitimo; o v2 mede "
        "poder acima do esperado para o custo, nao ausencia de poder.\n"
        "- [F] Nenhuma Carta foi alterada; as divergencias e os `dominante` do v2 sao apenas "
        "candidatas a uma spec de balanco futura.\n"
    )
    with open(REL, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("relatorio gravado", REL)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", required=True, choices=["1", "2", "3", "relatorio"])
    a = ap.parse_args()
    {"1": fase1, "2": fase2, "3": fase3, "relatorio": relatorio}[a.fase]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
