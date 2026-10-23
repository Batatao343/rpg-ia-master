"""SPEC-297 Etapa 0 - linha de base com a flag `off` (R1)."""

import os
import subprocess
import sys

import pytest

from services import shared_pool as sp


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv("RPG_SHARED_POOL", raising=False)
    assert sp.pool_mode() == "off"
    assert sp.enabled() is False


@pytest.mark.parametrize(
    "raw,expected", [("shadow", "shadow"), ("ON", "on"), ("lixo", "off"), ("", "off")]
)
def test_flag_parsing_fail_safe(monkeypatch, raw, expected):
    monkeypatch.setenv("RPG_SHARED_POOL", raw)
    assert sp.pool_mode() == expected


def test_off_keeps_spec223_r7_tests_unchanged():
    env = {**os.environ, "RPG_SHARED_POOL": "off"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_npc_catalog_scope.py",
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-800:]
