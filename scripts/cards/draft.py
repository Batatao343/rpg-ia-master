"""SPEC-336 R2: rascunho de Cartas por LLM (SMART), SÓ no vocabulário fechado.

    bash scripts/dev/py.sh scripts/cards/draft.py --postura "Médico de Campo" \
        --subclasse boticario --n 24 --raridades comum,incomum,rara --onda 1

Saída: ``data/cards/_rascunhos/<onda>_<postura>_<subclasse>.json`` (fora do pool —
o loader ignora pastas ``_*``). Fluxo seguinte: ``lint.py`` -> ``sim.py`` ->
``promote.py``. Sem chave de provider, ou com o LLM em fallback de erro: AVISO e
lote VAZIO — nunca inventa cartas offline. Rodar com chave tem custo (SMART):
só sob demanda do dono; os testes usam um LLM de mentira.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import gamedata  # noqa: E402
from observability.telemetry import log_fallback  # noqa: E402
from services import card_effects as fx  # noqa: E402
from services import card_lint, cards  # noqa: E402

DRAFT_DIR = os.path.join(gamedata.DATA_DIR, "cards", "_rascunhos")
RARIDADES_PADRAO = ("comum", "incomum", "rara")
# patamar/tier/level_req por raridade (lote de entrada; a curadoria ajusta)
_PATAMAR_POR_RARIDADE = {
    "comum": "inicial",
    "incomum": "avancado",
    "rara": "epico_i",
    "abissal": "lendario",
}


class EfeitoRascunho(BaseModel):
    """Efeito na gramática da SPEC-330 (campos livres; o vocabulário é checado depois)."""

    kind: str
    quando: str | None = None
    se: dict[str, Any] | None = None
    alvo: str | None = None
    valor: int | None = None
    dano_base: int | None = None
    categoria_arma: str | None = None
    duracao: int | None = None
    condicao: str | None = None
    escala: dict[str, Any] | None = None
    chamado: int | None = None


class CartaRascunho(BaseModel):
    id: str = Field(description="slug curto, sem acento, prefixo da Postura")
    name: str = Field(description="até 4 palavras, PT-BR, sem anglicismo")
    tipo: str = Field(default="ativa", description="ativa | reacao | utilitaria")
    patamar: str = "inicial"
    raridade: str = "comum"
    custo_entropia: int = 0
    frequencia: str = "livre"
    efeitos: list[EfeitoRascunho]
    palavras_chave: dict[str, Any] = Field(default_factory=dict)
    descricao: str = Field(description="até 140 caracteres, sensorial, sem números")
    momento: str = Field(description="melhor jogada quando… (uma frase, distinta das existentes)")
    tier: int = 1
    level_req: int = 1


class LoteRascunho(BaseModel):
    cartas: list[CartaRascunho]


def slugify(text: str) -> str:
    return fx._fold(text).replace("-", "_")


def lore_snippets(postura: str, subclasse: str, k: int = 3) -> list[str]:
    """Até ``k`` trechos públicos de lore via ``query_rag``. Falha de RAG vira aviso."""
    try:
        import rag

        raw = rag.query_rag(f"{postura} {subclasse}", "lore", max_visibility="public")
    except Exception as exc:  # noqa: BLE001 - RAG é opcional para o rascunho
        log_fallback("card_draft", "rag_unavailable", exc)
        return []
    parts = [p.strip() for p in str(raw or "").split("\n\n") if p.strip()]
    return [p[:400] for p in parts[:k]]


def existing_for(postura: str, subclasse: str) -> list[dict]:
    return [
        {"name": c.get("name"), "momento": c.get("momento") or c.get("papel") or ""}
        for c in cards.cards_for_class(postura, subclasse)
        if c.get("subclasse") == subclasse
    ]


def build_prompt(
    postura: str,
    subclasse: str,
    n: int,
    raridades: tuple[str, ...],
    existentes: list[dict],
    lore: list[str],
) -> tuple[str, str]:
    rule = card_lint.roda().get(postura, {})
    lex = card_lint.lexico()
    glossario = fx.glossary_for_prompt(list(fx.glossary()))
    system = f"""Você desenha Cartas de combate para um RPG de texto sombrio ambientado em Valoria.
Escreva SOMENTE no vocabulário fechado abaixo; nada fora dele é aceito.

VOCABULÁRIO FECHADO
- kinds de efeito: {sorted(fx.all_kinds())}
- gatilhos (`quando`): {sorted(fx.GATILHOS)}
- alvos: {sorted(fx.ALVOS)}
- condições (`se`): {sorted(fx.CONDICOES)}
- palavras-chave de propriedade (`palavras_chave`): {sorted(fx.CARD_KEYWORDS)}
GLOSSÁRIO DE VALORIA
{glossario}

RODA DA POSTURA {postura}
- primário: {rule.get("primario")}  - secundário: {rule.get("secundario")}
- NUNCA: {rule.get("nunca")}  (cartas com isto são descartadas)

VOZ: nome até 4 palavras; descrição até 140 caracteres, concreta e sensorial, SEM números;
sabor de Valoria ({", ".join(lex["valoria"][:12])}); proibido: {", ".join(lex["proibidos"][:10])}…
Cada carta traz `momento`: UMA frase "melhor jogada quando…" diferente de todas as existentes.
Raridade = complexidade: comum 1 efeito e ≤ 1 palavra-chave; incomum ≤ 2; rara livre. Evite cartas
parecidas entre si: varie kinds, gatilhos e momentos."""
    human = f"""Proponha {n} cartas novas para {postura}, subclasse `{subclasse}`.
