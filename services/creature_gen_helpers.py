"""SPEC-374: helpers puros da geração de criatura em runtime (extraídos de ``creature_gen``).

Forma (R11), reparo de eixos (R13), dicas de prompt (núcleos de nome e padrões livres) e a
coerência eixo × corpo (U14). Estão num módulo próprio para ``creature_gen.py`` não crescer
(``tests/test_size_budget.py``); ``creature_gen`` os reexporta, então ``cg.normalizar_forma`` etc.
seguem valendo. Nada aqui chama LLM; o que precisa de ``creature_gen`` importa tarde (sem ciclo).
"""

from __future__ import annotations

import hashlib
import re

from services import bestiary_lint as bl
from services import enemy_decks
from services.card_lint import Issue


def padroes_livres(
    regiao: str,
    runtime: list[dict],
    semente: str,
    n: int = 4,
    *,
    fichas: dict[str, dict] | None = None,
) -> str:
    """SPEC-374 R12: o U13 (padrão + cadência iguais) era o erro mais comum depois dos eixos.
    Mostra ``n`` padrões que NINGUÉM usa na região, por cadência (lacaio/padrão = a cada 3;
    elite/chefe = a cada 2), em ordem fixa pela ``semente``. Só sugere: o gate segue sendo o juiz."""
    import itertools

    from services.creature_gen import fichas_da_regiao

    usados = {
        (tuple(f.get("padrao") or []), f.get("a_cada_n"))
        for f in fichas_da_regiao(regiao, fichas)
        + [r for r in runtime if r.get("regiao") == regiao]
    }
    slots = sorted(enemy_decks._SLOT_LABEL)
    ofensivos = {"ataque", "ataque_multiplo"}  # ela precisa atacar em algum momento
    cands = [
        list(c)
        for k in (2, 3)
        for c in itertools.product(slots, repeat=k)
        if len(set(c)) > 1 and ofensivos & set(c)
    ]
    cands.sort(key=lambda c: hashlib.sha256(f"{regiao}|{semente}|{c}".encode()).hexdigest())
    por_cad = {cad: [c for c in cands if (tuple(c), cad) not in usados][:n] for cad in (3, 2)}
    fmt = lambda ls: " | ".join(",".join(c) for c in ls)  # noqa: E731
    if por_cad[3] == por_cad[2]:  # nada colide: uma lista só (economiza prompt)
        return f"qualquer categoria: {fmt(por_cad[3])}" if por_cad[3] else ""
    partes = [
        f"{rotulo}: {fmt(por_cad[cad])}"
        for rotulo, cad in (("lacaio ou padrao", 3), ("elite ou chefe", 2))
        if por_cad[cad]
    ]
    return "; ".join(partes)


def linha_nucleos(ocupados: str) -> str:
    """SPEC-374 R12: a 1ª palavra do nome (U1/U4) das criaturas listadas, para o LLM não repetir.
    Sai das linhas de ``<ja_existem_na_regiao>`` (``nome — família / ...``); sem lista, vazio."""
    marcadores = set(bl.lexico().get("marcadores_variante", []))  # já proibidos no nome
    vistos: dict[str, str] = {}  # núcleo (como o gate compara) -> palavra como está no nome
    for linha in ocupados.splitlines():
        if " — " not in linha:
            continue
        nome = linha.split(" — ", 1)[0]
        n = bl.nucleo_nome(nome)
        if not n or len(n) < 4 or n in marcadores or n in vistos:
            continue
        palavra = next((w for w in nome.split() if bl.nucleo_nome(w) == n), n)
        vistos[n] = palavra.strip(".,;:\"'")
    if not vistos:
        return ""
    return (
        "Já começam nome na região (escolha outra primeira palavra): "
        + ", ".join(sorted(vistos.values(), key=bl._fold))
        + "."
    )


