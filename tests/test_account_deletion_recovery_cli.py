"""Operator recovery cannot turn a preview into a fresh account deletion."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest

from scripts import recover_account_deletions as cli


def test_apply_requires_matching_owner_confirmation(monkeypatch):
    owner = uuid4()
    monkeypatch.setattr(sys, "argv", ["recover_account_deletions", "--owner", str(owner), "--apply"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2


def test_preview_is_read_only_and_apply_requires_existing_tombstone(monkeypatch, capsys):
    owner = uuid4()
    calls = []

    class DB:
        def execute(self, statement, params=()):
            calls.append((statement, params))
            return self

        def fetchall(self):
            return []

    class Pool:
        def connection(self):
            return nullcontext(DB())

        def close(self):
            calls.append(("close", ()))

    runtime = SimpleNamespace(game_store=SimpleNamespace(pool=Pool()), resources=(Pool(),),
                              identity_verifier=object(), blob_store=object())
    monkeypatch.setattr(cli.RuntimeConfig, "from_env", lambda: SimpleNamespace(profile="hosted-supabase"))
    monkeypatch.setattr(cli, "build_runtime", lambda _config: runtime)
    monkeypatch.setattr(sys, "argv", ["recover_account_deletions", "--owner", str(owner)])
    assert cli.main() == 0
    assert '"deletions": []' in capsys.readouterr().out
    assert all(statement.lstrip().lower().startswith("select") or statement == "close"
               for statement, _ in calls)
    monkeypatch.setattr(sys, "argv", ["recover_account_deletions", "--owner", str(owner),
                                  "--apply", "--confirm-owner", str(owner)])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2


def test_scheduled_batch_is_opt_in_bounded_and_resumes_only_tombstones(monkeypatch, capsys):
    owner=uuid4()
    calls=[]
    class DB:
        rowcount=3
        def execute(self, statement, params=()):
            calls.append((statement,params))
            return self
        def fetchall(self):
            return [{"owner_id":owner,"status":"deleting"}]
        def transaction(self):
            return nullcontext()
    class Pool:
        def connection(self): return nullcontext(DB())
        def close(self): pass
    pool=Pool()
    runtime=SimpleNamespace(game_store=SimpleNamespace(pool=pool),resources=(pool,),
                            identity_verifier=object(),blob_store=object())
    monkeypatch.setattr(cli.RuntimeConfig,"from_env",lambda: SimpleNamespace(profile="hosted-supabase"))
    monkeypatch.setattr(cli,"build_runtime",lambda _config: runtime)
    monkeypatch.setattr(sys,"argv",["recover_account_deletions","--batch","--apply","--max","2"])
    with pytest.raises(SystemExit) as denied:
        cli.main()
    assert denied.value.code==2
    monkeypatch.setenv("RPG_ACCOUNT_RECOVERY_BATCH","1")
    class Lifecycle:
        def __init__(self,*_args): pass
        def finish(self,value):
            assert value==owner
            return "deleted"
    monkeypatch.setattr(cli,"PostgresAccountLifecycle",Lifecycle)
    assert cli.main()==0
    assert '"auth_buckets_purged": 3' in capsys.readouterr().out
    assert any("limit %s" in statement and params==(2,) for statement,params in calls)
    assert not any("insert" in statement.lower() for statement,_ in calls)
