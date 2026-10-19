"""Real Postgres transactions plus fake image provider; fixtures roll back everything."""
import os
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone, UTC
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from infrastructure.contracts import Conflict, Principal
from infrastructure.file_blob import FileBlobStore
from infrastructure.postgres import PostgresGameStore
from infrastructure.postgres_jobs import PostgresJobQueue
from infrastructure.wallet import InsufficientShards
from services.art_brief import build_player_art_brief
from services.art_triggers import ArtGenerationRequest
from services.dynamic_art import DynamicArtRepository
from services.image_quotes import ImageQuoteRepository, public_quote
from services.job_fence import job_scope
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION
from tests.fakes.fake_image_generator import FakeImageGenerator
from tests.fakes.local_pricing import installed_card_max_age_seconds
from workers.dynamic_art_jobs import generate_dynamic_art_job


@pytest.fixture
def image_case(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        try:
            if connection.execute("select to_regclass('app.image_quotes') as t").fetchone()["t"] is None:
                connection.execute(Path("supabase/migrations/20261012160000_image_quotes.sql").read_text(encoding="utf-8"))
            class Pool:
                def connection(self):
                    return nullcontext(connection)
            pool = Pool()
            at = datetime(2026, 10, 12, 12, tzinfo=UTC)
            class FixedDatetime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return at.astimezone(tz) if tz else at.replace(tzinfo=None)
            import services.image_quotes
            monkeypatch.setattr(services.image_quotes, "datetime", FixedDatetime)
            owner, game_id = Principal(uuid4(), "test", "owner"), uuid4()
            store = PostgresGameStore(pool)
            state = {"game_id": str(game_id), "messages": [], "event_log": [],
                     "player": {"name": "Iria", "class_name": "Devoto do Abismo", "level": 1},
                     "world": {"current_location": "Teste", "turn_count": 0, "world_clock": {"day": 1}}}
            store.create(owner, state)
            version_id, profile_id = "image-test-" + str(uuid4()), "image-profile-" + str(uuid4())
            connection.execute("""insert into app.pricing_versions
              (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
               fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
               rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
              values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,%s,%s)""",
              (version_id, at, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
               INSTALLED_RATE_CARD_OBSERVED_AT, installed_card_max_age_seconds(at), Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
            connection.execute("""insert into app.image_price_profiles
              (profile_id,pricing_version_id,model,size,max_provider_usd,source,expires_at)
              values (%s,%s,'gpt-image-2-2026-04-21','1024x1536',0.02,'synthetic test only',%s)""",
              (profile_id, version_id, at + timedelta(hours=1)))
            monkeypatch.setenv("RPG_IMAGE_PRICE_PROFILE", profile_id)
            repository = ImageQuoteRepository(pool, at=at)
            repository.wallet.adjust_admin(owner, adjustment_id=str(uuid4()), signed_milli=1000,
                actor_id=uuid4(), reason="rolled back deterministic image test fixture")
            yield SimpleNamespace(pool=pool, db=connection, owner=owner, game_id=game_id, at=at,
                                  repo=repository, queue=PostgresJobQueue(pool), store=store, state=state)
        finally:
            connection.rollback()


def issue(case, *, reformulation=False):
    key = str(uuid4())
    return case.repo.issue(case.owner, case.game_id,
        request=ArtGenerationRequest("player_portrait", key, "player", "player", None, key),
        brief=build_player_art_brief(case.state["player"], reformulation=reformulation),
        model="gpt-image-2-2026-04-21", profile_version="test-v1", reformulation=reformulation)


def confirm(case, quote, **kwargs):
    with case.db.transaction():
        return case.repo.confirm(case.owner, case.game_id, quote["quote_id"], connection=case.db,
            epoch=0, version=1, queue=kwargs.get("queue", case.queue))


def lease(case, generation):
    return case.queue.lease("image-test", {"generate_dynamic_art"}, 1)[0]


def run(case, generation, job, tmp_path, *, cost="0.01", fail=None):
    class Generator(FakeImageGenerator):
        def generate(self, request):
            if fail == "provider":
                self.calls += 1
                raise TimeoutError("external result unknown")
            result = super().generate(request)
            return replace(result, usage={} if cost is None else {"provider_cost_usd": cost})
    generator = Generator()
    repository = DynamicArtRepository(case.pool, model="", profile_version="")
    with job_scope(job):
        try:
            result = generate_dynamic_art_job(generator=generator, blob_store=FileBlobStore(tmp_path),
                generation={"model": "forged client value", "private_brief": {}},
                owner_id=case.owner.user_id, game_id=case.game_id, asset_id=UUID(job.request.payload["asset_id"]),
                admission=lambda: case.repo.dispatch(generation["generation_id"], case.owner.user_id, case.game_id),
                usage_sink=lambda model, usage: repository.record_usage(generation["generation_id"], model=model, usage=usage))
            if fail == "after_provider":
                raise RuntimeError("blob/DB boundary failed")
            repository.complete(generation["generation_id"], asset_id=UUID(result["asset_id"]), result=result)
        except Exception:
            case.repo.hold_or_release(generation["generation_id"])
            raise
    return generator, result


def test_quote_is_immutable_owner_scoped_no_reserve_or_provider_and_reformulation_is_new(image_case):
    c = image_case
    first = issue(c)
    c.state["player"]["subclass"] = "consagrado"
    second = issue(c, reformulation=True)
    assert first["quote_id"] != second["quote_id"] and first["prompt_hash"] != second["prompt_hash"]
    assert second["reformulation"] and first["credits_milli"] == 4
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    assert not c.db.execute("select 1 from app.jobs where game_id=%s", (c.game_id,)).fetchone()
    with pytest.raises(Conflict):
        c.repo.get(Principal(uuid4(), "test", "other"), c.game_id, first["quote_id"])
    assert set(public_quote(first)) == {"quote_id", "type", "credits_milli", "pricing_version", "expires_at", "reformulation"}
    for statement in ["update app.image_quotes set credits_milli=1 where quote_id=%s",
                      "delete from app.image_quotes where quote_id=%s"]:
        with pytest.raises(Exception, match="immutable"), c.db.transaction():
            c.db.execute(statement, (first["quote_id"],))


def test_expired_quote_and_wrong_timeline_fail_closed(image_case):
    c = image_case
    quote = issue(c)
    c.repo.at = c.at + timedelta(minutes=6)
    with pytest.raises(Conflict, match="expirado"):
        confirm(c, quote)
    c.repo.at = c.at
    with pytest.raises(Conflict), c.db.transaction():
        c.repo.confirm(c.owner, c.game_id, quote["quote_id"], connection=c.db, epoch=1, version=1, queue=c.queue)
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    assert not c.db.execute("select 1 from app.art_generations where game_id=%s", (c.game_id,)).fetchone()


def test_insufficient_balance_and_enqueue_fault_leave_no_reservation_or_job(image_case):
    c = image_case
    quote = issue(c)
    c.repo.wallet.adjust_admin(c.owner, adjustment_id=str(uuid4()), signed_milli=-1000,
        actor_id=uuid4(), reason="synthetic insufficient balance")
    with pytest.raises(InsufficientShards):
        confirm(c, quote)
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    c.repo.wallet.adjust_admin(c.owner, adjustment_id=str(uuid4()), signed_milli=1000,
        actor_id=uuid4(), reason="restore rolled back fixture")
    class BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("DB queue fault after reserve")
    with pytest.raises(RuntimeError, match="queue fault"):
        confirm(c, quote, queue=BrokenQueue())
    assert c.repo.wallet.balance(c.owner).available_milli == 1000
    assert not c.db.execute("select 1 from app.wallet_reservations where owner_id=%s", (c.owner.user_id,)).fetchone()
    assert not c.db.execute("select 1 from app.art_generations where game_id=%s", (c.game_id,)).fetchone()


@pytest.mark.parametrize("cost,settled,anomaly", [("0.01", 2, 0), ("0.05", 4, 6)])
def test_confirm_replay_and_exact_settlement_never_debit_above_quote(image_case, tmp_path, cost, settled, anomaly):
    c = image_case
    quote = issue(c)
    generation = confirm(c, quote)
    assert confirm(c, quote)["generation_id"] == generation["generation_id"]
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4
    assert c.db.execute("select count(*) as n from app.jobs where game_id=%s", (c.game_id,)).fetchone()["n"] == 1
    job = lease(c, generation)
    generator, result = run(c, generation, job, tmp_path, cost=cost)
    assert generator.calls == 1 and result["status"] == "ready"
    balance = c.repo.wallet.balance(c.owner)
    assert balance.available_milli == 1000 - settled and balance.reserved_milli == 0
    record = c.db.execute("select * from app.art_generations where generation_id=%s", (generation["generation_id"],)).fetchone()
    assert record["financial_anomaly_milli"] == anomaly
    with job_scope(job), pytest.raises(Conflict):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    assert c.db.execute("select count(*) as n from app.wallet_entries where owner_id=%s and entry_type='settle'",
                        (c.owner.user_id,)).fetchone()["n"] == 1


@pytest.mark.parametrize("fail", ["provider", "after_provider"])
def test_uncertain_provider_and_db_boundary_hold_no_retry_and_no_refund(image_case, tmp_path, fail):
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    with pytest.raises((TimeoutError, RuntimeError)):
        run(c, generation, job, tmp_path, fail=fail)
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4
    with job_scope(job), pytest.raises(Conflict):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    row = c.db.execute("select status,error_code from app.art_generations where generation_id=%s", (generation["generation_id"],)).fetchone()
    assert row == {"status": "failed", "error_code": "external_result_uncertain"}
    assert c.db.execute("select status from app.wallet_reservations where usage_operation_id=%s", (generation["generation_id"],)).fetchone()["status"] == "uncertain"


def test_success_with_unknown_billing_preserves_reconcilable_hold(image_case, tmp_path):
    c = image_case
    generation = confirm(c, issue(c))
    run(c, generation, lease(c, generation), tmp_path, cost=None)
    repository = DynamicArtRepository(c.pool, model="", profile_version="")
    row = repository.get(c.owner, generation["generation_id"])
    assert row["status"] == "ready" and row["financial_status"] == "uncertain"
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4


def test_crash_after_dispatch_ticket_before_network_retains_hold(image_case):
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    with job_scope(job):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
        c.repo.hold_or_release(generation["generation_id"])
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4


def test_pre_dispatch_failure_releases_and_old_jobs_and_stale_fence_never_dispatch(image_case):
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    with pytest.raises(Conflict):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    with job_scope(job):
        c.repo.hold_or_release(generation["generation_id"])
    assert c.repo.wallet.balance(c.owner).available_milli == 1000
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    with job_scope(job), pytest.raises(Conflict):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)


def test_database_brief_tampering_fails_before_ticket(image_case):
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    c.db.execute("update app.art_generations set model='unquoted' where generation_id=%s", (generation["generation_id"],))
    with job_scope(job), pytest.raises(Conflict, match="divergiu"):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    assert not c.db.execute("select 1 from app.wallet_attempt_tickets where owner_id=%s", (c.owner.user_id,)).fetchone()


def test_expired_job_fence_cannot_dispatch_and_reclaimed_ticket_never_retries(image_case):
    # SPEC-236 R9: an image job has max_attempts=1, so an expired lease after its only attempt goes
    # `dead` (never re-leased). The stale fence still cannot dispatch, the ticket already issued is
    # never reused, and the hold stays for the recovery sweep: no second effect, no charge/refund.
    from infrastructure.contracts import LeaseHeld
    c = image_case
    generation = confirm(c, issue(c))
    first = lease(c, generation)
    with job_scope(first):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    c.db.execute("update app.jobs set lease_until=now()-interval '1 second' where id=%s", (first.job_id,))
    assert c.queue.lease("image-test", {"generate_dynamic_art"}, 1) == []
    row = c.db.execute("select status,attempts,max_attempts,last_error_code from app.jobs where id=%s",
                       (first.job_id,)).fetchone()
    assert row == {"status": "dead", "attempts": 1, "max_attempts": 1, "last_error_code": "lease_expired_max_attempts"}
    assert c.queue.lease("image-test", {"generate_dynamic_art"}, 1) == []
    with job_scope(first), pytest.raises((LeaseHeld, Conflict)):
        c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4
    assert c.db.execute("select count(*) as n from app.wallet_attempt_tickets where owner_id=%s", (c.owner.user_id,)).fetchone()["n"] == 1
    assert not c.db.execute("select 1 from app.wallet_entries where owner_id=%s and entry_type in ('settle','release')",
                            (c.owner.user_id,)).fetchone()


def test_quote_rls_owner_select_only_and_no_client_mutation(image_case):
    c = image_case
    quote = issue(c)
    with c.db.transaction():
        c.db.execute("set local role rpg_api")
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)", (str(uuid4()),))
        assert not c.db.execute("select quote_id from app.image_quotes where quote_id=%s", (quote["quote_id"],)).fetchone()
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)", (str(c.owner.user_id),))
        assert c.db.execute("select quote_id from app.image_quotes where quote_id=%s", (quote["quote_id"],)).fetchone()
    for role in ["anon", "authenticated"]:
        with pytest.raises(Exception, match="permission denied"), c.db.transaction():
            c.db.execute(f"set local role {role}")
            c.db.execute("select quote_id from app.image_quotes")
    with pytest.raises(Exception, match="permission denied"), c.db.transaction():
        c.db.execute("set local role rpg_api")
        c.db.execute("update app.image_price_profiles set max_provider_usd=1")


