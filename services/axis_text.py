"""SPEC-374 U14: coerência entre os eixos declarados de uma criatura gerada e o texto do corpo.

Contexto: o curador Opus rejeitou "Ouvido de Sal" (sal branco na prosa, ``carne_exposta`` no eixo;
corpo preso por raízes, ``nada`` no eixo): com a ``linha_eixos`` o Python escreve os eixos e a prosa
pode descolar deles, e o gate de unicidade (U2/U3) passa a mentir para as próximas criaturas.

Regra determinística e CONSERVADORA (um falso positivo gasta a correção curta de uma ficha boa).
Calibrada contra as 281 fichas aprovadas (``docs/spec374/u14-falso-positivo.md``): o texto do corpo
só é cobrado onde o vocabulário distingue o valor sem ambiguidade.

- **Material, dominância:** o valor declarado tem no máximo 1 raiz distinta no corpo (léxico amplo)
  e OUTRO material tem pelo menos 3 raízes distintas do léxico FORTE (sal, osso, ferro, cristal,
  cera, lama, cinza, madeira, quitina): o corpo descreve claramente outra matéria;
- **Locomoção ``nada``, ausência:** nenhuma raiz de água/nado no corpo (``anda`` e os demais
  valores não exigem nada: o texto de uma criatura quase nunca nomeia o jeito de andar);
- ``percepcao``, ``plano_corporal`` e ``escala`` NÃO entram: o texto das fichas aprovadas não
  nomeia a percepção de forma verificável (45 % das aprovadas reprovariam), e a regra seria ruído.
"""

from __future__ import annotations

import re
from typing import Any

from services import bestiary_lint as bl

# Raízes de palavra (texto dobrado). Casam no INÍCIO de palavra; ``$`` no fim exige fim de palavra.
LEXICO: dict[str, dict[str, tuple[str, ...]]] = {
    "material": {
        "carne_exposta": (
            "carne",
            "muscul",
            "tendo",
            "tendi",
            "viscer",
            "entranh",
            "ferid",
            "chaga",
            "sangr",
            "nervo",
            "tripa",
            "pele viva",
        ),
        "cera_sebo": ("cera", "sebo", "gordur", "banha", "vela", "parafin", "derret"),
        "cinza": ("cinza", "brasa", "carvao", "fuligem", "queimad", "calcinad", "po$"),
        "couro_tecido": (
            "couro",
            "pele",
            "tecid",
            "pano",
            "trapo",
            "bandag",
            "costur",
            "retalho",
            "manto",
            "mortalha",
            "lona",
            "saco",
            "farrapo",
            "odre",
            "veste",
        ),
        "escoria_fuligem": (
            "escori",
            "fuligem",
            "forja",
            "fundic",
            "caldeir",
            "carvao",
            "queimad",
            "alcatrao",
            "piche",
            "borra",
        ),
        "eter_cristalizado": (
            "eter",
            "cristal",
            "vidro",
            "translucid",
            "gema",
            "prisma",
            "facet",
            "transparen",
        ),
        "ferro_ferrugem": (
            "ferro",
            "ferrug",
            "metal",
            "aco$",
            "rebite",
            "lamina",
            "corrente",
            "prego",
            "engrenag",
            "bronze",
            "cobre",
            "parafus",
            "chapa",
            "arame",
        ),
        "lama_turfa": (
            "lama",
            "turfa",
            "barro",
            "lodo",
            "pantan",
            "limo$",
            "brejo",
            "charco",
            "argila",
            "lodac",
        ),
        "madeira_fibra": (
            "madeira",
            "raiz",
            "raizes",
            "tronco",
            "galho",
            "folha",
            "fibra",
            "cipo",
            "casca",
            "lenho",
            "musgo",
            "broto",
            "seiva",
            "graveto",
            "espinho",
            "vegetal",
            "junco",
            "palha",
            "fungo",
            "cogumel",
            "arvore",
            "planta",
            "ramo",
            "talo",
        ),
        "osso": (
            "oss",
            "costel",
            "cranio",
            "vertebr",
            "esquelet",
            "caveira",
            "femur",
            "espinha",
            "marfim",
            "tibia",
            "umero",
            "pelve",
            "ossuari",
        ),
        "quitina": (
            "quitin",
            "carapac",
            "casca",
            "exoesquelet",
            "elitro",
            "pinca",
            "ferrao",
            "antena",
            "inseto",
            "artropod",
            "segment",
            "besouro",
            "aranha",
            "escorpi",
            "formig",
            "vespa",
            "caranguej",
            "crustac",
        ),
        "sal_mineral": (
            "sal$",
            "sais$",
            "salin",
            "salmour",
            "salgad",
            "mineral",
            "pedra",
            "rocha",
            "pedreg",
            "calcari",
            "gesso",
            "cristaliz",
            "granito",
            "arenito",
            "cascalho",
        ),
    },
    "locomocao": {
        "nada": (
            "nadad",
            "nadar",
            "nadam",
            "nadan",
            "nadou",
            "nadav",
            "barbatan",
            "branqui",
            "natac",
            "mergulh",
            "flutu",
            "boia",
            "boiav",
            "submers",
            "remar",
            "remam",
            "cardume",
            "peixe",
            "enguia",
            "lula",
            "polvo",
            "tentacul",
            "marinh",
            "aquatic",
            "mare$",
            "mares$",
            "oceano",
            "correnteza",
            "afog",
            "inund",
            "alagad",
            "lodo",
            "lama$",
            "pantan",
            "charco",
            "poca$",
            "pocas$",
            "rio$",
            "lago$",
            "mar$",
            "ondas",
            "(?:na|sob a|sob|debaixo da|dentro da|pela|na) agua",
            "agua funda",
        ),
    },
}

