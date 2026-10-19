"""SPEC-257: logs de pagamento (webhook Stripe, verificacao Google Play, carteira) sem segredos."""
import json
import uuid
from types import SimpleNamespace

import pytest

from infrastructure.contracts import Principal
from observability import logging_setup
from observability.metrics import metrics
from services.google_play import GooglePlayError
from services.stripe_checkout import StripeError

TOKEN = "PURCHASETOKENSENTINELA257-" + "x" * 20
SECRET = "client_secret_SENTINELA257"


@pytest.fixture(autouse=True)
def _logs(monkeypatch):
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    import api
    api._rate_hits.clear()
    return TestClient(api.app)


def _lines(capsys):
    out = capsys.readouterr().out
    return out, [json.loads(x) for x in out.splitlines() if x.startswith("{")]


def _patch_stripe(monkeypatch, *, verify, accept=None):
    import api
    from services import stripe_checkout
    monkeypatch.setattr(stripe_checkout.StripeSettings, "from_env",
                        classmethod(lambda cls: SimpleNamespace(webhook_secret="whsec")))
    monkeypatch.setattr(stripe_checkout, "verify_event", verify)
    monkeypatch.setattr(api, "_stripe_payments",
                        lambda: SimpleNamespace(accept_event=accept or (lambda e, body_sha256: {})))


def test_bad_signature_logged(client, capsys, monkeypatch):
    def bad(*_a, **_k):
        raise StripeError("stripe_signature_invalid")

    _patch_stripe(monkeypatch, verify=bad)
    r = client.post("/payments/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=zz"})
    assert r.status_code == 400
    out, lines = _lines(capsys)
    (line,) = [x for x in lines if x["event"] == "payments.stripe_webhook"]
    assert line["outcome"] == "signature_invalid" and line["level"] == "warning"
    assert line["duration_ms"] >= 0 and "event_ref" in line


def test_duplicate_and_applied_logged(client, capsys, monkeypatch):
    event = {"id": "evt_SENTINELA257", "type": "checkout.session.completed", "created": 1}
    results = iter([{"received": True, "duplicate": False, "apply_result": "credited"},
                    {"received": True, "duplicate": True, "apply_result": "noop"}])
    _patch_stripe(monkeypatch, verify=lambda *a, **k: event, accept=lambda e, body_sha256: next(results))
    for _ in range(2):
        assert client.post("/payments/stripe/webhook", content=b"{}",
                           headers={"stripe-signature": "x"}).status_code == 200
    out, lines = _lines(capsys)
    hooks = [x for x in lines if x["event"] == "payments.stripe_webhook"]
    assert [h["outcome"] for h in hooks] == ["applied", "duplicate"]
    assert hooks[0]["apply_result"] == "credited" and hooks[0]["event_type"] == "checkout.session.completed"
    assert hooks[0]["event_ref"] and "evt_SENTINELA257" not in out         # id do evento so pseudonimizado
    assert any("rpg_payment_verifications_total" in k and "stripe" in k for k in metrics.snapshot())


def test_replay_conflict_and_ignored_type(client, capsys, monkeypatch):
    event = {"id": "evt_1", "type": "customer.created", "created": 1}

    def conflict(_event, body_sha256):
        raise StripeError("stripe_event_replay_conflict")

    _patch_stripe(monkeypatch, verify=lambda *a, **k: event, accept=conflict)
    assert client.post("/payments/stripe/webhook", content=b"{}",
                       headers={"stripe-signature": "x"}).status_code == 400
    _patch_stripe(monkeypatch, verify=lambda *a, **k: event,
                  accept=lambda e, body_sha256: {"received": True, "duplicate": False, "apply_result": "noop"})
    assert client.post("/payments/stripe/webhook", content=b"{}",
                       headers={"stripe-signature": "x"}).status_code == 200
    _out, lines = _lines(capsys)
    outcomes = [x["outcome"] for x in lines if x["event"] == "payments.stripe_webhook"]
    assert outcomes == ["replay_conflict", "ignored_type"]