def test_real_worker_configuration_failure_releases_before_ticket(image_case, monkeypatch):
    import workers.run_worker
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(workers.run_worker, "get_runtime", lambda: SimpleNamespace(
        resources=[c.pool], memory_store=PgVectorMemoryStore(c.pool), blob_store=None))
    handler = workers.run_worker.build_handlers()["generate_dynamic_art"]
    with job_scope(job), pytest.raises(KeyError):
        handler(job.request.payload)
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    assert not c.db.execute("select 1 from app.wallet_attempt_tickets where owner_id=%s", (c.owner.user_id,)).fetchone()


def bind_api(case, monkeypatch):
    from copy import deepcopy

    import api
    import infrastructure.runtime
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    runtime = SimpleNamespace(resources=[case.pool], game_store=case.store, job_queue=case.queue,
                              turn_coordinator=PostgresTurnCoordinator(case.pool))
    def loaded(_):
        game = case.store.get(case.owner, case.game_id)
        return {**deepcopy(game.state), "_storage_version": game.version}
    monkeypatch.setattr(api, "_image_finance", lambda *, guard=True: (runtime, case.owner, case.repo))
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(api, "load_game_state", loaded)
    monkeypatch.setattr(api, "_resolve_save_file", lambda _: None)
    monkeypatch.setattr(infrastructure.runtime, "get_runtime", lambda: runtime)
    return api, runtime


