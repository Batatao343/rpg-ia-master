"""SPEC-417 R1-R8: catraca de teste enfraquecido (`scripts/dev/weak_tests.py`)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.dev import weak_tests as wt

OLD = "def test_a():\n    assert 1 == 1\n"


def _marks(src: str) -> list[wt.Mark]:
    return wt.marks(src)


def test_skip_novo_sem_reason_falha() -> None:
    new = "import pytest\n\n@pytest.mark.skip\ndef test_a():\n    assert 1 == 1\n"
    found = wt.new_marks(OLD, new)
    assert [(m.qualname, m.kind, m.has_reason) for m in found] == [("test_a", "skip", False)]
    with_reason = new.replace("@pytest.mark.skip", '@pytest.mark.skip(reason="x")')
    assert [m.has_reason for m in wt.new_marks(OLD, with_reason)] == [True]


def test_marca_antiga_nao_conta() -> None:
    src = "import pytest\n\n@pytest.mark.skip\ndef test_a():\n    assert 1 == 1\n"
    assert wt.new_marks(src, src) == []


def test_tirar_reason_de_marca_antiga_conta() -> None:
    old = 'import pytest\n\n@pytest.mark.skipif(True, reason="x")\ndef test_a():\n    assert 1\n'
    new = old.replace(', reason="x"', "")
    found = wt.new_marks(old, new)
    assert [(m.kind, m.has_reason) for m in found] == [("skipif", False)]


def test_formas_de_pulo() -> None:
    src = (
        "import pytest\n"
        "from pytest import mark\n"
        "pytestmark = [pytest.mark.skip]\n"
        "@mark.skip\n"
        "def test_a():\n    assert 1\n"
        "def test_b():\n    pytest.skip('m')\n"
        "def test_c():\n    pytest.xfail()\n"
        "def test_d():\n    pytest.importorskip('x')\n"
        "@pytest.mark.parametrize('v', [pytest.param(1, marks=pytest.mark.xfail)])\n"
        "def test_e(v):\n    assert v\n"
        "class TestK:\n"
        "    pytestmark = pytest.mark.skipif(True, reason='r')\n"
        "    def test_m(self):\n        assert 1\n"
    )
    got = {(m.qualname, m.kind, m.has_reason) for m in _marks(src)}
    assert got == {
        ("<module>", "skip", False),
        ("test_a", "skip", False),
        ("test_b", "skip", True),
        ("test_c", "xfail", False),
        ("test_d", "importorskip", False),
        ("test_e", "xfail", False),
        ("TestK", "skipif", True),
    }


def test_string_com_marca_nao_conta() -> None:
    assert _marks('X = "@pytest.mark.skip"\nY = "pytest.skip()"\n') == []


def test_justificativa_na_spec() -> None:
    mark = wt.Mark("test_a", "skip", False, False, 3)
    spec = "linha qualquer\n`test_a` fica em skip ate a SPEC-999\n"
    assert wt.justified(mark, "tests/test_x.py", spec)
    assert not wt.justified(mark, "tests/test_x.py", "nada sobre ele\n")
    assert not wt.justified(mark, "tests/test_x.py", None)
    module_mark = wt.Mark("<module>", "importorskip", False, False, 1)
    assert wt.justified(module_mark, "tests/test_x.py", "test_x.py usa importorskip de proposito")


def test_xfail_nao_estrito_vira_info(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        'import pytest\n\n@pytest.mark.xfail(reason="bug")\ndef test_a():\n    assert 1 == 2\n',
        encoding="utf-8",
    )
    findings = wt.check(repo, "main", "HEAD", None, worktree=True)
    levels = [f.level for f in findings]
    assert "FAIL" not in levels
    assert any(f.level == "INFO" and "strict" in f.text for f in findings)


@pytest.mark.parametrize(
    "body",
    [
        "    assert foo() == 1\n",
        "    with pytest.raises(ValueError):\n        foo()\n",
        "    m.assert_called_once_with()\n",
        "    check_response(r, '/')\n",
        "    helper()\n",
        "    fuzz_operation(op, c, max_examples=1)\n",
    ],
)
def test_teste_novo_com_assert_passa(body: str) -> None:
    new = "import pytest\n\ndef helper():\n    assert foo()\n\ndef test_b():\n" + body
    assert wt.weak_new_tests(None, new) == []


@pytest.mark.parametrize(
    "body", ["    foo()\n", "    assert True\n", "    pass\n", "    assert 1\n"]
)
def test_teste_novo_sem_assert_falha(body: str) -> None:
    assert wt.weak_new_tests(OLD, OLD + "\ndef test_b():\n" + body) == ["test_b"]


def test_fixture_test_nao_conta() -> None:
    src = "import pytest\n\n@pytest.fixture\ndef test_fix():\n    return 1\n"
    assert wt.weak_new_tests(None, src) == []


def test_metodo_em_classe_Test() -> None:
    src = "class TestK:\n    def test_m(self):\n        pass\n    def test_ok(self):\n        assert 1 == 1\n"
    assert wt.weak_new_tests(None, src) == ["TestK.test_m"]
    assert "helper_nao_teste" not in wt.test_functions(src)


def test_assert_delta_relata_remocao() -> None:
    old = "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n\ndef test_b():\n    pass\n"
    new = "def test_a():\n    assert 3 == 3\n"
    assert wt.assert_delta(old, new) == (3, 1, 1)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _git_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git ausente")  # exigido pelo ambiente de teste
    repo = tmp_path / "r"
    (repo / "tests").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "tests" / "test_x.py").write_text(OLD, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_cli_em_repo_sintetico(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _git_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "spec-999")
    bad = "import pytest\n\n@pytest.mark.skip\ndef test_a():\n    assert 1 == 1\n\ndef test_novo():\n    pass\n"
    (repo / "tests" / "test_x.py").write_text(bad, encoding="utf-8")
    _git(repo, "commit", "-qam", "bad")
    argv = ["--repo", str(repo), "--base", "main", "--head", "HEAD"]
    assert wt.main(argv) == 1
    out = capsys.readouterr().out
    assert sum(1 for ln in out.splitlines() if ln.startswith("FAIL")) == 2

    good = bad.replace("@pytest.mark.skip", '@pytest.mark.skip(reason="motivo")').replace(
        "    pass", "    assert 1 == 1"
    )
    (repo / "tests" / "test_x.py").write_text(good, encoding="utf-8")
    _git(repo, "commit", "-qam", "good")
    assert wt.main(argv) == 0
    assert "OK weak-tests" in capsys.readouterr().out


def test_ref_inexistente_e_rc2(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    assert wt.main(["--repo", str(repo), "--base", "nao-existe", "--head", "HEAD"]) == 2
