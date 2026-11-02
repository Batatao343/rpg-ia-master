"""SPEC-361 R5-R8: variante = criatura existente + modificador de trama curado (sem LLM).

O catálogo vive em ``data/bestiario/modificadores_trama.yaml``. A variante copia o template da
base, troca só campos categóricos (papel, padrão, categoria +1 no máximo até ``elite``) e
resolve os textos-modelo. Números: os da base; se a categoria muda, ``materialize_enemy_concept``
recalcula (mesmas tabelas da geração).
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from services import bestiary_lint as bl
from services import card_lint, enemy_decks
from services.card_lint import Issue

CATALOGO_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "bestiario" / "modificadores_trama.yaml"
)
LIMIAR_BASE = 1.0
_ESCADA = ("lacaio", "padrao", "elite")
_NUMERICOS = (
    "virtudes",
    "vitalidade",
    "max_vitalidade",
    "ferimento_espacos",
    "esquiva",
    "hp",
    "max_hp",
    "ac",
    "type",
    "categoria",
    "vitalidade_por_nivel_encontro",
    "acoes_por_rodada",
)


@lru_cache(maxsize=1)
def catalogo() -> tuple[dict, ...]:
    if not CATALOGO_PATH.is_file():
        return ()
    doc = yaml.safe_load(CATALOGO_PATH.read_text(encoding="utf-8")) or {}
    return tuple(doc.get("modificadores") or ())


def reload() -> None:
    catalogo.cache_clear()


def modificador_por_id(mid: str | None) -> dict | None:
    return next((m for m in catalogo() if m.get("id") == mid), None)


# --------------------------------------------------------------------------
# Lint do catálogo (§3.4) e da variante resolvida (R8)
# --------------------------------------------------------------------------
def _textos_mod(m: dict) -> dict[str, str]:
    t = m.get("texto") or {}
    return {k: str(t.get(k) or "") for k in ("epiteto", "frase", "telegrafo", "aparencia")}


def _proibidos() -> list[str]:
    return bl.lexico().get("proibidos_nome", []) + card_lint.lexico().get("proibidos", [])


def lint_catalogo(mods: tuple[dict, ...] | list[dict] | None = None) -> list[Issue]:
    mods = list(catalogo() if mods is None else mods)
    out: list[Issue] = []
    if not 12 <= len(mods) <= 16:
        out.append(Issue("error", "CAT", f"catálogo com {len(mods)} modificadores (12-16)"))
    vistos: dict[str, str] = {}
    ids = set()
    for m in mods:
        mid = str(m.get("id") or "?")
        if mid in ids:
            out.append(Issue("error", "CAT", f"{mid}: id repetido"))
        ids.add(mid)
        for campo, texto in _textos_mod(m).items():
            if not texto:
                out.append(Issue("error", "CAT", f"{mid}: texto.{campo} vazio"))
            if any(ch.isdigit() for ch in texto):
                out.append(Issue("error", "R20", f"{mid}: texto.{campo} tem dígito"))
            hit = bl._terms_in(texto, _proibidos())
            if hit:
                out.append(Issue("error", "U8", f"{mid}: texto.{campo} usa {hit}"))
        hit = bl._terms_in(_textos_mod(m)["epiteto"], bl.lexico().get("marcadores_variante", []))
        if hit:
            out.append(Issue("error", "U5", f"{mid}: epíteto com marcador de variante {hit}"))
        if "{nome}" not in _textos_mod(m)["telegrafo"]:
            out.append(Issue("error", "CAT", f"{mid}: telegrafo sem {{nome}}"))
        if "{base}" not in _textos_mod(m)["frase"]:
            out.append(Issue("error", "CAT", f"{mid}: frase sem {{base}}"))
        for fam in m.get("familias") or []:
            if fam not in bl.FAMILIAS_VALORIA:
                out.append(
                    Issue("error", "CAT", f"{mid}: família {fam!r} fora de FAMILIAS_VALORIA")
                )
        for cat in m.get("categorias") or []:
            if cat not in ("lacaio", "padrao", "elite", "chefe"):
                out.append(Issue("error", "CAT", f"{mid}: categoria {cat!r}"))
        ef = m.get("efeitos") or {}
        if ef.get("categoria_delta", 0) not in (0, 1):
            out.append(Issue("error", "CAT", f"{mid}: categoria_delta fora de {{0, 1}}"))
        papel = ef.get("papel_tatico")
        if papel is not None and papel not in bl.ENUMS["papel_tatico"]:
            out.append(Issue("error", "ENUM", f"{mid}: papel_tatico {papel!r}"))
        padrao = ef.get("padrao")
        if padrao is not None and (
            not 2 <= len(padrao) <= 4 or any(s not in enemy_decks._SLOT_LABEL for s in padrao)
        ):
            out.append(Issue("error", "ENUM", f"{mid}: padrao {padrao!r}"))
        cmin = ef.get("contagem_min")
        if cmin is not None and not (isinstance(cmin, int) and 1 <= cmin <= 4):
            out.append(Issue("error", "CAT", f"{mid}: contagem_min {cmin!r}"))
        for eixo in m.get("proibido_com") or {}:
            if eixo not in bl.ENUMS:
                out.append(Issue("error", "CAT", f"{mid}: proibido_com.{eixo} não é eixo"))
        for g in m.get("gatilhos") or []:
            gf = bl._fold(g)
            if gf in vistos and vistos[gf] != mid:
                out.append(Issue("error", "CAT", f"{mid}: gatilho {g!r} repetido de {vistos[gf]}"))
            vistos[gf] = mid
    return out


def lint_variante(template: dict, mod: dict) -> list[Issue]:
    """R8/R20 nos textos resolvidos: U8, zero dígito; U5 só no epíteto."""
    out: list[Issue] = []
    tid = str(template.get("id") or "?")
    sig = ((template.get("tactical_profile") or {}).get("assinatura") or {}).get("telegrafo")
    textos = {
        "name": template.get("name"),
        "description": template.get("description"),
        "appearance": template.get("appearance"),
        "telegrafo": sig,
    }
    for campo, texto in textos.items():
        texto = str(texto or "")
        if any(ch.isdigit() for ch in texto.replace("{nome}", "")):
            out.append(Issue("error", "R20", f"{tid}: {campo} tem dígito"))
        hit = bl._terms_in(texto, _proibidos())
        if hit:
            out.append(Issue("error", "U8", f"{tid}: {campo} usa {hit}"))
    hit = bl._terms_in(_textos_mod(mod)["epiteto"], bl.lexico().get("marcadores_variante", []))
    if hit:
        out.append(Issue("error", "U5", f"{tid}: epíteto com marcador {hit}"))
    return out


# --------------------------------------------------------------------------
# Detecção e base (R5/R6)
# --------------------------------------------------------------------------
def detectar_modificador(texto: str) -> dict | None:
    """Primeiro gatilho (na ordem do arquivo) que aparece no texto dobrado."""
    folded = bl._fold(texto)
    if not folded.strip():
        return None
    for m in catalogo():
        for g in m.get("gatilhos") or []:
            if bl._has_term(folded, bl._fold(g)):
                return m
    return None


def _compativel(f: dict, mod: dict) -> bool:
    if f.get("familia") not in (mod.get("familias") or []):
        return False
    if f.get("categoria") not in (mod.get("categorias") or []):
        return False
    anat = f.get("anatomia") or {}
    for eixo, proibidos in (mod.get("proibido_com") or {}).items():
        if (anat.get(eixo) or f.get(eixo)) in (proibidos or []):
            return False
    return True


@lru_cache(maxsize=1024)
def _dobrado(texto: str) -> str:
    return bl._fold(texto)


def score_base(f: dict, mod: dict, nucleo: str, categoria: str | None) -> float:
    s = 2.0 if categoria and f.get("categoria") == categoria else 0.0
    corpo = _dobrado(
        f"{f.get('comportamento') or ''} {(f.get('anatomia') or {}).get('texto') or ''}"
    )
    s += sum(1 for a in (mod.get("afinidades") or []) if bl._has_term(corpo, bl._fold(a)))
    s += card_lint.similarity(nucleo or "", f"{f.get('nome') or ''} {f.get('silhueta') or ''}")
    return s


def escolher_base(
    mod: dict,
    regiao: str,
    *,
    nucleo: str,
    categoria: str | None,
    fichas: dict[str, dict] | None = None,
    bestiary: dict | None = None,
    extras: list[dict] | None = None,
) -> str | None:
    """Base com ``score >= LIMIAR_BASE`` entre fichas aprovadas da região (+ ``extras`` do pool)."""
    from services import creature_gen as cg

    cands = [
        f
        for f in cg.fichas_aprovadas(fichas).values()
        if f.get("regiao") == regiao and _compativel(f, mod)
    ]
    cands += [f for f in (extras or []) if f.get("regiao") == regiao and _compativel(f, mod)]
    if bestiary is not None:
        cands = [f for f in cands if f.get("id") in bestiary]
    scored = sorted(
        ((score_base(f, mod, nucleo, categoria), str(f.get("id"))) for f in cands),
        key=lambda t: (-t[0], t[1]),
    )
    if not scored or scored[0][0] < LIMIAR_BASE:
        return None
    return scored[0][1]


# --------------------------------------------------------------------------
# Aplicação (R7)
# --------------------------------------------------------------------------
def _sobe(categoria: str, delta: int) -> str:
    if categoria not in _ESCADA:
        return categoria  # chefe (ou desconhecida) nunca sobe
    return _ESCADA[min(len(_ESCADA) - 1, _ESCADA.index(categoria) + max(0, int(delta or 0)))]


def _cortar(texto: str, limite: int) -> str:
    from services.creature_gen import cortar_frase

    return cortar_frase(texto, limite)


def aplicar_variante(base_template: dict, mod: dict, *, encounter_level: int = 1) -> dict:
    """Template da variante. Sem LLM, sem número livre; determinístico."""
    from agents.bestiary import materialize_enemy_concept

    t = copy.deepcopy(base_template)
    base_id = str(t.get("archetype_id") or t.get("id"))
    base_nome = str(t.get("name") or base_id)
    ef = mod.get("efeitos") or {}
    tx = _textos_mod(mod)
    cat_base = str(t.get("categoria") or "padrao")
    cat = _sobe(cat_base, int(ef.get("categoria_delta") or 0))
    if cat != cat_base:
        attacks = t.get("attacks") or []
        nums = materialize_enemy_concept(
            {
                "name": base_nome,
                "categoria": cat,
                "arquetipo": t.get("arquetipo") or "equilibrado",
                "nome_ataque": (attacks[0] or {}).get("name") if attacks else "Ataque",
            },
            encounter_level=encounter_level,
        )
        for key in _NUMERICOS:
            if key in nums:
                t[key] = nums[key]
            else:
                t.pop(key, None)
    tp = copy.deepcopy(t.get("tactical_profile") or {})
    if ef.get("padrao"):
        tp["padrao"] = list(ef["padrao"])
    ass = dict(tp.get("assinatura") or {})
    if ass.get("carta"):
        ass["telegrafo"] = tx["telegrafo"]
        tp["assinatura"] = ass
    t["tactical_profile"] = tp
    if ef.get("papel_tatico"):
        t["papel_tatico"] = ef["papel_tatico"]
    t["name"] = f"{base_nome} {tx['epiteto']}"
    t["description"] = _cortar(tx["frase"].format(base=base_nome), 200)
    base_look = str(t.get("appearance") or t.get("description") or "")
    look = tx["aparencia"]
    t["appearance"] = _cortar(f"{look[:1].upper()}{look[1:]}. {base_look}", 300)
    t["id"] = f"{base_id}__v_{mod['id']}"
    t["variant_of"] = base_id
    t["archetype_id"] = base_id
    t["geracao"] = {
        **(t.get("geracao") or {}),
        "caminho": "variante",
        "modificador": mod["id"],
        "base": base_id,
        "contagem_min": ef.get("contagem_min"),
    }
    t.pop("pool_entry_id", None)
    t.pop("ficha", None)
    return t


def contagem_min(template: dict) -> int:
    try:
        return int(((template.get("geracao") or {}).get("contagem_min")) or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "aplicar_variante",
    "catalogo",
    "contagem_min",
    "detectar_modificador",
    "escolher_base",
    "lint_catalogo",
    "lint_variante",
    "modificador_por_id",
]


def _debug_scores(mod_id: str, regiao: str, nucleo: str, categoria: str | None) -> list[Any]:
    """Apoio de depuração (não usado em produção)."""
    from services import creature_gen as cg

    mod = modificador_por_id(mod_id) or {}
    return sorted(
        (
            (round(score_base(f, mod, nucleo, categoria), 3), f["id"])
            for f in cg.fichas_aprovadas().values()
            if f.get("regiao") == regiao and _compativel(f, mod)
        ),
        reverse=True,
    )