def test_api_canonical_commit_reserves_and_enqueues_once_and_round_trips_state(image_case, monkeypatch):
    from infrastructure.request_context import principal_scope
    c = image_case
    api, runtime = bind_api(c, monkeypatch)
    with principal_scope(c.owner):
        quote = api.create_image_quote(str(c.game_id), api.ArtQuoteRequest())
        request = api.ArtConfirmRequest(action_id=str(uuid4()), quote_id=quote["quote_id"], confirmed=True)
        response = api.confirm_player_art(str(c.game_id), request)
        assert api.confirm_player_art(str(c.game_id), request)["generation_id"] == response["generation_id"]
        assert api.confirm_player_art(str(c.game_id), api.ArtConfirmRequest(
            action_id=str(uuid4()), quote_id=quote["quote_id"], confirmed=True))["generation_id"] == response["generation_id"]
    loaded = c.store.get(c.owner, c.game_id)
    assert loaded.version == 2 and loaded.state["art_generation_ledger"][-1]["generation_id"] == response["generation_id"]
    assert c.repo.wallet.balance(c.owner).reserved_milli == 4
    assert c.db.execute("select count(*) as n from app.jobs where game_id=%s", (c.game_id,)).fetchone()["n"] == 1
    # Portrait reformulation cannot bypass a ticket/hold still outstanding.
    from fastapi import HTTPException
    with principal_scope(c.owner), pytest.raises(HTTPException, match="409"):
        api.create_image_quote(str(c.game_id), api.ArtQuoteRequest(reformulation=True))


