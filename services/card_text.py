"""SPEC-353 R15/R18/R37/R39a — texto de regra da Carta com o número que o motor usa.

``fx.render_card_text`` (estático, usado por lint e testes) fica como está. Aqui o texto da MÃO,
do Acervo e do espólio mostra o dano EFETIVO (Carta + herói iniciante + modificadores), o custo
em Vitalidade e a utilitária no conflito. Puro: sem LLM, sem efeito colateral.
"""

from __future__ import annotations

import re
from typing import Any

from services import card_effects as fx

_CAUSA_RE = re.compile(r"Causa (\d+) de dano")


def effective_rule_text(
    player: dict | None,
    card: dict,
    *,
    in_combat: bool = False,
    target: dict | None = None,
) -> str:
    """Texto de regra gerado. ``in_combat`` põe a utilitária como "sem efeito no conflito"."""
    effect = card.get("efeito") or {}
    kind = str(effect.get("kind") or "")
    if kind == "utilitaria" or card.get("tipo") == "utilitaria":
        hint = str(effect.get("prompt_hint") or "").strip().rstrip(".")
        if in_combat:
            return "Sem efeito no conflito." + (f" Fora dele: {hint}." if hint else "")
        return f"Fora de combate: {hint}." if hint else fx.render_card_text(card)
    text = fx.render_card_text(card)
    if kind == "taunt":  # R39a: o texto estático promete mais do que o motor cumpre (presságio)
        text = text.replace(
            "ele precisa atacar você", "a partir da próxima intenção, ele tende a atacar você"
        )
    if kind == "dano" and player is not None:
        text = _with_effective_damage(text, player, card, target)
    harm = int((card.get("mecanica_classe") or {}).get("auto_dano", 0) or 0)
    if harm > 0:
        text = text.rstrip() + f" Custa {harm} de Vitalidade."
    return text


def _with_effective_damage(text: str, player: dict, card: dict, target: Any) -> str:
    from services import combat_preview as cp

    m = _CAUSA_RE.search(text)
    if not m:
        return text
    try:
        total, _dtype, partes = cp.effective_damage_base(player, card, target)
    except Exception:  # silent-ok: texto estático da Carta é o fallback honesto
        return text
    if total == int(m.group(1)) and len(partes) == 1:
        return text
    detail = partes[0]
    for part in partes[1:]:
        detail += f" − {part[1:]}" if part.startswith("-") else f" + {part.lstrip('+')}"
    return _CAUSA_RE.sub(f"Causa {total} de dano ({detail})", text, count=1)