def test_google_cancelled_logged_with_outcome(client, capsys, monkeypatch):
    import api
    from infrastructure import request_context

    def verify(*_a, **_k):
        err = GooglePlayError("google_play_purchase_cancelled")
        err.upstream_status = 200
        raise err

    principal = Principal(uuid.uuid4(), "iss", "sub")
    monkeypatch.setattr(request_context, "current_principal", lambda **k: principal)
    monkeypatch.setattr(api, "_google_play", lambda: SimpleNamespace(verify=verify))
    r = client.post("/account/purchases/google/verify", json={
        "product_id": "shards_100", "purchase_token": TOKEN, "order_id": "GPA.1234-5678"})
    assert r.status_code == 409
    out, lines = _lines(capsys)
    (line,) = [x for x in lines if x["event"] == "payments.google_verify"]
    assert line["outcome"] == "google_play_purchase_cancelled" and line["product_id"] == "shards_100"
    assert line["order_ref"] and "GPA.1234" not in out and line["upstream_status"] == 200


def test_no_purchase_token_in_logs(client, capsys, monkeypatch):
    import api
    from infrastructure import request_context

    def verify(*_a, **_k):
        raise GooglePlayError("google_play_unavailable")

    principal = Principal(uuid.uuid4(), "iss", "sub")
    monkeypatch.setattr(request_context, "current_principal", lambda **k: principal)
    monkeypatch.setattr(api, "_google_play", lambda: SimpleNamespace(verify=verify))
    client.post("/account/purchases/google/verify", json={"product_id": "shards_100", "purchase_token": TOKEN})
    out, _lines_ = _lines(capsys)
    assert TOKEN not in out and "PURCHASETOKENSENTINELA257" not in out and SECRET not in out


def test_checkout_failed_logged_without_secret(capsys):
    from infrastructure.payment_log import checkout_failed
    checkout_failed("create", StripeError(f"stripe_session_invalid {SECRET}"))
    out, lines = _lines(capsys)
    (line,) = [x for x in lines if x["event"] == "payments.checkout_failed"]
    assert line["stage"] == "create" and line["level"] == "error" and line["error_type"] == "StripeError"
    assert SECRET not in out


def test_wallet_settle_failure_logged(capsys):
    from infrastructure.payment_log import wallet_event
    reservation = uuid.uuid4()
    wallet_event("settle_failed", reservation, RuntimeError(f"saldo {SECRET}"), stage="settle_usage")
    out, lines = _lines(capsys)
    (line,) = [x for x in lines if x["event"] == "wallet.settle_failed"]
    assert line["error_type"] == "RuntimeError" and line["op_ref"] and line["stage"] == "settle_usage"
    assert str(reservation) not in out and SECRET not in out


def test_wallet_recovery_item_failure_logged(capsys, monkeypatch):
    from services import wallet_recovery

    row = {"owner_id": uuid.uuid4(), "reservation_id": uuid.uuid4(), "reference_type": "operation",
           "usage_operation_id": uuid.uuid4(), "op_status": "failed"}
    monkeypatch.setattr(wallet_recovery, "_candidates", lambda *a, **k: [row])

    def boom(*_a, **_k):
        raise RuntimeError("db caiu")

    monkeypatch.setattr(wallet_recovery, "_resolve_operation", boom)
    import infrastructure.wallet as wallet_module
    monkeypatch.setattr(wallet_module, "PostgresWallet", lambda pool: object())
    counts = wallet_recovery.recover_wallet_reservations(object(), 5)
    assert counts["wallet_errors"] == 1
    _out, lines = _lines(capsys)
    assert [x for x in lines if x["event"] == "wallet.recovery_item_failed"]


def test_fee_reconcile_failure_never_logs_free_text(capsys):
    """Revisao Sol: o codigo do StripeError so entra no log se for snake_case fechado."""
    from infrastructure.payment_log import fee_reconcile_failed
    fee_reconcile_failed("payment_economics", StripeError("Card 4242 declined for joe@example.com"))
    fee_reconcile_failed("payment_economics", StripeError("stripe_economics_unavailable"))
    out, lines = _lines(capsys)
    got = [x for x in lines if x["event"] == "payments.fee_reconcile_failed"]
    assert [x["error_code"] for x in got] == ["other", "stripe_economics_unavailable"]
    assert "4242" not in out and "example.com" not in out
