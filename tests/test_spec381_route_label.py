"""SPEC-381 R21: ``route_label`` devolve o template da rota (nunca ``"other"``) para cada router."""

from __future__ import annotations

import pytest

from services.body_limit import route_label

CASES = [
    ("/auth/config", "/auth/config"),
    ("/health", "/health"),
    ("/data/options", "/data/options"),
    ("/account/checkout/skus", "/account/checkout/skus"),
    ("/game/prologue", "/game/prologue"),
    ("/game/new", "/game/new"),
    ("/game/equip", "/game/equip"),
    ("/game/saves", "/game/saves"),
    ("/game/abc123/art/quote", "/game/{id}/art/quote"),
    ("/account/checkout/ord-1", "/account/checkout/{id}"),
]


@pytest.mark.parametrize(("path", "expected"), CASES)
def test_route_label_is_the_template(path, expected):
    import api  # noqa: PLC0415

    assert route_label(path, routes=api.app.routes) == expected
