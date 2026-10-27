"""SPEC-336 R3: lint determinístico das Cartas (fonte única da esteira e do CI).

Funções puras: nada de LLM nem de rede. Consumido por ``scripts/cards/lint.py``,
``scripts/cards/promote.py`` e por ``services/content_validator.validate_cards``
(que roda no CI via ``scripts/validate_content.py``).

A similaridade do ``momento`` é lexical (Jaccard sobre tokens normalizados) por
padrão — offline e reprodutível. ``similarity(..., embed=fn)`` aceita um
embutidor (os mesmos embeddings do RAG) para a esteira com chave.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import gamedata
from services import card_effects as fx

PATAMARES = frozenset(
    {"inicial", "avancado", "superior", "epico_i", "epico_ii", "lendario", "mitico", "apice"}
)
FREQUENCIAS = frozenset({"livre", "turno", "cena", "descanso_curto", "descanso_longo"})
TIPOS = frozenset({"ativa", "passiva", "utilitaria", "reacao", "virtude", "status", "maldicao"})
_SEM_EFEITO_OK = frozenset({"status"})  # SPEC-333: efeito = `ao_comprar_status` (card_status.py)
RARIDADES = frozenset({"comum", "incomum", "rara", "abissal"})
OBRIGATORIOS = ("id", "name", "tipo", "classe", "patamar", "frequencia", "descricao", "tier")

LIMIAR_MOMENTO = 0.6  # similaridade >= isto + mesma assinatura = provável duplicata
LIMIAR_MOMENTO_SOLO = 0.85  # momento quase igual na mesma subclasse, mesmo sem a assinatura
MAX_PALAVRAS_NOME = 4
MAX_CHARS_DESCRICAO = 140
MAX_PALAVRAS_NOVAS_POR_ONDA = 2  # R9
MIN_CARTAS_POR_PALAVRA_NOVA = 6  # R9

# SPEC-335 R5: frases-modelo do gerador antigo (scripts/gen_tiers_5_plus.py); proibidas.
GENERICAS = ("converte_risco_acumulado", "decisao_mecanica_de_fim_de_campanha")
_REVISOR_REAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,39}$")
_REVISOR_FALSO = ("pendente", "posterior", "amostra", "depois", "tbd", "todo", "null", "none")


def revisor_valido(nome: str | None) -> bool:
    """Revisor real = identificador (``dono``), nunca texto livre nem promessa (SPEC-335 P1-1)."""
    nome = (nome or "").strip()
    return bool(_REVISOR_REAL.match(nome)) and not any(f in nome.lower() for f in _REVISOR_FALSO)


GENERICAS_CONTRAPARTIDA = ("consome_entropia_e_respeita_a_frequencia",)

# SPEC-335 R3: raridade = complexidade. Patamares aceitos por raridade.
PATAMARES_DA_RARIDADE = {
    "comum": frozenset({"inicial"}),
    "incomum": frozenset({"avancado", "superior"}),
    "rara": frozenset({"epico_i", "epico_ii"}),
    "abissal": frozenset({"lendario", "mitico", "apice"}),
}

_STOP = frozenset(
    "a o as os um uma de do da dos das em no na nos nas e ou que se por para com sem ao aos "
    "quando mais menos mesmo mesma seu sua seus suas ele ela eles elas e o".split()
)


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warn"
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}: {self.message}"


# --------------------------------------------------------------------------
# Dados de apoio
# --------------------------------------------------------------------------
_LEXICO: dict[str, list[str]] | None = None
_RODA: dict | None = None


def _cards_dir() -> str:
    return os.path.join(gamedata.DATA_DIR, "cards")


def lexico() -> dict[str, list[str]]:
    """``{"proibidos": [...], "valoria": [...]}`` de ``_lexico_valoria.txt``."""
    global _LEXICO
    if _LEXICO is None:
        out: dict[str, list[str]] = {"proibidos": [], "valoria": []}
        section = ""
        path = os.path.join(_cards_dir(), "_lexico_valoria.txt")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        section = line[1:-1]
                    elif section in out:
                        out[section].append(fx._fold(line))
        _LEXICO = out
    return _LEXICO


def roda() -> dict[str, dict]:
    global _RODA
    if _RODA is None:
        path = os.path.join(_cards_dir(), "_roda_posturas.json")
        with open(path, encoding="utf-8") as f:
            _RODA = json.load(f).get("posturas") or {}
    return _RODA


def reload() -> None:
    global _LEXICO, _RODA
    _LEXICO = None
    _RODA = None


def iter_card_files(cards_dir: str | None = None) -> Iterable[str]:
    """Arquivos .json de Cartas, recursivo, ignorando ``_*`` (metadados/rascunhos)."""
    base = cards_dir or _cards_dir()
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith("_"))
        for fn in sorted(files):
            if fn.endswith(".json") and not fn.startswith("_"):
                yield os.path.join(root, fn)


def load_pool(cards_dir: str | None = None) -> list[dict]:
    """Todas as Cartas do pool (sem rascunhos), na forma materializada."""
    out: list[dict] = []
    for path in iter_card_files(cards_dir):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue  # JSON quebrado é achado do content_validator, não do lint
        for card in data.get("cards") or []:
            if isinstance(card, dict) and card.get("id"):
                out.append(fx.materialize(card))
    return out


def load_batch(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("cards") if isinstance(data, dict) else data
    return [fx.materialize(c) for c in (raw or []) if isinstance(c, dict)]


# --------------------------------------------------------------------------
# Assinatura e similaridade
# --------------------------------------------------------------------------
def signature(card: dict) -> tuple:
    """``(kinds, palavras-chave, gatilhos, condições, custo)`` — sem magnitude."""
    effects = fx.normalize(card)
    kinds = tuple(sorted({str(e.get("kind")) for e in effects}))
    kws = tuple(sorted(fx.card_keyword_ids(card)))
    trig = tuple(sorted({fx.gatilho(e) for e in effects}))
    conds = tuple(
        sorted({k for e in effects for k in (e.get("se") or {}) if isinstance(e.get("se"), dict)})
    )
    cost = (int(card.get("custo_entropia", 0) or 0), fx.custo_folego(card))
    return (kinds, kws, trig, conds, cost)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", fx._fold(text).replace("_", " "))
    return {w for w in words if w not in _STOP and len(w) > 2}


def similarity(a: str, b: str, embed: Callable[[str], list[float]] | None = None) -> float:
    """0..1. Lexical (Jaccard) por padrão; cosseno se ``embed`` for dado."""
    if embed is not None:
        va, vb = embed(a), embed(b)
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(x * x for x in vb))
        return (sum(x * y for x, y in zip(va, vb, strict=False)) / (na * nb)) if na and nb else 0.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# --------------------------------------------------------------------------
# Checagens por Carta
# --------------------------------------------------------------------------
def _words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", str(text or "").strip()) if w]


def check_schema(card: dict, *, exigir_momento: bool = True) -> list[Issue]:
    out: list[Issue] = []
    for key in OBRIGATORIOS:
        if card.get(key) in (None, ""):
            out.append(Issue("error", "schema", f"campo obrigatório ausente: {key}"))
    if not (card.get("efeitos") or card.get("efeito") or card.get("tipo") in _SEM_EFEITO_OK):
        out.append(Issue("error", "schema", "sem efeitos"))
    if card.get("tipo") not in TIPOS:
        out.append(Issue("error", "schema", f"tipo inválido: {card.get('tipo')!r}"))
    if card.get("patamar") not in PATAMARES:
        out.append(Issue("error", "schema", f"patamar inválido: {card.get('patamar')!r}"))
    if card.get("frequencia") not in FREQUENCIAS:
        out.append(Issue("error", "schema", f"frequência inválida: {card.get('frequencia')!r}"))
    if card.get("raridade") is not None and card["raridade"] not in RARIDADES:
        out.append(Issue("error", "schema", f"raridade inválida: {card['raridade']!r}"))
    versao = card.get("versao")
    if versao is not None and not (
        isinstance(versao, int) and not isinstance(versao, bool) and versao >= 1
    ):
        out.append(Issue("error", "schema", "versao precisa ser inteiro >= 1"))
    if exigir_momento and not str(card.get("momento") or "").strip():
        out.append(Issue("error", "momento", "carta sem `momento` (melhor jogada quando…)"))
    return out


def check_vocabulary(card: dict) -> list[Issue]:
    return [Issue("error", "vocabulario", m) for m in fx.validate_card(card)]


def check_budget(card: dict) -> list[Issue]:
    msg = fx.budget_error(card)
    return [Issue("error", "orcamento", msg)] if msg else []


def check_raridade(card: dict) -> list[Issue]:
    """R3: comum <= 1 efeito e <= 1 palavra-chave; incomum <= 2; abissal com Exaurir e custo
    explícito; ``raridade`` coerente com o ``patamar``. Só Cartas de onda (``onda``): o acervo
    legado foi rotulado por patamar, sem reescrita mecânica."""
    rar = card.get("raridade")
    if card.get("onda") is None or not rar:
        return []
    out: list[Issue] = []
    patamar = card.get("patamar")
    if patamar not in PATAMARES_DA_RARIDADE.get(rar, frozenset()):
        out.append(
            Issue("error", "raridade", f"raridade {rar!r} incoerente com o patamar {patamar!r}")
        )
    n_efeitos = len(fx.normalize(card))
    n_kws = len(fx.keywords(card))
    if rar == "comum" and (n_efeitos > 1 or n_kws > 1):
        msg = f"comum com {n_efeitos} efeitos e {n_kws} palavras-chave (máx. 1 e 1)"
        out.append(Issue("error", "raridade", msg))
    if rar == "incomum" and (n_efeitos > 2 or n_kws > 2):
        msg = f"incomum com {n_efeitos} efeitos e {n_kws} palavras-chave (máx. 2)"
        out.append(Issue("error", "raridade", msg))
    if rar == "abissal":
        kws = fx.keywords(card)
        custo = (
            int(card.get("custo_entropia", 0) or 0) > 0
            or bool(kws.get("sacrificio"))
            or bool((card.get("mecanica_classe") or {}).get("auto_dano"))
        )
        if not kws.get("exaurir") or not custo:
            out.append(Issue("error", "raridade", "abissal exige Exaurir e custo explícito"))
    return out


def check_voice(card: dict) -> list[Issue]:
    out: list[Issue] = []
    name = str(card.get("name") or "")
    if len(_words(name)) > MAX_PALAVRAS_NOME:
        out.append(
            Issue("error", "voz", f"nome com mais de {MAX_PALAVRAS_NOME} palavras: {name!r}")
        )
    desc = str(card.get("descricao") or "")
    if not desc.strip():
        out.append(Issue("error", "voz", "descrição vazia"))
    if len(desc) > MAX_CHARS_DESCRICAO:
        out.append(
            Issue("error", "voz", f"descrição com {len(desc)} > {MAX_CHARS_DESCRICAO} caracteres")
        )
    if re.search(r"\d", desc):
        out.append(Issue("error", "voz", "número na descrição (o número vem do texto gerado)"))
    if any(frase in fx._fold(desc) for frase in GENERICAS):
        out.append(Issue("error", "voz", "descrição genérica (frase-modelo, sem sabor próprio)"))
    contra = fx._fold(card.get("contrapartida"))
    if any(frase in contra for frase in GENERICAS_CONTRAPARTIDA):
        out.append(Issue("error", "voz", "contrapartida genérica (frase-modelo)"))
    banned = set(lexico()["proibidos"])
    for field in ("name", "descricao", "momento"):
        hit = sorted(_tokens_all(str(card.get(field) or "")) & banned)
        if hit:
            out.append(Issue("error", "voz", f"termo fora do léxico de Valoria em {field}: {hit}"))
    if desc and not (_tokens_all(desc) & set(lexico()["valoria"])):
        out.append(Issue("warn", "voz", "descrição sem nenhum termo de sabor de Valoria"))
    return out


def _tokens_all(text: str) -> set[str]:
    """Como ``_tokens`` mas sem cortar palavras curtas (hp, mob…)."""
    return set(re.findall(r"[a-z0-9]+", fx._fold(text).replace("_", " ")))


# SPEC-335 P1-1: o golpe com rolagem tira o dano de `conflict_turn._damage_from`
# (`dano_base`/`categoria_arma`), que não chama `fx.scaled_value`; a `escala` só vale nos efeitos
# EXTRAS ou disparados. No principal de dano ela é inerte (e o orçamento a cobraria).
ESCALA_INERTE_KINDS = frozenset({"dano", "contra_ataque"})


def check_escala_principal(card: dict) -> list[Issue]:
    prim = fx.primary_effect(card)
    if (
        prim
        and prim.get("escala") is not None
        and str(prim.get("kind")) in ESCALA_INERTE_KINDS
        and fx.gatilho(prim) == fx.GATILHO_PADRAO
    ):
        return [
            Issue(
                "error",
                "escala_inerte",
                "`escala` no efeito principal de dano não faz nada: mova-a para um efeito extra",
            )
        ]
    return []


# SPEC-335 (revisão Sol do Lote 4): `revelar` de campo que o painel já mostra não faz nada.
REVELAR_PUBLICO_ERRO = frozenset({"vitalidade"})  # sempre no painel (`bestiary_knowledge`)
REVELAR_PUBLICO_AVISO = frozenset({"intencao"})  # o presságio (329) já mostra a intenção


def check_revelar_publico(card: dict) -> list[Issue]:
    out: list[Issue] = []
    for eff in fx.normalize(card):
        if eff.get("kind") != "revelar":
            continue
        campo = str(eff.get("campo", "resistencias"))
        if campo in REVELAR_PUBLICO_ERRO:
            msg = f"`revelar {campo}` é inerte: o campo já é público no painel"
            out.append(Issue("error", "revelar_publico", msg))
        elif campo in REVELAR_PUBLICO_AVISO:
            msg = f"`revelar {campo}` duplica o que o presságio já mostra"
            out.append(Issue("warn", "revelar_publico", msg))
    return out


def check_reacao_folego(card: dict) -> list[Issue]:
    """Reação de Carta de onda exige Fôlego >= 1 (R12 da 328: guardar Fôlego para reagir é
    uma escolha). O acervo legado fica de fora (há reações de Fôlego 0, inalteradas)."""
    if card.get("onda") is None or card.get("tipo") != "reacao":
        return []
    if fx.custo_folego(card) < 1:
        return [Issue("error", "reacao_folego", "reação com custo de Fôlego 0 (mínimo 1)")]
    return []


def check_marca_dano(card: dict) -> list[Issue]:
    """A Marca do Abismo some no próximo dano: um `dano` depois dela, na ordem REAL do motor
    (principal e depois os extras), a consome na própria Carta."""
    prim = fx.primary_effect(card)
    ordem = ([prim] if prim else []) + fx.extra_effects(card)
    vistos_marca = False
    for eff in ordem:
        if eff.get("kind") == "marca_do_abismo":
            vistos_marca = True
        elif vistos_marca and eff.get("kind") in ("dano", "contra_ataque"):
            msg = "`dano` depois da Marca do Abismo na mesma Carta a consome no ato"
            return [Issue("error", "marca_consumida", msg)]
    return []


def check_color_pie(card: dict) -> list[Issue]:
    rule = roda().get(str(card.get("classe") or ""))
    if not rule:
        return []
    out: list[Issue] = []
    kws = fx.keywords(card)
    for eff in fx.normalize(card):
        kind = str(eff.get("kind") or "")
        alvo = str(eff.get("alvo") or "")
        if kind in rule["nunca_kinds"]:
            out.append(
                Issue("error", "color_pie", f"{card['classe']} nunca faz {kind} ({rule['nunca']})")
            )
        if alvo in (rule["kind_alvo_proibido"].get(kind) or []):
            out.append(
                Issue(
                    "error",
                    "color_pie",
                    f"{card['classe']} nunca faz {kind} em {alvo} ({rule['nunca']})",
                )
            )
        limite = rule["limites_kind"].get(kind)
        if limite is not None:
            valor = fx.base_value(eff)
            if valor > int(limite):
                out.append(
                    Issue(
                        "error",
                        "color_pie",
                        f"{card['classe']}: {kind} {valor} acima do teto {limite} ({rule['nunca']})",
                    )
                )
    for key in rule["nunca_palavras_chave"]:
        if key in kws or key in fx.card_keyword_ids(card):
            out.append(
                Issue("error", "color_pie", f"{card['classe']} nunca usa {key} ({rule['nunca']})")
            )
    return out


def _vigente(pool: list[dict]) -> list[dict]:
    """Só a versão mais alta de cada id (R7)."""
    best: dict[str, dict] = {}
    for c in pool:
        cur = best.get(c["id"])
        if cur is None or fx.versao(c) >= fx.versao(cur):
            best[c["id"]] = c
    return list(best.values())


def check_names(card: dict, pool: list[dict]) -> list[Issue]:
    name = fx._fold(card.get("name"))
    for other in _vigente(pool):
        if other["id"] == card["id"]:
            if fx.versao(card) <= fx.versao(other) and other is not card:
                return [
                    Issue(
                        "error",
                        "nome",
                        f"id {card['id']!r} já existe na versão {fx.versao(other)} (suba `versao`)",
                    )
                ]
            continue
        if fx._fold(other.get("name")) == name:
            return [
                Issue("error", "nome", f"nome repetido: {card.get('name')!r} já é {other['id']}")
            ]
    return []


def check_redundancy(
    card: dict,
    pool: list[dict],
    embed: Callable[[str], list[float]] | None = None,
) -> list[Issue]:
    sig = signature(card)
    momento = str(card.get("momento") or "")
    out: list[Issue] = []
    for other in _vigente(pool):
        if other["id"] == card["id"] or other.get("classe") != card.get("classe"):
            continue
        sim = (
            similarity(momento, str(other.get("momento") or ""), embed)
            if momento and other.get("momento")
            else 0.0
        )
        same_sig = signature(other) == sig
        if same_sig and (sim >= LIMIAR_MOMENTO or not other.get("momento")):
            out.append(
                Issue(
                    "error",
                    "redundancia",
                    f"provável duplicata de {other['id']} (mesma assinatura mecânica, momento {sim:.2f})",
                )
            )
        elif sim >= LIMIAR_MOMENTO_SOLO and other.get("subclasse") == card.get("subclasse"):
            out.append(
                Issue(
                    "error",
                    "redundancia",
                    f"momento quase idêntico ao de {other['id']} ({sim:.2f})",
                )
            )
        elif same_sig:
            out.append(
                Issue(
                    "warn",
                    "redundancia",
                    f"mesma assinatura mecânica de {other['id']} (momento {sim:.2f})",
                )
            )
    return out


def lint_card(
    card: dict,
    pool: list[dict] | None = None,
    *,
    exigir_momento: bool = True,
    embed: Callable[[str], list[float]] | None = None,
) -> list[Issue]:
    """Todos os checks de uma Carta contra o ``pool`` (outras cartas, sem ela)."""
    card = fx.materialize(card)
    others = [c for c in (pool or []) if c is not card]
    issues = check_schema(card, exigir_momento=exigir_momento)
    if any(i.code == "schema" and i.message.startswith("campo obrigatório") for i in issues):
        return issues  # sem o básico, o resto vira ruído
    issues += check_vocabulary(card)
    if not any(i.code == "vocabulario" for i in issues):
        issues += check_budget(card)
    issues += check_voice(card)
    issues += check_raridade(card)
    issues += check_color_pie(card)
    issues += check_escala_principal(card)
    issues += check_revelar_publico(card)
    issues += check_reacao_folego(card)
    issues += check_marca_dano(card)
    issues += check_names(card, others)
    issues += check_redundancy(card, others, embed)
    return issues


def lint_batch(
    batch: list[dict],
    pool: list[dict] | None = None,
    *,
    exigir_momento: bool = True,
    embed: Callable[[str], list[float]] | None = None,
) -> dict[str, list[Issue]]:
    """Cada Carta do lote contra o pool E contra as outras do lote."""
    base = list(pool or [])  # inclui o mesmo id: só entra se `versao` for estritamente maior
    result: dict[str, list[Issue]] = {}
    seen: list[dict] = []
    for card in batch:
        issues = lint_card(card, base + seen, exigir_momento=exigir_momento, embed=embed)
        # Duplicata dentro do lote vale para as DUAS cartas: a 2ª leva o erro; a 1ª só o aviso.
        result[str(card.get("id"))] = issues
        seen.append(fx.materialize(card))
    return result


def lint_wave(batch: list[dict]) -> list[Issue]:
    """R9: ≤ 2 palavras-chave novas por onda, cada uma com ≥ 6 cartas na onda.
    "Nova" = glossário com ``onda`` == onda do lote."""
    out: list[Issue] = []
    ondas = {int(c["onda"]) for c in batch if isinstance(c.get("onda"), int)}
    glossario = fx.glossary()
    for onda in sorted(ondas):
        novas = [k for k, v in glossario.items() if v.get("onda") == onda]
        if len(novas) > MAX_PALAVRAS_NOVAS_POR_ONDA:
            out.append(
                Issue(
                    "error",
                    "onda",
                    f"onda {onda}: {len(novas)} palavras-chave novas (máx. {MAX_PALAVRAS_NOVAS_POR_ONDA})",
                )
            )
        for key in novas:
            n = sum(1 for c in batch if c.get("onda") == onda and key in fx.card_keyword_ids(c))
            if n < MIN_CARTAS_POR_PALAVRA_NOVA:
                out.append(
                    Issue(
                        "error",
                        "onda",
                        f"palavra-chave nova {key!r} com {n} carta(s) na onda (mín. {MIN_CARTAS_POR_PALAVRA_NOVA})",
                    )
                )
    return out


def errors(issues: Iterable[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]
