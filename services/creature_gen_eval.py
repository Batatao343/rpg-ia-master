"""SPEC-361 §3.9: métricas puras do eval de geração de criatura em runtime.

Sem I/O e sem LLM: recebem os registros que ``scripts/bestiario/eval_geracao.py`` grava por
pedido e devolvem números. Os limiares ficam aqui, congelados na Etapa 0; quem otimiza o
produto não os altera (``docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md``).

Registro por pedido (dict):
    id, forcar, caminho_esperado, caminho, lint_primeira (bool|None), lint_final (bool|None),
    textos (list[str]), anatomia (str), ficha (dict|None), latencia_ms (int),
    prompt_chars (int), vizinhos (list[str]: anatomias da região)
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from typing import Any

from services import bestiary_lint as bl
from services import card_lint

LIMIARES: dict[str, tuple[str, float]] = {
    # métrica: (operador, valor) — §3.9, coluna "depois --real"
    "lint_primeira": (">=", 0.70),
    "lint_final": (">=", 0.90),
    "fallback": ("<=", 0.10),
    "caminho_ok": (">=", 1.0),
    "proibidos": ("<=", 0),
    "digitos": ("<=", 0),
    "idioma_pt": (">=", 1.0),
    "fisico": (">=", 0.95),
    "campos_349": (">=", 1.0),
    "vizinho_max": ("<", 0.45),
    "latencia_nova_p95_ms": ("<=", 15000),
    "latencia_variante_p95_ms": ("<=", 50),
    "prompt_chars": ("<=", 14000),
}

_PT = frozenset(
    "a o as os um uma de do da dos das em no na nos nas e que se por para com sem ao aos "
    "quando mais seu sua seus suas ele ela eles elas como mas entre pelo pela onde quem".split()
)
_EN = frozenset(
    "the a an of and in on to with from that this it its is are was were by for as at "
    "into out when which who where his her their they them".split()
)
_WORD = re.compile(r"[a-zà-ÿ]+")
CAMPOS_349 = ("telegrafo", "contra_jogo", "gancho", "aparencia", "arte_visual")


def digitos(text: str) -> int:
    """Ocorrências de dígito (R20)."""
    return len(re.findall(r"\d", str(text or "")))


def termos_proibidos(text: str) -> list[str]:
    """U8: genérico de manual (léxico do bestiário) + jargão do léxico de Cartas."""
    lex = bl.lexico()
    termos = lex.get("proibidos_nome", []) + card_lint.lexico().get("proibidos", [])
    return bl._terms_in(text, termos)


def eh_portugues(text: str) -> bool:
    """Mais stopwords pt do que en (texto vazio conta como pt: não há o que medir)."""
    words = _WORD.findall(str(text or "").casefold())
    pt = sum(1 for w in words if w in _PT)
    en = sum(1 for w in words if w in _EN)
    return pt > en or (pt == 0 and en == 0)


def eh_fisico(text: str, minimo: int = 3) -> bool:
    """≥ ``minimo`` partes do corpo do léxico, sem termo conceitual (U9)."""
    return not bl.checar_fisico(str(text or ""), minimo)


def campos_349_ok(ficha: dict | None) -> bool:
    if not isinstance(ficha, dict):
        return False
    return all(str(ficha.get(c) or "").strip() for c in CAMPOS_349)


def vizinho_max(anatomia: str, vizinhos: Iterable[str]) -> float:
    return max((card_lint.similarity(anatomia or "", v or "") for v in vizinhos), default=0.0)


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil por interpolação linear (p em 0..100). Lista vazia → 0."""
    vs = sorted(float(v) for v in valores)
    if not vs:
        return 0.0
    k = (len(vs) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return vs[lo] if lo == hi else vs[lo] + (vs[hi] - vs[lo]) * (k - lo)


def _frac(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def avaliar(registros: Sequence[dict[str, Any]], *, modo: str = "depois") -> dict[str, Any]:
    """Métricas de §3.9 sobre os registros. ``modo='antes'`` pula as que não fazem sentido."""
    novas = [r for r in registros if r.get("forcar") == "nova"]
    autos = [r for r in registros if r.get("forcar") == "auto"]
    textos = [t for r in registros for t in (r.get("textos") or [])]
    gerados = [r for r in registros if r.get("caminho") in ("nova", "variante", "legacy")]
    out: dict[str, Any] = {"n": len(registros), "n_nova": len(novas), "n_auto": len(autos)}
    if modo != "antes":
        out["lint_primeira"] = _frac(sum(1 for r in novas if r.get("lint_primeira")), len(novas))
        out["lint_final"] = _frac(sum(1 for r in novas if r.get("lint_final")), len(novas))
        out["fallback"] = _frac(sum(1 for r in novas if r.get("caminho") == "fallback"), len(novas))
        out["caminho_ok"] = _frac(
            sum(1 for r in autos if r.get("caminho") == r.get("caminho_esperado")), len(autos)
        )
        out["variante_vs_nova"] = {
            "variante": sum(1 for r in autos if r.get("caminho") == "variante"),
            "nova": sum(1 for r in autos if r.get("caminho") == "nova"),
        }
    out["proibidos"] = sum(len(termos_proibidos(t)) for t in textos)
    out["digitos"] = sum(digitos(t) for t in textos)
    out["idioma_pt"] = _frac(sum(1 for t in textos if eh_portugues(t)), len(textos))
    out["fisico"] = _frac(sum(1 for r in gerados if eh_fisico(r.get("anatomia"))), len(gerados))
    out["campos_349"] = _frac(
        sum(1 for r in gerados if campos_349_ok(r.get("ficha"))), len(gerados)
    )
    out["vizinho_max"] = round(
        max(
            (vizinho_max(r.get("anatomia") or "", r.get("vizinhos") or []) for r in gerados),
            default=0.0,
        ),
        4,
    )
    lat_nova = [r["latencia_ms"] for r in novas if r.get("latencia_ms") is not None]
    lat_var = [r["latencia_ms"] for r in registros if r.get("caminho") == "variante"]
    out["latencia_nova_p50_ms"] = round(percentil(lat_nova, 50))
    out["latencia_nova_p95_ms"] = round(percentil(lat_nova, 95))
    out["latencia_variante_p95_ms"] = round(percentil(lat_var, 95), 2)
    out["prompt_chars"] = max((int(r.get("prompt_chars") or 0) for r in registros), default=0)
    return out


def _ok(valor: Any, op: str, lim: float) -> bool | None:
    if valor is None:
        return None
    return {">=": valor >= lim, "<=": valor <= lim, "<": valor < lim}[op]


def checar_limiares(metricas: dict[str, Any]) -> dict[str, bool | None]:
    """``{métrica: passou}`` (None = métrica ausente neste modo)."""
    return {k: _ok(metricas.get(k), op, lim) for k, (op, lim) in LIMIARES.items()}


__all__ = [
    "CAMPOS_349",
    "LIMIARES",
    "avaliar",
    "campos_349_ok",
    "checar_limiares",
    "digitos",
    "eh_fisico",
    "eh_portugues",
    "percentil",
    "termos_proibidos",
    "vizinho_max",
]
