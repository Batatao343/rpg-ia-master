"""SPEC-189 offline signature and test-only adapter contracts."""
import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest

from services.stripe_checkout import StripeError, StripeTestAdapter, verify_event

SECRET = "whsec_fixture_only"
NOW = 1791892800


def signed(event, *, timestamp=NOW):
    body = json.dumps(event, separators=(",", ":")).encode()
    digest = hmac.new(SECRET.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return body, f"t={timestamp},v1={digest}"


def test_signature_checks_raw_bytes_before_json():
    body, signature = signed({"id": "evt_fixture", "type": "ignored", "livemode": False,
                              "created": NOW, "data": {"object": {"id": "obj_fixture"}}})
    assert verify_event(body, signature, SECRET, now=NOW)["id"] == "evt_fixture"
    for changed, header in [(body + b" ", signature), (b"not json", signature),
                            (body, ""), (body, signature.replace("v1=", "v0="))]:
        with pytest.raises(StripeError, match="signature"):
            verify_event(changed, header, SECRET, now=NOW)
    with pytest.raises(StripeError, match="signature"):
        verify_event(body, signature, SECRET, now=NOW + 301)
    with pytest.raises(StripeError, match="signature"):
        verify_event(body, signature, SECRET, now=NOW - 301)


def test_live_event_and_live_key_are_rejected():
    body, signature = signed({"id": "evt_live", "type": "ignored", "livemode": True,
                              "created": NOW, "data": {"object": {}}})
    with pytest.raises(StripeError, match="live"):
        verify_event(body, signature, SECRET, now=NOW)
    with pytest.raises(StripeError, match="test"):
        StripeTestAdapter("sk_live_forbidden")


def test_adapter_uses_server_amount_and_stable_idempotency():
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"id": "cs_test_fixture", "url": "https://checkout.stripe.com/c/pay/test_fixture",
                                         "livemode": False})
    adapter = StripeTestAdapter("sk_test_fixture", transport=httpx.MockTransport(handle))
    result = adapter.create_session("order-fixture", amount_cents=1050,
                                    success_url="https://game.example/?checkout=success",
                                    cancel_url="https://game.example/?checkout=cancel")
    assert result["id"] == "cs_test_fixture"
    assert calls[0].headers["idempotency-key"] == "checkout:order-fixture"
    data = calls[0].content.decode()
    assert "unit_amount%5D=1050" in data
    assert "metadata%5Border_id%5D=order-fixture" in data
    assert "owner" not in data and "shard_milli" not in data


def test_signed_fixture_on_disk_is_verifiable():
    root = Path(__file__).parent / "fixtures/stripe"
    body = (root / "checkout_paid.json").read_bytes()
    header = (root / "checkout_paid.signature").read_text(encoding="ascii").strip()
    verified = verify_event(body, header, SECRET, now=NOW)
    assert verified["data"]["object"]["payment_status"] == "paid"


def test_signature_rotation_accepts_any_valid_v1_and_never_calls_json_on_bad_signature(monkeypatch):
    body, header = signed({"id": "evt_rotated", "type": "unknown", "created": NOW,
                           "livemode": False, "data": {"object": {}}})
    assert verify_event(body, header + ",v1=" + "0"*64, SECRET, now=NOW)["id"] == "evt_rotated"
    def fail_parse(_body):
        raise AssertionError("unverified JSON was parsed")
    monkeypatch.setattr("services.stripe_checkout.json.loads", fail_parse)
    with pytest.raises(StripeError, match="signature"):
        verify_event(body, "t=" + str(NOW) + ",v1=" + "0"*64, SECRET, now=NOW)


@pytest.mark.parametrize("key", ["sk_live_bad", "", "rk_live_bad"])
def test_configuration_is_closed_without_explicit_test_key_and_server_catalog(monkeypatch, key):
    from services.stripe_checkout import StripeSettings
    monkeypatch.setenv("RPG_STRIPE_ENABLED", "1")
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("RPG_CHECKOUT_ORIGIN", "https://game.example")
    monkeypatch.setenv("RPG_STRIPE_ALLOWED_SKUS", '["fixture"]')
    with pytest.raises(StripeError):
        StripeSettings.from_env()


def test_actual_fee_is_bound_to_test_intent_and_balance_transaction():
    def handler(request):
        assert request.url.path == "/v1/payment_intents/pi_fixture"
        return httpx.Response(200, json={"id": "pi_fixture", "livemode": False,
            "latest_charge": {"payment_intent": "pi_fixture", "balance_transaction":
                {"id": "txn_fixture", "fee": 57, "currency": "brl"}}})
    adapter = StripeTestAdapter("sk_test_fixture", transport=httpx.MockTransport(handler))
    assert adapter.payment_economics("pi_fixture")["fee_cents"] == 57
    with pytest.raises(StripeError):
        adapter.payment_economics("pi_fixture/../../secrets")
