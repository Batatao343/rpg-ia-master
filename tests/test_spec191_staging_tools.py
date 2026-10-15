"""SPEC-191 staging tooling: offline unit tests (fakes only, no network/DB)."""

from __future__ import annotations

from pathlib import Path
import json

import httpx
import pytest

from scripts.staging import auth_config, backup_restore, common, migrations, smoke_ab, synthetic_data

REF = "abcdefghijklmnopqrst"


def test_guard_requires_matching_confirmation_and_denylist():
    env = {"SUPABASE_PROJECT_REF": REF}
    assert common.require_staging(REF, env) == REF
    for bad in (None, "", "other"):
        with pytest.raises(SystemExit):
            common.require_staging(bad, env)
    with pytest.raises(SystemExit):
        common.require_staging(REF, {})
    with pytest.raises(SystemExit):
        common.require_staging(REF, {**env, "RPG_PROTECTED_PROJECT_REFS": f"zzz, {REF}"})


def test_redaction_masks_secrets_emails_and_urls():
    out = common.redact({
        "service_role_key": "abc", "ok": True, "n": 3,
        "note": "user a@b.com dsn postgresql://postgres.x:hunter2@host:6543/db jwt eyJhbGciOiJI.eyJzdWIiOiIx.sig",
        "nested": [{"password": "p", "sb": "sb_secret_abc123"}],
    })
    dumped = json.dumps(out)
    for leaked in ("hunter2", "a@b.com", "eyJhbGci", "sb_secret_abc123", '"abc"'):
        assert leaked not in dumped
    assert out["ok"] is True and out["n"] == 3
    assert "email:" in out["note"]


def test_write_evidence_is_redacted(tmp_path):
    path = common.write_evidence("x", {"access_token": "t0k", "mail": "z@y.io"}, tmp_path / "e.json")
    text = path.read_text(encoding="utf-8")
    assert "t0k" not in text and "z@y.io" not in text


def _env():
    return {"SUPABASE_ACCESS_TOKEN": "tok", "RPG_STAGING_SITE_URL": "https://stg.example.app",
            "RPG_STAGING_REDIRECT_URLS": "https://stg.example.app/a, https://stg.example.app/b",
            "RPG_STAGING_TURNSTILE_SECRET": "real-secret"}


def test_desired_config_and_turnstile_test_key_gate():
    cfg = auth_config.desired_config(_env())
    assert cfg["mailer_autoconfirm"] is False and cfg["security_captcha_provider"] == "turnstile"
    assert cfg["uri_allow_list"] == "https://stg.example.app/a,https://stg.example.app/b"
    assert set(auth_config.RATE_LIMITS) <= set(cfg)
    env = {k: v for k, v in _env().items() if k != "RPG_STAGING_TURNSTILE_SECRET"}
    with pytest.raises(SystemExit):
        auth_config.desired_config(env)
    assert auth_config.desired_config(env, True)["security_captcha_secret"] == auth_config.TURNSTILE_TEST_SECRET


def test_auth_config_plan_and_apply_payload():
    state = {"mailer_autoconfirm": True, "site_url": "https://stg.example.app"}
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"] == "Bearer tok"
        if request.method == "PATCH":
            body = json.loads(request.content)
            state.update({k: v for k, v in body.items() if k != "security_captcha_secret"})
        return httpx.Response(200, json=state)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    plan = auth_config.run("plan", REF, _env(), client)
    assert not plan["applied"] and "site_url" not in plan["diff"]
    assert plan["diff"]["mailer_autoconfirm"] == {"from": True, "to": False}
    assert "real-secret" not in json.dumps(plan)
    assert [c.method for c in calls] == ["GET"]
    applied = auth_config.run("apply", REF, _env(), client)
    patch = json.loads([c for c in calls if c.method == "PATCH"][0].content)
    assert patch["security_captcha_enabled"] is True and patch["security_captcha_secret"] == "real-secret"
    assert applied["applied"] and applied["verified"]
    assert "real-secret" not in json.dumps(applied)


def _loc(*pairs):
    return [{"version": v, "name": n, "path": None} for v, n in pairs]


def test_migration_repair_plan():
    local = _loc(("20260101000001", "a"), ("20260101000002", "b"), ("20260101000003", "c"))
    remote = [{"version": "20261014150000", "name": "a"}, {"version": "20261014150001", "name": "b"},
              {"version": "20260101000009", "name": "ghost"}]
    plan = migrations.plan_repair(local, remote)
    assert plan["renames"] == [{"name": "a", "from": "20261014150000", "to": "20260101000001"},
                               {"name": "b", "from": "20261014150001", "to": "20260101000002"}]
    assert plan["pending"] == ["20260101000003"] and plan["remote_only"] == ["20260101000009"]
    synced = [{"version": r["version"], "name": r["name"]} for r in local]
    assert migrations.plan_status(local, synced)["in_sync"] is True
    assert migrations.plan_repair(local, synced)["renames"] == []


