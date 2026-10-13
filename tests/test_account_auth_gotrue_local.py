"""Real local GoTrue generated signup/recovery links, without sending email."""
from contextlib import nullcontext
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from infrastructure.contracts import Unauthorized
from infrastructure.supabase_identity import SupabaseIdentityProvider

pytestmark=pytest.mark.infra_local


def test_local_gotrue_signup_verify_recovery_and_revoked_access():
    url=os.getenv("RPG_TEST_SUPABASE_URL","")
    public=os.getenv("RPG_TEST_SUPABASE_PUBLISHABLE","")
    secret=os.getenv("RPG_TEST_SUPABASE_SERVICE","")
    if not (url and public and secret):pytest.skip("local GoTrue credentials absent")
    # This test can never target staging/production or external SMTP.
    assert url=="http://127.0.0.1:55321"
    psycopg=pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    headers={"apikey":secret,"Authorization":f"Bearer {secret}"}
    email=f"spec190-{uuid4().hex}@example.test"
    owner=None
    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:55322/postgres",row_factory=dict_row) as db:
        try:
            # Full migration/RLS is tested separately in rollback. Keeping its
            # DDL locks while calling another DB client (GoTrue) blocks Auth.
            if db.execute("select to_regclass('app.account_deletions') t").fetchone()["t"] is None:
                sql=Path("supabase/migrations/20261013173632_account_lifecycle.sql").read_text(encoding="utf-8")
                db.execute(sql.partition("alter table app.account_deletions")[0])
            class Pool:
                def connection(self):return nullcontext(db)
            identity=SupabaseIdentityProvider(url,public,pool=Pool(),service_key=secret)
            link=httpx.post(url+"/auth/v1/admin/generate_link",headers=headers,
                            json={"type":"signup","email":email,"password":"old-password-spec190"},timeout=8)
            assert link.status_code==200
            payload=link.json()
            owner=payload["id"]
            tokens=identity.verify_email(payload["hashed_token"])
            assert identity.verify(tokens.access_token).user_id==tokens.user_id
            with pytest.raises(Unauthorized):identity.verify_email(payload["hashed_token"])
            recovery=httpx.post(url+"/auth/v1/admin/generate_link",headers=headers,
                                json={"type":"recovery","email":email},timeout=8)
            assert recovery.status_code==200
            identity.reset_password(recovery.json()["hashed_token"],"new-password-spec190")
            with pytest.raises(Unauthorized):identity.login(email,"old-password-spec190")
            with pytest.raises(Unauthorized):identity.verify(tokens.access_token)
            new=identity.login(email,"new-password-spec190")
            assert identity.verify(new.access_token).user_id==tokens.user_id
            identity.logout(new.access_token)
            with pytest.raises(Unauthorized):identity.verify(new.access_token)
        finally:
            db.rollback()
            if owner:
                result=httpx.delete(url+f"/auth/v1/admin/users/{owner}",headers=headers,timeout=8)
                assert result.status_code in (200,204,404)