# Léxico FORTE de material (só vocabulário que distingue a matéria; sem couro/pele/casca/fibra).
FORTE: dict[str, tuple[str, ...]] = {
    "sal_mineral": ("sal$", "sais$", "salin", "salmour", "salgad", "salitre", "evapor"),
    "osso": (
        "osso$",
        "ossos$",
        "ossead",
        "ossud",
        "ossada",
        "costel",
        "cranio",
        "vertebr",
        "esquelet",
        "caveira",
        "femur",
        "marfim",
    ),
    "ferro_ferrugem": (
        "ferro",
        "ferrug",
        "metal",
        "rebite",
        "prego",
        "engrenag",
        "bronze",
        "cobre",
        "parafus",
        "chapa",
        "arame",
    ),
    "eter_cristalizado": ("eter", "cristal", "vidro", "prisma", "gema", "translucid"),
    "cera_sebo": ("cera", "sebo", "banha", "parafin"),
    "lama_turfa": ("lama$", "lamac", "turfa", "barro", "lodo", "lodac", "pantan", "charco"),
    "cinza": ("cinza", "brasa", "carvao", "fuligem", "calcinad"),
    "madeira_fibra": ("madeira", "tronco", "galho", "lenho", "cipo", "seiva", "graveto", "broto"),
    "quitina": ("quitin", "carapac", "exoesquelet", "elitro", "pinca", "ferrao"),
}

MIN_DOMINANTE = 3  # raízes distintas do OUTRO valor para a dominância (B)
MAX_DECLARADO = 1  # raízes distintas do valor declarado, no máximo, para a dominância (B)

_CAMPOS_TEXTO = (
    ("anatomia", "texto"),
    ("silhueta",),
    ("comportamento",),
    ("aparencia",),
    ("description",),
    ("contra_jogo",),
    ("gancho",),
    ("mecanica_assinatura", "frase"),
    ("arte", "visual"),
)

_RE_CACHE: dict[tuple[str, str, str], re.Pattern[str]] = {}


def _regex(eixo: str, valor: str, raiz: str) -> re.Pattern[str]:
    chave = (eixo, valor, raiz)
    if chave not in _RE_CACHE:
        fim = r"\b" if raiz.endswith("$") else ""
        _RE_CACHE[chave] = re.compile(r"\b" + bl._fold(raiz.rstrip("$")) + fim)
    return _RE_CACHE[chave]


def texto_do_corpo(ficha: dict) -> str:
    partes: list[str] = []
    for caminho in _CAMPOS_TEXTO:
        cur: Any = ficha
        for k in caminho:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(cur, str) and cur:
            partes.append(cur)
    return bl._fold(" ".join(partes))


def raizes_distintas(texto: str, eixo: str, valor: str) -> int:
    return sum(
        1 for r in LEXICO.get(eixo, {}).get(valor, ()) if _regex(eixo, valor, r).search(texto)
    )


def incoerencias(ficha: dict) -> list[tuple[str, str, str]]:
    """``[(eixo, valor_declarado, motivo)]`` — vazio quando o corpo é coerente com os eixos."""
    anat = ficha.get("anatomia") or {}
    texto = texto_do_corpo(ficha)
    if not texto:
        return []
    out: list[tuple[str, str, str]] = []
    mat = anat.get("material")
    if mat in LEXICO["material"]:
        h = raizes_distintas(texto, "material", str(mat))
        if h <= MAX_DECLARADO:
            fortes = {
                v: sum(1 for r in raizes if _regex("forte", v, r).search(texto))
                for v, raizes in FORTE.items()
                if v != mat
            }
            melhor = max(fortes, key=lambda v: fortes[v])
            if fortes[melhor] >= MIN_DOMINANTE and fortes[melhor] >= h + 2:
                out.append(("material", str(mat), f"domina:{melhor}"))
    if anat.get("locomocao") == "nada" and raizes_distintas(texto, "locomocao", "nada") == 0:
        out.append(("locomocao", "nada", "ausente"))
    return out
