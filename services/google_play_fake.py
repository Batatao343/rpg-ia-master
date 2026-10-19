"""SPEC-194: deterministic Google Play stand-in for LOCAL development only.

Never selectable in hosted/portable profiles (see api._google_play). A fake token is
``fake-<obfuscated_account_id>-<nonce>`` so the fake can attest the account without a Store.
"""

from __future__ import annotations

import os

from services.google_play import PURCHASED, GooglePlayError, ProductPurchase

FAKE_PREFIX = "fake-"


def fake_requested() -> bool:
    return os.getenv("RPG_GOOGLE_PLAY_FAKE") == "1"


def fake_allowed() -> bool:
    """Local profile + explicit flag only; refused on Vercel or any hosted* profile even if misconfigured."""
    profile = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower()
    return (
        fake_requested()
        and profile == "local"
        and not profile.startswith("hosted")
        and not os.getenv("VERCEL")
    )


class FakeGooglePlayClient:
    def __init__(self) -> None:
        self.consumed: set[str] = set()

    def get_purchase(self, product_id: str, token: str) -> ProductPurchase:
        if not token.startswith(FAKE_PREFIX) or token.count("-") < 2:
            raise GooglePlayError("google_play_purchase_not_found")
        account = token[len(FAKE_PREFIX) :].rsplit("-", 1)[0]
        return ProductPurchase(
            product_id=product_id,
            order_id="GPA.FAKE-" + token[-12:],
            purchase_state=PURCHASED,
            consumption_state=1 if token in self.consumed else 0,
            acknowledgement_state=0,
            quantity=1,
            purchase_time_millis=1,
            account_id=account,
            purchase_type=None,
        )  # compra normal (sem purchaseType de teste)

    def consume(self, product_id: str, token: str) -> None:
        self.consumed.add(token)
