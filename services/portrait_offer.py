"""SPEC-389 R1-R3: decisao e diagnostico da oferta paga de retrato (fora do `api.py`).

Toda ausencia de `retrato.gerar` tem 1 causa de um conjunto FECHADO (`OFFER_CAUSES`); cada resposta
de combate emite 1 `creature_portrait.offer_view` (controle positivo: sem a linha, o problema e o log)."""

from __future__ import annotations

import os
import time
from collections import Counter
from typing import Any

from observability.boot import INSTANCE_REF
from observability.telemetry import log_event, log_fallback, pseudonym
from services.checkout_retry import retry_once
from services.portrait_offer_log import log_offer_omitted, note_gate, set_tally, tally

INSTANCE = INSTANCE_REF  # mesmo id de processo do `instance_ref` de toda linha de log
PRICE_TTL_S = 60.0

OFFER_CAUSES = (
    "switch_off",
    "switches_unreadable",
    "switches_stale",
    "env_off",
    "pricing_unavailable",
    "price_absent",
    "price_peek_failed",
    "art_not_live:flag",
    "art_not_live:profile",
    "art_not_live:dynamic_art",
    "registry_read_failed",
    "fallback_enemy",
    "pending",
    "private_other_game",
    "has_own_art",
    "image_gate_failed",
)
_EXPECTED = ("fallback_enemy", "pending", "private_other_game", "has_own_art", "art_not_live")


def gate() -> tuple[bool, str | None]:
    """Mesmo portao da cotacao (`_guard_image_effect`) como predicado sem excecao: (aberto, causa)."""
    from services.finops_alerts import require_paid_effect
    from services.kill_switches import IMAGE, _env_off, get_switches
    from services.shard_pricing import PricingUnavailable

    try:
        switches = get_switches()
        if not switches.is_enabled(IMAGE):
            cause = "switch_off"
            if IMAGE in _env_off():
                cause = "env_off"
            elif getattr(switches, "stale", False):
                cause = "switches_stale"
            elif getattr(switches, "unreadable", False):
                cause = "switches_unreadable"
            if cause in ("switches_stale", "switches_unreadable"):
                log_offer_omitted(cause)
            note_gate(cause)
            return False, cause
        require_paid_effect("image")
    except PricingUnavailable:
        note_gate("pricing_unavailable")
        return False, "pricing_unavailable"
    except Exception as exc:  # noqa: BLE001 — leitura do store falhou: sem oferta (fail-closed)
        log_offer_omitted("image_gate_failed", exc)
        return False, "image_gate_failed"
    return True, None


def price_estilhas(cache: dict[str, Any]) -> int | None:
    """Teto da cotacao em Estilhas inteiras (so leitura). Cache de 60 s SO para preco valido (R3)."""
    now = time.monotonic()
    if cache.get("value") is not None and now - float(cache["at"]) < PRICE_TTL_S:
        note_gate("", price_cached=True)
        return cache["value"]
    try:
        from infrastructure.runtime import get_runtime
        from services.image_quotes import ImageQuoteRepository

        repo = ImageQuoteRepository(get_runtime().resources[0])
        milli = retry_once(lambda: repo.peek_ceiling("monster"))  # SPEC-387 R6
    except Exception as exc:  # noqa: BLE001
        log_offer_omitted("price_peek_failed", exc)
        return None  # SPEC-387 R5: falha nunca vai para o cache
    if not milli:
        cache.update(at=0.0, value=None, milli=None)  # None nunca fica 60 s (R3)
        note_gate("price_absent")
        return None
    value = -(-int(milli) // 1000)
    cache.update(at=now, value=value, milli=int(milli))
    return value


def art_cause(mode_on: bool, database: bool) -> str | None:
    """Por que o registro/oferta nao esta vivo (`None` = vivo)."""
    if not mode_on:
        return "art_not_live:flag"
    if not database:
        return "art_not_live:profile"
    if os.getenv("RPG_DYNAMIC_ART_ENABLED", "0").strip().lower() not in {"1", "true", "yes"}:
        return "art_not_live:dynamic_art"
    return None


def begin(art_live: bool, game_id: str = "") -> None:
    set_tally(
        {
            "offered": 0,
            "omitted": Counter(),
            "art_live": art_live,
            "price_cached": False,
            "game_ref": pseudonym(game_id) if game_id else "",  # /game/state nao liga a correlacao
        }
    )


def classify(
    portrait: dict[str, Any], reasons: list[str], registry_live: bool, art: str | None
) -> str | None:
    """Causa da ausencia de `gerar` para 1 inimigo (`None` = ofertado)."""
    if portrait.get("gerar"):
        return None
    # precedencia real de `portrait_for`: o fallback nem le o registro; arte propria/do tipo vence a linha
    # `private` de outro jogo; `pending` com essa linha vira `private_other_game`.
    if "fallback_enemy" in reasons:
        return "fallback_enemy"
    if "has_own_art" in reasons:
        return "has_own_art"
    if "pending" in reasons:
        return "private_other_game" if "private_other_game" in reasons else "pending"
    gate_cause = (tally() or {}).get("gate") or ""
    if not registry_live:
        return art or (gate_cause if gate_cause == "registry_read_failed" else "art_not_live:flag")
    return gate_cause or "price_absent"


def record(
    portrait: dict[str, Any], reasons: list[str], registry_live: bool, art: str | None
) -> None:
    current = tally()
    if current is None:
        return
    cause = classify(portrait, reasons, registry_live, art)
    if cause is None:
        current["offered"] += 1
    else:
        current["omitted"][cause] += 1


def summarize(current: dict[str, Any]) -> dict[str, Any]:
    from services.kill_switches import get_switches

    age = None
    try:
        age = get_switches().age_s
    except Exception as exc:  # noqa: BLE001 — diagnostico nunca derruba a view
        log_fallback("creature_portrait", "switch_age_failed", exc)
    return {
        "instance": INSTANCE,
        "game_ref": current.get("game_ref", ""),
        "offered": int(current["offered"]),
        "omitted": dict(current["omitted"]),
        "switch_age_s": age,
        "price_cached": bool(current.get("price_cached")),
        "art_live": bool(current.get("art_live")),
    }


def finish() -> dict[str, Any] | None:
    """Emite o `offer_view` da resposta (1 por `_combat_block` com inimigo vivo)."""
    current = tally()
    set_tally(None)
    if current is None:
        return None
    data = summarize(current)
    unexpected = [c for c in data["omitted"] if not c.startswith(_EXPECTED)]
    level = "warning" if unexpected else "info"
    log_event("creature_portrait", "offer_view", level=level, **data)
    return data
