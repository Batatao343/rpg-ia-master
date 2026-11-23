"""SPEC-428: tamanho-alvo da narracao por tipo de turno (`RPG_NARRATION_SIZE=off|shadow|on`).

Instrucao de prompt apenas: sem `max_tokens`, sem mudar schema nem o que o motor decide.
`off` (default, e qualquer valor invalido) => o prompt do narrador e o de sempre, byte a byte.
`shadow` => prompt igual ao de `off`; so loga `narration.size_class` (a classe do turno).
`on` => classes encurtadas (`cena`, `fala_mediada`, `descanso`) ganham a linha `TAMANHO DA RESPOSTA`.
Nunca loga texto de narracao.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from observability.telemetry import log_event
from services.env import env_choice

SizeClass = Literal["abertura", "local_novo", "revelacao", "fala_mediada", "descanso", "cena"]

# Clausula de opcoes de SPEC-043 R3 (movida de agents/storyteller.py sem mudar um byte).
OPCOES_CLAUSE = (
    "\n    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa "
    "linha iniciada por '— ', e termine com '— Ou outra ação.' "
    "(dê rumo ao jogador; as opções mecânicas de combate vêm à parte)."
)
PARAGRAPH_RULE_OFF = "- Responda em 2 a 3 parágrafos."
PARAGRAPH_RULE_ON = (
    "- Responda em 2 a 3 parágrafos, salvo quando TAMANHO DA RESPOSTA, abaixo, pedir menos."
)


@dataclass(frozen=True)
class SizeTarget:
    size_class: SizeClass
    shortened: bool
    paragraphs: str
    chars_min: int  # faixa medida em `narration_chars` (opcoes incluidas)
    chars_max: int
    words_min: int  # o que o prompt pede (prosa antes das opcoes)
    words_max: int


def _keep(size_class: SizeClass) -> SizeTarget:
    return SizeTarget(size_class, False, "", 0, 0, 0, 0)


TARGETS: dict[SizeClass, SizeTarget] = {
    "cena": SizeTarget("cena", True, "2 parágrafos curtos (2 a 4 frases cada)", 750, 1000, 90, 140),
    "fala_mediada": SizeTarget("fala_mediada", True, "1 a 2 parágrafos curtos", 600, 900, 70, 120),
    "descanso": SizeTarget("descanso", True, "2 parágrafos curtos", 800, 1100, 100, 150),
    "local_novo": _keep("local_novo"),
    "revelacao": _keep("revelacao"),
    "abertura": _keep("abertura"),
}


def mode() -> str:
    """`off` | `shadow` | `on`; ausente ou invalido = `off`."""
    return env_choice("RPG_NARRATION_SIZE", ("off", "shadow", "on"), "off")


def paragraph_rule() -> str:
    """Regra estatica de paragrafos: so o modo `on` troca o texto."""
    return PARAGRAPH_RULE_ON if mode() == "on" else PARAGRAPH_RULE_OFF


def _has_gancho(t: Any) -> bool:
    gancho = str(getattr(t, "gancho_novo", None) or "")
    return "<GANCHO_NOVO>" in gancho or "<DESFECHO_DE_QUEST>" in gancho


def _is_revelacao(t: Any) -> bool:
    note = str(getattr(t, "world_note", None) or "")
    return (
        _has_gancho(t)
        or bool(getattr(t, "discovery_events", None))
        or bool(getattr(t, "rumor_find", None))
        or note.startswith("ENCONTRO NA ESTRADA")
    )


def _is_new_location(t: Any) -> bool:
    dest = getattr(t, "dest", None)
    if not dest:
        return False
    before = getattr(t, "world_before", None) or {}
    return dest.get("id") not in (before.get("visited") or [])


def classify(t: Any) -> SizeClass:
    """Classe do turno (R4), pela primeira regra que casa. Le atributos; nao muta `t`."""
    from services import interlocutor

    world = getattr(t, "world", None) or {}
    if int(world.get("turn_count", 0) or 0) <= 1:
        return "abertura"
    if _is_new_location(t):
        return "local_novo"
    if _is_revelacao(t):
        return "revelacao"
    scene = getattr(t, "scene_state", None) or {}
    if scene.get("interlocutor_reason") in interlocutor.MEDIATION_REASONS:
        return "fala_mediada"
    if getattr(t, "rested_player", None) is not None:
        return "descanso"
    return "cena"


def size_line(target: SizeTarget) -> str:
    """Linha dinamica `TAMANHO DA RESPOSTA` (R6b)."""
    return (
        f"\n    - TAMANHO DA RESPOSTA: {target.paragraphs}, entre {target.words_min} e "
        f"{target.words_max} palavras antes das opções. Corte descrição e repetição; "
        "nunca corte o que está em <EVENTOS_DESTE_TURNO>, fato novo, fala com informação, "
        "oferta de missão nem a consequência da ação do jogador."
    )


def closing_clause(t: Any) -> str:
    """Clausula de opcoes; em `on`, classe encurtada ganha a linha de tamanho. Loga fora de `off`."""
    current = mode()
    if current == "off":
        return OPCOES_CLAUSE
    target = TARGETS[classify(t)]
    log_event(
        "narration",
        "size_class",
        mode=current,
        size_class=target.size_class,
        shortened=target.shortened,
        chars_max=target.chars_max if target.shortened else 0,
    )
    if current == "on" and target.shortened:
        return OPCOES_CLAUSE + size_line(target)
    return OPCOES_CLAUSE