def test_migration_apply_repair_and_push_with_fake_conn(tmp_path):
    executed = []

    class Cur:
        def execute(self, sql, params=None):
            executed.append((" ".join(sql.split())[:40], params))

    migrations.apply_repair(Cur(), [{"name": "a", "from": "1", "to": "2"}])
    assert executed[0][1] == ("2", "1", "a")

    class Tx:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class Conn(Cur):
        def transaction(self): return Tx()

    f = tmp_path / "20260101000003_c.sql"
    f.write_text("select 1;", encoding="utf-8")
    local = [{"version": "20260101000003", "name": "c", "path": f}]
    executed.clear()
    assert migrations.apply_push(Conn(), local, ["20260101000003"]) == ["20260101000003"]
    assert executed[1][1] == ("20260101000003", ["select 1;"], "c")


def test_real_local_migrations_parse():
    rows = migrations.local_migrations()
    assert rows and all(len(r["version"]) == 14 for r in rows)


def test_smoke_aggregation_and_latency():
    ok = {"rls": {"ok": True}, "wallet": {"ok": False, "pending_migration": True}}
    assert smoke_ab.aggregate(ok) == {"ok": True, "failed": [], "pending_migration": ["wallet"]}
    bad = smoke_ab.aggregate({"rls": {"ok": False}, "x": {"ok": True}})
    assert not bad["ok"] and bad["failed"] == ["rls"]
    assert not smoke_ab.aggregate({})["ok"]
    summary = smoke_ab.latency_summary([10.0, 20.0, 30.0, 40.0], 1)
    assert summary["p50_ms"] == 20.0 and summary["p95_ms"] == 40.0 and summary["errors"] == 1


def test_smoke_auth_captcha_check_with_mock_transport():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert "captcha_token" not in request.content.decode()
        return httpx.Response(400, json={"msg": "captcha verification process failed"})

    ctx = smoke_ab.Ctx({"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "s",
                        "SUPABASE_PUBLISHABLE_KEY": "p", "DATABASE_URL": "postgresql://u:p@h/db"},
                       httpx.Client(transport=httpx.MockTransport(handler)))
    res = smoke_ab.check_auth_captcha(ctx)
    assert res["ok"] and seen == ["/auth/v1/signup", "/auth/v1/recover", "/auth/v1/resend"]


def test_backup_compare_state_and_disposable_guard(tmp_path):
    exp = {"row_counts": {"app.games": 2}, "objects": {"users/a/x.txt": "h1", "users/b/y.txt": "h2"}}
    assert backup_restore.compare_state(exp, {"app.games": 2}, {"users/a/x.txt": "h1", "users/b/y.txt": "h2"})["ok"]
    bad = backup_restore.compare_state(exp, {"app.games": 1}, {"users/a/x.txt": "zz", "extra": "e"})
    assert not bad["ok"] and bad["row_mismatch"]["app.games"]["actual"] == 1
    assert bad["objects_missing"] == ["users/b/y.txt"] and bad["objects_extra"] == ["extra"]
    assert bad["objects_hash_mismatch"] == ["users/a/x.txt"]
    backup_restore.assert_disposable("postgresql://u:p@127.0.0.1:5432/db", True)
    with pytest.raises(SystemExit):
        backup_restore.assert_disposable("postgresql://u:p@127.0.0.1/db", False)
    with pytest.raises(SystemExit):
        backup_restore.assert_disposable("postgresql://u:p@db.abc.supabase.co/postgres", True)
    obj = tmp_path / "objects" / backup_restore.BUCKET / "u"
    obj.mkdir(parents=True)
    (obj / "f.txt").write_bytes(b"hi")
    assert list(backup_restore.object_hashes(tmp_path)) == ["u/f.txt"]


def test_storage_object_listing_recurses():
    def handler(request: httpx.Request) -> httpx.Response:
        prefix = json.loads(request.content)["prefix"]
        rows = {"": [{"name": "users", "id": None}], "users/": [{"name": "f.txt", "id": "1"}]}[prefix]
        return httpx.Response(200, json=rows)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert backup_restore.list_objects(client, "https://x.supabase.co", {}) == ["users/f.txt"]


def test_synthetic_manifest_has_no_secrets():
    m = synthetic_data.build_manifest([{"id": "u", "game_id": "g", "memory_doc": "d", "objects": ["users/u/a.webp"],
                                        "email": "x@example.invalid", "password": "p"}])
    assert "email" not in str(m) and "password" not in str(m) and m["users"][0]["objects"] == ["users/u/a.webp"]


def test_restore_refuses_remote_target_or_unconfirmed():
    import pytest
    with pytest.raises(SystemExit):
        backup_restore.restore(Path("."), "postgresql://x@db.example.com/postgres", Path("."), True, {})
    with pytest.raises(SystemExit):
        backup_restore.restore(Path("."), "postgresql://x@127.0.0.1/postgres", Path("."), False, {})