def test_api_failed_atomic_commit_preserves_original_game_and_releases_operation_lease(image_case, monkeypatch):
    from fastapi import HTTPException

    from infrastructure.request_context import principal_scope
    c = image_case
    api, runtime = bind_api(c, monkeypatch)
    c.repo.wallet.adjust_admin(c.owner, adjustment_id=str(uuid4()), signed_milli=-1000,
        actor_id=uuid4(), reason="rolled back insufficient balance API fixture")
    with principal_scope(c.owner):
        quote = api.create_image_quote(str(c.game_id), api.ArtQuoteRequest())
        request = api.ArtConfirmRequest(action_id=str(uuid4()), quote_id=quote["quote_id"], confirmed=True)
        with pytest.raises(HTTPException) as failure:
            api.confirm_player_art(str(c.game_id), request)
        assert failure.value.status_code == 402
    loaded = c.store.get(c.owner, c.game_id)
    assert loaded.version == 1 and not loaded.state.get("art_generation_ledger")
    assert not c.db.execute("select 1 from app.jobs where game_id=%s", (c.game_id,)).fetchone()
    assert c.db.execute("select active_operation_id from app.games where id=%s", (c.game_id,)).fetchone()["active_operation_id"] is None


@pytest.mark.parametrize("dispatched", [False, True])
def test_restore_releases_only_pre_ticket_images_and_keeps_uncertain_holds(image_case, dispatched):
    from services.restore_effects import restore_effects
    c = image_case
    generation = confirm(c, issue(c))
    if dispatched:
        with job_scope(lease(c, generation)):
            c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
    stored = c.store.get(c.owner, c.game_id)
    c.store.save_checkpoint(c.owner, stored, stored.state)
    with c.db.transaction():
        restore_effects(c.db, principal=c.owner, game_id=c.game_id, document=stored.state)
    assert c.repo.wallet.balance(c.owner).reserved_milli == (4 if dispatched else 0)
    if dispatched:
        assert c.db.execute("select status from app.wallet_reservations where usage_operation_id=%s", (generation["generation_id"],)).fetchone()["status"] == "uncertain"


