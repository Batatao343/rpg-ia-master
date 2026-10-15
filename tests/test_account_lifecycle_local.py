"""SPEC-190 real PostgreSQL ownership, retention, revocation and publication gates.

Canonical migrations and all synthetic rows roll back. Storage/Auth network is
replaced at the transport boundary; local Supabase table schemas remain real.
"""
from contextlib import nullcontext
import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from infrastructure.account_lifecycle import PRIVATE_TABLES, PostgresAccountLifecycle
from infrastructure.contracts import Principal, Unauthorized
from infrastructure.supabase_identity import SupabaseIdentityProvider
from infrastructure.wallet import PostgresWallet

pytestmark = pytest.mark.infra_local


@pytest.fixture
def deletion_case():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL absent")
    with psycopg.connect(dsn,row_factory=dict_row) as db:
        try:
            for table,name in (("image_quotes","20261012160000_image_quotes.sql"),
                               ("payment_orders","20261013120000_stripe_checkout.sql"),
                               ("account_deletions","20261013173632_account_lifecycle.sql")):
                if db.execute("select to_regclass(%s) t",(f"app.{table}",)).fetchone()["t"] is None:
                    db.execute(Path("supabase/migrations",name).read_text(encoding="utf-8"))
            class Pool:
                def connection(self): return nullcontext(db)
            pool = Pool()
            a,b = uuid4(),uuid4()
            owners = [Principal(owner,"test",str(owner)) for owner in (a,b)]
            games,sessions,keys = [],[],[]
            for owner in owners:
                game,session,operation,job = (uuid4() for _ in range(4))
                key = f"users/{owner.user_id}/games/{game}/orphan.webp"
                games.append(game); sessions.append(session); keys.append(key)
                db.execute("insert into auth.users(id,email) values(%s,%s)",(owner.user_id,f"{owner.user_id}@example.test"))
                db.execute("insert into auth.sessions(id,user_id) values(%s,%s)",(session,owner.user_id))
                db.execute("""insert into app.games(id,owner_id,schema_version,state,state_sha256,status,
                    player_name,class_name,player_level,location_name,world_day,game_over,combat_simulation)
                    values(%s,%s,1,%s,%s,'active','private-name','Devoto',1,'Porto',1,false,false)""",
                    (game,owner.user_id,Jsonb({"game_id":str(game),"private":"secret"}),"a"*64))
                db.execute("""insert into app.operations(id,owner_id,game_id,kind,status,request_sha256,receipt)
                    values(%s,%s,%s,'turn','completed',%s,%s)""",(operation,owner.user_id,game,"a"*64,Jsonb({"private":"turn"})))
                db.execute("""insert into app.jobs(id,owner_id,game_id,kind,dedupe_key,status,payload,max_attempts,lease_token,lease_owner,lease_until)
                    values(%s,%s,%s,'dynamic_art',%s,'running',%s,3,%s,'worker',now()+interval '10 minutes')""",
                    (job,owner.user_id,game,str(uuid4()),Jsonb({"private":"prompt"}),uuid4()))
                db.execute("""insert into app.memory_documents(id,owner_id,game_id,scope,content,content_sha256)
                    values(%s,%s,%s,'session','private memory',%s)""",(str(uuid4()),owner.user_id,game,"a"*64))
                db.execute("insert into storage.objects(bucket_id,name) values('rpg-dynamic',%s)",(key,))
            calls=[]
            class Blobs:
                bucket="rpg-dynamic"
                fail=False
                def delete(self,key):
                    calls.append(("blob",key))
                    assert db.execute("select 1 from auth.sessions where user_id=%s",(a,)).fetchone() is None
                    if self.fail:return False
                    # Emulate Storage transport's controlled delete transaction.
                    db.execute("select set_config('storage.allow_delete_query','true',true)")
                    db.execute("delete from storage.objects where bucket_id='rpg-dynamic' and name=%s",(key,))
                    return True
            class Identity:
                def delete_user(self,owner):
                    assert db.execute("select 1 from auth.sessions where user_id=%s",(owner,)).fetchone() is None
                    assert not db.execute("select 1 from app.games where owner_id=%s",(owner,)).fetchone()
                    calls.append(("auth",owner))
                    db.execute("delete from auth.users where id=%s",(owner,))
            blobs=Blobs()
            lifecycle=PostgresAccountLifecycle(pool,Identity(),blobs)
            yield SimpleNamespace(db=db,pool=pool,a=owners[0],b=owners[1],games=games,sessions=sessions,keys=keys,
                                  calls=calls,blobs=blobs,lifecycle=lifecycle)
        finally:db.rollback()


