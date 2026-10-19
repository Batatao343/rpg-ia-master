"""SPEC-207 Etapa 1: redaction fail-closed do pacote de auditoria."""

from __future__ import annotations

import uuid

from services.audit_redaction import redact_record, scan_pii, scrub_text


def test_scrub_email_phone_url():
    text = (
        "me ache em ana.souza@example.com ou (11) 98765-4321, "
        "+55 11 98765 4321, link https://x.supabase.co/storage/v1/object/sign/a.png?token=abc "
        "e https://h.example/p?signature=zz"
    )
    out = scrub_text(text)
    assert "example.com" not in out and "98765" not in out
    assert "token=abc" not in out and "signature=zz" not in out
    assert "[REDACTED:email]" in out and "[REDACTED:phone]" in out and "[REDACTED:url]" in out


def test_scrub_keeps_game_numbers():
    text = "Você ganha 50 moedas no dia 12; custo 0.000041550; latência 12345678 ms."
    assert scrub_text(text) == text


def test_owner_values_never_survive():
    owner = uuid.uuid4()
    email = "dono.real@example.org"
    record = {"a": {"b": [f"id {owner} e {owner.hex} e {email.upper()}"]}}
    spec = {"a": {"b": ("list", "scalar")}}
    out = redact_record(record, spec=spec, owner_values={str(owner), email})
    flat = str(out)
    assert (
        str(owner) not in flat and owner.hex not in flat and email.casefold() not in flat.casefold()
    )
    assert "[REDACTED:owner]" in flat


def test_unknown_key_dropped():
    out = redact_record(
        {"keep": 1, "owner_id": "x", "nested": {"ok": "a", "ip": "1.2.3.4"}},
        spec={"keep": "scalar", "nested": {"ok": "scalar"}},
    )
    assert out == {"keep": 1, "nested": {"ok": "a"}}


def test_audio_and_tokens_dropped():
    out = redact_record(
        {
            "text": "Bearer abc.def.ghi sk-ABCDEFGHIJKLMNOPQRST eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
            "audio": b"RIFF....WAVE",
            "transcript": "voz crua",
        },
        spec={"text": "scalar"},
    )
    assert set(out) == {"text"}
    assert "abc.def" not in out["text"] and "sk-ABC" not in out["text"] and "eyJ" not in out["text"]
    # objeto não escalar em campo escalar cai (nunca é copiado)
    assert redact_record({"text": {"x": 1}}, spec={"text": "scalar"}) == {"text": None}


def test_scan_pii_detects_and_clears():
    owner = str(uuid.uuid4())
    assert "email" in scan_pii("x a@b.com")
    assert "ip" in scan_pii("from 10.0.0.12")
    assert "uuid" in scan_pii(owner)
    assert "owner_value" in scan_pii(owner.replace("-", ""), owner_values={owner})
    assert scan_pii('{"cost_usd":"0.000041550","latency_ms":8123,"sha":"' + "a1" * 32 + '"}') == []


# --- Revisão Astra: payloads adversariais que escapavam do scrubber -------------
import pytest  # noqa: E402

_ADVERSARIAL = [
    ("cpf 123.456.789-09 fim", "123.456.789"),
    ("cpf 12345678909.", "12345678909"),
    ("cnpj 12.345.678/0001-95", "345.678"),
    ("zap 11987654321 me chama", "11987654321"),
    ("cartao 4111 1111 1111 1111", "4111 1111"),
    ("cartao 4111111111111111", "4111111111111111"),
    ("ipv6 2001:db8::1 e fe80::1ff:fe23:4567:890a", "db8::1"),
    ("ipv6 ::1 local", "::1"),
    ("meu ip 192.168.0.10. fim", "192.168.0.10"),
    ("aws AKIAIOSFODNN7EXAMPLE e ASIAY34FZKBOKMUTVV7A", "IOSFODNN7"),
    ("gh ghp_abcdefghijklmnopqrstuvwxyz0123456789", "ghp_abcdef"),
    ("slack xoxb-1234-5678-abcdefghij", "abcdefghij"),
    ("db postgres://user:s3nh4@db.host/x", "s3nh4"),
    ("cookie rpg_session=abcdef123456; senha: hunter22", "hunter22"),
    ("token api_key=zz9-SECRET-zz9", "zz9-SECRET"),
]


@pytest.mark.parametrize("text,needle", _ADVERSARIAL)
def test_adversarial_pii_is_scrubbed(text, needle):
    out = scrub_text(text)
    assert needle not in out, out
    assert "[REDACTED:" in out
    assert scan_pii(out) == []
    assert scan_pii(text) != []


def test_hex_hashes_and_game_numbers_not_flagged():
    import hashlib

    for i in range(300):  # hashes hex com longas sequências de dígitos não são PII
        assert scan_pii(hashlib.sha256(str(i).encode()).hexdigest()) == []
    keep = "Às 12:30 do dia 3, 50 moedas; lore_content_123456789012345678901234; v1.2.3"
    assert scrub_text(keep) == keep
