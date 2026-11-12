"""SPEC-415 R1-R9: pre-checagens do pouso (`scripts/dev/land_check.py`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev import land_check as lc

TEMPLATE_RISK = "> **Risco:** `baixo` | `médio` | `alto`\n"


def test_dirty_paths_parses_renames_and_untracked_dirs() -> None:
    raw = " M a.py\0R  novo.md\0velho.md\0?? docs/aulas/\0"
    assert lc.dirty_paths(raw) == ["a.py", "novo.md", "velho.md", "docs/aulas/"]


def test_collisions_by_path_and_dir_prefix() -> None:
    branch = ["docs/guias/TESTES.md", "docs/aulas/x.md", "api.py"]
    dirty = ["docs/guias/TESTES.md", "docs/aulas/"]
    assert lc.collisions(branch, dirty) == ["docs/guias/TESTES.md", "docs/aulas/x.md"]
    assert lc.collisions(["docs/aulas2/x.md"], ["docs/aulas/"]) == []


def test_parse_risk() -> None:
    assert lc.parse_risk("> **Risco:** `médio`\n") == "médio"
    assert lc.parse_risk(TEMPLATE_RISK) is None
    assert lc.parse_risk("# sem risco\n") is None
    assert lc.parse_risk("> **Risco:** `médio`. Não é baixo porque `x`.\n") == "médio"


def test_last_verdict_uses_only_verdict_line() -> None:
    two = "> **Veredito:** `CHANGES_REQUIRED`\n...\n> **Veredito:** `APPROVED_WITH_FOLLOWUPS`\n"
    assert lc.last_verdict(two) == "APPROVED_WITH_FOLLOWUPS"
    assert lc.last_verdict("sem veredito") is None
    rejected = "> **Veredito:** `CHANGES_REQUIRED`\n## Pendências\nre-revisar até APPROVED\n"
    assert lc.last_verdict(rejected) == "CHANGES_REQUIRED"
    approved = "> **Veredito:** `APPROVED`\nantes era CHANGES_REQUIRED\n"
    assert lc.last_verdict(approved) == "APPROVED"
    assert lc.last_verdict("Veredito: APPROVED\n") is None


def test_review_problems_by_risk() -> None:
    ok = "> **Veredito:** `APPROVED`\n## Evidência verificada\n| t | main |\n## Pendências\n"
    assert lc.review_problems("baixo", {}) == []
    assert lc.review_problems(None, {}) != []
    assert len(lc.review_problems("médio", {})) == 1
    assert len(lc.review_problems("alto", {"SPEC-999-terra-review.md": ok})) == 1
    bad = "> **Veredito:** `CHANGES_REQUIRED`\n## Evidência verificada\nx\n"
    assert len(lc.review_problems("alto", {"SPEC-999-sol-review.md": bad})) == 1
    noev = "> **Veredito:** `APPROVED`\n## Evidência verificada\n\n## Pendências\n"
    assert len(lc.review_problems("alto", {"SPEC-999-sol-review.md": noev})) == 1
    assert lc.review_problems("alto", {"SPEC-999-sol-review.md": ok}) == []
    assert lc.review_problems("médio", {"SPEC-999-terra-review.md": ok}) == []
    # nome fora do lint nao conta; handoff sem linha de veredito e invalido
    assert len(lc.review_problems("médio", {"SPEC-999-Terra-review.md": ok})) == 1
    assert len(lc.review_problems("médio", {"SPEC-999-terra-review.md": "APPROVED\n"})) == 1


def test_review_problems_any_role_rejecting_blocks() -> None:
    ok = "> **Veredito:** `APPROVED`\n## Evidência verificada\nx\n"
    bad = "> **Veredito:** `CHANGES_REQUIRED`\n## Evidência verificada\nx\n"
    both = {"SPEC-999-terra-review.md": bad, "SPEC-999-luna-review.md": ok}
    assert len(lc.review_problems("médio", both)) == 1
    # so o mais recente de cada papel conta (ordem de nome)
    rounds = {"SPEC-999-terra-independent-review.md": bad, "SPEC-999-terra-review.md": ok}
    assert lc.review_problems("médio", rounds) == []
    opus = {"SPEC-999-sol-review.md": ok, "SPEC-999-terra-review.md": ok}
    assert lc.review_problems("alto", opus) == []


def test_pending_measures() -> None:
    assert len(lc.pending_measures("a\nvalor <MEDIR: wc -l x>\n")) == 1
    assert lc.pending_measures("o marcador `<MEDIR: x>` e so convencao\n") == []
    assert lc.pending_measures("valor `texto <MEDIR: x>` aqui\n") == []
    assert len(lc.pending_measures("`ok` e <MEDIR: x> cru\n")) == 1


def test_parse_free_ram_gb_comma_and_dot() -> None:
    assert lc.parse_free_ram_gb("RAM livre: 2,9 GB de 15,7 GB") == 2.9
    assert lc.parse_free_ram_gb("RAM livre: 2.9 GB de 15.7 GB") == 2.9
    assert lc.parse_free_ram_gb("lixo") is None


def test_ci_problem() -> None:
    sha = "a" * 40
    assert lc.ci_problem([], sha)
    good = {"headSha": sha, "event": "workflow_dispatch", "conclusion": "success"}
    assert lc.ci_problem([good], sha) is None
    assert lc.ci_problem([{**good, "conclusion": "failure"}], sha)
    assert lc.ci_problem([{**good, "event": "push"}], sha)


class FakeGit:
    """Runner injetavel: responde git/ram/gh sem tocar o repositorio real."""

    def __init__(self, tmp: Path, ram: str = "RAM livre: 5,0 GB de 15,7 GB", risk: str = "baixo"):
        self.calls: list[list[str]] = []
        self.tmp, self.ram = tmp, ram
        (tmp / "specs").mkdir(exist_ok=True)
        (tmp / "specs" / "SPEC-999-x.md").write_text(
            f"> **Risco:** `{risk}`\ncorpo\n", encoding="utf-8"
        )

    def __call__(self, args: list[str], cwd: str | None = None) -> tuple[int, str]:
        self.calls.append(args)
        if args[:3] == ["git", "worktree", "list"]:
            return (
                0,
                f"worktree /principal\nbranch refs/heads/main\n\nworktree {self.tmp}\nbranch refs/heads/spec-999\n",
            )
        if args[:2] == ["git", "rev-parse"]:
            return 0, "b" * 40 + "\n"
        if args[:2] == ["bash", "scripts/dev/ram.sh"]:
            return 0, self.ram + "\nsem pytest/python orfao\n"
        return 0, ""


def test_ram_below_floor_fails_unless_skipped(tmp_path: Path, capsys) -> None:
    run = FakeGit(tmp_path, ram="RAM livre: 2,5 GB de 15,7 GB")
    assert lc.main(["999", "--only", "ram"], run, {}) == 1
    assert "FAIL ram" in capsys.readouterr().out
    assert lc.main(["999", "--only", "ram"], run, {"RPG_LAND_SKIP": "ram"}) == 0
    assert "WARN ram" in capsys.readouterr().out
    assert lc.main(["999", "--only", "ram"], run, {"RPG_LAND_SKIP": "format"}) == 2


def test_ram_unreadable_is_warning(tmp_path: Path, capsys) -> None:
    run = FakeGit(tmp_path, ram="???")
    assert lc.main(["999", "--only", "ram"], run, {}) == 0
    assert "WARN ram" in capsys.readouterr().out


def test_ci_off_by_default_warns_for_alto(tmp_path: Path, capsys) -> None:
    run = FakeGit(tmp_path, risk="alto")
    assert lc.main(["999", "--only", "ci"], run, {}) == 0
    assert "WARN ci" in capsys.readouterr().out
    assert not any(c[0] == "gh" for c in run.calls)


def test_format_check_uses_force_exclude() -> None:
    cmd = lc.format_command(["evals/core/x.py", "a.py"])
    assert "--force-exclude" in cmd and cmd[-2:] == ["evals/core/x.py", "a.py"]


@pytest.mark.parametrize("argv", [[], ["12"], ["999", "--only", "nada"], ["999", "x"]])
def test_bad_usage_is_rc2(argv: list[str]) -> None:
    assert lc.main(argv, lambda a, c=None: (0, ""), {}) == 2


def test_missing_branch_is_rc2() -> None:
    def run(args: list[str], cwd: str | None = None) -> tuple[int, str]:
        return 0, "worktree /principal\nbranch refs/heads/main\n"

    assert lc.main(["999"], run, {}) == 2
