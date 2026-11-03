"""SPEC-361 §3.9: métricas puras do eval de geração de criatura em runtime.

Sem I/O e sem LLM: recebem os registros que ``scripts/bestiario/eval_geracao.py`` grava por
pedido e devolvem números. Os limiares ficam aqui, congelados na Etapa 0; quem otimiza o
produto não os altera (``docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md``).

Registro por pedido (dict):
    id, forcar, caminho_esperado, caminho, lint_primeira (bool|None), lint_final (bool|None),
    textos (list[str]), anatomia (str), ficha (dict|None), latencia_ms (int),
    prompt_chars (int), vizinhos (list[str]: anatomias da região) ou vizinho_max (float, já
    calculado pelo script quando a lista não é gravada)

SPEC-374 (Etapa E, autor de eval != executor de produto):

- ``idioma_pt`` (R4/D1): "a" e "as" saíram das stopwords inglesas; são artigos do português
  e empatavam textos curtos ("Abrir a Maré" contava como não-pt). A regra de empate não muda.
- Latência (R5/D2): o limiar é do **job** fora do turno, ``latencia_job_p95_ms <= 30 000``
  (o prazo ``RPG_CREATURE_GEN_DEADLINE_S``); mede o mesmo de antes (``latencia_ms`` das
  ``forcar: nova``, incluindo as que caíram em fallback). ``latencia_nova_p50_ms`` é
  informativa. "Turno sem LLM de geração" é teste estrutural, não métrica.
- Denominadores (P2-8 b): ``lint_primeira``/``lint_final``/``fallback`` sobre as ``forcar:
  nova`` (``n_nova``); ``fisico``/``campos_349``/``vizinho_max`` só sobre as fichas escritas
  pelo gerador (``caminho`` nova/legacy, ``n_gerados``): as ``nova`` que caíram em fallback e
  as variantes ficam fora; ``idioma_pt``/``proibidos``/``digitos`` sobre todos os textos.
- Fronteira do ``lint_primeira`` (D3, confirmada pelo autor de eval): conta como 1ª tentativa
  o que roda **antes** do 1º lint e não escolhe conteúdo (eixos escritos pelo Python a partir
  da linha que o LLM escolheu, forma tolerante, troca de ``{nome}`` no telegrafo). Não conta
  nada que rode **depois** do 1º lint (reparo, padrão, eixos de reserva, correção curta, 2ª
  chamada). O valor vem do produto (``ResultadoGeracao.lint_primeira``); a revisão Sol confere
  no código que ele é o resultado do 1º lint antes de qualquer reparo.
- Protocolo da rodada medida (R6/D6, ``PROTOCOLO``/``checar_protocolo``): 2 rodadas reais
  seguidas, mesmo commit, set da 361 (sha fixo), ``mock=False``; ``lint_primeira`` agregado
  ``>= 0,70`` (16/22) e nenhuma rodada ``< 7/11``; os demais ``LIMIARES`` valem em cada
  rodada. O set de ajuste (``tests/fixtures/spec374_pedidos_ajuste.yaml``) nunca é rodada
  medida.
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
    "latencia_job_p95_ms": ("<=", 30000),  # SPEC-374 R5/D2: prazo do job, fora do turno
    "latencia_variante_p95_ms": ("<=", 50),
    "prompt_chars": ("<=", 14000),
}

_PT = frozenset(
    "a o as os um uma de do da dos das em no na nos nas e que se por para com sem ao aos "
    "quando mais seu sua seus suas ele ela eles elas como mas entre pelo pela onde quem".split()
)
# SPEC-374 R4: sem "a" e "as" (artigos do português; no inglês só empatavam textos curtos)
_EN = frozenset(
    "the an of and in on to with from that this it its is are was were by for at "
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


def _vizinho_do_registro(r: dict[str, Any]) -> float:
    """Com a lista de vizinhos, calcula; sem ela, usa o ``vizinho_max`` gravado por pedido."""
    if r.get("vizinhos"):
        return vizinho_max(r.get("anatomia") or "", r.get("vizinhos") or [])
    return float(r.get("vizinho_max") or 0.0)


def _frac(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def avaliar(registros: Sequence[dict[str, Any]], *, modo: str = "depois") -> dict[str, Any]:
    """Métricas de §3.9 sobre os registros. ``modo='antes'`` pula as que não fazem sentido."""
    novas = [r for r in registros if r.get("forcar") == "nova"]
    autos = [r for r in registros if r.get("forcar") == "auto"]
    textos = [t for r in registros for t in (r.get("textos") or [])]
    # fichas escritas pelo gerador (a variante reaproveita o corpo da base: fica fora de
    # físico/campos/vizinho, que medem a criatura escrita do zero)
    gerados = [r for r in registros if r.get("caminho") in ("nova", "legacy")]
    out: dict[str, Any] = {
        "n": len(registros),
        "n_nova": len(novas),
        "n_auto": len(autos),
        "n_gerados": len(gerados),
    }
    if modo != "antes":
        out["lint_primeira_n"] = sum(1 for r in novas if r.get("lint_primeira"))
        out["lint_primeira"] = _frac(out["lint_primeira_n"], len(novas))
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
    out["vizinho_max"] = round(max((_vizinho_do_registro(r) for r in gerados), default=0.0), 4)
    lat_nova = [r["latencia_ms"] for r in novas if r.get("latencia_ms") is not None]
    lat_var = [r["latencia_ms"] for r in registros if r.get("caminho") == "variante"]
    out["latencia_nova_p50_ms"] = round(percentil(lat_nova, 50))
    out["latencia_job_p95_ms"] = round(percentil(lat_nova, 95))
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


# SPEC-374 R6/D6 — protocolo da rodada medida, fixado antes de medir.
SHA256_PEDIDOS_361 = "baf3831005468ebae5d1e8e0237077fad6199aeee90907b8dfcc988d52db6dbc"
PROTOCOLO: dict[str, Any] = {
    "rodadas": 2,
    "pedidos_sha256": SHA256_PEDIDOS_361,
    "lint_primeira_agregado": 0.70,  # >= 16 de 22
    "lint_primeira_piso_rodada": (7, 11),  # nenhuma rodada abaixo de 7/11 (63,6 %)
}


def checar_protocolo(rodadas: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Veredito do protocolo R6 sobre os documentos JSON das rodadas medidas.

    Cada rodada: ``{modo, real, mock, commit, pedidos_sha256, metricas}`` (o que
    ``eval_geracao.py`` grava). Passa só se: exatamente ``PROTOCOLO["rodadas"]`` rodadas, todas
    ``depois``/``real``/``mock=False``, no mesmo commit (não vazio), com o set da 361;
    ``lint_primeira`` agregado >= 0,70 e cada rodada >= 7/11; e os demais ``LIMIARES`` em cada
    rodada."""
    rodadas = list(rodadas)
    piso_num, piso_den = PROTOCOLO["lint_primeira_piso_rodada"]
    ok_n = [int((r.get("metricas") or {}).get("lint_primeira_n") or 0) for r in rodadas]
    den_n = [int((r.get("metricas") or {}).get("n_nova") or 0) for r in rodadas]
    commits = {r.get("commit") for r in rodadas}
    validade = {
        "n_rodadas": len(rodadas) == PROTOCOLO["rodadas"],
        "real_sem_mock": all(
            r.get("modo") == "depois" and r.get("real") is True and r.get("mock") is False
            for r in rodadas
        ),
        # mesmo commit, conhecido e limpo (o script marca "+sujo" com arquivo rastreado alterado)
        "mesmo_commit": len(commits) == 1
        and bool(c := next(iter(commits), None))
        and not str(c).endswith("+sujo"),
        "set_361": all(r.get("pedidos_sha256") == PROTOCOLO["pedidos_sha256"] for r in rodadas),
    }
    piso = [d > 0 and o * piso_den >= piso_num * d for o, d in zip(ok_n, den_n, strict=True)]
    tot_ok, tot_den = sum(ok_n), sum(den_n)
    agregado_ok = bool(tot_den) and tot_ok >= PROTOCOLO["lint_primeira_agregado"] * tot_den
    por_rodada = [
        {k: v for k, v in checar_limiares(r.get("metricas") or {}).items() if k != "lint_primeira"}
        for r in rodadas
    ]
    limiares_ok = all(v is True for lim in por_rodada for v in lim.values())
    passou = bool(rodadas) and all(validade.values()) and all(piso) and agregado_ok and limiares_ok
    return {
        "passou": passou,
        "validade": validade,
        "lint_primeira_agregado": (tot_ok, tot_den),
        "agregado_ok": agregado_ok,
        "piso_rodada": piso,
        "limiares_por_rodada": por_rodada,
    }


__all__ = [
    "CAMPOS_349",
    "PROTOCOLO",
    "SHA256_PEDIDOS_361",
    "checar_protocolo",
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