def test_erasure_revokes_before_cleanup_fences_running_jobs_and_preserves_b(deletion_case):
    c=deletion_case
    export=c.lifecycle.export(c.a)
    assert export["owner_id"]==str(c.a.user_id)
    assert all(str(row["owner_id"])==str(c.a.user_id) for rows in export["data"].values() for row in rows)
    c.lifecycle.begin(c.a.user_id)
    assert not c.db.execute("select 1 from auth.sessions where user_id=%s",(c.a.user_id,)).fetchone()
    job=c.db.execute("select * from app.jobs where owner_id=%s",(c.a.user_id,)).fetchone()
    assert job["status"]=="cancelled" and job["lease_token"] is None and job["payload"]=={}
    c.blobs.fail=True
    assert c.lifecycle.finish(c.a.user_id)=="deleting"
    assert not c.db.execute("select 1 from app.games where owner_id=%s",(c.a.user_id,)).fetchone()
    assert not c.db.execute("select 1 from auth.users where id=%s",(c.a.user_id,)).fetchone()
    assert c.db.execute("select 1 from storage.objects where name=%s",(c.keys[0],)).fetchone()
    c.blobs.fail=False
    assert c.lifecycle.delete(c.a.user_id)=="deleted"
    assert c.lifecycle.delete(c.a.user_id)=="deleted"
    for table in PRIVATE_TABLES:
        assert not c.db.execute(f"select 1 from app.{table} where owner_id=%s",(c.a.user_id,)).fetchone()
    assert c.db.execute("select name from storage.objects where name=%s",(c.keys[1],)).fetchone()
    assert c.db.execute("select id from auth.sessions where id=%s",(c.sessions[1],)).fetchone()
    assert c.lifecycle.export(c.b)["data"]["games"][0]["id"]==c.games[1]
    with pytest.raises(Unauthorized):c.lifecycle.export(c.a)


def test_tombstone_denies_private_and_service_role_late_storage_publication(deletion_case):
    import psycopg
    c=deletion_case
    c.lifecycle.begin(c.a.user_id)
    for statement,args in (
        ("insert into storage.objects(bucket_id,name) values('rpg-dynamic',%s)",(f"users/{c.a.user_id}/late.webp",)),
        ("update app.games set player_name='late' where owner_id=%s",(c.a.user_id,)),
        ("update app.jobs set status='succeeded',result='{}' where owner_id=%s",(c.a.user_id,))):
        with pytest.raises(psycopg.errors.InsufficientPrivilege),c.db.transaction():
            c.db.execute(statement,args)
    # The DB trigger runs even for a privileged service_role which bypasses RLS.
    with pytest.raises(psycopg.errors.InsufficientPrivilege),c.db.transaction():
        c.db.execute("set local role service_role")
        c.db.execute("insert into storage.objects(bucket_id,name) values('rpg-dynamic',%s)",(f"users/{c.a.user_id}/late-service.webp",))


def test_tombstone_fences_late_usage_event_write(deletion_case):
    import psycopg
    c = deletion_case
    operation = c.db.execute("select id,game_id from app.operations where owner_id=%s",
                             (c.a.user_id,)).fetchone()
    c.lifecycle.begin(c.a.user_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege), c.db.transaction():
        c.db.execute("""insert into app.usage_events
            (event_id,operation_id,owner_id,game_id,component,attempt_ordinal,category,provider,
             model,outcome,cost_usd,cost_basis,pricing_version,billing_exact,event_sha256)
            values (%s,%s,%s,%s,'late',0,'llm','test','test','completed',0,'estimated',
                'test',false,%s)""",
            (uuid4(), operation["id"], c.a.user_id, operation["game_id"], "a" * 64))


