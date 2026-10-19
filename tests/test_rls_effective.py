"""SPEC-224: RLS efetivo no runtime (role de menor privilégio + SET LOCAL ROLE por request).

Roda contra o Supabase local (RPG_TEST_DATABASE_URL, role postgres) e usa o login real
`rpg_runtime`, cuja senha local é definida pelo próprio teste (somente loopback).
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest

from infrastructure.contracts import Principal
from infrastructure.request_context import principal_scope
from datetime import UTC

pytestmark = [pytest.mark.infra_local, pytest.mark.security_local]

_LOCAL_PW = "rpg_runtime_local_only"


def _principal(owner):
    return Principal(user_id=owner, issuer="test", subject=str(owner))


def _insert_game(connection, owner, game):
    connection.execute(
        """insert into app.games
        (id,owner_id,schema_version,state,state_sha256,status,player_name,class_name,
         player_level,location_name,world_day,game_over,combat_simulation)
        values (%s,%s,3,jsonb_build_object('game_id',%s::text),%s,'active','X','Devoto',1,'T',1,false,false)""",
        (game, owner, str(game), "c" * 64),
    )


@pytest.fixture()
def world():
    psycopg = pytest.importorskip("psycopg")
    admin_dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not admin_dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    parts = urlsplit(admin_dsn)
    if (parts.hostname or "") not in {"127.0.0.1", "localhost", "::1"}:
        pytest.skip("teste só roda contra Postgres loopback")
    runtime_dsn = urlunsplit(parts._replace(netloc=f"rpg_runtime:{_LOCAL_PW}@{parts.hostname}:{parts.port}"))
    a, b, ga, gb = uuid4(), uuid4(), uuid4(), uuid4()
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(f"alter role rpg_runtime password '{_LOCAL_PW}'")
        _insert_game(admin, a, ga)
        _insert_game(admin, b, gb)
    yield {"a": a, "b": b, "ga": ga, "gb": gb, "runtime_dsn": runtime_dsn, "admin_dsn": admin_dsn}
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("delete from app.games where id in (%s,%s)", (ga, gb))


def _pools(world, **kwargs):
    from infrastructure.postgres import PostgresPool

    admin = PostgresPool(world["runtime_dsn"], max_size=2)
    user = PostgresPool(world["runtime_dsn"], max_size=2, admin_pool=admin, request_rls=True, **kwargs)
    return user, admin


def test_user_pool_unfiltered_select_sees_only_the_principal_rows(world):
    psycopg = pytest.importorskip("psycopg")
    user, admin = _pools(world)
    try:
        with principal_scope(_principal(world["a"])):
            with user.connection() as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_api"
                ids = {r["id"] for r in c.execute("select id from app.games").fetchall()}
                assert world["ga"] in ids and world["gb"] not in ids
                # app code "forgot" the owner filter on UPDATE/DELETE: still 0 rows of B
                assert c.execute("update app.games set player_name='h' where id=%s", (world["gb"],)).rowcount == 0
                assert c.execute("delete from app.games where id=%s", (world["gb"],)).rowcount == 0
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with c.transaction():
                        _insert_game(c, world["b"], uuid4())
    finally:
        user.close(); admin.close()


def test_admin_connection_is_cross_owner_and_never_rpg_api(world):
    user, admin = _pools(world)
    try:
        with principal_scope(_principal(world["a"])):
            with user.admin_connection() as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_runtime"
                ids = {r["id"] for r in c.execute("select id from app.games").fetchall()}
                assert {world["ga"], world["gb"]} <= ids
            with user.connection(as_admin=True) as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_runtime"
    finally:
        user.close(); admin.close()


def test_role_does_not_leak_across_pooled_connections(world):
    user, admin = _pools(world)
    try:
        with principal_scope(_principal(world["a"])):
            with user.connection() as c:
                c.execute("select 1")
        # same physical connection (max_size=2, reused) outside any principal: no role
        with user.connection() as c:
            assert c.execute("select current_user as u").fetchone()["u"] == "rpg_runtime"
        with principal_scope(_principal(world["b"])):
            with user.connection() as c:
                ids = {r["id"] for r in c.execute("select id from app.games").fetchall()}
                assert world["gb"] in ids and world["ga"] not in ids
    finally:
        user.close(); admin.close()


def test_request_rls_disabled_is_the_documented_rollback(world):
    if os.getenv("RPG_TEST_REQUEST_RLS") == "1":
        pytest.skip("o modo de suite forca request_rls")
    from infrastructure.postgres import PostgresPool

    pool = PostgresPool(world["runtime_dsn"], max_size=1, request_rls=False)
    try:
        with principal_scope(_principal(world["a"])):
            with pool.connection() as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_runtime"
    finally:
        pool.close()


def test_admin_pool_absent_falls_back_to_same_pool_without_role(world):
    from infrastructure.postgres import PostgresPool

    pool = PostgresPool(world["runtime_dsn"], max_size=1, request_rls=True)
    try:
        with principal_scope(_principal(world["a"])):
            with pool.admin_connection() as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_runtime"
            with pool.connection() as c:
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_api"
    finally:
        pool.close()


def test_game_store_cannot_cross_owners_even_without_owner_filter(world):
    """A query that forgets `owner_id` through the real store pool still only sees owner A."""
    user, admin = _pools(world)
    try:
        with principal_scope(_principal(world["a"])):
            with user.connection() as c:
                n = c.execute("select count(*) as n from app.games").fetchone()["n"]
                mine = c.execute("select count(*) as n from app.games where owner_id=%s",
                                 (world["a"],)).fetchone()["n"]
                assert n == mine
    finally:
        user.close(); admin.close()


def test_full_runtime_user_paths_under_rpg_api_and_system_paths_on_admin_pool(world):
    """Runtime real (build_database_runtime): request via rpg_runtime+rpg_api, sistema via rpg_admin."""
    psycopg = pytest.importorskip("psycopg")
    from urllib.parse import urlsplit as _split
    from urllib.parse import urlunsplit as _unsplit

    from infrastructure.contracts import JobRequest
    from infrastructure.runtime import RuntimeConfig, build_database_runtime

    parts = _split(world["admin_dsn"])
    admin_pw = "rpg_admin_local_only"
    with psycopg.connect(world["admin_dsn"], autocommit=True) as admin:
        admin.execute(f"alter role rpg_admin password '{admin_pw}'")
    admin_dsn = _unsplit(parts._replace(netloc=f"rpg_admin:{admin_pw}@{parts.hostname}:{parts.port}"))
    config = RuntimeConfig.from_env({
        "RPG_RUNTIME_PROFILE": "local", "DATABASE_URL": world["runtime_dsn"],
        "RPG_ADMIN_DATABASE_URL": admin_dsn, "SUPABASE_URL": "http://127.0.0.1:55321",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_local", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_local",
    })
    assert config.request_rls is True
    runtime = build_database_runtime(config)
    owner = world["a"]
    principal = _principal(owner)
    new_game = uuid4()
    try:
        pool = runtime.game_store.pool
        assert pool.admin_pool is not None and pool.admin_pool is not pool
        state = {"game_id": str(new_game), "messages": [], "event_log": [],
                 "player": {"name": "Rls", "class_name": "Devoto", "level": 1},
                 "world": {"current_location": "Teste", "turn_count": 0, "world_clock": {"day": 1}}}
        with principal_scope(principal):
            stored = runtime.game_store.create(principal, state)
            assert stored.game_id == new_game
            assert {g.game_id for g in runtime.game_store.list(principal)} >= {new_game, world["ga"]}
            assert world["gb"] not in {g.game_id for g in runtime.game_store.list(principal)}
            assert runtime.game_store.get(principal, world["gb"]) is None  # jogo de B invisivel
            # catalogo: escrita de usuario por rpg_api; escrita global so no pool de sistema
            runtime.runtime_catalog.put("rls_ns", "k", {"v": 1}, scope="user", owner_id=owner, game_id=None)
            runtime.runtime_catalog.put("rls_ns", "g", {"v": 2}, scope="global", owner_id=None, game_id=None)
            assert runtime.runtime_catalog.get("rls_ns", "k", owner_id=owner, game_id=None) == {"v": 1}
            assert runtime.runtime_catalog.get("rls_ns", "g", owner_id=None, game_id=None) == {"v": 2}
            # fila: enqueue no request; lease/complete (cross-owner) no pool de sistema, sem principal
            job_id = runtime.job_queue.enqueue(JobRequest(
                "rls_test_job", f"rls-{uuid4()}", {"x": 1}, owner_id=owner, game_id=new_game))
            # limitador (tabela vetada a rpg_api) funciona dentro do request via credencial de sistema
            assert runtime.rate_limiter.consume(f"rls-{uuid4()}", limit=5, window_seconds=60).allowed
            # SPEC-219 x SPEC-224: a cota diaria (tabela vetada a rpg_api) tambem vai pelo pool de
            # sistema; antes abria conexao de request, levava permission denied e o handler falhava aberto.
            quota_owner = uuid4()
            try:
                assert runtime.daily_quota.bump(quota_owner, "turn", 1).allowed
                assert not runtime.daily_quota.bump(quota_owner, "turn", 1).allowed
            finally:
                with psycopg.connect(world["admin_dsn"], autocommit=True) as cleanup:
                    cleanup.execute("delete from app.owner_daily_counters where owner_id=%s", (quota_owner,))
        leased = runtime.job_queue.lease("rls-worker", {"rls_test_job"}, 5)
        assert [j.job_id for j in leased] == [job_id]
        runtime.job_queue.complete(leased[0].job_id, leased[0].lease_token, {"ok": True})
        # com principal ativo, uma funcao de sistema (lease) continua sem trocar de role
        with principal_scope(principal):
            assert runtime.job_queue.lease("rls-worker", {"rls_test_job"}, 5) == []
    finally:
        with psycopg.connect(world["admin_dsn"], autocommit=True) as admin:
            admin.execute("delete from app.jobs where kind='rls_test_job'")
            admin.execute("delete from app.runtime_catalog where namespace='rls_ns'")
            admin.execute("delete from app.games where id=%s", (new_game,))
        runtime.resources[0].close()


def _image_quote_case(world, monkeypatch):
    """Quote de imagem real (pricing/profile sinteticos) para exercitar efeitos financeiros no request."""
    psycopg = pytest.importorskip("psycopg")
    from datetime import datetime, timedelta, timezone

    from psycopg.types.json import Jsonb

    import services.image_quotes
    from infrastructure.postgres import PostgresGameStore
    from services.art_brief import build_player_art_brief
    from services.art_triggers import ArtGenerationRequest
    from services.image_quotes import ImageQuoteRepository
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION
    from tests.fakes.local_pricing import installed_card_max_age_seconds

    at = datetime(2026, 10, 12, 12, tzinfo=UTC)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)

    monkeypatch.setattr(services.image_quotes, "datetime", FixedDatetime)
    version_id, profile_id = "rls-image-" + str(uuid4()), "rls-image-profile-" + str(uuid4())
    with psycopg.connect(world["admin_dsn"], autocommit=True) as admin:
        admin.execute("""insert into app.pricing_versions
          (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
           fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,
           rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
          values (%s,0.03,5,'test',%s,864000,0.1,%s,%s,'test',%s,%s,%s)""",
          (version_id, at, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
           INSTALLED_RATE_CARD_OBSERVED_AT, installed_card_max_age_seconds(), Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
        admin.execute("""insert into app.image_price_profiles
          (profile_id,pricing_version_id,model,size,max_provider_usd,source,expires_at)
          values (%s,%s,'gpt-image-2-2026-04-21','1024x1536',0.02,'synthetic rls test only',%s)""",
          (profile_id, version_id, at + timedelta(hours=1)))
    monkeypatch.setenv("RPG_IMAGE_PRICE_PROFILE", profile_id)
    user, admin_pool = _pools(world)
    owner = uuid4()
    principal = _principal(owner)
    game_id = uuid4()
    state = {"game_id": str(game_id), "messages": [], "event_log": [],
             "player": {"name": "Iria", "class_name": "Devoto do Abismo", "level": 1},
             "world": {"current_location": "Teste", "turn_count": 0, "world_clock": {"day": 1}}}
    with principal_scope(principal):
        PostgresGameStore(user).create(principal, state)
    repository = ImageQuoteRepository(user, at=at)
    repository.wallet.adjust_admin(principal, adjustment_id=str(uuid4()), signed_milli=1000,
                                   actor_id=uuid4(), reason="rls test fixture credit")
    key = str(uuid4())
    with principal_scope(principal):
        quote = repository.issue(principal, game_id,
            request=ArtGenerationRequest("player_portrait", key, "player", "player", None, key),
            brief=build_player_art_brief(state["player"]),
            model="gpt-image-2-2026-04-21", profile_version="test-v1")
    return user, admin_pool, principal, game_id, repository, quote


def _cancel_owner_jobs(world, principal):
    """O banco local e compartilhado: job de arte orfao seria arrendado por outros testes."""
    import psycopg

    with psycopg.connect(world["admin_dsn"], autocommit=True) as admin:
        admin.execute("""update app.jobs set status='cancelled',lease_token=null,lease_until=null,
            lease_owner=null,updated_at=now() where owner_id=%s and status in ('queued','retry','running')""",
            (principal.user_id,))


def test_image_quote_confirm_inside_the_request_commit_reaches_the_wallet(world, monkeypatch):
    """Regressao Astra: o confirm do quote roda DENTRO da transacao de commit do turno (rpg_api) e
    reserva Estilhas na wallet, tabela vetada a `rpg_api`. Sem elevacao escopada, o confirm quebrava
    com InsufficientPrivilege e a arte paga ficava impossivel com o RLS ligado."""
    from infrastructure.postgres_jobs import PostgresJobQueue

    user, admin_pool, principal, game_id, repository, quote = _image_quote_case(world, monkeypatch)
    try:
        with principal_scope(principal):
            with user.connection() as c, c.transaction():
                generation = repository.confirm(principal, game_id, quote["quote_id"], connection=c,
                                                epoch=0, version=1, queue=PostgresJobQueue(user))
                assert generation["wallet_reservation_id"] is None or generation["generation_id"]
                # depois do efeito de sistema, a transacao volta a ser do owner (rpg_api)
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_api"
        with user.admin_connection() as c:
            row = c.execute("select wallet_reservation_id from app.art_generations where image_quote_id=%s",
                            (quote["quote_id"],)).fetchone()
            assert row and row["wallet_reservation_id"] is not None
    finally:
        _cancel_owner_jobs(world, principal)
        user.close(); admin_pool.close()


def test_restore_effects_release_wallet_hold_under_request_role(world, monkeypatch):
    """Restore (morte -> checkpoint) roda sob rpg_api e libera a reserva de um quote abandonado."""
    from infrastructure.postgres_jobs import PostgresJobQueue
    from services.restore_effects import restore_effects

    user, admin_pool, principal, game_id, repository, quote = _image_quote_case(world, monkeypatch)
    try:
        with principal_scope(principal):
            with user.connection() as c, c.transaction():
                repository.confirm(principal, game_id, quote["quote_id"], connection=c,
                                   epoch=0, version=1, queue=PostgresJobQueue(user))
        with user.admin_connection() as c:
            c.execute("""insert into app.game_checkpoints
                (game_id,owner_id,game_version,state,state_sha256,timeline_epoch,canonical_turn)
                select id,owner_id,version,state,state_sha256,0,0 from app.games where id=%s""",
                (game_id,))
        with principal_scope(principal):
            with user.connection() as c, c.transaction():
                restore_effects(c, principal=principal, game_id=game_id,
                                document={"art_generation_ledger": []})
                assert c.execute("select current_user as u").fetchone()["u"] == "rpg_api"
        with user.admin_connection() as c:
            status = c.execute("""select w.status from app.art_generations g join app.wallet_reservations w
                on w.reservation_id=g.wallet_reservation_id where g.image_quote_id=%s""",
                (quote["quote_id"],)).fetchone()["status"]
            assert status != "reserved"
    finally:
        _cancel_owner_jobs(world, principal)
        user.close(); admin_pool.close()
