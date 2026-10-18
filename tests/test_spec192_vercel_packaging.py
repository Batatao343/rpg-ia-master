"""SPEC-192 — empacotamento Vercel (offline)."""
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from infrastructure.runtime import apply_serverless_defaults

ROOT = Path(__file__).resolve().parent.parent


def test_vercel_json_shape():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert "web" in cfg["buildCommand"] and "npm run build" in cfg["buildCommand"]
    fn = cfg["functions"]["vercel_app.py"]
    assert 1 <= fn["maxDuration"] <= 300  # teto Hobby (Fluid compute)
    assert "observability" not in fn["excludeFiles"]  # pacote Python importado por api.py
    # SPEC-217 R14: o rollout do Jev importa a politica congelada de evals/experiments (+ evals/core).
    globs = fn["excludeFiles"].strip("{}").split(",")
    assert "evals/**" not in globs and "evals/experiments/**" not in globs
    assert "evals/core/**" not in globs
    sse = [h for h in cfg["headers"] if h["source"] == "/game/action/stream"]
    assert sse and {"key": "X-Accel-Buffering", "value": "no"} in sse[0]["headers"]


def test_explicit_entrypoint_not_main_py():
    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert py["tool"]["vercel"]["entrypoint"] == "vercel_app:app"
    assert (ROOT / "vercel_app.py").is_file()


def test_entry_exports_fastapi_app():
    code = "import vercel_app, api; assert vercel_app.app is api.app"
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]


def test_requirements_vercel_utf8_subset_of_lock():
    raw = (ROOT / "requirements-vercel.txt").read_bytes()
    text = raw.decode("utf-8")  # não pode ser UTF-16
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {p["name"]: p["version"] for p in lock["package"]}
    pins = re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", text, re.M)
    assert pins
    names = {n.lower().replace("_", "-") for n, _ in pins}
    for name, ver in pins:
        assert versions[name.lower().replace("_", "-")] == ver
    assert {"fastapi", "psycopg", "langchain-openai", "faiss-cpu"} <= names
    for banned in ("pytest", "playwright", "boto3", "pillow"):
        assert banned not in names
    assert (ROOT / "requirements.txt").read_bytes() == raw  # Vercel lê requirements.txt


def test_vercelignore_excludes_state_and_keeps_runtime():
    lines = (ROOT / ".vercelignore").read_text(encoding="utf-8").split()
    for p in ("saves", "data/runtime", "data/saves_memory", "playtest_runs", "docs", "tests"):
        assert p in lines
    for p in ("data", "observability", "assets", "faiss_lore_index"):
        assert p not in lines


def test_hosted_on_vercel_uses_tmp_cache():
    env = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "VERCEL": "1"}
    assert apply_serverless_defaults(env) == "/tmp/rpg-runtime"
    assert env["RPG_RUNTIME_CACHE_DIR"] == "/tmp/rpg-runtime"


def test_serverless_defaults_respect_override_and_non_hosted():
    env = {"RPG_RUNTIME_PROFILE": "hosted-supabase", "VERCEL": "1", "RPG_RUNTIME_CACHE_DIR": "/x"}
    assert apply_serverless_defaults(env) is None and env["RPG_RUNTIME_CACHE_DIR"] == "/x"
    assert apply_serverless_defaults({"VERCEL": "1"}) is None
    assert apply_serverless_defaults({"RPG_RUNTIME_PROFILE": "hosted-supabase"}) is None


def test_hosted_profile_never_writes_saves_or_faiss(tmp_path, monkeypatch):
    """Perfil não-legacy: save/memória vão ao GameStore/pgvector, sem tocar o cwd."""
    src = (ROOT / "persistence.py").read_text(encoding="utf-8")
    rag = (ROOT / "rag.py").read_text(encoding="utf-8")
    assert src.count('RPG_RUNTIME_PROFILE", "legacy"') >= 3
    assert rag.count('RPG_RUNTIME_PROFILE", "legacy"') >= 2
