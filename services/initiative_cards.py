"""SPEC-397 R5: Cartas de Iniciativa (`buff_iniciativa`) que anulam a emboscada.

Ativas valem no baralho/preparadas; PASSIVAS valem só por serem conhecidas (não ocupam
slot nem baralho), como `combat_mechanics.learned_passives`."""

from __future__ import annotations

from services import card_effects as fx
from services import cards

VIGILIA_CARD_ID = "dev_zel_vigilia"


def _grants_initiative(card_id: str) -> bool:
    if card_id == VIGILIA_CARD_ID:
        return True
    card = cards.get_card(str(card_id))
    return bool(card and any(e.get("kind") == "buff_iniciativa" for e in fx.normalize(card)))


def has_initiative_card(player: dict | None) -> bool:
    p = player or {}
    for cid in list(p.get("deck") or []) + list(p.get("prepared_cards") or []):
        if _grants_initiative(cid):
            return True
    for cid in p.get("known_cards") or []:
        if (cards.get_card(str(cid)) or {}).get("tipo") == "passiva" and _grants_initiative(cid):
            return True
    return False
