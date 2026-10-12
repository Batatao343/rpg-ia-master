"""SPEC-186 deterministic private routing, limits, cleanup and spend gates."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import wave

import httpx
import pytest

from infrastructure.wallet import InsufficientShards
from services.speech_pricing import SPEECH_PRICING_VERSION, speech_bound, speech_event
from services.speech_to_text import (
    Candidate, HttpSpeechProvider, MAX_AUDIO_BYTES, ProviderReading, SpeechCircuit,
    SpeechError, configured_candidates, prepare_audio, transcribe_audio,
)

GROQ = Candidate('groq', 'whisper-large-v3-turbo')
OPENAI = Candidate('openai', 'gpt-4o-mini-transcribe')


def wav_bytes(seconds=1, *, rate=16000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b'\0\0' * int(seconds * rate))
    return output.getvalue()


class FakeFinance:
    def __init__(self, *, funds=True):
        self.funds = funds
        self.calls = []
        self.events = []

    def begin(self, operation, request_hash, candidates):
        if not self.funds:
            raise InsufficientShards('no funds')
        self.calls.append(('begin', operation, request_hash))

    def admit(self, ordinal, candidate):
        self.calls.append(('admit', ordinal, candidate))

    def finish(self, events, success):
        self.events = events
        self.calls.append(('finish', success))
        return 'settled' if all(e.billing_exact for e in events) else 'pending_reconciliation'


class FakeProvider:
    def __init__(self, *results):
        self.results = list(results)
        self.paths = []
        self.calls = []

    async def transcribe(self, candidate, audio):
        self.paths.append(audio)
        self.calls.append(candidate)
        assert audio.is_file()
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def run(provider, finance=None, candidates=None, payload=None):
    finance = finance or FakeFinance()
    result = asyncio.run(transcribe_audio(payload or wav_bytes(), 'audio/wav', uuid4(), finance,
                                          provider=provider, candidates=candidates or [GROQ, OPENAI],
                                          circuit=SpeechCircuit()))
    return result, finance


def test_primary_returns_ptbr_without_auto_send_or_persistence():
    provider = FakeProvider(ProviderReading(200, 'Vou até Valoria.', {}))
    result, finance = run(provider)
    assert result['text'] == 'Vou até Valoria.' and result['billing_status'] == 'settled'
    assert provider.calls == [GROQ]
    assert [c[0] for c in finance.calls] == ['begin', 'admit', 'finish']
    assert finance.events[0].category == 'speech_to_text'
    assert finance.events[0].cost_usd == Decimal('0.000111112')  # 10s minimum
    assert 'Valoria' not in repr(finance.events)
    assert all(not p.exists() and not p.parent.exists() for p in provider.paths)


def test_fallback_uses_distinct_tickets_and_sums_billable_usage_only():
    provider = FakeProvider(ProviderReading(429, None, {'provider_cost_usd': '0'}),
                            ProviderReading(200, 'Ayla em Porto.', {
                                'input_tokens': 100, 'audio_tokens': 100, 'text_tokens': 0,
                                'output_tokens': 20}))
    result, finance = run(provider)
    assert result['billing_status'] == 'settled'
    assert provider.calls == [GROQ, OPENAI]
    assert len({e.event_id for e in finance.events}) == 2
    assert sum(e.cost_usd for e in finance.events) == Decimal('0.000225000')
    assert [c[1] for c in finance.calls if c[0] == 'admit'] == [0, 1]
    assert all(not p.parent.exists() for p in provider.paths)


def test_timeout_fallback_does_not_hide_unknown_charge():
    provider = FakeProvider(httpx.ReadTimeout('sensitive provider body'),
                            ProviderReading(200, 'Texto editável.', {
                                'input_tokens': 100, 'audio_tokens': 100, 'text_tokens': 0,
                                'output_tokens': 20}))
    result, finance = run(provider)
    assert result['billing_status'] == 'pending_reconciliation'
    assert not finance.events[0].billing_exact and finance.events[1].billing_exact
    assert all(not p.exists() for p in provider.paths)


@pytest.mark.parametrize('failure', [ProviderReading(400, None, {}), ProviderReading(503, None, {}),
                                    httpx.ReadTimeout('private'), RuntimeError('private'),
                                    asyncio.CancelledError()])
def test_cleanup_on_provider_error_timeout_internal_and_cancellation(failure):
    provider = FakeProvider(failure)
    finance = FakeFinance()
    with pytest.raises((SpeechError, RuntimeError, asyncio.CancelledError)):
        run(provider, finance, [GROQ])
    assert all(not p.exists() and not p.parent.exists() for p in provider.paths)
    assert len(finance.events) == 1 and finance.calls[-1] == ('finish', False)


@pytest.mark.parametrize('payload,mime,code', [(b'bad', 'audio/wav', 'audio_invalid'),
    (wav_bytes(60.01), 'audio/wav', 'audio_duration'),
    (b'0' * (MAX_AUDIO_BYTES + 1), 'audio/wav', 'audio_bytes'),
    (wav_bytes(), 'application/octet-stream', 'audio_mime'),
    (wav_bytes()[:-100], 'audio/wav', 'audio_truncated')],
    ids=['invalid', 'duration', 'bytes', 'mime', 'truncated'])
def test_limits_before_reservation_and_provider(payload, mime, code):
    finance, provider = FakeFinance(), FakeProvider()
    with pytest.raises(SpeechError, match=code):
        asyncio.run(transcribe_audio(payload, mime, uuid4(), finance, provider=provider, candidates=[GROQ]))
    assert finance.calls == [] and provider.calls == []


def test_no_balance_means_no_provider():
    provider = FakeProvider()
    with pytest.raises(InsufficientShards):
        run(provider, FakeFinance(funds=False))
    assert provider.calls == []


def test_configurable_models_and_local_circuit(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'fake-secret')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('RPG_SPEECH_GROQ_MODEL', 'future-id')
    assert configured_candidates() == [Candidate('groq', 'future-id')]
    assert speech_bound('groq', 'future-id') is None  # no billable authorization
    circuit = SpeechCircuit()
    for _ in range(3):
        circuit.record(GROQ, False)
    assert not circuit.available(GROQ) and circuit.available(OPENAI)


def test_compressed_decoder_absence_fails_before_reserve(monkeypatch, tmp_path):
    monkeypatch.setenv('RPG_SPEECH_FFMPEG', str(tmp_path / 'absent.exe'))
    with pytest.raises(SpeechError, match='audio_decoder_unavailable'):
        prepare_audio(b'\x1aE\xdf\xa3' + b'bad', 'audio/webm', tmp_path)


def test_compressed_decode_ignores_spoofed_metadata_and_bounds_process(monkeypatch, tmp_path):
    def decode(command, **kwargs):
        assert command[1:3] == ['-nostdin', '-v']
        assert kwargs['timeout'] == 10 and 'shell' not in kwargs
        assert command[command.index('-protocol_whitelist') + 1] == 'file,pipe'
        assert command[command.index('-t') + 1] == '61'
        Path(command[-1]).write_bytes(wav_bytes(61))
    monkeypatch.setattr('services.speech_to_text.subprocess.run', decode)
    with pytest.raises(SpeechError, match='audio_duration'):
        prepare_audio(b'\x1aE\xdf\xa3' + b'fake-duration=1', 'audio/webm', tmp_path)


def test_openai_duration_or_invalid_counters_never_become_exact():
    for usage in ({'type': 'duration', 'seconds': 1},
                  {'input_tokens': True, 'output_tokens': 10},
                  {'input_tokens': 16001, 'audio_tokens': 16001, 'text_tokens': 0, 'output_tokens': 1}):
        event = speech_event(uuid4(), 0, OPENAI.provider, OPENAI.model, 'success', usage)
        assert not event.billing_exact and event.cost_basis == 'estimated'
    event = speech_event(uuid4(), 0, OPENAI.provider, OPENAI.model, 'success', {
        'input_tokens': 100, 'audio_tokens': 99, 'text_tokens': 1, 'output_tokens': 20})
    assert not event.billing_exact


def test_http_adapter_bounds_and_redacts_response(monkeypatch):
    import json
    captured = {}
    def respond(request):
        captured['url'] = str(request.url)
        assert b'recording.wav' in request.content
        assert b'name="chunking_strategy"' not in request.content
        assert b'name="prompt"' not in request.content
        assert b'name="stream"' not in request.content
        return httpx.Response(200, json={'text': 'Frase privada', 'usage': {
            'input_tokens': 14, 'output_tokens': 45,
            'input_token_details': {'audio_tokens': 14, 'text_tokens': 0},
            'secret': 'must not persist'}, 'other': 'discard'})
    real_client = httpx.AsyncClient
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    provider = HttpSpeechProvider()
    result, finance = run(provider, candidates=[OPENAI])
    assert result['text'] == 'Frase privada'
    assert finance.events[0].cost_usd == Decimal('0.000242500')
    assert captured['url'] == 'https://api.openai.com/v1/audio/transcriptions'
    assert 'Frase privada' not in json.dumps(finance.events[0].__dict__, default=str)


def test_original_wav_extra_chunks_never_reach_provider(tmp_path):
    payload = wav_bytes() + b'private-metadata-and-second-data-chunk'
    audio, duration = prepare_audio(payload, 'audio/wav', tmp_path)
    assert duration == 1 and audio.read_bytes() == wav_bytes()


@pytest.mark.parametrize('extension,codec,mime', [('webm', 'libopus', 'audio/webm'),
    ('ogg', 'libopus', 'audio/ogg'), ('mp4', 'aac', 'audio/mp4')])
def test_real_decoder_browser_media_round_trip(tmp_path, extension, codec, mime):
    import shutil
    import subprocess
    import os
    decoder = os.getenv('RPG_SPEECH_FFMPEG') or shutil.which('ffmpeg')
    if decoder is None:
        pytest.skip('ffmpeg absent; service fails closed for compressed formats')
    source, encoded = tmp_path / 'source.wav', tmp_path / f'recorded.{extension}'
    source.write_bytes(wav_bytes())
    subprocess.run([decoder, '-nostdin', '-v', 'error', '-i', str(source), '-c:a', codec, str(encoded)],
                   check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    audio, duration = prepare_audio(encoded.read_bytes(), mime, tmp_path)
    assert audio.is_file() and Decimal('0.9') <= duration <= Decimal('1.2')
    with wave.open(str(audio), 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getframerate() == 16000


def test_oversized_provider_response_falls_back_without_body_leak(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setenv('GROQ_API_KEY', 'fake-key')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=b'private' * 20000))))
    finance = FakeFinance()
    with pytest.raises(SpeechError, match='speech_provider_failed') as failure:
        run(HttpSpeechProvider(), finance, [GROQ])
    assert 'private' not in str(failure.value)
    assert not finance.events[0].billing_exact


def test_cancelled_wait_removes_audio_and_records_ticket():
    finance, provider = FakeFinance(), FakeProvider()
    async def wait_then_cancel(candidate, audio):
        provider.paths.append(audio)
        await asyncio.sleep(60)
    provider.transcribe = wait_then_cancel
    async def cancel():
        task = asyncio.create_task(transcribe_audio(wav_bytes(), 'audio/wav', uuid4(), finance,
                                                     provider=provider, candidates=[GROQ]))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancel())
    assert len(finance.events) == 1 and finance.calls[-1] == ('finish', False)
    assert all(not p.parent.exists() for p in provider.paths)


def test_decoder_timeout_removes_all_temporary_files_before_finance(monkeypatch):
    import subprocess
    paths = []
    def timeout(command, **kwargs):
        paths.append(Path(command[-1]).parent)
        raise subprocess.TimeoutExpired(command[0], 10)
    monkeypatch.setattr('services.speech_to_text.subprocess.run', timeout)
    finance, provider = FakeFinance(), FakeProvider()
    with pytest.raises(SpeechError, match='audio_invalid'):
        asyncio.run(transcribe_audio(b'\x1aE\xdf\xa3bad', 'audio/webm', uuid4(), finance,
                                      provider=provider, candidates=[GROQ]))
    assert all(not p.exists() for p in paths) and finance.calls == [] and provider.calls == []


def test_financial_finish_failure_still_removes_files():
    finance = FakeFinance()
    def fail(*args):
        raise RuntimeError('usage ledger unavailable')
    finance.finish = fail
    provider = FakeProvider(ProviderReading(200, 'Texto', {}))
    with pytest.raises(RuntimeError):
        run(provider, finance, [GROQ])
    assert all(not p.parent.exists() for p in provider.paths)


def test_groq_adapter_response_and_duration_usage_are_private(monkeypatch):
    real_client = httpx.AsyncClient
    def respond(request):
        assert str(request.url) == 'https://api.groq.com/openai/v1/audio/transcriptions'
        assert b'verbose_json' in request.content
        assert b'name="prompt"' not in request.content
        return httpx.Response(200, json={'text': 'Vou a Valoria', 'duration': 1,
                                        'segments': [{'text': 'must discard'}],
                                        'usage': {'type': 'duration', 'seconds': 1}})
    monkeypatch.setenv('GROQ_API_KEY', 'fake-key')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    result, finance = run(HttpSpeechProvider(), candidates=[GROQ])
    assert result['text'] == 'Vou a Valoria' and finance.events[0].audio_units == 1000
    assert finance.events[0].cost_usd == Decimal('0.000111112')


def test_quote_accepts_only_registered_exact_speech_card():
    from dataclasses import replace
    from services.shard_pricing import PricingUnavailable, quote_usage
    event = speech_event(uuid4(), 0, GROQ.provider, GROQ.model, 'success', {}, duration=Decimal('1'))
    version = SimpleNamespace(version_id='test', fx_usd_brl=Decimal('5'),
                              fx_buffer_rate=Decimal('0.1'), shard_budget_unit_brl=Decimal('0.03'))
    assert event.pricing_version == SPEECH_PRICING_VERSION
    assert quote_usage([event], version, at=datetime.now(timezone.utc), authorized_snapshot=True).shard_milli_debited == 1
    with pytest.raises(PricingUnavailable):
        quote_usage([replace(event, pricing_version='unregistered')], version,
                    at=datetime.now(timezone.utc), authorized_snapshot=True)
