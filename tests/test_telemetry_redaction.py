from observability.metrics import Metrics
from observability.telemetry import correlation_scope, pseudonym, redact, safe_json


def test_redaction_remove_payloads_tokens_email_and_signed_url():
    event = {
        "authorization": "Bearer secret.jwt.token",
        "email": "hero@example.com",
        "action": "meu plano secreto",
        "nested": {"refresh_token": "refresh", "safe": "ok"},
        "message": "Bearer abc.def ghi hero@example.com",
    }
    rendered = safe_json(event)
    assert "secret.jwt" not in rendered
    assert "hero@example.com" not in rendered
    assert "meu plano" not in rendered
    assert ': "refresh"' not in rendered
    assert '"safe": "ok"' in rendered


def test_ids_sao_pseudonimos_estaveis_sem_uuid_cru():
    raw = "7db1d65d-490b-4651-8bf6-c8f34b679bb3"
    assert pseudonym(raw, secret="x") == pseudonym(raw, secret="x")
    with correlation_scope(game_id=raw) as context:
        assert raw not in str(context)
        assert context["game_id_ref"] == pseudonym(raw)


def test_metricas_rejeitam_labels_de_alta_cardinalidade():
    metrics = Metrics()
    metrics.increment("rpg_turn_commits_total", {"outcome": "ok"})
    try:
        metrics.increment(
            "rpg_turn_commits_total", {"outcome": "ok", "game_id": "raw"},
        )
    except ValueError as exc:
        assert "labels" in str(exc)
    else:
        raise AssertionError("label game_id deveria ser recusada")


def test_redact_e_puro():
    source = {"payload": {"password": "x"}, "ok": ["value"]}
    assert redact(source) == {"payload": "[REDACTED]", "ok": ["value"]}
    assert source["payload"]["password"] == "x"


def test_metricas_suportam_observacoes_e_gauges_sem_ids():
    metrics = Metrics()
    metrics.observe("rpg_http_duration_seconds", {"route": "/health"}, 0.2)
    metrics.set_gauge("rpg_db_pool", {"state": "available"}, 3)
    snapshot = metrics.snapshot()
    assert any(key.endswith(".count") and value == 1 for key, value in snapshot.items())
    assert any("rpg_db_pool" in key and value == 3 for key, value in snapshot.items())
