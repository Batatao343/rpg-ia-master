"""SPEC-369 D-369-5: ajuste determinístico de uma Carta ao orçamento da SPEC-330.

Extraído de ``scripts/bestiario/gerar_mecanica.py`` (``_fit_orcamento``) para ser
reaproveitado por ``scripts/cards/draft.py``. Só mexe em números: ``custo_folego``
(0..3) e ``dano_base`` do maior efeito de dano.
"""

from __future__ import annotations

from services import card_effects as fx


def _maior_dano(card: dict) -> dict | None:
    efeitos = card.get("efeitos") or ([card["efeito"]] if card.get("efeito") else [])
    return max(
        (e for e in efeitos if e.get("kind") == "dano" and e.get("dano_base", 0) > 1),
        key=lambda e: int(e["dano_base"]),
        default=None,
    )


def fit_orcamento(card: dict, max_passos: int = 40, passos: list[str] | None = None) -> dict:
    """Mantém a Carta dentro da faixa: acima, sobe o Fôlego (faixa maior) e, no limite, tira
    dano; abaixo, desce o Fôlego. Muta ``card``; cada passo vai em ``passos`` (se dado)."""
    for _ in range(max_passos):
        if not fx.budget_error(card):
            break
        band = fx.budget_band(card)
        if band is None:
            break
        fol = fx.custo_folego(card)
        if fx.power_score(card) > band[1]:
            if fol < 3:
                card["custo_folego"] = fol + 1
                _anota(passos, f"custo_folego {fol}->{fol + 1}")
                continue
            alvo = _maior_dano(card)
            if alvo is None:
                break
            alvo["dano_base"] = int(alvo["dano_base"]) - 1
            _anota(passos, f"dano_base {alvo['dano_base'] + 1}->{alvo['dano_base']}")
        elif fol > 0:
            card["custo_folego"] = fol - 1
            _anota(passos, f"custo_folego {fol}->{fol - 1}")
        else:
            break
    if "efeito" in card:
        card["efeito"] = fx.primary_effect(card) or card["efeito"]
    return card


def _anota(passos: list[str] | None, texto: str) -> None:
    if passos is not None:
        passos.append(texto)
