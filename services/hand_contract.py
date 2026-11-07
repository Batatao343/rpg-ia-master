"""SPEC-398 R1/R2: contrato público da mão coerente com o motor.

A vista da mão nunca sugere jogar o que o motor recusa: Carta que não é `ativa`
(reação, passiva) sai `jogavel: false` com motivo; Carta de alvo inimigo sem alvo
visível traz o `invalid_reason` do motor. Só leitura; sem LLM."""

from __future__ import annotations

from services import cards
from services import combat_targeting as targeting

NOT_PLAYABLE = "not_playable_from_hand"
# Motivos de alvo que bloqueiam a jogada na UI (mesmo vocabulário do motor).
TARGET_BLOCKS = ("target_hidden", "no_valid_target", "target_dead")


def merge_row_targeting(row: dict, state: dict) -> None:
    """Acrescenta alvos/motivo ao item da mão (`public_view`) e corrige o contrato."""
    card_id = str(row.get("id"))
    row.update(targeting.hand_card_targeting(state, card_id))
    card = cards.get_card(card_id) or {}
    if card and card.get("tipo") not in ("ativa", "utilitaria"):
        row["jogavel"] = False
        row["alvo"] = "si"
        row["valid_targets"] = []
        row["invalid_reason"] = NOT_PLAYABLE
