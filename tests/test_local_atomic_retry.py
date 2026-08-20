from __future__ import annotations

import json
import os
from pathlib import Path

from infrastructure.local_adapters import _atomic_json


def test_atomic_json_repete_replace_bloqueado_temporariamente(
    tmp_path: Path, monkeypatch,
) -> None:
    destination = tmp_path / "catalog.json"
    real_replace = os.replace
    attempts = 0

    def flaky_replace(source: str | Path, target: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "lock efêmero simulado")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", flaky_replace)
    _atomic_json(destination, {"npc": {"name": "Corvo"}})

    assert attempts == 3
    assert json.loads(destination.read_text(encoding="utf-8"))["npc"]["name"] == "Corvo"
    assert not list(tmp_path.glob("*.tmp"))
