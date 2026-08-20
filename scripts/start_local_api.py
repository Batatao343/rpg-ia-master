"""Inicia FastAPI local em background sem expor chaves do Supabase no shell."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]


def _supabase_status() -> dict[str, str]:
    npx = "npx.cmd" if os.name == "nt" else "npx"
    result = subprocess.run(
        [npx, "--yes", "supabase@2.115.0", "status", "--output", "json"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def start(port: int, artifact_dir: Path) -> int:
    status = _supabase_status()
    env = os.environ.copy()
    env.update({
        "RPG_RUNTIME_PROFILE": "local",
        "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:55322/postgres",
        "SUPABASE_URL": status["API_URL"],
        "SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
        "SUPABASE_SERVICE_ROLE_KEY": status["SERVICE_ROLE_KEY"],
        "RPG_SESSION_SECRET": "local-browser-session-secret-32-chars",
        "RPG_FORCE_MOCK": "1",
        "RPG_CORS_ORIGINS": f"http://127.0.0.1:{port},http://localhost:{port}",
    })
    executable = Path(sys.executable).with_name("uvicorn.exe" if os.name == "nt" else "uvicorn")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout = (artifact_dir / "api-browser.stdout.log").open("ab")
    stderr = (artifact_dir / "api-browser.stderr.log").open("ab")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen(
        [str(executable), "api:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
        creationflags=flags,
    )
    stdout.close()
    stderr.close()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("API local encerrou durante startup")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                (artifact_dir / "api-browser.pid").write_text(str(process.pid), encoding="ascii")
                return process.pid
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    process.terminate()
    raise RuntimeError("API local não ficou saudável em 30 segundos")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", type=Path, default=Path("readiness_artifacts"))
    args = parser.parse_args()
    print(json.dumps({"pid": start(args.port, args.artifact_dir), "health": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
