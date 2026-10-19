"""Pause the real image worker at provider return; deletion wins before put."""
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from infrastructure.account_lifecycle import PostgresAccountLifecycle
from infrastructure.contracts import Unauthorized
from infrastructure.supabase_blob import SupabaseBlobStore
from services.job_fence import job_scope
from tests.fakes.fake_image_generator import FakeImageGenerator
from tests.test_image_quotes_local import confirm, image_case, issue, lease
from workers.dynamic_art_jobs import generate_dynamic_art_job


def test_leased_image_worker_cannot_upload_after_account_erasure(image_case,monkeypatch):
    c=image_case
    c.db.execute(Path("supabase/migrations/20261013120000_stripe_checkout.sql").read_text(encoding="utf-8"))
    c.db.execute(Path("supabase/migrations/20261013173632_account_lifecycle.sql").read_text(encoding="utf-8"))
    lifecycle=PostgresAccountLifecycle(c.pool,SimpleNamespace(delete_user=lambda _id:None),
                                      SimpleNamespace(bucket="rpg-dynamic",delete=lambda _key:True))
    generation=confirm(c,issue(c)); job=lease(c,generation)
    class Generator(FakeImageGenerator):
        def generate(self,request):
            result=super().generate(request)
            assert lifecycle.delete(c.owner.user_id)=="deleted"
            return result
    def network_forbidden(*_args,**_kwargs):
        raise AssertionError("late worker attempted Storage upload")
    monkeypatch.setattr(httpx,"post",network_forbidden)
    with job_scope(job),pytest.raises(Unauthorized,match="account_deleted"):
        generate_dynamic_art_job(generator=Generator(),blob_store=SupabaseBlobStore("http://storage.test","secret",pool=c.pool),
            generation={},owner_id=c.owner.user_id,game_id=c.game_id,asset_id=UUID(job.request.payload["asset_id"]),
            admission=lambda:c.repo.dispatch(generation["generation_id"],c.owner.user_id,c.game_id))
    assert not c.db.execute("select 1 from app.art_generations where owner_id=%s",(c.owner.user_id,)).fetchone()
    # External effect began; immutable financial dispatch fact/hold survives for reconciliation.
    assert c.db.execute("select 1 from app.wallet_attempt_tickets where owner_id=%s",(c.owner.user_id,)).fetchone()
    assert c.repo.wallet.balance(c.owner).reserved_milli==4
