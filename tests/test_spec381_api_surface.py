"""SPEC-381 R6/R7: oraculo TEMPORARIO da refatoracao de ``api.py`` (apagado no pouso).

Compara a superficie HTTP viva (OpenAPI, rotas, middlewares, handlers, lifecycle) com o dump
congelado em ``docs/spec381/before/`` byte a byte, nos perfis ``legacy`` e ``hosted``, e confere
que ``import api`` so ganha os modulos novos (``api_core``, ``api_models``, ``api_presenters``,
``routes.*``). Nao e contrato da API (SPEC-385).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "docs" / "spec381" / "before"
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import api_surface_dump  # noqa: E402

BYTE_EXACT = ("openapi.json", "routes.json", "middleware.json", "handlers.json", "lifecycle.json")
NEW_MODULES = ("api_core", "api_models", "api_presenters", "routes")


@pytest.mark.parametrize("profile", ["legacy", "hosted"])
def test_http_surface_is_byte_identical(profile, tmp_path):
    api_surface_dump._spawn(profile, tmp_path)
    for name in BYTE_EXACT:
        assert (tmp_path / name).read_bytes() == (BEFORE / profile / name).read_bytes(), name
    before = set(
        json.loads((BEFORE / profile / "modules.json").read_text(encoding="utf-8"))["added"]
    )
    after = set(json.loads((tmp_path / "modules.json").read_text(encoding="utf-8"))["added"])
    assert before - after == set(), "import api deixou de carregar modulos"
    extra = {m for m in after - before if m.split(".")[0] not in NEW_MODULES}
    assert extra == set(), f"modulo pre-existente novo em import api: {sorted(extra)}"
