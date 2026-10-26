"""SPEC-325 R4: conta disparos das 8 capacidades de conflito durante uma campanha.

O contador escuta `observability.telemetry.log_event` (so o nome do evento). Chaves:
`<cap>` = efeito real (flag `on`), `<cap>_shadow` = decisao so registrada.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

from services.combat_flags import CAPS

# evento (`combat.<nome>`) -> chave de contagem
EVENT_TO_KEY: dict[str, str] = {
    "combat.reveal_resist": "reveal_resist",
    "combat.reveal_resist_shadow": "reveal_resist_shadow",
    "combat.nonlethal": "nonlethal",
    "combat.nonlethal_shadow": "nonlethal_shadow",
    "combat.chase_approach": "chase_approach",
    "combat.chase_approach_shadow": "chase_approach_shadow",
    "combat.chase_attack_refused": "chase_attack",
    "combat.chase_attack_reengage": "chase_attack",
    "combat.chase_attack_shadow": "chase_attack_shadow",
    "combat.chase_abandon": "chase_abandon",
    "combat.chase_sacrifice": "chase_abandon",
    "combat.chase_abandon_shadow": "chase_abandon_shadow",
    "combat.chase_sacrifice_shadow": "chase_abandon_shadow",
    "combat.object_used": "objects",
    "combat.objects_shadow": "objects_shadow",
    "combat.companion_order": "companion_orders",
    "combat.companion_orders_shadow": "companion_orders_shadow",
    "combat.reinforcements_warned": "reinforcements",
    "combat.reinforcements_fired": "reinforcements",
    "combat.reinforcements_shadow": "reinforcements_shadow",
}

KEYS: tuple[str, ...] = tuple(k for cap in CAPS for k in (cap, f"{cap}_shadow"))


def empty_counts() -> dict[str, int]:
    return dict.fromkeys(KEYS, 0)


class CapabilityCounter:
    """Acumula contagens por chave; `snapshot()` devolve as 16 chaves (zeros incluídos)."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def __call__(self, event: str) -> None:
        key = EVENT_TO_KEY.get(event)
        if key:
            self._counts[key] += 1

    def snapshot(self) -> dict[str, int]:
        out = empty_counts()
        out.update({k: int(v) for k, v in self._counts.items()})
        return out


@contextmanager
def counting() -> Iterator[CapabilityCounter]:
    """Instala o contador como sink de `log_event` durante o bloco."""
    from observability import telemetry

    counter = CapabilityCounter()
    telemetry.set_event_sink(counter)
    try:
        yield counter
    finally:
        telemetry.set_event_sink(None)