@pytest.mark.parametrize("image_type", ["npc", "scene"])
def test_npc_and_scene_confirmation_and_uncertain_result_survive_reopen(image_case, monkeypatch, tmp_path, image_type):
    import api
    from infrastructure.request_context import principal_scope
    from services.art_brief import build_epic_art_brief, build_npc_art_brief
    c = image_case
    if image_type == "npc":
        c.state["npcs"] = {"test-npc": {"name": "Iria", "role": "teste"}}
        brief = build_npc_art_brief(c.state, "test-npc")
        kind = "npc_first_appearance"
    else:
        brief = build_epic_art_brief(c.state, {"detail": "teste"})
        kind = "arc_epic_moment"
        profile_id = "image-scene-" + str(uuid4())
        c.db.execute("""insert into app.image_price_profiles
            (profile_id,pricing_version_id,model,size,max_provider_usd,source,expires_at)
            select %s,pricing_version_id,model,'1536x1024',max_provider_usd,source,expires_at
            from app.image_price_profiles where profile_id=%s""",
            (profile_id, os.environ["RPG_IMAGE_PRICE_PROFILE"]))
        monkeypatch.setenv("RPG_IMAGE_PRICE_PROFILE_SCENE", profile_id)
    trigger = ArtGenerationRequest(kind, "test-npc", image_type, "test-npc", "test-arc", "test-action")
    offer = api._enqueue_art_generation(c.state, trigger, brief)
    c.store.save(c.owner, c.game_id, 1, c.state)
    api, runtime = bind_api(c, monkeypatch)
    with principal_scope(c.owner):
        quote = api.create_image_quote(str(c.game_id), api.ArtQuoteRequest(image_type=image_type, offer_id=offer["offer_id"]))
        request = api.ArtConfirmRequest(action_id=str(uuid4()), quote_id=quote["quote_id"], confirmed=True)
        response = api.confirm_player_art(str(c.game_id), request)
        assert response["type"] == image_type and response["art_offers"] == []
        assert response["art_generations"] == [{"generation_id": response["generation_id"], "type": image_type, "subject_id": "test-npc"}]
    generation = c.db.execute("select * from app.art_generations where generation_id=%s", (UUID(response["generation_id"]),)).fetchone()
    with pytest.raises(TimeoutError):
        run(c, generation, lease(c, generation), tmp_path, fail="provider")
    with principal_scope(c.owner):
        status = api.dynamic_art_status(str(c.game_id), response["generation_id"])
        reopened = api.format_response(c.store.get(c.owner, c.game_id).state)
        replay = api.confirm_player_art(str(c.game_id), request)
    assert status["status"] == "reconcile_required" and status["financial_status"] == "uncertain" and status["credits_held"]
    assert reopened.art_generations == response["art_generations"] == replay["art_generations"]
    assert reopened.art_offers == [] and "private_brief" not in str(reopened.art_generations)