def checar_coerencia_eixos(ficha: dict) -> list[Issue]:
    """U14 (SPEC-374): eixo declarado × corpo descrito (``services/axis_text``). A mensagem diz
    o que trocar, porque a correção curta lê o texto do issue."""
    from services import axis_text

    fid = str(ficha.get("id") or "?")
    out: list[Issue] = []
    for eixo, valor, motivo in axis_text.incoerencias(ficha):
        if eixo == "material":
            outro = motivo.split(":", 1)[1] if ":" in motivo else "?"
            msg = (
                f"{fid}: material={valor} mas o corpo é de {outro}; troque linha_eixos por uma "
                f"linha com material {outro} ou reescreva o corpo na matéria {valor}"
            )
        else:
            msg = (
                f"{fid}: locomocao={valor} mas o corpo não nada nem vive na água; troque "
                "linha_eixos por uma linha com outra locomoção ou descreva o nado"
            )
        out.append(Issue("error", "U14", msg))
    return out


_FORMA_CAMPOS = (
    "nome",
    "anatomia_texto",
    "silhueta",
    "comportamento",
    "nome_ataque",
    "telegrafo",
    "mecanica_assinatura",
    "contra_jogo",
    "gancho",
    "description",
    "aparencia",
    "arte_visual",
    "arte_evitar",
)


_ASPAS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "«": '"', "»": '"'})


_PONTUACAO_DUPLA = re.compile(r"([!?,;:])\1+")


_PONTO_DUPLO = re.compile(r"(?<!\.)\.\.(?!\.)")


_ARTIGO = r"(?:(?:o|a|os|as|um|uma)\s+)?"


def _limpar_forma(texto: str) -> str:
    t = " ".join(texto.translate(_ASPAS).split())
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" and t[0] not in t[1:-1]:
        t = t[1:-1].strip()  # o campo inteiro entre UM par de aspas (não '"a" e "b"')
    t = _PONTUACAO_DUPLA.sub(r"\1", t)
    return _PONTO_DUPLO.sub(".", t)


def normalizar_forma(gen: dict, *, nome: str) -> dict:
    """R11: só forma, nunca conteúdo. Lista FECHADA de transformações:

    1. ``_FORMA_CAMPOS``: espaços colapsados, aspas curvas retas, aspas que embrulham o campo
       inteiro caem, pontuação duplicada (``!!``, ``,,``, ``..``) vira simples;
    2. ``telegrafo`` sem ``{nome}`` que COMEÇA pelo nome da ficha (com ou sem artigo): o nome
       (e o artigo) vira ``{nome}``.

    Não converte dígito, não troca palavra proibida, não reescreve frase: isso é da correção
    curta. Devolve uma cópia; campos fora da lista passam intactos."""
    out = dict(gen)
    for campo in _FORMA_CAMPOS:
        if isinstance(out.get(campo), str):
            out[campo] = _limpar_forma(out[campo])
    tel = out.get("telegrafo")
    if isinstance(tel, str) and "{nome}" not in tel and nome.strip():
        m = re.match(rf"\s*{_ARTIGO}{re.escape(nome.strip())}(?=\W|$)", tel, re.IGNORECASE)
        if m:
            out["telegrafo"] = "{nome}" + tel[m.end() :]
    return out


def reparar_eixos(ficha: dict, issues: list[Issue], livres: list[dict], lint) -> dict | None:
    """R13: se TODO erro é U2/U3 (colisão de eixos) ou U14 (eixo × corpo), tenta as outras
    linhas de ``livres`` na ordem; a prosa fica. Devolve a 1ª ficha que passa no lint, ou None.
    Reparo depois do lint: não conta no ``lint_primeira``."""
    if not livres or not issues or any(i.code not in ("U2", "U3", "U14") for i in issues):
        return None
    atual = ficha.get("anatomia") or {}
    for c in livres:
        mesma = all(c.get(e) == atual.get(e) for e in bl.EIXOS_PADRAO_ENUM)
        if mesma and c.get("papel_tatico") == ficha.get("papel_tatico"):
            continue
        nova = {
            **ficha,
            "anatomia": {**atual, **{e: c[e] for e in bl.EIXOS_PADRAO_ENUM}},
            "papel_tatico": c["papel_tatico"],
        }
        if not lint(nova):
            return nova
    return None