Distribuição de raridade: {", ".join(raridades)}.
JÁ EXISTEM (nome — momento): {json.dumps(existentes, ensure_ascii=False)}
TRECHOS DE LORE: {json.dumps(lore, ensure_ascii=False)}"""
    return system, human


def to_card(raw: CartaRascunho, postura: str, subclasse: str, onda: int) -> dict:
    efeitos = [e.model_dump(exclude_none=True) for e in raw.efeitos]
    card: dict[str, Any] = {
        "id": slugify(raw.id) or slugify(raw.name),
        "name": raw.name.strip(),
        "tipo": raw.tipo if raw.tipo in ("ativa", "reacao", "utilitaria") else "ativa",
        "origem": f"onda-{onda}",
        "classe": postura,
        "subclasse": subclasse,
        "patamar": _PATAMAR_POR_RARIDADE.get(raw.raridade, raw.patamar),
        "raridade": raw.raridade,
        "custo_entropia": max(0, raw.custo_entropia),
        "frequencia": raw.frequencia,
        "virtude_permitida": [],
        "efeitos": efeitos,
        "descricao": raw.descricao.strip(),
        "momento": raw.momento.strip(),
        "tier": max(1, min(9, raw.tier)),
        "level_req": max(1, raw.level_req),
        "apex": False,
        "onda": onda,
        "versao": 1,
    }
    if raw.palavras_chave:
        card["palavras_chave"] = raw.palavras_chave
    return card


def generate(
    llm: Any,
    postura: str,
    subclasse: str,
    n: int,
    raridades: tuple[str, ...] = RARIDADES_PADRAO,
    onda: int = 1,
    lore: list[str] | None = None,
) -> dict:
    """Pede o lote ao ``llm``. Devolve ``{"cards": [...], "rejeitadas": [...], "aviso": str}``.
    Guard de resiliência: um ``AIMessage`` (FallbackLLM/erro) em vez de ``LoteRascunho`` vira
    lote vazio com aviso; cartas fora do vocabulário fechado são separadas, nunca entram."""
    if getattr(llm, "is_mock", False) or getattr(llm, "is_fallback", False):
        log_fallback("card_draft", "no_llm")
        return {"cards": [], "rejeitadas": [], "aviso": "sem chave de provider: lote vazio"}
    existentes = existing_for(postura, subclasse)
    system, human = build_prompt(
        postura,
        subclasse,
        n,
        raridades,
        existentes,
        lore if lore is not None else lore_snippets(postura, subclasse),
    )
    try:
        result = llm.with_structured_output(LoteRascunho).invoke(
            [SystemMessage(content=system), HumanMessage(content=human)]
        )
    except Exception as exc:  # noqa: BLE001 - provider pode falhar de qualquer forma
        log_fallback("card_draft", "llm_error", exc)
        return {"cards": [], "rejeitadas": [], "aviso": f"falha do LLM ({type(exc).__name__})"}
    if isinstance(result, BaseMessage) or not isinstance(result, LoteRascunho):
        log_fallback("card_draft", "llm_fallback")
        return {"cards": [], "rejeitadas": [], "aviso": "LLM devolveu mensagem de erro: lote vazio"}
    aceitas: list[dict] = []
    rejeitadas: list[dict] = []
    vistos: set[str] = set()
    for raw in result.cartas:
        card = to_card(raw, postura, subclasse, onda)
        problemas = fx.validate_card(card)
        if card["id"] in vistos:
            problemas.append("id repetido no lote")
        if problemas:
            rejeitadas.append({"id": card["id"], "motivos": problemas})
            continue
        vistos.add(card["id"])
        aceitas.append(card)
    return {"cards": aceitas, "rejeitadas": rejeitadas, "aviso": ""}


def write_batch(
    out: dict, postura: str, subclasse: str, onda: int, directory: str = DRAFT_DIR
) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"onda{onda}_{slugify(postura)}_{slugify(subclasse)}.json")
    payload = {
        "_meta": f"SPEC-336 rascunho onda {onda} - {postura}/{subclasse}. Fora do pool; passe por lint, sim e promote.",
        "cards": out["cards"],
        "_rejeitadas_vocabulario": out["rejeitadas"],
    }
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--postura", required=True)
    ap.add_argument("--subclasse", required=True)
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--raridades", default=",".join(RARIDADES_PADRAO))
    ap.add_argument("--onda", type=int, default=1)
    args = ap.parse_args(argv)
    if args.postura not in card_lint.roda():
        print(f"Postura desconhecida: {args.postura!r}. Válidas: {sorted(card_lint.roda())}")
        return 2
    from llm_setup import ModelTier, get_llm

    llm = get_llm(temperature=0.9, tier=ModelTier.SMART)
    out = generate(
        llm, args.postura, args.subclasse, args.n, tuple(args.raridades.split(",")), args.onda
    )
    if out["aviso"]:
        print(f"AVISO: {out['aviso']}")
    path = write_batch(out, args.postura, args.subclasse, args.onda)
    print(f"{len(out['cards'])} cartas ({len(out['rejeitadas'])} fora do vocabulário) -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
