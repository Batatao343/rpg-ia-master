"""STT HTTP boundary: authenticated owner, CSRF, own limiter and raw upload cap."""
from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4
import wave

from fastapi.testclient import TestClient
import pytest

import api
from infrastructure.contracts import Principal, Unauthorized
from services.auth_sessions import CsrfSigner
from services.speech_to_text import Candidate, MAX_AUDIO_BYTES, ProviderReading


@pytest.fixture
def speech_client(monkeypatch):
    owner = uuid4()
    principal = Principal(owner, 'test', str(owner))
    calls, rate_calls = [], []
    secret = 'a' * 64
    csrf = CsrfSigner(secret).issue()
    monkeypatch.setenv('RPG_SESSION_SECRET', secret)
    monkeypatch.setenv('RPG_SPEECH_ENABLED', '1')
    monkeypatch.setattr(api, '_database_profile', lambda: True)
    def verify(cookie):
        if cookie != 'valid':
            raise Unauthorized('session absent')
        return principal
    def consume(key, **kwargs):
        rate_calls.append((key, kwargs))
        return SimpleNamespace(allowed=True, retry_after_seconds=60)
    runtime = SimpleNamespace(identity_verifier=SimpleNamespace(verify=verify),
                              rate_limiter=SimpleNamespace(consume=consume))
    monkeypatch.setattr('infrastructure.runtime.get_runtime', lambda: runtime)
    class Finance:
        def __init__(self, runtime_arg, principal_arg):
            assert runtime_arg is runtime and principal_arg.user_id == owner
        def begin(self, *args):
            calls.append('begin')
        def admit(self, *args):
            calls.append('admit')
        def finish(self, *args):
            calls.append('finish')
            return 'settled'
    monkeypatch.setattr('infrastructure.speech_finance.PostgresSpeechFinance', Finance)
    monkeypatch.setattr('services.speech_to_text.configured_candidates', lambda: [
        Candidate('groq', 'whisper-large-v3-turbo')])
    async def transcribe(*args):
        calls.append('provider')
        return ProviderReading(200, 'Posso editar antes de enviar.', {})
    monkeypatch.setattr('services.speech_to_text.HttpSpeechProvider.transcribe', transcribe)
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0\0' * 16000)
    client = TestClient(api.app)
    client.cookies.set('rpg_access', 'valid')
    client.cookies.set('rpg_csrf', csrf)
    headers = {'content-type': 'audio/wav', 'origin': 'http://localhost:5173',
               'x-csrf-token': csrf, 'x-operation-id': str(uuid4())}
    return client, headers, output.getvalue(), calls, rate_calls, runtime, owner


def test_authenticated_transcription_requires_explicit_game_send(speech_client, monkeypatch):
    client, headers, payload, calls, rate_calls, _, owner = speech_client
    monkeypatch.setattr(api.game_graph, 'invoke', lambda *_a: pytest.fail('must not call game'))
    # SPEC-200: POST /game/action executa via stream — guardar os dois modos.
    monkeypatch.setattr(api.game_graph, 'stream', lambda *_a, **_k: pytest.fail('must not call game'))
    response = client.post('/account/transcriptions?owner_id=other', headers=headers, content=payload)
    assert response.status_code == 200
    assert response.json()['text'] == 'Posso editar antes de enviar.'
    assert response.headers['cache-control'] == 'no-store'
    assert calls == ['begin', 'admit', 'provider', 'finish']
    assert rate_calls == [(f'speech:{owner}', {'limit': 5, 'window_seconds': 60})]


def test_session_and_csrf_precede_audio_processing(speech_client):
    client, headers, payload, calls, *_ = speech_client
    client.cookies.clear()
    assert client.post('/account/transcriptions', headers=headers, content=payload).status_code == 401
    client.cookies.set('rpg_access', 'valid')
    assert client.post('/account/transcriptions', headers=headers, content=payload).status_code == 403  # SPEC-220 R10
    assert calls == []


@pytest.mark.parametrize('header_patch,content,status', [
    ({'content-type': 'text/plain'}, b'bad', 415),
    ({'content-length': str(MAX_AUDIO_BYTES + 1)}, b'bad', 413),
    ({'x-operation-id': 'not-uuid'}, b'bad', 422),
    ({}, b'bad', 422),
], ids=['mime', 'declared_bytes', 'operation', 'invalid_audio'])
def test_request_limits_precede_financial_or_network_effects(speech_client, header_patch, content, status):
    client, headers, _, calls, *_ = speech_client
    assert client.post('/account/transcriptions', headers=headers | header_patch, content=content).status_code == status
    assert calls == []


def test_chunked_body_is_bounded_before_reservation(speech_client):
    client, headers, _, calls, *_ = speech_client
    def chunks():
        yield b'1' * (MAX_AUDIO_BYTES // 2)
        yield b'2' * (MAX_AUDIO_BYTES // 2 + 1)
    response = client.post('/account/transcriptions', headers=headers, content=chunks())
    assert response.status_code == 413 and calls == []


def test_voice_limiter_and_disabled_mode_make_zero_provider_calls(speech_client, monkeypatch):
    client, headers, payload, calls, _, runtime, _ = speech_client
    runtime.rate_limiter.consume = lambda *_a, **_kw: SimpleNamespace(allowed=False, retry_after_seconds=17)
    response = client.post('/account/transcriptions', headers=headers, content=payload)
    assert response.status_code == 429 and response.headers['retry-after'] == '17'
    monkeypatch.setenv('RPG_SPEECH_ENABLED', '0')
    assert client.post('/account/transcriptions', headers=headers, content=payload).status_code == 503
    assert calls == []


def test_internal_error_does_not_expose_transcript_or_provider_body(speech_client, monkeypatch):
    client, headers, payload, _, *_ = speech_client
    async def fail(*args):
        raise RuntimeError('secret-key recording filename transcript private')
    monkeypatch.setattr('services.speech_to_text.HttpSpeechProvider.transcribe', fail)
    response = client.post('/account/transcriptions', headers=headers, content=payload)
    assert response.status_code == 503 and {k: v for k, v in response.json().items() if k != 'request_id'} == {'detail': 'speech_internal_error'}