def projetar_exemplo(ficha: dict, limite: int | None = None) -> str:
    from services.creature_gen import LIM_EXEMPLO, cortar_frase

    limite = LIM_EXEMPLO if limite is None else limite
    anat = ficha.get("anatomia") or {}
    ol = ficha.get("origem_lore") or {}
    arte = ficha.get("arte") or {}
    mec = ficha.get("mecanica_assinatura") or {}
    eixos = "/".join(str(anat.get(e) or "") for e in bl.EIXOS_PADRAO_ENUM)
    cabecalho = [
        f"nome: {ficha.get('nome')} | familia: {ficha.get('familia')} | origem: "
        f"{ol.get('fonte')}{'/' + str(ol.get('detalhe')) if ol.get('detalhe') else ''}",
        f"eixos: {eixos} | papel: {ficha.get('papel_tatico')} | arquetipo: "
        f"{ficha.get('arquetipo')} | categoria: {ficha.get('categoria')} | padrao: "
        f"{','.join(ficha.get('padrao') or [])}",
    ]
    # (rótulo, texto, peso): todos os campos de R11 entram; o teto é repartido entre eles
    prosa = [
        ("anatomia", anat.get("texto"), 3.0),
        ("silhueta", ficha.get("silhueta"), 1.0),
        ("comportamento", ficha.get("comportamento"), 1.6),
        ("telegrafo", ficha.get("telegrafo"), 1.0),
        ("assinatura", mec.get("frase") if isinstance(mec, dict) else mec, 1.0),
        ("contra_jogo", ficha.get("contra_jogo"), 1.1),
        ("gancho", ficha.get("gancho"), 1.1),
        ("aparencia", ficha.get("aparencia"), 1.2),
        ("arte_visual", arte.get("visual"), 1.4),
        ("arte_evitar", arte.get("evitar"), 0.9),
    ]
    prosa = [(r, " ".join(str(t or "").split()), w) for r, t, w in prosa]
    fixo = sum(len(c) + 1 for c in cabecalho) + sum(len(r) + 3 for r, _t, _w in prosa)
    livre = max(0, limite - fixo)
    tetos: dict[str, int] = {}
    pendentes = list(prosa)
    while pendentes:  # "water-filling": campo curto devolve a sobra aos longos
        peso = sum(w for _r, _t, w in pendentes)
        cabem = [(r, t, w) for r, t, w in pendentes if len(t) <= livre * w / peso]
        if not cabem:
            for r, _t, w in pendentes:
                tetos[r] = int(livre * w / peso)
            break
        for r, t, _w in cabem:
            tetos[r] = len(t)
            livre -= len(t)
        pendentes = [x for x in pendentes if x not in cabem]
    linhas = cabecalho + [f"{r}: {cortar_frase(t, max(0, tetos[r]))}" for r, t, _w in prosa]
    return "\n".join(linhas)[:limite]


def reparar_padrao(ficha: dict, issues: list[Issue], lint) -> dict | None:
    """U13 só por padrão + cadência iguais: o padrão é mecânica (Python), então o motor tenta
    outra ordem dos mesmos slots (e depois um slot a mais), na ordem fixa, até o lint passar.
    Qualquer outro erro (ou telegrafo parecido) não é reparável aqui: vale a nova tentativa."""
    import itertools

    if not issues or any(
        not (i.code == "U13" and "padrão + cadência" in i.message) for i in issues
    ):
        return None
    slots = list(ficha.get("padrao") or [])
    cands = [list(c) for c in dict.fromkeys(itertools.permutations(slots))][1:]
    if len(slots) < 4:
        cands += [slots + [s] for s in sorted(enemy_decks._SLOT_LABEL) if s != slots[-1]]
    for padrao in cands[:12]:
        nova = {**ficha, "padrao": padrao}
        if not lint(nova):
            return nova
    return None
