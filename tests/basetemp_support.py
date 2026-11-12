"""SPEC-414 R3: nome e limpeza do ``basetemp`` curto do pytest (Windows + xdist).

Lógica pura, fora do ``conftest.py``: o conftest só chama estas funções.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

MAX_IDADE_S = 6 * 3600
_NOME_RE = re.compile(r"^pt-[0-9a-f]{8}(-\d+)?$")


def basetemp_name(checkout: Path, pid: int) -> str:
    sha = hashlib.sha1(str(checkout).encode()).hexdigest()[:8]
    return f"pt-{sha}-{pid}"


def prune_old_basetemps(tmpdir: Path, now: float, max_age_s: float = MAX_IDADE_S) -> list[Path]:
    """Remove ``pt-<sha8>[-<pid>]`` com mtime mais velho que ``max_age_s``; devolve os removidos."""
    removed: list[Path] = []
    try:
        entries = list(tmpdir.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if not _NOME_RE.match(entry.name):
            continue
        try:
            if not entry.is_dir() or now - entry.stat().st_mtime <= max_age_s:
                continue
            shutil.rmtree(entry)
            removed.append(entry)
        except OSError:  # silent-ok: limpeza best-effort
            continue
    return removed


def choose_basetemp(
    platform: str,
    is_worker: bool,
    has_basetemp: bool,
    numprocesses: object,
    checkout: Path,
    tmpdir: Path,
    pid: int,
) -> str | None:
    """Caminho do basetemp (Windows, controlador xdist, sem ``--basetemp``) ou None."""
    if platform != "win32" or is_worker or has_basetemp or not numprocesses:
        return None
    return str(tmpdir / basetemp_name(checkout, pid))
