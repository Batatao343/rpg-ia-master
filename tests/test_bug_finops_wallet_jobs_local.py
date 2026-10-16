"""SPEC-236 real-Postgres repros (Supabase local). Every fixture rolls back what it creates."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal
import io
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import wave

import pytest

from infrastructure.contracts import JobRequest, Principal
from infrastructure.postgres_turns import PostgresTurnCoordinator
from infrastructure.speech_finance import PostgresSpeechFinance
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.speech_to_text import Candidate, ProviderReading, SpeechCircuit, transcribe_audio
from services.usage_metering import RATE_CARD_VERSION, normalize_attempts

pytestmark = pytest.mark.infra_local
AT = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
GROQ = Candidate("groq", "whisper-large-v3-turbo")
OPENAI = Candidate("openai", "gpt-4o-mini-transcribe")
MIGRATION = Path("supabase/migrations/20261016100000_usage_counts_as_spend.sql")


@pytest.fixture
def db_case(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        try:
            if connection.execute("select to_regclass('app.wallet_accounts') as t").fetchone()["t"] is None:
                pytest.skip("SPEC-184 migration absent")
            connection.execute(MIGRATION.read_text(encoding="utf-8"))

            class Pool:
                def connection(self):
                    return nullcontext(connection)
            pool = Pool()
            runtime = SimpleNamespace(game_store=SimpleNamespace(pool=pool),
                                      turn_coordinator=PostgresTurnCoordinator(pool))
            owner = Principal(uuid4(), "test", "owner")
            version = "spec236-" + str(uuid4())
            connection.execute("""insert into app.pricing_versions
              (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
               fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
               rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
              values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,864000,%s)""",
               (version, AT, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                INSTALLED_RATE_CARD_OBSERVED_AT,
                Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
            monkeypatch.setenv("RPG_SPEECH_PRICING_VERSION", version)
            finance = PostgresSpeechFinance(runtime, owner, at=AT)
            finance.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=1000,
                                        actor_id=uuid4(), reason="spec236 rolled back fixture")
            yield SimpleNamespace(db=connection, pool=pool, runtime=runtime, owner=owner,
                                  version=version, finance=finance, wallet=finance.wallet)
        finally:
            connection.rollback()


def _wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(bytes(2) * 16000)
    return output.getvalue()


class Provider:
    def __init__(self, *readings):
        self.readings = list(readings)

    async def transcribe(self, candidate, path):
        result = self.readings.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _entries(c, kind: str) -> list[dict]:
    return c.db.execute("select * from app.wallet_entries where owner_id=%s and entry_type=%s",
                        (c.owner.user_id, kind)).fetchall()


def _ledger(c) -> tuple[int, int]:
    row = c.db.execute("select coalesce(sum(available_delta),0) a,coalesce(sum(reserved_delta),0) r "
                       "from app.wallet_entries where owner_id=%s", (c.owner.user_id,)).fetchone()
    return int(row["a"]), int(row["r"])


def _operation(c, status: str = "abandoned", kind: str = "speech_to_text"):
    op = uuid4()
    c.db.execute("insert into app.operations(id,owner_id,kind,status,request_sha256) "
                 "values (%s,%s,%s,%s,%s)", (op, c.owner.user_id, kind, status, "c" * 64))
    return op


def _age_reservation(c, reservation_id) -> None:
    c.db.execute("update app.wallet_reservations set created_at=now()-interval '2 hours' "
                 "where reservation_id=%s", (reservation_id,))


# --- migration ------------------------------------------------------------------------------
def test_migration_is_idempotent_and_backfills_legacy_phantom_cost(db_case):
    c = db_case
    c.db.execute(MIGRATION.read_text(encoding="utf-8"))  # second application in the same tx
    op = _operation(c, "failed", "turn")
    c.db.execute("""insert into app.usage_events
        (event_id,operation_id,owner_id,component,attempt_ordinal,category,provider,model,outcome,
         cost_usd,cost_basis,pricing_version,billing_exact,event_sha256)
        values (%s,%s,%s,'llm',0,'llm','deepseek','m','invoke_error',1.0,'estimated',
                'unknown-conservative-v1',false,%s)""", (uuid4(), op, c.owner.user_id, "d" * 64))
    c.db.execute(MIGRATION.read_text(encoding="utf-8"))  # backfill takes the legacy row out
    row = c.db.execute("select counts_as_spend,cost_usd from app.usage_events where operation_id=%s",
                       (op,)).fetchone()
    assert row["counts_as_spend"] is False and row["cost_usd"] == Decimal("1.0")  # fact kept
    with pytest.raises(Exception), c.db.transaction():  # a no-spend basis can never carry cost
        c.db.execute("""insert into app.usage_events
            (event_id,operation_id,owner_id,component,attempt_ordinal,category,provider,model,
             outcome,cost_usd,cost_basis,pricing_version,billing_exact,event_sha256,counts_as_spend)
            values (%s,%s,%s,'llm',1,'llm','deepseek','m','invoke_error',0.5,'failed_no_usage',
                    'failed-no-usage-v1',false,%s,false)""", (uuid4(), op, c.owner.user_id, "e" * 64))


def test_failed_attempt_is_persisted_at_zero_outside_turn_cost(db_case):
    from infrastructure.usage_events import append_usage_events
    c = db_case
    op = _operation(c, "running", "turn")
    events = normalize_attempts([
        {"provider": "deepseek", "model": "deepseek-v4-flash", "outcome": "invoke_error",
         "network_attempted": True, "usage": None},
        {"provider": "groq", "model": "openai/gpt-oss-120b", "outcome": "success",
         "network_attempted": True, "usage": {"input_tokens": 1000, "output_tokens": 300}},
    ], operation_id=op)
    append_usage_events(c.db, owner_id=c.owner.user_id, operation_id=op, game_id=None, events=events)
    append_usage_events(c.db, owner_id=c.owner.user_id, operation_id=op, game_id=None, events=events)
    rows = c.db.execute("select provider,cost_usd,counts_as_spend,cost_basis from app.usage_events "
                        "where operation_id=%s order by attempt_ordinal", (op,)).fetchall()
    assert [(r["cost_usd"], r["counts_as_spend"]) for r in rows] == [
        (Decimal("0"), False), (Decimal("0.000330000"), True)]
    from infrastructure.finops_reader import PostgresFinopsReader
    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    until = datetime(2100, 1, 1, tzinfo=timezone.utc)
    mine = [g for g in PostgresFinopsReader(c.pool).usage_groups(since, until)
            if g.provider == "deepseek" and g.cost_basis == "failed_no_usage"]
    assert mine and all(g.cost_usd == 0 and not g.counts_as_spend for g in mine)


# --- R4 -------------------------------------------------------------------------------------
def test_cron_recovers_orphan_reservation(db_case):
    from services.wallet_recovery import recover_wallet_reservations
    c = db_case
    op = _operation(c)  # the function died between reserve and finish; the op was abandoned
    reservation = c.wallet.reserve(c.owner, reference_type="speech_to_text", reference_id=str(op),
                                   pricing_version_id=c.version, ceiling_milli=7,
                                   fence_token=uuid4(), usage_operation_id=op, at=AT)
    assert c.wallet.balance(c.owner).available_milli == 993
    fresh = recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)
    assert fresh["wallet_seen"] == 0  # grace period: never races a request still finishing
    _age_reservation(c, reservation.reservation_id)
    result = recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)
    assert result["wallet_released"] == 1 and result["wallet_errors"] == 0
    assert c.wallet.balance(c.owner).available_milli == 1000
    assert c.wallet.balance(c.owner).reserved_milli == 0
    releases = _entries(c, "release")
    assert len(releases) == 1 and releases[0]["reason"] == "recovery_pre_dispatch"
    again = recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)
    assert again["wallet_seen"] == 0 and len(_entries(c, "release")) == 1  # idempotent
    assert _ledger(c) == (1000, 0)


def test_cron_settles_exact_usage_and_holds_unknown(db_case):
    from infrastructure.usage_events import append_usage_events
    from services.wallet_recovery import recover_wallet_reservations
    c = db_case
    results = {}
    for name, usage in (("exact", {"input_tokens": 1000, "output_tokens": 300}), ("unknown", None)):
        op = _operation(c, "completed", "turn")
        reservation = c.wallet.reserve(c.owner, reference_type="operation", reference_id=str(op),
                                       pricing_version_id=c.version, ceiling_milli=20,
                                       fence_token=uuid4(), usage_operation_id=op, at=AT)
        c.wallet.admit_attempt(c.owner, reservation.reservation_id,
                               fence_token=reservation.fence_token, attempt_key="a1",
                               provider="groq", model="openai/gpt-oss-120b", at=AT)
        events = normalize_attempts([{"provider": "groq", "model": "openai/gpt-oss-120b",
                                      "outcome": "success" if usage else "invoke_error",
                                      "network_attempted": True, "usage": usage}], operation_id=op)
        append_usage_events(c.db, owner_id=c.owner.user_id, operation_id=op, game_id=None,
                            events=events)
        _age_reservation(c, reservation.reservation_id)
        results[name] = reservation.reservation_id
    out = recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)
    assert out["wallet_settled"] == 1 and out["wallet_uncertain"] == 1 and out["wallet_errors"] == 0
    status = {name: c.db.execute("select status,settled_milli from app.wallet_reservations "
                                 "where reservation_id=%s", (rid,)).fetchone()
              for name, rid in results.items()}
    assert status["exact"]["status"] == "settled" and status["exact"]["settled_milli"] >= 1
    assert status["unknown"]["status"] == "uncertain"
    from infrastructure.finops_reader import PostgresFinopsReader
    held, age, _ = PostgresFinopsReader(c.pool).wallet_holds(datetime.now(timezone.utc))
    assert held >= 1 and age > 0
    assert _ledger(c) == (c.wallet.balance(c.owner).available_milli,
                          c.wallet.balance(c.owner).reserved_milli)


# --- R5 -------------------------------------------------------------------------------------
def test_stt_definitive_failure_releases(db_case):
    c = db_case
    op = uuid4()
    provider = Provider(ProviderReading(429, None, {}),
                        ProviderReading(200, "Ayla", {"input_tokens": 100, "audio_tokens": 100,
                                                      "text_tokens": 0, "output_tokens": 20}))
    result = asyncio.run(transcribe_audio(_wav(), "audio/wav", op, c.finance, provider=provider,
                                          candidates=[GROQ, OPENAI], circuit=SpeechCircuit()))
    assert result["billing_status"] == "settled"
    assert c.wallet.balance(c.owner).reserved_milli == 0
    events = c.db.execute("select provider,cost_usd,cost_basis,counts_as_spend from app.usage_events "
                          "where operation_id=%s order by attempt_ordinal", (op,)).fetchall()
    assert [(e["provider"], e["cost_basis"], e["counts_as_spend"]) for e in events] == [
        ("groq", "definitive_no_charge", False), ("openai", "rate_card", True)]
    assert events[0]["cost_usd"] == 0
    settled = _entries(c, "settle")
    assert len(settled) == 1 and int(settled[0]["amount_milli"]) == 1  # only OpenAI's exact cost
    assert c.wallet.balance(c.owner).available_milli == 999
    assert _ledger(c) == (999, 0)


def test_stt_timeout_stays_held_until_operator_reconciles(db_case):
    import httpx
    c = db_case
    op = uuid4()
    provider = Provider(httpx.ReadTimeout("x"),
                        ProviderReading(200, "Ayla", {"input_tokens": 100, "audio_tokens": 100,
                                                      "text_tokens": 0, "output_tokens": 20}))
    result = asyncio.run(transcribe_audio(_wav(), "audio/wav", op, c.finance, provider=provider,
                                          candidates=[GROQ, OPENAI], circuit=SpeechCircuit()))
    assert result["billing_status"] == "pending_reconciliation"
    row = c.db.execute("select * from app.wallet_reservations where reservation_id=%s",
                       (c.finance.reservation.reservation_id,)).fetchone()
    assert row["status"] == "uncertain" and c.wallet.balance(c.owner).reserved_milli > 0
    from scripts import admin_wallet_reconcile as cli
    args = cli.build_parser().parse_args([
        "--owner", str(c.owner.user_id), "--reservation", str(row["reservation_id"]),
        "--actor", str(uuid4()), "--evidence", "groq-case-123"])
    preview = cli.run(args, c.runtime)
    assert preview["mode"] == "dry-run" and preview["unknown_events"] == 1
    assert c.wallet.balance(c.owner).reserved_milli > 0  # dry-run writes nothing
    args = cli.build_parser().parse_args([
        "--owner", str(c.owner.user_id), "--reservation", str(row["reservation_id"]),
        "--actor", str(uuid4()), "--evidence", "groq-case-123", "--apply",
        "--confirm-owner", str(c.owner.user_id)])
    done = cli.run(args, c.runtime)
    # the timed-out attempt is waived by proof; OpenAI's exact usage is still debited
    assert done["status_after"] == "settled" and done["settled_milli"] == 1
    assert c.wallet.balance(c.owner).reserved_milli == 0
    assert c.wallet.balance(c.owner).available_milli == 999 and _ledger(c) == (999, 0)


# --- R6 -------------------------------------------------------------------------------------
def test_partial_refund_before_checkout_still_credits(db_case):
    import hashlib
    from infrastructure.stripe_payments import StripePayments
    from services.stripe_checkout import StripeSettings
    c = db_case
    if c.db.execute("select to_regclass('app.payment_orders') t").fetchone()["t"] is None:
        pytest.skip("SPEC-189 migration absent")
    sku = "spec236-" + str(uuid4())
    c.db.execute("""insert into app.purchase_skus
        (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
        values (%s,%s,'web',%s,10.50,311)""", (sku, c.version, sku))

    class FakeStripe:
        def create_session(self, order_id, **kwargs):
            return {"id": "cs_test_" + order_id, "livemode": False,
                    "url": "https://checkout.stripe.com/c/pay/test_" + order_id}

        def payment_economics(self, _intent):
            return None
    settings = StripeSettings("sk_test_fixture", "whsec_fixture", "https://game.example", (sku,))
    owner = Principal(uuid4(), "test", "buyer")
    repo = StripePayments(c.pool, settings, FakeStripe(), at=AT)
    order = repo.checkout(owner, sku, uuid4())
    oid = order["order_id"]

    def deliver(kind, obj):
        item = {"id": "evt_" + str(uuid4()), "type": kind, "created": 1791892800,
                "livemode": False, "data": {"object": obj}}
        return repo.accept_event(item, body_sha256=hashlib.sha256(str(item).encode()).hexdigest())
    # 1% partial refund delivered BEFORE the paid Checkout (webhook backlog resumed out of order)
    deliver("charge.refunded", {"id": "ch_" + oid, "metadata": {}, "payment_intent": "pi_" + oid,
                                "currency": "brl", "amount": 1050, "amount_refunded": 10})
    deliver("checkout.session.completed", {
        "id": "cs_test_" + oid, "metadata": {"order_id": oid}, "mode": "payment",
        "payment_status": "paid", "amount_total": 1050, "currency": "brl",
        "payment_intent": "pi_" + oid})
    assert repo.order(owner, oid)["status"] == "paid"
    purchase = c.db.execute("select amount_milli from app.wallet_entries where owner_id=%s "
                            "and entry_type='purchase'", (owner.user_id,)).fetchone()
    assert int(purchase["amount_milli"]) == 311  # full credit
    claw = c.db.execute("select coalesce(sum(amount_milli),0) n from app.wallet_entries "
                        "where owner_id=%s and entry_type='clawback'", (owner.user_id,)).fetchone()
    assert int(claw["n"]) == 2  # floor(10/1050 * 311) = 2, proportional and auditable
    assert repo.wallet.balance(owner).available_milli == 309
    outcome = c.db.execute("select outcome from app.payment_financial_events f join app.payment_orders o "
                           "using(order_id) where o.owner_id=%s and f.kind='refund'",
                           (owner.user_id,)).fetchone()["outcome"]
    assert outcome == "pending_partial_refund"


# --- R9 -------------------------------------------------------------------------------------
def test_expired_lease_respects_max_attempts(db_case):
    from infrastructure.postgres_jobs import PostgresJobQueue
    c = db_case
    queue = PostgresJobQueue(c.pool, lease_seconds=30)
    kind = "spec236_poison_" + uuid4().hex[:8]
    job_id = queue.enqueue(JobRequest(kind, "k", {}, max_attempts=3))
    for attempt in (1, 2, 3):
        leased = queue.lease("w", {kind}, 1)
        assert [j.attempt for j in leased] == [attempt]
        # the handler kills its process: the lease simply expires
        c.db.execute("update app.jobs set lease_until=now()-interval '1 second' where id=%s", (job_id,))
    assert queue.lease("w", {kind}, 1) == []
    row = c.db.execute("select status,attempts,last_error_code,lease_token from app.jobs where id=%s",
                       (job_id,)).fetchone()
    assert (row["status"], row["attempts"], row["last_error_code"], row["lease_token"]) == (
        "dead", 3, "lease_expired_max_attempts", None)


def test_dead_job_reenqueued(db_case):
    from infrastructure.postgres_jobs import revive_dead_job
    c = db_case
    kind, key = "embed_memory", "spec236-doc-" + uuid4().hex
    c.db.execute("""insert into app.jobs(id,owner_id,kind,dedupe_key,status,payload,max_attempts,
                    attempts,last_error_code) values (%s,%s,%s,%s,'dead','{}'::jsonb,5,5,'provider')""",
                 (uuid4(), c.owner.user_id, kind, key))
    assert revive_dead_job(c.db, kind, key) is False  # cooldown: just died
    c.db.execute("update app.jobs set updated_at=now()-interval '1 hour' where dedupe_key=%s", (key,))
    assert revive_dead_job(c.db, kind, key) is True
    row = c.db.execute("select status,attempts,last_error_code from app.jobs where dedupe_key=%s",
                       (key,)).fetchone()
    assert (row["status"], row["attempts"], row["last_error_code"]) == ("queued", 0, None)
    assert revive_dead_job(c.db, kind, key) is False  # live job is never touched


# --- R10 ------------------------------------------------------------------------------------
def test_llm_settle_above_ceiling_caps_and_records_anomaly_once(db_case):
    from infrastructure.usage_events import append_usage_events
    c = db_case
    op = _operation(c, "completed", "turn")
    reservation = c.wallet.reserve(c.owner, reference_type="operation", reference_id=str(op),
                                   pricing_version_id=c.version, ceiling_milli=20,
                                   fence_token=uuid4(), usage_operation_id=op, at=AT)
    c.wallet.admit_attempt(c.owner, reservation.reservation_id, fence_token=reservation.fence_token,
                           attempt_key="a1", provider="groq", model="openai/gpt-oss-120b", at=AT)
    events = normalize_attempts([{"provider": "groq", "model": "openai/gpt-oss-120b",
                                  "outcome": "success", "network_attempted": True,
                                  "usage": {"input_tokens": 10, "output_tokens": 5,
                                            "provider_cost_usd": "5.00"}}], operation_id=op)
    append_usage_events(c.db, owner_id=c.owner.user_id, operation_id=op, game_id=None, events=events)
    done = c.wallet.settle_usage(c.owner, reservation.reservation_id,
                                 fence_token=reservation.fence_token,
                                 usage_event_ids=[e.event_id for e in events], at=AT)
    assert done.status == "settled" and done.settled_milli == 20
    anomaly = c.db.execute("select financial_anomaly_milli from app.wallet_reservations "
                           "where reservation_id=%s", (reservation.reservation_id,)).fetchone()
    assert anomaly["financial_anomaly_milli"] > 0
    replay = c.wallet.settle_usage(c.owner, reservation.reservation_id,
                                   fence_token=reservation.fence_token,
                                   usage_event_ids=[e.event_id for e in events], at=AT)
    assert replay == done and len(_entries(c, "settle")) == 1
    assert c.wallet.balance(c.owner).available_milli == 980 and _ledger(c) == (980, 0)


# --- R10 / R4 (image) -----------------------------------------------------------------------
@pytest.fixture
def image_case(db_case, monkeypatch):
    from datetime import timedelta
    from infrastructure.postgres import PostgresGameStore
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.image_quotes import ImageQuoteRepository
    c = db_case
    if c.db.execute("select to_regclass('app.image_quotes') as t").fetchone()["t"] is None:
        pytest.skip("SPEC-188 migration absent")

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return AT.astimezone(tz) if tz else AT.replace(tzinfo=None)
    import services.image_quotes
    monkeypatch.setattr(services.image_quotes, "datetime", FixedDatetime)
    game_id = uuid4()
    state = {"game_id": str(game_id), "messages": [], "event_log": [],
             "player": {"name": "Iria", "class_name": "Devoto do Abismo", "level": 1},
             "world": {"current_location": "Teste", "turn_count": 0, "world_clock": {"day": 1}}}
    PostgresGameStore(c.pool).create(c.owner, state)
    profile = "spec236-profile-" + str(uuid4())
    c.db.execute("""insert into app.image_price_profiles
      (profile_id,pricing_version_id,model,size,max_provider_usd,source,expires_at)
      values (%s,%s,'gpt-image-2-2026-04-21','1024x1536',0.02,'synthetic test only',%s)""",
                 (profile, c.version, AT + timedelta(hours=1)))
    monkeypatch.setenv("RPG_IMAGE_PRICE_PROFILE", profile)
    repo = ImageQuoteRepository(c.pool, at=AT)
    queue = PostgresJobQueue(c.pool)
    from services.art_brief import build_player_art_brief
    from services.art_triggers import ArtGenerationRequest
    key = str(uuid4())
    quote = repo.issue(c.owner, game_id,
                       request=ArtGenerationRequest("player_portrait", key, "player", "player", None, key),
                       brief=build_player_art_brief(state["player"]),
                       model="gpt-image-2-2026-04-21", profile_version="test-v1")
    with c.db.transaction():
        generation = repo.confirm(c.owner, game_id, quote["quote_id"], connection=c.db,
                                  epoch=0, version=1, queue=queue)
    return SimpleNamespace(c=c, repo=repo, queue=queue, generation=generation, game_id=game_id)


def _generation(c, generation_id) -> dict:
    return c.db.execute("select g.status,g.error_code,r.status as reservation_status "
                        "from app.art_generations g join app.wallet_reservations r "
                        "on r.reservation_id=g.wallet_reservation_id where g.generation_id=%s",
                        (generation_id,)).fetchone()


def test_image_deferred_too_long_releases_reservation(image_case):
    from datetime import timedelta
    from services.job_fence import job_scope
    i, c = image_case, image_case.c
    gid = i.generation["generation_id"]
    reserved_before = c.wallet.balance(c.owner).reserved_milli
    assert reserved_before > 0
    job = i.queue.lease("w", {"generate_dynamic_art"}, 1)[0]
    with job_scope(job):
        assert i.repo.release_if_deferred_too_long(gid, timedelta(hours=6)) is False  # just paused
    c.db.execute("update app.art_generations set created_at=now()-interval '7 hours' "
                 "where generation_id=%s", (gid,))
    with job_scope(job):
        assert i.repo.release_if_deferred_too_long(gid, timedelta(hours=6)) is True
    row = _generation(c, gid)
    assert (row["status"], row["error_code"], row["reservation_status"]) == (
        "failed", "deferred_timeout", "released")
    assert c.wallet.balance(c.owner).reserved_milli == 0
    assert c.wallet.balance(c.owner).available_milli == 1000


def test_dead_image_job_reservation_is_released_by_sweep(image_case):
    from services.wallet_recovery import recover_wallet_reservations
    i, c = image_case, image_case.c
    gid = i.generation["generation_id"]
    reservation_id = c.db.execute("select wallet_reservation_id from app.art_generations "
                                  "where generation_id=%s", (gid,)).fetchone()["wallet_reservation_id"]
    _age_reservation(c, reservation_id)
    # live (queued) job: the sweep must not touch the reservation
    assert recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)["wallet_skipped"] == 1
    assert _generation(c, gid)["reservation_status"] == "reserved"
    c.db.execute("update app.jobs set status='dead',last_error_code='lease_expired_max_attempts' "
                 "where kind='generate_dynamic_art' and dedupe_key=%s", ("art:" + str(gid),))
    out = recover_wallet_reservations(c.pool, owner_id=c.owner.user_id)
    assert out["wallet_released"] == 1 and out["wallet_errors"] == 0
    row = _generation(c, gid)
    assert (row["status"], row["error_code"], row["reservation_status"]) == (
        "failed", "job_dead_pre_dispatch", "released")
    assert c.wallet.balance(c.owner).available_milli == 1000 and _ledger(c) == (1000, 0)
