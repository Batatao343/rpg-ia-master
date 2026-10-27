"""SPEC-337 R20/R21: o gate local roda RLS/Storage/IDOR e rejeita `skipped`."""

from __future__ import annotations

from pathlib import Path

from scripts import audit_local_gate as gate

ROOT = Path(__file__).resolve().parents[1]


def test_gate_lists_security_files():
    source = (ROOT / "scripts" / "audit_local_gate.py").read_text(encoding="utf-8")
    for name in ("test_rls_local.py", "test_storage_security_local.py", "test_http_idor_local.py"):
        assert f"tests/{name}" in source
        assert f"tests/{name}" in gate.SECURITY_TEST_FILES
        assert (ROOT / "tests" / name).exists()
    assert "*SECURITY_TEST_FILES" in source
    for var in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        assert var in source


def _junit(tmp_path, *, skip: bool) -> Path:
    inner = '<skipped message="env"/>' if skip else ""
    path = tmp_path / "results.xml"
    path.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_rls_local" name="test_rls_isola">'
        f"{inner}</testcase>"
        '<testcase classname="tests.test_other_local" name="test_x"><skipped/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def test_skip_in_security_file_is_reported(tmp_path):
    assert gate._skipped_security_tests(_junit(tmp_path, skip=True)) == [
        "tests.test_rls_local::test_rls_isola"
    ]


def test_no_skip_is_clean_and_other_files_ignored(tmp_path):
    assert gate._skipped_security_tests(_junit(tmp_path, skip=False)) == []
    assert gate._skipped_security_tests(tmp_path / "missing.xml") == []
