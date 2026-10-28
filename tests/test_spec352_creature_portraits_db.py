"""SPEC-352 com Postgres real (`RPG_TEST_DATABASE_URL`): registro, dinheiro, falha, ciclo de vida.

Sem a URL estes testes dão `skip` — e isso NÃO vale como verde para a spec. Cada teste roda numa
transação revertida (exceto `test_concurrent_claim_two_connections`, que commita e limpa)."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest

from infrastructure.contracts import Conflict, Principal
from infrastructure.file_blob import FileBlobStore
from infrastructure.postgres import _apply_request_role
from services.art_brief import build_creature_art_brief
from services.art_triggers import ArtGenerationRequest
from services.creature_portraits import (
    CreaturePortraitTaken,
    PostgresPortraitRegistry,
    purge_game_portraits,
)
from services.dynamic_art import DynamicArtRepository
from services.job_fence import job_scope
from tests.fakes.fake_image_generator import FakeImageGenerator
from tests.test_image_quotes_local import confirm, image_case, lease  # noqa: F401
from workers.dynamic_art_jobs import copy_creature_portrait_job, generate_dynamic_art_job

MIGRATION = Path("supabase/migrations/20261028120000_creature_portraits.sql")
GOBLIN = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}


@pytest.fixture
def pc(image_case):  # noqa: F811
    c = image_case
    c.registry = PostgresPortraitRegistry(c.pool)
    if c.db.execute("select to_regclass('app.creature_portraits') as t").fetchone()["t"] is None:
        c.db.execute(MIGRATION.read_text(encoding="utf-8"))
    c.key = f"tipo:gen:t{uuid4().hex[:10]}"
    return c


def issue_monster(c, key=None, *, owner=None, game_id=None):
    key = key or c.key
    request_key = str(uuid4())
    return c.repo.issue(
        owner or c.owner,
        game_id or c.game_id,
        request=ArtGenerationRequest(
            "creature_portrait", f"{key}|{request_key}", "monster", key, None, request_key
        ),
        brief=build_creature_art_brief(GOBLIN, important=False),
        model="gpt-image-2-2026-04-21",
        profile_version="test-v1",
    )


def second_owner(c):
    owner, game_id = Principal(uuid4(), "test", "owner-b"), uuid4()
    state = dict(c.state, game_id=str(game_id))
    c.store.create(owner, state)
    c.repo.wallet.adjust_admin(
        owner,
        adjustment_id=str(uuid4()),
        signed_milli=1000,
        actor_id=uuid4(),
        reason="rolled back deterministic image test fixture",
    )
    return SimpleNamespace(owner=owner, game_id=game_id)


def confirm_as(c, quote, who):
    with c.db.transaction():
        return c.repo.confirm(
            who.owner,
            who.game_id,
            quote["quote_id"],
            connection=c.db,
            epoch=0,
            version=1,
            queue=c.queue,
        )


def row_of(c, key=None):
    return c.db.execute(
        "select * from app.creature_portraits where portrait_key=%s", (key or c.key,)
    ).fetchone()


def run_monster(c, generation, job, tmp_path, *, shared=True, fail=None, owner=None, game_id=None):
    owner = owner or c.owner
    game_id = game_id or c.game_id

    class Generator(FakeImageGenerator):
        def generate(self, request):
            if fail == "provider":
                self.calls += 1
                raise TimeoutError("external result unknown")
            result = super().generate(request)
            return replace(result, usage={"provider_cost_usd": "0.01"})

    class Broken:
        def put(self, *_a, **_k):
            raise RuntimeError("bucket indisponível")

    shared_store = FileBlobStore(tmp_path / "s") if shared is True else Broken()
    repository = DynamicArtRepository(c.pool, model="", profile_version="")
    with job_scope(job):
        try:
            result = generate_dynamic_art_job(
                generator=Generator(),
                blob_store=FileBlobStore(tmp_path),
                shared_blob_store=shared_store,
                generation={"model": "forged", "private_brief": {}},
                owner_id=owner.user_id,
                game_id=game_id,
                asset_id=UUID(job.request.payload["asset_id"]),
                admission=lambda: c.repo.dispatch(
                    generation["generation_id"], owner.user_id, game_id
                ),
                usage_sink=lambda model, usage: repository.record_usage(
                    generation["generation_id"], model=model, usage=usage
                ),
            )
            repository.complete(
                generation["generation_id"], asset_id=UUID(result["asset_id"]), result=result
            )
        except Exception:
            c.repo.hold_or_release(generation["generation_id"])
            raise
    return result


# --- migration / schema -----------------------------------------------------------------------
def test_migration_idempotent(pc):
    sql = MIGRATION.read_text(encoding="utf-8")
    pc.db.execute(sql)
    pc.db.execute(sql)
    assert row_of(pc) is None


def test_constraints_accept_monster(pc):
    quote = issue_monster(pc)
    assert quote["image_type"] == "monster"
    generation = confirm(pc, quote)
    assert generation["subject_type"] == "monster"
    assert generation["trigger_kind"] == "creature_portrait"


def test_ready_requires_thumb_and_pending_requires_owner(pc):
    for sql, args in [
        (
            "insert into app.creature_portraits (portrait_key,scope,status,visibility,origin_owner_id,store)"
            " values (%s,'tipo','ready','shared',%s,'shared')",
            (pc.key, pc.owner.user_id),
        ),
        (
            "insert into app.creature_portraits (portrait_key,scope,status,visibility)"
            " values (%s,'tipo','pending','shared')",
            (pc.key,),
        ),
    ]:
        with pytest.raises(psycopg.errors.DatabaseError), pc.db.transaction():
            pc.db.execute(sql, args)


# --- registro: ida e volta, imutabilidade, RLS ------------------------------------------------
def test_roundtrip_claim_pending_then_ready_and_second_game_sees_it(pc, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rt")
    quote = issue_monster(pc)
    generation = confirm(pc, quote)
    assert row_of(pc)["status"] == "pending"
    mine = pc.registry.get_many([pc.key], game_id=str(pc.game_id))
    assert mine[pc.key]["status"] == "pending"
    result = run_monster(pc, generation, lease(pc, generation), tmp)
    row = row_of(pc)
    assert row["status"] == "ready" and row["store"] == "shared"
    assert set(row["object_keys"]) == {"full", "thumb"}
    assert all(k.startswith("shared/creatures/") for k in row["object_keys"].values())
    assert all((tmp / "s" / k).exists() for k in row["object_keys"].values())
    assert "shared_copy_failed" not in result
    # outro jogo (outro dono): vê pronto, sem oferta e sem débito
    other = second_owner(pc)
    seen = pc.registry.get_many([pc.key], game_id=str(other.game_id))
    assert seen[pc.key]["status"] == "ready"
    assert pc.repo.wallet.balance(other.owner).available_milli == 1000
    # débito do pagador liquidado ≤ teto
    balance = pc.repo.wallet.balance(pc.owner)
    assert balance.reserved_milli == 0 and balance.available_milli >= 1000 - quote["credits_milli"]


def test_ready_immutable(pc, tmp_path_factory):
    generation = confirm(pc, issue_monster(pc))
    run_monster(pc, generation, lease(pc, generation), tmp_path_factory.mktemp("im"))
    for sql in (
        'update app.creature_portraits set object_keys=\'{"thumb":"x"}\'::jsonb where portrait_key=%s',
        "update app.creature_portraits set visibility='game' where portrait_key=%s",
        "update app.creature_portraits set status='pending' where portrait_key=%s",
    ):
        with pytest.raises(Exception, match="immutable"), pc.db.transaction():
            pc.db.execute(sql, (pc.key,))


def test_rpg_api_cannot_write(pc):
    for sql in (
        "insert into app.creature_portraits (portrait_key,scope,status,visibility,origin_owner_id)"
        " values ('tipo:gen:rls','tipo','pending','shared',gen_random_uuid())",
        "update app.creature_portraits set status='failed'",
        "delete from app.creature_portraits",
    ):
        with pytest.raises(psycopg.errors.DatabaseError), pc.db.transaction():
            _apply_request_role(pc.db, pc.owner.user_id)
            pc.db.execute(sql)


def test_rpg_api_reads_shared_and_own_game_only(pc):
    other_game = uuid4()
    rows = [
        (f"{pc.key}:shared", "shared", None),
        (f"unico:{pc.game_id}:x:mine", "game", pc.game_id),
        (f"unico:{other_game}:x:theirs", "game", other_game),
    ]
    for key, visibility, origin in rows:
        pc.db.execute(
            """insert into app.creature_portraits (portrait_key,scope,status,visibility,origin_owner_id,
            origin_game_id,store,object_keys) values (%s,%s,'ready',%s,%s,%s,'shared','{"thumb":"k"}')""",
            (key, "unico" if visibility == "game" else "tipo", visibility, uuid4(), origin),
        )
    from psycopg import Rollback

    seen = set()
    with pc.db.transaction():
        _apply_request_role(pc.db, pc.owner.user_id)
        seen = {
            r["portrait_key"]
            for r in pc.db.execute(
                "select portrait_key from app.creature_portraits where portrait_key like %s or"
                " portrait_key like %s",
                (f"{pc.key}%", "unico:%"),
            ).fetchall()
        }
        raise Rollback()
    assert f"{pc.key}:shared" in seen
    assert f"unico:{pc.game_id}:x:mine" in seen
    assert f"unico:{other_game}:x:theirs" not in seen


# --- claim / dinheiro -------------------------------------------------------------------------
def test_second_confirm_same_key_is_taken_without_reservation_or_debit(pc):
    first = confirm(pc, issue_monster(pc))
    other = second_owner(pc)
    quote_b = issue_monster(pc, owner=other.owner, game_id=other.game_id)
    with pytest.raises(CreaturePortraitTaken):
        confirm_as(pc, quote_b, other)
    balance = pc.repo.wallet.balance(other.owner)
    assert balance.available_milli == 1000 and balance.reserved_milli == 0
    assert not pc.db.execute(
        "select 1 from app.wallet_reservations where owner_id=%s", (other.owner.user_id,)
    ).fetchone()
    assert not pc.db.execute(
        "select 1 from app.art_generations where game_id=%s", (other.game_id,)
    ).fetchone()
    jobs = pc.db.execute(
        "select count(*) as n from app.jobs where kind='generate_dynamic_art' and dedupe_key like %s",
        (f"art:{first['generation_id']}",),
    ).fetchone()["n"]
    assert jobs == 1
    assert row_of(pc)["generation_id"] == first["generation_id"]
    assert isinstance(CreaturePortraitTaken("x"), Conflict)


def test_confirm_replay_is_idempotent(pc):
    quote = issue_monster(pc)
    first = confirm(pc, quote)
    assert confirm(pc, quote)["generation_id"] == first["generation_id"]
    assert (
        pc.db.execute(
            "select count(*) as n from app.creature_portraits where portrait_key=%s", (pc.key,)
        ).fetchone()["n"]
        == 1
    )


def test_important_keys_are_independent(pc):
    own = f"unico:{pc.game_id}:goblin:grishnak"
    other_own = f"unico:{pc.game_id}:goblin:ugruk"
    confirm(pc, issue_monster(pc, own))
    confirm(pc, issue_monster(pc, other_own))
    confirm(pc, issue_monster(pc))
    assert {
        r["portrait_key"]
        for r in pc.db.execute(
            "select portrait_key from app.creature_portraits where portrait_key in (%s,%s,%s)",
            (own, other_own, pc.key),
        ).fetchall()
    } == {own, other_own, pc.key}


def test_claim_after_failed_ok_and_pre_dispatch_failure_releases(pc):
    generation = confirm(pc, issue_monster(pc))
    job = lease(pc, generation)
    with job_scope(job):
        pc.repo.hold_or_release(generation["generation_id"])
    assert pc.repo.wallet.balance(pc.owner).available_milli == 1000
    assert row_of(pc)["status"] == "failed"
    assert pc.registry.get_many([pc.key], game_id=str(pc.game_id)) == {}
    other = second_owner(pc)
    again = confirm_as(pc, issue_monster(pc, owner=other.owner, game_id=other.game_id), other)
    assert (
        row_of(pc)["status"] == "pending" and row_of(pc)["generation_id"] == again["generation_id"]
    )


def test_dead_pending_generation_is_claimable_even_without_mark_failed(pc):
    generation = confirm(pc, issue_monster(pc))
    pc.db.execute(
        "update app.art_generations set status='failed' where generation_id=%s",
        (generation["generation_id"],),
    )
    assert pc.registry.get_many([pc.key], game_id=str(pc.game_id)) == {}
    other = second_owner(pc)
    confirm_as(pc, issue_monster(pc, owner=other.owner, game_id=other.game_id), other)


def test_post_dispatch_failure_uncertain_and_marks_failed(pc, tmp_path_factory):
    generation = confirm(pc, issue_monster(pc))
    job = lease(pc, generation)
    with pytest.raises(TimeoutError):
        run_monster(pc, generation, job, tmp_path_factory.mktemp("pf"), fail="provider")
    assert pc.repo.wallet.balance(pc.owner).reserved_milli > 0  # retido p/ conciliação
    status = pc.db.execute(
        "select status from app.wallet_reservations where usage_operation_id=%s",
        (generation["generation_id"],),
    ).fetchone()["status"]
    assert status == "uncertain"
    row = row_of(pc)
    assert row["status"] == "failed" and row["error_code"] == "external_result_uncertain"


def test_deferred_timeout_marks_failed(pc):
    generation = confirm(pc, issue_monster(pc))
    job = lease(pc, generation)
    pc.db.execute(
        "update app.art_generations set created_at=now()-interval '10 hours' where generation_id=%s",
        (generation["generation_id"],),
    )
    with job_scope(job):
        assert pc.repo.release_if_deferred_too_long(generation["generation_id"], timedelta(hours=6))
    assert row_of(pc)["status"] == "failed" and row_of(pc)["error_code"] == "deferred_timeout"
    assert pc.repo.wallet.balance(pc.owner).reserved_milli == 0


# --- cópia compartilhada ----------------------------------------------------------------------
def test_shared_copy_failure_keeps_generation_ready_private_then_copy_job_promotes(
    pc, tmp_path_factory
):
    tmp = tmp_path_factory.mktemp("cp")
    generation = confirm(pc, issue_monster(pc))
    job = lease(pc, generation)
    result = run_monster(pc, generation, job, tmp, shared=False)
    assert result["shared_copy_failed"] is True
    row = row_of(pc)
    assert row["status"] == "ready" and row["store"] == "private"
    assert all(k.startswith("users/") for k in row["object_keys"].values())
    shared = FileBlobStore(tmp / "s")
    payload = {
        "portrait_key": pc.key,
        "owner_id": str(pc.owner.user_id),
        "game_id": str(pc.game_id),
        "asset_id": result["asset_id"],
    }
    out = copy_creature_portrait_job(pc.registry, FileBlobStore(tmp), shared, payload)
    assert out["status"] == "promoted"
    row = row_of(pc)
    assert row["store"] == "shared"
    assert all(k.startswith("shared/creatures/") for k in row["object_keys"].values())
    assert copy_creature_portrait_job(pc.registry, FileBlobStore(tmp), shared, payload) == {
        "status": "already_shared"
    }


# --- visibilidade via pool --------------------------------------------------------------------
def _insert_ready(c, key, *, visibility, origin_game, pool_entry=None, store="shared", thumb="k"):
    c.db.execute(
        """insert into app.creature_portraits (portrait_key,scope,status,visibility,pool_entry_id,
        origin_owner_id,origin_game_id,store,object_keys) values
        (%s,%s,'ready',%s,%s,%s,%s,%s,jsonb_build_object('thumb',%s::text))""",
        (key, "tipo", visibility, pool_entry, c.owner.user_id, origin_game, store, thumb),
    )


def _pool_entry(c, status):
    entry_id = f"pe{uuid4().hex[:12]}"
    c.db.execute(
        """insert into app.shared_pool (entry_id,namespace,status,name,name_fold,name_origin,document,
        origin_owner_id,origin_game_id,promote_after) values
        (%s,'bestiary_template',%s,'Bicho','bicho','engine','{}'::jsonb,%s,%s,now())""",
        (entry_id, status, c.owner.user_id, str(c.game_id)),
    )
    return entry_id


@pytest.mark.parametrize(
    "pool_status,other_sees", [("held", False), ("promoted", True), ("rejected", False)]
)
def test_pool_visibility_follows_pool_status(pc, pool_status, other_sees):
    entry = _pool_entry(pc, pool_status)
    key = f"tipo:bst:{entry}"
    _insert_ready(pc, key, visibility="pool", origin_game=pc.game_id, pool_entry=entry)
    assert (key in pc.registry.get_many([key], game_id=str(uuid4()))) is other_sees
    mine = key in pc.registry.get_many([key], game_id=str(pc.game_id))
    assert mine is (pool_status != "rejected")


def test_unico_game_row_only_for_origin_game(pc):
    key = f"unico:{pc.game_id}:goblin:grishnak"
    _insert_ready(pc, key, visibility="game", origin_game=pc.game_id)
    assert key in pc.registry.get_many([key], game_id=str(pc.game_id))
    assert key not in pc.registry.get_many([key], game_id=str(uuid4()))


def test_npc_row_needs_known_npc(pc):
    key = f"npc:npc_{uuid4().hex[:8]}"
    _insert_ready(pc, key, visibility="shared", origin_game=pc.game_id)
    assert key not in pc.registry.get_many([key], game_id=str(uuid4()))
    assert key in pc.registry.get_many([key], game_id=str(uuid4()), npc_known=[key])


# --- ciclo de vida ----------------------------------------------------------------------------
def test_account_fence_blocks_deleted_owner(pc):
    pc.db.execute("insert into app.account_deletions (owner_id) values (%s)", (pc.owner.user_id,))
    with pytest.raises(Exception, match="account_deleted"), pc.db.transaction():
        pc.db.execute(
            "insert into app.creature_portraits (portrait_key,scope,status,visibility,origin_owner_id)"
            " values (%s,'tipo','pending','shared',%s)",
            (pc.key, pc.owner.user_id),
        )


def test_erase_owner_unlinks_shared_deletes_game_rows_and_pending(pc):
    shared_key = f"{pc.key}:s"
    game_key = f"unico:{pc.game_id}:x:y"
    pending_key = f"{pc.key}:p"
    private_key = f"{pc.key}:v"
    _insert_ready(pc, shared_key, visibility="shared", origin_game=pc.game_id)
    _insert_ready(pc, game_key, visibility="game", origin_game=pc.game_id)
    pc.db.execute(
        "insert into app.creature_portraits (portrait_key,scope,status,visibility,origin_owner_id)"
        " values (%s,'tipo','pending','shared',%s)",
        (pending_key, pc.owner.user_id),
    )
    _insert_ready(pc, private_key, visibility="shared", origin_game=pc.game_id, store="private")
    keys = PostgresPortraitRegistry.erase_owner(pc.db, pc.owner.user_id)
    assert keys == ["k"]  # só a compartilhada apagada (a de jogo) devolve objeto a remover
    assert row_of(pc, game_key) is None
    assert row_of(pc, pending_key) is None
    assert row_of(pc, private_key) is None
    kept = row_of(pc, shared_key)
    assert kept["status"] == "ready" and kept["origin_owner_id"] is None
    assert kept["origin_game_id"] is None


def test_export_lists_origin_rows_without_keys(pc):
    _insert_ready(pc, pc.key, visibility="shared", origin_game=pc.game_id)
    rows = PostgresPortraitRegistry.export_rows(pc.db, pc.owner.user_id)
    mine = [r for r in rows if r["portrait_key"] == pc.key]
    assert mine and set(mine[0]) == {"portrait_key", "scope", "status", "created_at", "updated_at"}


def test_delete_game_removes_game_rows_only(pc):
    game_key = f"unico:{pc.game_id}:x:y"
    shared_key = pc.key
    _insert_ready(
        pc, game_key, visibility="game", origin_game=pc.game_id, thumb="shared/creatures/ab/g.webp"
    )
    _insert_ready(pc, shared_key, visibility="shared", origin_game=pc.game_id)
    purge_game_portraits(pc.db, pc.owner.user_id, pc.game_id)
    assert row_of(pc, game_key) is None and row_of(pc, shared_key) is not None
    job = pc.db.execute(
        "select payload from app.jobs where kind='purge_shared_art' and owner_id=%s",
        (pc.owner.user_id,),
    ).fetchone()
    assert job and job["payload"]["object_keys"] == ["shared/creatures/ab/g.webp"]


def test_retire_frees_key_and_returns_shared_objects(pc, tmp_path_factory):
    generation = confirm(pc, issue_monster(pc))
    run_monster(pc, generation, lease(pc, generation), tmp_path_factory.mktemp("rt2"))
    keys = pc.registry.retire(portrait_key=pc.key, reason="teste")
    assert len(keys) == 2 and all(k.startswith("shared/creatures/") for k in keys)
    assert row_of(pc)["status"] == "retired"
    assert pc.registry.get_many([pc.key], game_id=str(pc.game_id)) == {}
    other = second_owner(pc)
    confirm_as(pc, issue_monster(pc, owner=other.owner, game_id=other.game_id), other)
    assert row_of(pc)["status"] == "pending"
    with pytest.raises(Conflict):
        pc.registry.retire(portrait_key=pc.key, reason="de novo")  # pending não retira


def test_peek_ceiling_reads_without_writing_a_quote(pc):
    before = pc.db.execute("select count(*) as n from app.image_quotes").fetchone()["n"]
    milli = pc.repo.peek_ceiling("monster")
    after = pc.db.execute("select count(*) as n from app.image_quotes").fetchone()["n"]
    assert milli == 4 and before == after


def test_concurrent_claim_two_connections_real_confirm_flow():
    """P0-1 (Sol): fluxo REAL do `_confirm` - claim + geração na MESMA transação, sem commit prévio.

    tx1 abre (claim + geração); tx2 chama claim e bloqueia no PK; tx1 commita. tx2 deve ver a geração
    recém-commitada (snapshot novo) e levantar `CreaturePortraitTaken`."""
    import threading
    import time

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    from psycopg.rows import dict_row

    key = f"tipo:gen:race{uuid4().hex[:10]}"
    owners, games, gens = [uuid4(), uuid4()], [uuid4(), uuid4()], [uuid4(), uuid4()]
    admin = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    if admin.execute("select to_regclass('app.creature_portraits') as t").fetchone()["t"] is None:
        pytest.skip("migration da SPEC-352 não aplicada neste banco")
    c1 = psycopg.connect(dsn, row_factory=dict_row)
    c2 = psycopg.connect(dsn, row_factory=dict_row)
    results = ["", ""]

    def gen_insert(conn, i):
        conn.execute(
            """insert into app.art_generations (generation_id,owner_id,game_id,trigger_kind,
            trigger_instance_id,subject_type,subject_id,status,model,profile_version,prompt_hash,
            anchor_hash) values (%s,%s,%s,'creature_portrait',%s,'monster',%s,'pending','m','p',
            repeat('a',64),repeat('b',64))""",
            (gens[i], owners[i], games[i], key + str(i), key),
        )

    def claim(conn, i):
        PostgresPortraitRegistry.claim(
            conn,
            portrait_key=key,
            scope="tipo",
            pool_entry_id=None,
            origin_owner_id=owners[i],
            origin_game_id=games[i],
            generation_id=gens[i],
        )

    try:
        for owner, game in zip(owners, games, strict=True):
            admin.execute(
                "insert into app.games (id,owner_id,schema_version,state,state_sha256,status,"
                "player_name,class_name,player_level,location_name,world_day,game_over,"
                "combat_simulation) values "
                "(%s,%s,1,'{}'::jsonb,repeat('c',64),'active','T','T',1,'T',1,false,false)",
                (game, owner),
            )
        claim(c1, 0)
        gen_insert(c1, 0)

        def second():
            try:
                claim(c2, 1)
                gen_insert(c2, 1)
                c2.commit()
                results[1] = "won"
            except CreaturePortraitTaken:
                c2.rollback()
                results[1] = "taken"

        thread = threading.Thread(target=second)
        thread.start()
        time.sleep(1.5)  # tx2 está bloqueada no PK
        c1.commit()
        results[0] = "won"
        thread.join(30)
        assert results == ["won", "taken"]
        row = admin.execute(
            "select generation_id, version from app.creature_portraits where portrait_key=%s",
            (key,),
        ).fetchone()
        assert row["generation_id"] == gens[0] and row["version"] == 1
    finally:
        c1.close()
        c2.close()
        admin.execute("delete from app.creature_portraits where portrait_key=%s", (key,))
        admin.execute("delete from app.art_generations where generation_id = any(%s)", (gens,))
        admin.execute("delete from app.games where id = any(%s)", (games,))
        admin.close()


# --- revisão Sol ------------------------------------------------------------------------------
def test_copy_job_is_enqueued_in_the_same_transaction_as_complete(pc, tmp_path_factory):
    """P1-1: cópia falhou -> `ready/private` + job de cópia já na fila, sem janela de perda."""
    generation = confirm(pc, issue_monster(pc))
    run_monster(pc, generation, lease(pc, generation), tmp_path_factory.mktemp("q1"), shared=False)
    assert row_of(pc)["store"] == "private"
    job = pc.db.execute(
        "select payload,status from app.jobs where kind='copy_creature_portrait' and dedupe_key=%s",
        (f"copy-portrait:{generation['generation_id']}",),
    ).fetchone()
    assert job and job["status"] == "queued" and job["payload"]["portrait_key"] == pc.key


def test_sweeper_requeues_old_private_rows(pc):
    from services.creature_portraits import sweep_private_portraits

    generation = confirm(pc, issue_monster(pc))
    pc.db.execute(
        """update app.creature_portraits set status='ready',store='private',
        object_keys='{"thumb":"users/x/y.webp"}'::jsonb,updated_at=now()-interval '2 hours'
        where portrait_key=%s""",
        (pc.key,),
    )
    assert sweep_private_portraits(pc.pool)["private_requeued"] >= 1
    assert pc.db.execute(
        "select 1 from app.jobs where kind='copy_creature_portrait' and dedupe_key like %s",
        (f"copy-portrait:{generation['generation_id']}:sweep:%",),
    ).fetchone()


def test_erase_owner_drops_unpromoted_pool_rows_and_frees_key(pc):
    held = _pool_entry(pc, "held")
    promoted = _pool_entry(pc, "promoted")
    k_held, k_promoted = f"tipo:bst:{held}", f"tipo:bst:{promoted}"
    _insert_ready(
        pc,
        k_held,
        visibility="pool",
        origin_game=pc.game_id,
        pool_entry=held,
        thumb="shared/creatures/ab/h.webp",
    )
    _insert_ready(pc, k_promoted, visibility="pool", origin_game=pc.game_id, pool_entry=promoted)
    keys = PostgresPortraitRegistry.erase_owner(pc.db, pc.owner.user_id)
    assert "shared/creatures/ab/h.webp" in keys
    assert row_of(pc, k_held) is None  # chave livre para nova cotação
    kept = row_of(pc, k_promoted)
    assert kept["status"] == "ready" and kept["origin_owner_id"] is None
