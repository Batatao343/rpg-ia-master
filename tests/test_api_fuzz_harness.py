"""SPEC-338: testes offline do harness de fuzz (rodam no default, sem o marker ``api_fuzz``)."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api
from scripts.ci_docs_only import DOC_TEST_PATTERN
from tests.fakes.api_fuzz import (
    EXCLUDED_503,
    INTENTIONAL_503,
    check_response,
    fuzz_failures,
    network_blocked,
)

ROOT = Path(__file__).resolve().parents[1]
FUZZ_FILES = (
    ROOT / "tests" / "test_api_fuzz_schemathesis.py",
    ROOT / "tests" / "test_api_fuzz_harness.py",
    ROOT / "tests" / "fakes" / "api_fuzz.py",
)


def test_api_fuzz_file_is_not_a_doc_test():
    # R6: o guarda do docs-only não pode tratar estes arquivos como teste de documentação.
    # (este arquivo cita o padrão por import, nunca como literal.)
    for path in FUZZ_FILES[:1] + FUZZ_FILES[2:]:
        assert not DOC_TEST_PATTERN.search(path.read_text(encoding="utf-8")), path.name


def test_intentional_503_allowlist_matches_source():
    source = (ROOT / "api.py").read_text(encoding="utf-8")
    codes = set(re.findall(r"HTTPException\(\s*503,\s*(?:detail=)?\"([a-z_]+)\"", source))
    assert codes, "regex não achou nenhum 503"
    assert codes <= INTENTIONAL_503 | EXCLUDED_503, codes - (INTENTIONAL_503 | EXCLUDED_503)


def test_network_is_blocked_inside_fuzz():
    with network_blocked():
        with pytest.raises(RuntimeError, match="network blocked"):
            httpx.Client().get("https://example.com")
        assert TestClient(api.app).get("/health").status_code == 200
    # fora do contexto o transporte volta ao original
    assert httpx.HTTPTransport.handle_request.__name__ == "handle_request"


def test_check_response_accepts_only_intentional_503():
    ok = httpx.Response(503, json={"detail": "stripe_disabled"})
    bad = httpx.Response(503, json={"detail": "algo_novo"})
    boom = httpx.Response(500, json={"detail": "internal_error"})
    check_response(ok, "/x", headers=False)
    for response in (bad, boom):
        with pytest.raises(AssertionError):
            check_response(response, "/x", headers=False)


def test_check_response_flags_leak():
    leaky = httpx.Response(400, text='Traceback (most recent call last): File "x"')
    with pytest.raises(AssertionError):
        check_response(leaky, "/x", headers=False)


def test_harness_flags_injected_500():
    schemathesis = pytest.importorskip("schemathesis")
    mini = FastAPI()

    @mini.get("/boom")
    def boom():
        raise RuntimeError("injetado")

    @mini.get("/fine")
    def fine():
        return {"ok": True}

    @mini.get("/off")
    def off():
        raise HTTPException(503, "stripe_disabled")

    schema = schemathesis.openapi.from_dict(mini.openapi())
    client = TestClient(mini, raise_server_exceptions=False)
    failures = fuzz_failures(schema, client, max_examples=3, headers=False)
    assert set(failures) == {"GET /boom"}, failures


def test_api_fuzz_job_contract():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "validate.yml").read_text("utf-8"))
    job = wf["jobs"]["api-fuzz"]
    assert job["needs"] == "scope"
    assert job["timeout-minutes"] <= 15
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    assert "--group fuzz" in commands
    assert "--only-group fuzz" in commands and "pip-audit" in commands
    assert "-m api_fuzz" in commands
    assert "-n auto" not in commands and " -n " not in commands
    uploads = [s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact")]
    assert uploads and all(s.get("if") == "failure()" for s in uploads)


def test_fuzz_group_is_isolated_from_runtime_requirements():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "schemathesis" not in requirements and "hypothesis" not in requirements
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "not api_fuzz" in pyproject
    assert "default-groups" not in pyproject
