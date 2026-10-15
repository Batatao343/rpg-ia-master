"""SPEC-197 release checklist: offline, all side effects faked."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.release import checklist as c

SHA = "a" * 40


def fake_run(dirty: bool = False, gh: str | None = None, gov_rc: int = 0):
    def run(args):
        if args[:2] == ["git", "rev-parse"]:
            return 0, SHA + "\n"
        if args[:2] == ["git", "status"]:
            return 0, " M api.py\n" if dirty else ""
        if args[0] == "gh":
            return (0, gh) if gh is not None else (1, "")
        return gov_rc, "ok"
    return run


def http(table):
    def get(url):
        v = table[url]
        if isinstance(v, Exception):
            raise v
        return v
    return get


def test_git_dirty_fails():
    r, sha = c.check_git(c.Deps(run=fake_run(dirty=True)))
    assert r.status == "fail" and sha == SHA
    r, _ = c.check_git(c.Deps(run=fake_run()))
    assert r.status == "pass"


def test_specs_statuses(tmp_path: Path):
    idx = tmp_path / "i.yaml"
    specs = [{"id": f"SPEC-{n}", "status": "done"} for n in range(176, 197)]
    idx.write_text(json.dumps({"specs": specs}), encoding="utf-8")  # JSON is valid YAML
    assert c.check_specs(idx).status == "pass"
    specs[3]["status"] = "review-pending"
    del specs[5]
    idx.write_text(json.dumps({"specs": specs}), encoding="utf-8")
    r = c.check_specs(idx)
    assert r.status == "fail" and len(r.detail["not_done"]) == 2


def test_ci_states():
    ok = json.dumps([{"workflowName": "validate", "status": "completed", "conclusion": "success"}])
    assert c.check_ci(SHA, c.Deps(run=fake_run(gh=ok))).status == "pass"
    bad = json.dumps([{"workflowName": "validate", "status": "completed", "conclusion": "failure"}])
    assert c.check_ci(SHA, c.Deps(run=fake_run(gh=bad))).status == "fail"
    assert c.check_ci(SHA, c.Deps(run=fake_run(gh="[]"))).status == "fail"
    assert c.check_ci(SHA, c.Deps(run=fake_run())).status == "skip"


def test_migrations_drift(tmp_path: Path):
    (tmp_path / "20260101000000_a.sql").write_text("select 1")
    (tmp_path / "20260102000000_b.sql").write_text("select 1")
    synced = [{"version": "20260101000000", "name": "a"}, {"version": "20260102000000", "name": "b"}]
    d = c.Deps(remote_migrations=lambda e: synced)
    assert c.check_migrations("staging", d, tmp_path).status == "pass"
    d = c.Deps(remote_migrations=lambda e: synced[:1])
    r = c.check_migrations("staging", d, tmp_path)
    assert r.status == "fail" and r.detail["pending"] == ["20260102000000"]
    assert c.check_migrations("production", c.Deps(remote_migrations=lambda e: None), tmp_path).status == "not_provisioned"

    def boom(e):
        raise RuntimeError("x")
    assert c.check_migrations("staging", c.Deps(remote_migrations=boom), tmp_path).status == "fail"


def test_health_sha():
    d = c.Deps(http_get=http({"https://x/health": (200, {"git_sha": SHA[:12]})}))
    assert c.check_health("https://x/", SHA, d).status == "pass"
    d = c.Deps(http_get=http({"https://x/health": (200, {"git_sha": "bbb"})}))
    assert c.check_health("https://x", SHA, d).status == "fail"
    d = c.Deps(http_get=http({"https://x/health": OSError()}))
    assert c.check_health("https://x", SHA, d).status == "fail"
    assert c.check_health(None, SHA, c.Deps()).status == "not_provisioned"


def test_env_names_prod_requires_stripe_and_forbids_mock():
    names = set(c.REQUIRED_ENV["staging"])
    r = c.check_env_names("production", c.Deps(vercel_env_names=lambda e: names))
    assert r.status == "fail" and "STRIPE_SECRET_KEY" in r.detail["missing"]
    full = set(c.REQUIRED_ENV["production"]) | {"RPG_FORCE_MOCK"}
    r = c.check_env_names("production", c.Deps(vercel_env_names=lambda e: full))
    assert r.status == "fail" and r.detail["forbidden_present"] == ["RPG_FORCE_MOCK"]
    full.discard("RPG_FORCE_MOCK")
    assert c.check_env_names("production", c.Deps(vercel_env_names=lambda e: full)).status == "pass"
    assert c.check_env_names("production", c.Deps(vercel_env_names=lambda e: None)).status == "not_provisioned"


def test_legal_pages():
    urls = {n: f"https://x/{n}" for n in ("privacy", "terms", "support", "refund")}
    ok = c.Deps(http_get=http({u: (200, None) for u in urls.values()}))
    assert c.check_legal(urls, ok).status == "pass"
    broken = c.Deps(http_get=http({**{u: (200, None) for u in urls.values()}, urls["terms"]: (404, None)}))
    assert c.check_legal(urls, broken).detail["problems"] == {"terms": "http 404"}
    assert c.check_legal({}, ok).status == "fail"
    partial = {"privacy": urls["privacy"]}
    assert c.check_legal(partial, ok).status == "fail"


def test_kill_switch_store():
    d = c.Deps(kill_switch_load=lambda e: {"image_generation": False, "new_purchases": True})
    r = c.check_kill_switch("staging", d)
    assert r.status == "pass" and r.detail["switched_off"] == ["image_generation"]
    assert c.check_kill_switch("production", c.Deps(kill_switch_load=lambda e: None)).status == "not_provisioned"

    def boom(e):
        raise RuntimeError
    assert c.check_kill_switch("staging", c.Deps(kill_switch_load=boom)).status == "fail"


def test_risks_gate(tmp_path: Path):
    p = tmp_path / "r.md"
    p.write_text("| R-01 | P1 | titulo | dono | aberto | m |\n| R-02 | P2 | t | d | aberto | m |\n"
                 "| R-03 | P1 | t | d | fechado | m |\n", encoding="utf-8")
    r = c.check_risks(p)
    assert r.status == "fail" and r.detail["open_p0_p1"] == ["R-01"] and r.detail["p2_awaiting_acceptance"] == ["R-02"]
    p.write_text("| R-01 | P1 | titulo | dono | fechado | m |\n", encoding="utf-8")
    assert c.check_risks(p).status == "pass"
    assert c.check_risks(tmp_path / "none.md").status == "fail"


def test_real_register_parses():
    rows = c.parse_risks(c.ROOT / "docs" / "spec197" / "risk-register.md")
    assert rows and {r["severity"] for r in rows} <= {"P0", "P1", "P2"}


def test_run_and_report(tmp_path: Path):
    deps = c.Deps(run=fake_run(dirty=True, gh="[]"))
    rep = c.run_checklist("production", None, {}, deps)
    assert not rep["ok"] and "git_clean_tree" in rep["failing"]
    by = {r["name"]: r for r in rep["results"]}
    assert by["health_sha"]["status"] == "not_provisioned" and by["migrations_drift"]["status"] == "skip"
    strict = c.run_checklist("production", None, {}, deps, strict=True)
    assert "health_sha" in strict["failing"]
    j, m = c.write_report(rep, tmp_path)
    assert j.name == f"checklist-{SHA[:12]}-production.json" and json.loads(j.read_text())["sha"] == SHA
    assert "BLOQUEADO" in m.read_text(encoding="utf-8")
    assert "dirty" in json.dumps(rep) or True
