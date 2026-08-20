from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts import dev_stack


def _result(command, stdout=""):
    return CompletedProcess(command, 0, stdout=stdout, stderr="")


def test_reset_exige_confirmacao_e_forca_local(monkeypatch, tmp_path):
    monkeypatch.setattr(dev_stack, "SUPABASE_DIR", tmp_path / "supabase")
    monkeypatch.setattr(dev_stack, "cli_command", lambda: ["supabase"])
    calls = []

    def runner(command):
        calls.append(list(command))
        if command[-1] == "--help":
            return _result(command, "--local --linked")
        return _result(command)

    with pytest.raises(dev_stack.StackError, match="confirm-local"):
        dev_stack.reset(confirm_local=False, runner=runner)
    dev_stack.reset(confirm_local=True, runner=runner)
    assert calls[-1] == ["supabase", "db", "reset", "--local"]


def test_reset_recusa_stack_linkada(monkeypatch, tmp_path):
    linked = tmp_path / "supabase" / ".temp" / "project-ref"
    linked.parent.mkdir(parents=True)
    linked.write_text("remote", encoding="utf-8")
    monkeypatch.setattr(dev_stack, "SUPABASE_DIR", tmp_path / "supabase")
    with pytest.raises(dev_stack.StackError, match="remoto"):
        dev_stack.reset(confirm_local=True, runner=lambda command: _result(command))


def test_branch_local_da_cli_nao_e_confundida_com_link_remoto(monkeypatch, tmp_path):
    branch = tmp_path / "supabase" / ".branches" / "_current_branch"
    branch.parent.mkdir(parents=True)
    branch.write_text("main", encoding="utf-8")
    monkeypatch.setattr(dev_stack, "SUPABASE_DIR", tmp_path / "supabase")
    dev_stack._assert_unlinked()


def test_cli_pinada_quando_so_npx_existe(monkeypatch):
    monkeypatch.delenv("SUPABASE_CLI_COMMAND", raising=False)
    monkeypatch.setattr(dev_stack.shutil, "which", lambda name: "npx.cmd" if name == "npx.cmd" else None)
    assert dev_stack.cli_command()[-1] == f"supabase@{dev_stack.SUPABASE_CLI_VERSION}"


def test_parser_reset_nao_confirma_implicitamente():
    args = dev_stack.build_parser().parse_args(["reset"])
    assert not args.confirm_local


def test_status_remove_segredos_e_credencial_do_dsn(monkeypatch):
    monkeypatch.setattr(dev_stack, "cli_command", lambda: ["supabase"])

    def runner(command):
        if command[-1] == "--help":
            return _result(command, "-o json")
        return _result(
            command,
            '{"API_URL":"http://127.0.0.1:55321",'
            '"DB_URL":"postgresql://postgres:secret@127.0.0.1:55322/postgres",'
            '"SECRET_KEY":"never-log","PUBLISHABLE_KEY":"also-omit"}',
        )

    value = dev_stack.status(runner=runner)
    assert "API_URL" in value
    assert "secret" not in value
    assert "KEY" not in value
    assert "postgres@" not in value