def test_assert_ref_in_requires_every_target():
    common.assert_ref_in(REF, A=f"https://{REF}.supabase.co", B=f"postgres://u@db.{REF}.supabase.co/db")
    with pytest.raises(SystemExit):
        common.assert_ref_in(REF, A=f"https://{REF}.supabase.co", B="postgres://u@other.x/db")
    with pytest.raises(SystemExit):
        common.assert_ref_in(REF, A="")


def test_split_dsn_password_removes_secret_from_dsn():
    clean, pw = common.split_dsn_password(f"postgresql://postgres.{REF}:p%40ss@host.example:6543/postgres?sslmode=require")
    assert pw == "p@ss" and "p%40ss" not in clean and "p@ss" not in clean
    assert clean == f"postgresql://postgres.{REF}@host.example:6543/postgres?sslmode=require"
    assert common.split_dsn_password("postgresql://u@h/db") == ("postgresql://u@h/db", None)


@pytest.mark.parametrize("have_pg_dump", [True, False])
def test_dump_command_never_puts_password_on_argv(have_pg_dump):
    cmd, env = backup_restore._dump_command(f"postgresql://postgres.{REF}:s3cr3t@h:5432/postgres", ["--schema", "app"],
                                            have_pg_dump)
    assert "s3cr3t" not in " ".join(cmd)
    assert env["PGPASSWORD"] == "s3cr3t"


def test_synthetic_and_backup_main_reject_wrong_project_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_PROJECT_REF", REF)
    monkeypatch.setenv("SUPABASE_URL", "https://zzzzzzzzzzzzzzzzzzzz.supabase.co")
    monkeypatch.setenv("RPG_STAGING_DB_URL", f"postgresql://postgres.{REF}:x@h/db")
    monkeypatch.setattr(common, "load_dotenv_quietly", lambda: None)
    with pytest.raises(SystemExit):
        synthetic_data.main(["seed", "--confirm-staging", REF])
    with pytest.raises(SystemExit):
        backup_restore.main(["export", "--confirm-staging", REF, "x"])


def test_schema_diff_pure_helpers():
    from scripts.staging import schema_diff
    snap = {"tables": ["app.a", "app.google_play_purchases"], "grants": ["x"]}
    keep, excl = schema_diff.split_pending(snap, ("google_play",))
    assert keep["tables"] == ["app.a"] and excl == {"tables": ["app.google_play_purchases"]}
    d = schema_diff.diff({"t": ["a", "b"]}, {"t": ["a", "c"]})
    assert d == {"t": {"only_staging": ["b"], "only_local": ["c"]}}
    assert schema_diff.diff({"t": ["a"]}, {"t": ["a"]}) == {}


def test_assert_ref_in_is_strict_not_substring():
    pooler = f"postgresql://postgres.{REF}:x@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
    common.assert_ref_in(REF, U=f"https://{REF}.supabase.co", D=pooler)
    for evil in (f"https://evil.example/{REF}", f"https://{REF}.evil.com", f"https://x{REF}.supabase.co",
                 f"postgres://u@evil.example/{REF}", f"postgres://postgres.{REF}x@h/db",
                 f"https://notasupabase.co/?r={REF}", f"postgres://a.b.{REF}@h/db"):
        with pytest.raises(SystemExit):
            common.assert_ref_in(REF, T=evil)


def _rows(connects, errors=()):
    rows = [{"connect": c, "query": 5.0, "total": c + 5.0, "ssl": True, "peer": "1.1.1.1"} for c in connects]
    rows += [{"error": True, "error_type": "ConnectionTimeout", "total": t, "peer": "2.2.2.2"} for t in errors]
    return rows


def test_pooler_stats_and_criterion():
    good = smoke_ab.pooler_stats(_rows([40.0] * 49 + [3100.0]), 3)
    assert good["failovers"] == 1 and good["slow_connects"] == 1 and good["errors"] == 0
    assert good["peers"] == {"1.1.1.1": 50}
    assert smoke_ab.pooler_ok(good, 3)  # p95 stays low, max 3.1s < 2*3+1
    too_slow = smoke_ab.pooler_stats(_rows([40.0] * 40 + [1500.0] * 10), 3)
    assert not smoke_ab.pooler_ok(too_slow, 3)  # p95 >= 1000
    unbounded = smoke_ab.pooler_stats(_rows([40.0] * 99 + [15000.0]), 3)
    assert not smoke_ab.pooler_ok(unbounded, 3)  # max >= 7s
    assert not smoke_ab.pooler_ok(smoke_ab.pooler_stats(_rows([40.0] * 9, errors=[5000.0]), 3), 3)
    assert not smoke_ab.pooler_ok(smoke_ab.pooler_stats([], 3), 3)


def test_per_ip_summary_counts_stalls():
    summary = smoke_ab.per_ip_summary(_rows([30.0] * 7, errors=[5001.0, 5002.0, 12.0]), 5)
    assert summary["n"] == 10 and summary["errors"] == 3 and summary["timeouts"] == 2
    assert summary["timeout_rate"] == 0.2 and summary["error_types"] == ["ConnectionTimeout"]
