"""Real Postgres wallet/usage/replay/owner tests with fake STT providers; all facts roll back."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import io
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import wave

import httpx
import pytest

from infrastructure.account_read_model import PostgresAccountReader
from infrastructure.contracts import Conflict, Principal
from infrastructure.postgres_turns import PostgresTurnCoordinator
from infrastructure.speech_finance import PostgresSpeechFinance
from infrastructure.wallet import InsufficientShards, UncertainEffect, WalletConflict
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from tests.fakes.local_pricing import installed_card_max_age_seconds
from services.speech_to_text import Candidate, ProviderReading, SpeechCircuit, transcribe_audio
from services.usage_metering import RATE_CARD_VERSION

pytestmark = pytest.mark.infra_local
AT = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
GROQ = Candidate('groq', 'whisper-large-v3-turbo')
OPENAI = Candidate('openai', 'gpt-4o-mini-transcribe')


@pytest.fixture
def finance_case(monkeypatch):
    psycopg = pytest.importorskip('psycopg')
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv('RPG_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('RPG_TEST_DATABASE_URL absent')
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        try:
            if connection.execute("select to_regclass('app.wallet_accounts') as t").fetchone()['t'] is None:
                pytest.skip('SPEC184 migration absent')
            connection.execute(Path('supabase/migrations/20261012120000_speech_operations.sql').read_text(encoding='utf-8'))
            class Pool:
                def connection(self):
                    from contextlib import nullcontext
                    return nullcontext(connection)
            pool = Pool()
            runtime = SimpleNamespace(game_store=SimpleNamespace(pool=pool),
                                      turn_coordinator=PostgresTurnCoordinator(pool))
            owner = Principal(uuid4(), 'test', 'owner')
            version = 'speech-test-' + str(uuid4())
            connection.execute("""insert into app.pricing_versions
              (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
               fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
               rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
              values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,%s,%s)""",
               (version, AT, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                INSTALLED_RATE_CARD_OBSERVED_AT, installed_card_max_age_seconds(),
                Jsonb({'web': {'percentage': '0.04', 'fixed_brl': '0.20'}})))
            monkeypatch.setenv('RPG_SPEECH_PRICING_VERSION', version)
            finance = PostgresSpeechFinance(runtime, owner, at=AT)
            finance.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=1000,
                                       actor_id=uuid4(), reason='deterministic local fixture')
            yield finance, runtime, owner, connection
        finally:
            connection.rollback()


class Provider:
    def __init__(self, *readings):
        self.readings, self.calls, self.paths = list(readings), [], []
    async def transcribe(self, candidate, path):
        self.calls.append(candidate)
        self.paths.append(path)
        result = self.readings.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def execute(finance, provider, operation=None, candidates=None):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 16000)
    return asyncio.run(transcribe_audio(output.getvalue(), 'audio/wav', operation or uuid4(), finance,
                                      provider=provider, candidates=candidates or [GROQ, OPENAI],
                                      circuit=SpeechCircuit()))


def test_exact_primary_round_trip_and_owner_scoped_voice_dashboard(finance_case):
    finance, runtime, owner, db = finance_case
    op = uuid4()
    provider = Provider(ProviderReading(200, 'Nome Valoria privado', {}))
    result = execute(finance, provider, op)
    assert result['billing_status'] == 'settled'
    assert finance.wallet.balance(owner).reserved_milli == 0
    assert finance.wallet.balance(owner).available_milli == 999
    record = db.execute('select * from app.operations where id=%s', (op,)).fetchone()
    assert record['kind'] == 'speech_to_text' and record['game_id'] is None
    assert record['receipt'] == {'kind': 'speech_to_text', 'result_retained': False}
    assert 'Valoria' not in str(record)
    saved = db.execute('select * from app.usage_events where operation_id=%s', (op,)).fetchall()
    assert len(saved) == 1 and saved[0]['cost_usd'] == Decimal('0.000111112')
    reader = PostgresAccountReader(runtime.game_store.pool)
    assert reader.usage(owner)['items'][0]['category'] == 'voice'
    assert reader.series(owner, '24h')['totals']['voice'] == '1'
    other = Principal(uuid4(), 'test', 'other')
    assert reader.usage(other)['items'] == [] and reader.series(other, '24h')['totals']['voice'] == '0'
    assert finance.wallet.balance(other).available_milli == 0
    with pytest.raises(WalletConflict):
        finance.wallet.release_pre_effect(other, finance.reservation.reservation_id,
                                         fence_token=finance.claim.lease_token)
    assert all(not p.parent.exists() for p in provider.paths)


def test_billable_fallback_is_summed_once_and_replay_dispatches_zero(finance_case):
    finance, runtime, owner, db = finance_case
    op = uuid4()
    provider = Provider(ProviderReading(200, ' ' * 8001, {}), ProviderReading(200, 'Ayla', {
        'input_tokens': 100, 'audio_tokens': 100, 'text_tokens': 0, 'output_tokens': 20}))
    assert execute(finance, provider, op)['billing_status'] == 'settled'
    events = db.execute('select * from app.usage_events where operation_id=%s', (op,)).fetchall()
    assert len(events) == 2 and sum(e['cost_usd'] for e in events) == Decimal('0.000336112')
    first = finance.wallet.settle_usage(owner, finance.reservation.reservation_id,
                                      fence_token=finance.claim.lease_token,
                                      usage_event_ids=[e['event_id'] for e in events], at=AT)
    assert first.settled_milli == 1 and finance.wallet.balance(owner).available_milli == 999
    replay = Provider()
    with pytest.raises(Conflict):
        execute(PostgresSpeechFinance(runtime, owner, at=AT), replay, op)
    assert replay.calls == []
    other = Principal(uuid4(), 'test', 'other')
    PostgresSpeechFinance(runtime, other, at=AT).wallet.adjust_admin(
        other, adjustment_id=str(uuid4()), signed_milli=1000, actor_id=uuid4(), reason='test')
    with pytest.raises(Conflict):
        execute(PostgresSpeechFinance(runtime, other, at=AT), replay, op)
    assert replay.calls == []


def test_unknown_timeout_preserves_hold_and_retry_cannot_dispatch(finance_case):
    finance, runtime, owner, db = finance_case
    op = uuid4()
    provider = Provider(httpx.ReadTimeout('private body'), ProviderReading(200, 'Editável', {
        'type': 'duration', 'seconds': 1}))
    assert execute(finance, provider, op)['billing_status'] == 'pending_reconciliation'
    assert finance.wallet.balance(owner).reserved_milli > 0
    assert db.execute('select status from app.wallet_reservations where reservation_id=%s',
                      (finance.reservation.reservation_id,)).fetchone()['status'] == 'uncertain'
    assert len(db.execute('select * from app.wallet_settled_usage where owner_id=%s',
                          (owner.user_id,)).fetchall()) == 0
    replay = Provider()
    with pytest.raises(Conflict):
        execute(PostgresSpeechFinance(runtime, owner, at=AT), replay, op)
    assert replay.calls == []


def test_insufficient_funds_and_explicit_ceiling_prevent_provider(finance_case, monkeypatch):
    finance, _, owner, _ = finance_case
    finance.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=-1000,
                               actor_id=uuid4(), reason='test no funds')
    provider = Provider()
    with pytest.raises(InsufficientShards):
        execute(finance, provider)
    assert provider.calls == [] and finance.wallet.balance(owner).reserved_milli == 0
    monkeypatch.setenv('RPG_SPEECH_MAX_RESERVE_MILLI', '1')
    from services.speech_to_text import SpeechError
    with pytest.raises(SpeechError, match='speech_spend_ceiling'):
        execute(finance, provider)
    assert provider.calls == []


def test_cancelled_attempt_is_durable_and_fenced_without_transcript(finance_case):
    finance, runtime, owner, db = finance_case
    op = uuid4()
    provider = Provider(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        execute(finance, provider, op, [GROQ])
    assert finance.wallet.balance(owner).reserved_milli == 1
    assert db.execute('select status from app.operations where id=%s', (op,)).fetchone()['status'] == 'failed'
    assert db.execute('select billing_exact from app.usage_events where operation_id=%s', (op,)).fetchone()['billing_exact'] is False
    replay = Provider()
    with pytest.raises((WalletConflict, UncertainEffect)):
        execute(PostgresSpeechFinance(runtime, owner, at=AT), replay, op, [GROQ])
    assert replay.calls == [] and all(not p.parent.exists() for p in provider.paths)


def test_settlement_failure_after_durable_usage_recovers_hold(finance_case, monkeypatch):
    finance, _, owner, db = finance_case
    def fail(*args, **kwargs):
        raise RuntimeError('settlement connection down')
    monkeypatch.setattr(finance.wallet, 'settle_usage', fail)
    assert execute(finance, Provider(ProviderReading(200, 'Texto', {})))['billing_status'] == 'pending_reconciliation'
    assert finance.wallet.balance(owner).reserved_milli > 0
    assert db.execute('select status from app.wallet_reservations where reservation_id=%s',
                      (finance.reservation.reservation_id,)).fetchone()['status'] == 'uncertain'
    assert db.execute('select count(*) as n from app.usage_events where owner_id=%s',
                      (owner.user_id,)).fetchone()['n'] == 1
