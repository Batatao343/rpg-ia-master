"""SPEC-225 R7: scripts de ops recebem DSN por variável de ambiente, não por argv."""
from pathlib import Path

import pytest

from services.dsn_cli import add_dsn_arguments, resolve_dsn

ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = [
    "scripts/export_game_data.py", "scripts/migrate_file_saves.py", "scripts/recover_operations.py",
    "scripts/chaos_test.py", "scripts/load_test.py", "scripts/verify_restore.py", "scripts/export_game_audit.py",
]


def _parser():
    import argparse
    parser = argparse.ArgumentParser()
    add_dsn_arguments(parser)
    return parser


def test_dsn_from_default_env_var(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    parser = _parser()
    args = parser.parse_args([])
    assert resolve_dsn(parser, args) == "postgresql://u:p@h/db"


def test_dsn_from_named_env_var(monkeypatch):
    monkeypatch.setenv("RPG_TARGET_DB", "postgresql://x@h/db")
    parser = _parser()
    args = parser.parse_args(["--dsn-env", "RPG_TARGET_DB"])
    assert resolve_dsn(parser, args) == "postgresql://x@h/db"


def test_missing_env_without_default_fails_closed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    parser = _parser()
    args = parser.parse_args([])
    with pytest.raises(SystemExit):
        resolve_dsn(parser, args)


def test_missing_env_uses_local_default_when_given(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    parser = _parser()
    args = parser.parse_args([])
    assert resolve_dsn(parser, args, default_dsn="postgresql://postgres:postgres@127.0.0.1:55322/postgres").endswith("55322/postgres")


def test_literal_dsn_in_argv_is_refused_by_default(monkeypatch):
    parser = _parser()
    args = parser.parse_args(["--dsn", "postgresql://u:senha@h/db"])
    with pytest.raises(SystemExit):
        resolve_dsn(parser, args)


def test_literal_dsn_accepted_only_with_explicit_flag(monkeypatch, capsys):
    parser = _parser()
    args = parser.parse_args(["--dsn", "postgresql://u:senha@h/db", "--allow-dsn-argv"])
    assert resolve_dsn(parser, args) == "postgresql://u:senha@h/db"
    assert "argv" in capsys.readouterr().err  # aviso explícito


@pytest.mark.parametrize("rel", OPS_SCRIPTS)
def test_ops_script_uses_shared_dsn_helper(rel):
    source = (ROOT / rel).read_text(encoding="utf-8")
    assert "add_dsn_arguments(" in source and "resolve_dsn(" in source
    assert '"--dsn", default' not in source
