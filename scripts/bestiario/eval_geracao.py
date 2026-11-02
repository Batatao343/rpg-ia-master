"""Eval determinístico da geração de criatura em runtime, antes × depois (SPEC-361 R32, §3.9).

Uso:
    bash scripts/dev/py.sh scripts/bestiario/eval_geracao.py --modo antes|depois [--real] \
        [--pedidos tests/fixtures/spec361_pedidos.yaml] [--out docs/spec361/eval-<modo>-<data>.json]

- ``antes``: o gerador atual (``RPG_CREATURE_GEN=legacy``) nos mesmos pedidos;
- ``depois``: ``RPG_CREATURE_GEN=on`` + ``RPG_CREATURE_GEN_EVAL=1`` (``forcar`` do arquivo vale).
Sem ``--real`` roda no MockLLM (offline). Com ``--real`` usa ``ROUTES`` (custo) e aborta se o
LLM for simulado. As métricas são de ``services/creature_gen_eval.py`` (funções puras); os
pedidos e os limiares são congelados (quem otimiza o produto não os altera).
Grava o JSON e um ``.md`` com as colunas antes/depois (usa o último JSON do outro modo).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs" / "spec361"


def _setup(modo: str, real: bool) -> None:
    os.environ["RPG_CREATURE_GEN"] = "legacy" if modo == "antes" else "on"
    os.environ["RPG_CREATURE_GEN_EVAL"] = "1"
    os.environ.setdefault("RPG_SHARED_POOL", "off")
    os.environ["RPG_RUNTIME_CACHE_DIR"] = tempfile.mkdtemp(prefix="spec361_eval_")
    if real:
        os.environ.pop("RPG_FORCE_MOCK", None)
    else:
        os.environ["RPG_FORCE_MOCK"] = "1"


def _vizinhos(regiao: str) -> list[str]:
    from services import creature_gen as cg

    return [
        str((f.get("anatomia") or {}).get("texto") or "")
        for f in cg.fichas_da_regiao(regiao)
        if (f.get("anatomia") or {}).get("texto")
    ]


def _rodar_antes(item: dict) -> dict:
    import agents.bestiary as bst
    import gamedata

    # `forcar: nova` no antes = o mesmo pedido chega ao GERADOR (sem o dedupe do librarian),
    # para comparar gerador com gerador; `auto` passa pelo fluxo inteiro de hoje.
    original = bst.find_existing_entity
    if item.get("forcar") == "nova":
        bst.find_existing_entity = lambda *a, **k: None
    try:
        t0 = time.perf_counter()
        t = bst.generate_new_enemy(
            item["pedido"], item.get("motivo_trama") or "", location_id=item["location_id"]
        )
        lat = int((time.perf_counter() - t0) * 1000)
    finally:
        bst.find_existing_entity = original
    curado = str(t.get("id")) in (gamedata.BESTIARY or {})
    fallback = str(t.get("id") or "").startswith("fallback_")
    caminho = "existente" if curado else ("fallback" if fallback else "legacy")
    textos = [str(t.get(k) or "") for k in ("name", "description")]
    textos += [str(a.get("name") or "") for a in t.get("attacks") or []]
    return {
        "caminho": caminho,
        "textos": [x for x in textos if x] if caminho == "legacy" else [],
        "anatomia": str(t.get("description") or ""),
        "ficha": None,
        "latencia_ms": lat,
        "prompt_chars": 0,
        "lint_primeira": None,
        "lint_final": None,
        "nome": t.get("name"),
    }


_BEST: dict = {}


def _bestiario() -> dict:
    """Carregado uma vez (no jogo, `generate_new_enemy` já tem o bestiário antes do gerador)."""
    if not _BEST:
        from agents.bestiary import load_bestiary

        _BEST.update(load_bestiary())
    return _BEST


def _aquecer() -> None:
    """Caches de processo (fichas, Codex, léxicos): a latência medida é a do turno, não a do
    primeiro import do processo."""
    from services import bestiary_lint as bl
    from services import creature_gen as cg
    from services import creature_variants as cv

    cg._todas_fichas()
    cg._codex_monstros()
    bl.lexico()
    cv.catalogo()
    _bestiario()
    cg.resolver_nome("aquecimento", _bestiario())
    # imports preguiçosos do motor (combate, baralho, telemetria): no jogo já estão carregados
    from agents.bestiary import materialize_enemy_concept, template_from_db

    materialize_enemy_concept({"name": "Aquecimento", "arquetipo": "predador"})
    qualquer = template_from_db(_bestiario(), sorted(_bestiario())[0])
    if qualquer:
        cv.lint_variante(cv.aplicar_variante(qualquer, cv.catalogo()[-1]), cv.catalogo()[-1])


def _rodar_depois(item: dict) -> dict:
    from services import creature_gen as cg

    p = cg.PedidoCriatura(
        pedido=item["pedido"],
        regiao=item["regiao"],
        location_id=item["location_id"],
        categoria_sugerida=cg.categoria_sugerida(cg.hint_core(item["pedido"]) or item["pedido"]),
        motivo_trama=item.get("motivo_trama") or "",
        encounter_level=1,
        game_id=f"eval361-{item['id']}",
        turn=1,
        forcar=item.get("forcar") or "auto",
    )
    res = cg.gerar(p, bestiary=_bestiario())
    t = res.template
    ficha = res.ficha
    if res.caminho == "nova" and ficha:
        textos = list(cg.textos_da_ficha(ficha).values())
        anatomia = str((ficha.get("anatomia") or {}).get("texto") or "")
        plano = {
            "telegrafo": ficha.get("telegrafo"),
            "contra_jogo": ficha.get("contra_jogo"),
            "gancho": ficha.get("gancho"),
            "aparencia": ficha.get("aparencia"),
            "arte_visual": (ficha.get("arte") or {}).get("visual"),
        }
    elif res.caminho == "variante":
        sig = ((t.get("tactical_profile") or {}).get("assinatura") or {}).get("telegrafo") or ""
        textos = [t.get("name"), t.get("description"), t.get("appearance"), sig]
        textos = [str(x).replace("{nome}", "") for x in textos if x]
        anatomia = str(t.get("appearance") or "")
        plano = None
    else:
        textos, anatomia, plano = [], "", None
    return {
        "caminho": res.caminho,
        "textos": textos,
        "anatomia": anatomia,
        "ficha": plano,
        "latencia_ms": res.latencia_ms,
        "prompt_chars": res.prompt_chars,
        "lint_primeira": res.lint_primeira,
        "lint_final": res.caminho == "nova",
        "tentativas": res.tentativas,
        "codigos": res.codigos,
        "provider": res.provider,
        "nome": t.get("name"),
        "base": (t.get("geracao") or {}).get("base"),
        "modificador": (t.get("geracao") or {}).get("modificador"),
    }


def _md(antes: dict | None, depois: dict | None) -> str:
    from services import creature_gen_eval as ev

    linhas = [
        "# SPEC-361 — eval de geração de criatura (antes × depois)",
        "",
        "Gerado por `scripts/bestiario/eval_geracao.py`. Pedidos congelados em "
        "`tests/fixtures/spec361_pedidos.yaml`; métricas e limiares em "
        "`services/creature_gen_eval.py` (§3.9).",
        "",
        f"- antes: `{(antes or {}).get('arquivo', '—')}` · real={(antes or {}).get('real')}",
        f"- depois: `{(depois or {}).get('arquivo', '—')}` · real={(depois or {}).get('real')}",
        "",
        "| métrica | antes | depois | limiar | ok (depois) |",
        "|---|---|---|---|---|",
    ]
    ma = (antes or {}).get("metricas") or {}
    md = (depois or {}).get("metricas") or {}
    ok = ev.checar_limiares(md) if md else {}
    chaves = list(ev.LIMIARES) + [
        k for k in ("variante_vs_nova", "latencia_nova_p50_ms") if k not in ev.LIMIARES
    ]
    for k in chaves:
        lim = ev.LIMIARES.get(k)
        lim_txt = f"{lim[0]} {lim[1]}" if lim else "—"
        flag = {True: "sim", False: "**não**", None: "—"}[ok.get(k)]
        linhas.append(f"| {k} | {ma.get(k, '—')} | {md.get(k, '—')} | {lim_txt} | {flag} |")
    if depois:
        linhas += ["", "## Pedidos (depois)", "", "| id | caminho | tentativas | códigos | nome |"]
        linhas.append("|---|---|---|---|---|")
        for r in depois.get("registros") or []:
            linhas.append(
                f"| {r['id']} | {r['caminho']} | {r.get('tentativas', '—')} | "
                f"{','.join(r.get('codigos') or []) or '—'} | {r.get('nome') or '—'} |"
            )
    return "\n".join(linhas) + "\n"


def _ultimo(modo: str, pasta: Path = DOCS) -> dict | None:
    arquivos = sorted(pasta.glob(f"eval-{modo}-*.json"))
    if not arquivos:
        return None
    return json.loads(arquivos[-1].read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pedidos", default="tests/fixtures/spec361_pedidos.yaml")
    ap.add_argument("--modo", choices=("antes", "depois"), required=True)
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    _setup(args.modo, args.real)

    import llm_setup
    from services import creature_gen_eval as ev

    if args.real and llm_setup.is_simulated():
        print("--real pedido, mas o LLM está simulado (sem chave): abortado", file=sys.stderr)
        return 2
    providers: list[str] = []

    def hook(provider, model, tier, latency_ms, fell_back, *a, **k):
        providers.append(f"{provider}/{model}")

    llm_setup.set_llm_telemetry_hook(hook)
    if args.modo == "depois":
        _aquecer()
    pedidos = yaml.safe_load((ROOT / args.pedidos).read_text(encoding="utf-8"))["pedidos"]
    registros = []
    for item in pedidos:
        rodar = _rodar_antes if args.modo == "antes" else _rodar_depois
        try:
            reg = rodar(item)
        except Exception as exc:  # o eval registra a falha e segue
            reg = {"caminho": "erro", "erro": type(exc).__name__, "textos": [], "latencia_ms": None}
        reg.update(
            id=item["id"],
            forcar=item["forcar"],
            caminho_esperado=item["caminho_esperado"],
            regiao=item["regiao"],
            vizinhos=_vizinhos(item["regiao"]),
        )
        registros.append(reg)
        print(f"{item['id']}: {reg['caminho']} ({reg.get('latencia_ms')} ms)", file=sys.stderr)
    metricas = ev.avaliar(registros, modo=args.modo)
    hoje = dt.date.today().isoformat()
    out = Path(args.out) if args.out else DOCS / f"eval-{args.modo}-{hoje}.json"
    out = out if out.is_absolute() else ROOT / out
    doc = {
        "spec": "SPEC-361",
        "modo": args.modo,
        "real": bool(args.real),
        "mock": bool(llm_setup.is_simulated()),
        "data": hoje,
        "arquivo": (str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)).replace(
            "\\", "/"
        ),
        "pedidos_sha256": __import__("hashlib")
        .sha256((ROOT / args.pedidos).read_bytes().replace(b"\r\n", b"\n"))
        .hexdigest(),
        "providers": sorted(set(providers)),
        "metricas": metricas,
        "limiares_ok": ev.checar_limiares(metricas) if args.modo == "depois" else None,
        "registros": [{k: v for k, v in r.items() if k != "vizinhos"} for r in registros],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    antes = doc if args.modo == "antes" else _ultimo("antes", out.parent)
    depois = doc if args.modo == "depois" else _ultimo("depois", out.parent)
    md = out.parent / "eval-antes-x-depois.md"
    md.write_text(_md(antes, depois), encoding="utf-8", newline="\n")
    print(json.dumps(metricas, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
