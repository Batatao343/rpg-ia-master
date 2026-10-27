"""SPEC-340: registro de feature flags com validade."""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from scripts import flag_registry as fr

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date(2026, 10, 27)


def _entry(kind="ops", **kw):
    e = {"kind": kind, "default": None, "spec": None, "note": "n"}
    if kind == "release":
        e["expires"] = dt.date(2027, 1, 25)
    e.update(kw)
    return e


def test_ok_registry_has_no_errors():
    reg = {"RPG_A": _entry(), "RPG_B": _entry("release")}
    found = {"RPG_A": {"a.py"}, "RPG_B": {"b.py"}}
    assert fr.validate(reg, found, TODAY) == []


def test_missing_flag_reported():
    errs = fr.validate({}, {"RPG_FOO_NOVO": {"x.py"}}, TODAY)
    assert any("RPG_FOO_NOVO" in e for e in errs)


def test_orphan_reported():
    errs = fr.validate({"RPG_OLD": _entry()}, {}, TODAY)
    assert any("RPG_OLD" in e for e in errs)


def test_release_requires_expires():
    e = _entry("release")
    del e["expires"]
    errs = fr.validate({"RPG_A": e}, {"RPG_A": {"a.py"}}, TODAY)
    assert any("expires" in x for x in errs)


def test_expires_forbidden_outside_release():
    e = _entry("ops", expires=dt.date(2027, 1, 25))
    errs = fr.validate({"RPG_A": e}, {"RPG_A": {"a.py"}}, TODAY)
    assert any("expires" in x for x in errs)


def test_expired_release_fails_with_message():
    e = _entry("release", expires=dt.date(2026, 10, 1))
    errs = fr.validate({"RPG_A": e}, {"RPG_A": {"a.py"}}, TODAY)
    assert any("remova a flag ou renove `expires`" in x for x in errs)


def test_invalid_kind_and_spec_format():
    errs = fr.validate(
        {"RPG_A": _entry("bogus"), "RPG_B": _entry(spec="foo")},
        {"RPG_A": {"a"}, "RPG_B": {"b"}},
        TODAY,
    )
    assert any("kind" in x for x in errs)
    assert any("spec" in x for x in errs)


def test_dynamic_pattern_covers_found_and_not_orphan():
    reg = {"RPG_[A-Z]+_TIMEOUT": _entry(pattern=True)}
    assert fr.validate(reg, {"RPG_ABC_TIMEOUT": {"a.py"}}, TODAY) == []
    errs = fr.validate(reg, {}, TODAY)
    assert any("órfã" in x or "órfão" in x for x in errs)


def test_scan_sources_detects_new_flag_in_synthetic_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "mod.py").write_text('import os\nos.getenv("RPG_FOO_NOVO")\n', encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text('"RPG_ONLY_TEST"', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    found = fr.scan_sources(tmp_path)
    assert "RPG_FOO_NOVO" in found
    assert "RPG_ONLY_TEST" not in found
    errs = fr.validate({}, found, TODAY)
    assert any("RPG_FOO_NOVO" in e for e in errs)


def test_repo_registry_is_complete():
    assert fr.check(ROOT) == 0
