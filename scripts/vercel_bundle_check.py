"""SPEC-192: estima o tamanho descomprimido do bundle Python da Vercel.

Instala requirements.txt (wheels Linux) num diretório temporário e soma
com o código/dados do app (respeitando .vercelignore de forma aproximada).
Limite Python: 500 MB descomprimido (docs Vercel, Functions limits, 2026-08-24).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT_MB = 500
SKIP_TOP = {
    ".git",
    ".venv",
    ".tmp",
    ".claude",
    "saves",
    "saves_playtest",
    "playtest_runs",
    "readiness_artifacts",
    "docs",
    "handoffs",
    "tests",
    "project_index",
    "infra",
    "supabase",
    "lore_nova",
    "frontend",
    "specs",
    "playtest",
    "evals",
    "scripts",
    "__pycache__",
    ".pytest_cache",
}


def dir_size(path: Path, skip_top: set[str] | None = None) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        rel = Path(dirpath).relative_to(path)
        if skip_top is not None and rel == Path("."):
            dirnames[:] = [d for d in dirnames if d not in skip_top]
        if rel.parts[:2] in {("data", "runtime"), ("data", "saves_memory")}:
            dirnames[:] = []
            continue
        if (
            rel.parts[:2] == ("web", "node_modules")
            or rel.parts[:1] == ("web",)
            and rel.parts[1:2]
            in {("node_modules",), ("dist",), ("src",), ("e2e",), ("tests",), ("public",)}
        ):
            dirnames[:] = []
            continue
        for name in filenames:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return total


def main() -> int:
    target = Path(tempfile.mkdtemp(prefix="vercel-bundle-"))
    try:
        cmd = [
            "uv",
            "pip",
            "install",
            "--target",
            str(target),
            "-r",
            str(ROOT / "requirements.txt"),
            "--python-platform",
            "x86_64-manylinux_2_28",
            "--python-version",
            "3.13",
            "--no-cache" if "--no-cache" in sys.argv else "--quiet",
        ]
        subprocess.run(cmd, check=True)
        deps = dir_size(target)
        app = dir_size(ROOT, SKIP_TOP)
        web_dist = ROOT / "web" / "dist"
        dist = dir_size(web_dist) if web_dist.exists() else 0
        mb = lambda n: n / 1024 / 1024  # noqa: E731
        total = deps + app + dist
        print(f"dependencias (linux wheels): {mb(deps):8.1f} MB")
        print(f"app (codigo+data+faiss+assets): {mb(app):6.1f} MB")
        print(f"web/dist (se buildado): {mb(dist):10.1f} MB")
        print(f"TOTAL estimado: {mb(total):.1f} MB / limite {LIMIT_MB} MB")
        return 0 if mb(total) < LIMIT_MB else 1
    finally:
        shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
