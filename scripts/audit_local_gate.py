"""Run the free audit gate against an already provisioned local Supabase stack."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    port = 8767
    url = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'RPG_FORCE_MOCK': '1', 'RPG_VISUAL_BROWSER': '1',
           'RPG_AUDIT_BROWSER_URL': url,
           'RPG_TEST_DATABASE_URL': 'postgresql://postgres:postgres@127.0.0.1:55322/postgres'}
    artifacts = ROOT / 'readiness_artifacts' / 'audit'
    artifacts.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(
        [sys.executable, 'scripts/audit_local_server.py', '--port', str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError('audit API exited before readiness')
                try:
                    response = client.get(url + '/health')
                    if response.is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError('local audit API readiness timed out')
        return subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/test_context_identity_local.py', 'tests/test_restore_pgvector_local.py',
            'tests/test_postgres_jobs_local.py', 'tests/test_worker_fence_local.py',
            'tests/test_dynamic_art_local.py', 'tests/test_chronicle_local.py',
            'tests/test_frontend_visual_contracts.py', 'tests/test_audit_browser_local.py',
            f'--junitxml={artifacts / "results.xml"}',
        ], cwd=ROOT, env=env, check=False).returncode
    finally:
        # Only the child created above, never another developer's server.
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == '__main__':
    raise SystemExit(main())
