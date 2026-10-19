"""Stripe test-mode closure recognizes remote terminal states without live calls."""

import httpx
import pytest

from services.stripe_checkout import StripeError, StripeSettings, StripeTestAdapter


def test_expire_open_test_session_uses_authenticated_provider_call():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200, json={"id": "cs_test_fixture", "livemode": False, "status": "expired"}
        )

    adapter = StripeTestAdapter("sk_test_fixture", transport=httpx.MockTransport(respond))
    assert adapter.expire_session("cs_test_fixture") == "expired"
    assert [request.method for request in requests] == ["POST"]
    assert requests[0].url.path == "/v1/checkout/sessions/cs_test_fixture/expire"
    assert requests[0].headers["Authorization"] == "Bearer sk_test_fixture"


@pytest.mark.parametrize("terminal", ["complete", "expired"])
def test_already_closed_session_is_read_for_concurrent_retry(terminal):
    requests = []

    def respond(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(400, json={"error": {"message": "completed"}})
        return httpx.Response(
            200, json={"id": "cs_test_fixture", "livemode": False, "status": terminal}
        )

    adapter = StripeTestAdapter("sk_test_fixture", transport=httpx.MockTransport(respond))
    assert adapter.expire_session("cs_test_fixture") == terminal
    assert [request.method for request in requests] == ["POST", "GET"]


def test_provider_outage_keeps_deletion_pending():
    adapter = StripeTestAdapter(
        "sk_test_fixture", transport=httpx.MockTransport(lambda _request: httpx.Response(503))
    )
    with pytest.raises(StripeError):
        adapter.expire_session("cs_test_fixture")


def test_sales_kill_switch_preserves_cleanup_and_signed_webhook_configuration(monkeypatch):
    monkeypatch.setenv("RPG_STRIPE_ENABLED", "0")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fixture")
    monkeypatch.setenv("RPG_CHECKOUT_ORIGIN", "https://game.example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fixture")
    monkeypatch.delenv("RPG_STRIPE_ALLOWED_SKUS", raising=False)
    with pytest.raises(StripeError):
        StripeSettings.from_env()
    cleanup = StripeSettings.for_cleanup()
    assert cleanup.secret_key == "sk_test_fixture" and cleanup.allowed_skus == ()
    monkeypatch.delenv("RPG_CHECKOUT_ORIGIN", raising=False)
    reconciliation = StripeSettings.for_reconciliation()
    assert reconciliation.webhook_secret == "whsec_fixture" and reconciliation.allowed_skus == ()
