"""Run the free audit gate against an already provisioned local Supabase stack."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]

# SPEC-337 R20/R21: RLS/Storage/IDOR reais entram no gate e NÃO podem ficar `skipped`.
SECURITY_TEST_FILES = (
    "tests/test_rls_local.py",
    "tests/test_storage_security_local.py",
    "tests/test_http_idor_local.py",
)


def _skipped_security_tests(junit_path: Path) -> list[str]:
    """Testes dos arquivos de segurança que ficaram `skipped` no JUnit (R21)."""
    if not junit_path.exists():
        return []
    stems = {Path(name).stem for name in SECURITY_TEST_FILES}
    skipped: list[str] = []
    for case in ET.parse(junit_path).getroot().iter("testcase"):
        classname = case.get("classname", "")
        if not any(classname == f"tests.{stem}" or f".{stem}" in classname for stem in stems):
            continue
        if case.find("skipped") is not None:
            skipped.append(f"{classname}::{case.get('name')}")
    return skipped


def main() -> int:
    port = 8767
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "RPG_FORCE_MOCK": "1",
        "RPG_VISUAL_BROWSER": "1",
        "RPG_AUDIT_BROWSER_URL": url,
        "RPG_TEST_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:55322/postgres",
    }
    from scripts.start_local_api import _supabase_status

    status = _supabase_status()  # SPEC-337 R20: sem estas, test_storage_security_local pula
    env.update(
        {
            "SUPABASE_URL": status["API_URL"],
            "SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
            "SUPABASE_SERVICE_ROLE_KEY": status["SERVICE_ROLE_KEY"],
        }
    )
    artifacts = ROOT / "readiness_artifacts" / "audit"
    artifacts.mkdir(parents=True, exist_ok=True)
    env["RPG_AUDIT_ARTIFACTS"] = str(artifacts)
    env["RPG_IMAGE_PRICE_PROFILE"] = f"audit-image-{uuid4()}"
    started = time.monotonic()
    result_code = 1
    server = subprocess.Popen(
        [sys.executable, "scripts/audit_local_server.py", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("audit API exited before readiness")
                try:
                    response = client.get(url + "/health")
                    if response.is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("local audit API readiness timed out")
        result_code = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_context_identity_local.py",
                "tests/test_restore_pgvector_local.py",
                "tests/test_postgres_jobs_local.py",
                "tests/test_worker_fence_local.py",
                "tests/test_dynamic_art_local.py",
                "tests/test_chronicle_local.py",
                "tests/test_frontend_visual_contracts.py",
                "tests/test_audit_browser_local.py",
                "tests/test_artwork_recovery_browser.py",
                "tests/test_process_crash_local.py",
                "tests/test_mutation_api_local.py",
                *SECURITY_TEST_FILES,
                f"--junitxml={artifacts / 'results.xml'}",
            ],
            cwd=ROOT,
            env=env,
            check=False,
        ).returncode
        skipped = _skipped_security_tests(artifacts / "results.xml")
        if skipped:
            print(f"audit gate: testes de segurança pulados (proibido): {skipped}", file=sys.stderr)
            result_code = result_code or 1
        return result_code
    finally:
        # Only the child created above, never another developer's server.
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)
        (artifacts / "summary.json").write_text(
            json.dumps(
                {
                    "exit_code": result_code,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "provider_mode": "mock",
                    "image_provider_mode": "fake",
                    "api": url,
                    "junit": "results.xml",
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