def test_stale_jwt_denied_in_backend_direct_wallet_and_storage(deletion_case,monkeypatch):
    c=deletion_case
    def token(owner,session):
        encoded=base64.urlsafe_b64encode(json.dumps({"session_id":str(session)}).encode()).decode().rstrip("=")
        return f"header.{encoded}.signature"
    provider=SupabaseIdentityProvider("http://auth.test","publishable",pool=c.pool)
    monkeypatch.setattr(httpx,"get",lambda *_args,**_kw: httpx.Response(200,json={"id":str(c.a.user_id)}))
    assert provider.verify(token(c.a.user_id,c.sessions[0])).user_id==c.a.user_id
    c.lifecycle.begin(c.a.user_id)
    with pytest.raises(Unauthorized):provider.verify(token(c.a.user_id,c.sessions[0]))
    with c.db.transaction():
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)",(str(c.a.user_id),))
        c.db.execute("select set_config('request.jwt.claims',%s,true)",
                     (json.dumps({"sub":str(c.a.user_id),"session_id":str(c.sessions[0]),"role":"authenticated"}),))
        c.db.execute("set local role authenticated")
        assert c.db.execute("select * from public.rpg_wallet_balance()").fetchall()==[]
        assert c.db.execute("select 1 from storage.objects where name=%s",(c.keys[0],)).fetchall()==[]
        c.db.execute("reset role")
    with c.db.transaction():
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)",(str(c.a.user_id),))
        c.db.execute("set local role rpg_api")
        assert c.db.execute("select * from app.games").fetchall()==[]
        c.db.execute("reset role")
    c.db.execute("insert into app.wallet_accounts(owner_id) values(%s)",(c.b.user_id,))
    with c.db.transaction():
        c.db.execute("select set_config('request.jwt.claim.sub',%s,true)",(str(c.b.user_id),))
        c.db.execute("select set_config('request.jwt.claims',%s,true)",
                     (json.dumps({"sub":str(c.b.user_id),"session_id":str(c.sessions[1]),"role":"authenticated"}),))
        c.db.execute("set local role authenticated")
        assert len(c.db.execute("select * from public.rpg_wallet_balance()").fetchall())==1
        assert c.db.execute("select 1 from storage.objects where name=%s",(c.keys[1],)).fetchone()
        c.db.execute("reset role")


def test_financial_facts_survive_erasure_without_granting_signup_credit(deletion_case):
    c=deletion_case
    wallet=PostgresWallet(c.pool)
    assert wallet.balance(c.a).available_milli==0
    assert not c.db.execute("select 1 from app.wallet_entries where owner_id=%s",(c.a.user_id,)).fetchone()
    wallet.adjust_admin(c.a,adjustment_id=str(uuid4()),signed_milli=200,actor_id=uuid4(),reason="Synthetic paid-balance retention fixture")
    before=c.db.execute("select * from app.wallet_entries where owner_id=%s",(c.a.user_id,)).fetchall()
    assert c.lifecycle.delete(c.a.user_id)=="deleted"
    assert c.db.execute("select * from app.wallet_entries where owner_id=%s",(c.a.user_id,)).fetchall()==before
    assert wallet.balance(c.a).available_milli==200


def test_deletion_removes_address_derived_auth_rate_buckets(deletion_case):
    from services.account_security import auth_email_bucket_keys
    c=deletion_case
    email=f"{c.a.user_id}@example.test"
    keys=auth_email_bucket_keys(email)
    for key in keys:
        c.db.execute("""insert into app.rate_limit_buckets
            (bucket_key,window_started_at,window_seconds,request_count)
            values (%s,now(),900,1)""",(key,))
    c.lifecycle.begin(c.a.user_id)
    assert not c.db.execute("select 1 from app.rate_limit_buckets where bucket_key=any(%s)",
                            (list(keys),)).fetchone()


def test_recovery_batch_rotates_failed_tombstone_before_next_claim(deletion_case):
    from scripts.recover_account_deletions import claim_pending
    c=deletion_case
    c.lifecycle.begin(c.a.user_id)
    c.lifecycle.begin(c.b.user_id)
    c.db.execute("""update app.account_deletions set recovery_attempted_at=now()-interval '1 day'
        where owner_id=%s""",(c.a.user_id,))
    assert claim_pending(c.pool,1)[0]["owner_id"]==c.a.user_id
    assert claim_pending(c.pool,1)[0]["owner_id"]==c.b.user_id
