"""SPEC-192: offline logic of the staging evidence scripts (fakes, no network)."""
from scripts.staging import (account_deletion_recovery as adr, e2e_session as e2e, job_survival as js,
                             preview_isolation as pi, s192, schedule_cron as sc, verify_cron as vc)


def test_parse_sse_skips_pings_and_decodes_json():
    lines = ["event: accepted", 'data: {"game_id": "g"}', "", ": ping", "", "event: narrative",
             'data: {"chunk": "", "done": true}', ""]
    ev = s192.parse_sse(lines)
    assert [e["event"] for e in ev] == ["accepted", "narrative"]
    assert ev[1]["data"]["done"] is True
    assert s192.sequence_summary(ev + ev[1:]) == ["accepted", "narrative"]


def test_cookie_flags_and_bearer_scan():
    flags = s192.cookie_flags([
        "rpg_access=abc; Path=/; HttpOnly; Secure; SameSite=lax",
        "rpg_csrf=x; Path=/; Secure; SameSite=strict",
        "rpg_deletion=; Max-Age=0; Path=/account/delete"])
    assert flags["rpg_access"] == {"secure": True, "httponly": True, "samesite": "lax", "path": "/", "deleted": False}
    assert not flags["rpg_csrf"]["httponly"] and flags["rpg_deletion"]["deleted"]
    assert s192.json_has_bearer({"a": "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4eHh4In0.sig"}, [])
    assert s192.json_has_bearer({"a": "tok-12345"}, ["tok-12345"])
    assert not s192.json_has_bearer({"csrf_token": "abc.def"}, ["zzz"])


def test_percentiles():
    assert s192.pct([], 95) is None
    assert s192.pct([10, 20, 30, 40, 50], 95) == 50
    assert s192.stats([1, 2, 3])["p50_ms"] == 2


def _events(turn):
    return [{"event": "accepted", "data": {}}, {"event": "narrative", "data": {"chunk": "abc", "done": False}},
            {"event": "narrative", "data": {"chunk": "", "done": True}},
            {"event": "state", "data": {"world": {"turn_count": turn}, "continuity": {"session_action_count": 1}}}]


def test_stream_summary_and_turn_increment_rule():
    turns = [e2e.summarize_stream(_events(n), 200, 10, 20) for n in (2, 3, 4, 5, 6)]
    assert e2e.turns_ok(turns, 1)
    dup = turns[:2] + [turns[1]] + turns[3:]
    assert not e2e.turns_ok(dup, 1)
    err = e2e.summarize_stream([{"event": "error", "data": {}}], 200, 1, 1)
    assert err["has_error"] and not e2e.turns_ok([err], 0)


def test_preview_helpers():
    assert pi.parse_deploy_url('{"url": "https://rpg-ia-master-staging-abc.vercel.app"}').endswith("abc.vercel.app")
    envs = [{"key": "DATABASE_URL", "target": ["production"]}, {"key": "RPG_FORCE_MOCK", "target": ["preview"]}]
    assert pi.preview_env_leaks(envs) == []
    assert pi.preview_env_leaks(envs + [{"key": "DATABASE_URL", "target": ["preview"]}]) == ["DATABASE_URL"]
    assert pi.fails_closed(500, "Internal Server Error") and not pi.fails_closed(200, '{"authenticated": false}')
    out = "HTTP/1.1 503 Service Unavailable\r\nX: y\r\n\r\n{\"detail\":\"cron_not_configured\"}"
    assert pi.parse_curl_i(out) == {"status": 503, "body": '{"detail":"cron_not_configured"}'}


class FakeConn:
    def __init__(self, secret_exists):
        self.secret_exists, self.sql = secret_exists, []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        conn = self

        class R:
            def fetchone(self):
                if "from vault.secrets" in sql:
                    return {"id": "sid"} if conn.secret_exists else None
                if "cron.schedule" in sql:
                    return {"jobid": 7}

            def fetchall(self):
                return [{"extname": "pg_cron", "extversion": "1"}]
        return R()


def test_schedule_is_idempotent_and_keeps_secret_out_of_command():
    plans = sc.plan("https://x.example/")
    assert [p[0] for p in plans] == ["rpg-cron-jobs", "rpg-cron-account-deletions", "rpg-cron-operations",
                                        "rpg-cron-reconciliation", "rpg-cron-finops", "rpg-cron-health"]
    assert all("SECRETVALUE" not in p[2] for p in plans)
    assert all("https://x.example/internal/cron/" in p[2] and "app.cron_requests" in p[2] for p in plans[:5])
    assert plans[5][2] == "select app.cron_health_check()"
    assert "vault.decrypted_secrets" in plans[0][2]
    for exists, verb in ((False, "create_secret"), (True, "update_secret")):
        c = FakeConn(exists)
        res = sc.apply(c, "https://x.example", "SECRETVALUE")
        text = " ".join(s for s, _ in c.sql)
        assert verb in text and res["vault"] == ("updated" if exists else "created")
        assert text.count("cron.unschedule") == 6 and text.count("cron.schedule") == 6
        assert not any("SECRETVALUE" in str(p) for s, p in c.sql if "cron.schedule" in s)


def test_recovery_and_exactly_once_predicates():
    clean = {"private_rows": {}, "sessions": 0, "storage_objects": 0, "auth_user": 0}
    assert adr.recovered(clean, "deleted")
    assert not adr.recovered({**clean, "private_rows": {"games": 1}}, "deleted")
    assert not adr.recovered(clean, "deleting")
    ok = {"status": "succeeded", "leased": False, "documents": 1, "embedding_status": "ready", "jobs_for_doc": 1, "attempts": 1}
    assert js.exactly_once(ok) and js.exactly_once({**ok, "attempts": 2})
    assert not js.exactly_once({**ok, "attempts": 3}) and not js.exactly_once({**ok, "jobs_for_doc": 2})
    assert not js.exactly_once({**ok, "embedding_status": "pending"})


def test_cron_response_summary_exposes_failures_hidden_in_2xx():
    rows = [{"status_code": 200, "content": '{"ok":true}'}, {"status_code": 200, "content": '{"ok":false,"failed":1}'},
            {"status_code": 401, "content": "x"}]
    s = vc.summarize_responses(rows)
    assert s == {"n": 3, "by_status": {"200": 2, "401": 1}, "ok_false_in_2xx_body": 1}


def test_measure_bundle_parser_and_log_message():
    from scripts.staging import measure
    assert measure.bundle_mb_from_events(["Lambda bundle size 314,51 MB", "unrelated 5 MB", "function: 12.5 MB"]) == [314.51, 12.5]
    line = '{"type":"log","data":{"level":"error","message":"rpg.cron failed"}}'
    assert adr.log_message(line) == "error rpg.cron failed"


def test_sse_disconnect_exactly_one_turn_predicate():
    from scripts.staging.sse_disconnect import exactly_one_turn
    assert exactly_one_turn(0, 0, 1) and exactly_one_turn(0, 1, 1)
    assert not exactly_one_turn(0, 1, 2) and not exactly_one_turn(0, 0, 0)