def test_real_adapter_documented_token_response_settles_without_provider_cost(image_case, monkeypatch, tmp_path):
    import base64
    from decimal import Decimal

    import httpx

    import workers.run_worker
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.ports import ImageGenerationInput
    from services.image_pricing import IMAGE_PRICING_VERSION
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    png = FakeImageGenerator().generate(ImageGenerationInput("fake", "fake", "1024x1536", ())).payload
    requests = []
    def post(url, **kwargs):
        requests.append(kwargs)
        assert url.endswith("/images/generations") and "response_format" not in kwargs["json"]
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png).decode()}],
            "usage": {"input_tokens": 150, "output_tokens": 100,
                      "input_tokens_details": {"text_tokens": 100, "image_tokens": 50}}})
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-local-key")
    monkeypatch.setattr(workers.run_worker, "get_runtime", lambda: SimpleNamespace(
        resources=[c.pool], memory_store=PgVectorMemoryStore(c.pool), blob_store=FileBlobStore(tmp_path)))
    handler = workers.run_worker.build_handlers()["generate_dynamic_art"]
    with job_scope(job):
        result = handler(job.request.payload)
        assert handler(job.request.payload)["status"] == "already_ready"
    assert len(requests) == 1 and result["status"] == "ready"
    event = c.db.execute("select cost_usd,cost_basis,billing_exact,pricing_version from app.usage_events where operation_id=%s",
                         (generation["generation_id"],)).fetchone()
    assert event == {"cost_usd": Decimal("0.003900000"), "cost_basis": "rate_card",
                     "billing_exact": True, "pricing_version": IMAGE_PRICING_VERSION}
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    assert c.repo.wallet.balance(c.owner).available_milli == 999


def test_stale_image_card_fails_before_ticket_and_releases_safe_hold(image_case):
    from services.shard_pricing import PricingUnavailable
    c = image_case
    generation = confirm(c, issue(c))
    job = lease(c, generation)
    from services.image_pricing import _CARD
    from services.shard_pricing import rate_card_max_age
    # Past the image card's own window (SPEC-236: 30 d default), not the pricing version's.
    c.repo.at = datetime.fromisoformat(_CARD["observed_at"]) + rate_card_max_age() + timedelta(days=1)
    with job_scope(job):
        with pytest.raises(PricingUnavailable):
            c.repo.dispatch(generation["generation_id"], c.owner.user_id, c.game_id)
        c.repo.hold_or_release(generation["generation_id"])
    assert c.repo.wallet.balance(c.owner).reserved_milli == 0
    assert not c.db.execute("select 1 from app.wallet_attempt_tickets where owner_id=%s", (c.owner.user_id,)).fetchone()
