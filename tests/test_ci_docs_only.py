"""Workspace C6: docs-only CI filter, Markdown link checker and Dependabot groups."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from scripts import check_md_links, ci_docs_only

ROOT = Path(__file__).resolve().parents[1]


def test_docs_only_classification_is_conservative():
    assert ci_docs_only.docs_only(["docs/a.md", "handoffs/SPEC-001-sol-review.md", "ESTADO_ATUAL.md"])
    assert ci_docs_only.docs_only(["docs/historico/proximas-specs/x/y.md", "docs/img.png"])
    # lore/specs/código nunca contam como docs-only
    assert not ci_docs_only.docs_only(["docs/a.md", "data/codex/x.md"])
    assert not ci_docs_only.docs_only(["specs/SPEC-001-x.md"])
    assert not ci_docs_only.docs_only(["docs/a.md", "api.py"])
    assert not ci_docs_only.docs_only([])


def test_unknown_base_runs_full_suite(tmp_path):
    assert ci_docs_only.changed_paths(ROOT, "", "HEAD") is None
    assert ci_docs_only.changed_paths(ROOT, "0" * 40, "HEAD") is None
    assert ci_docs_only.changed_paths(ROOT, "deadbeef" * 5, "HEAD") is None
    out = tmp_path / "out"
    ci_docs_only.main(["--root", str(ROOT), "--base", "", "--head", "HEAD", "--github-output", str(out)])
    assert out.read_text(encoding="utf-8") == "docs_only=false\n"


def test_docs_only_from_real_git_range(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "api.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "n.md").write_text("# n\n")
    git("add", "-A")
    git("commit", "-qm", "docs")
    assert ci_docs_only.changed_paths(tmp_path, base, "HEAD") == ["docs/n.md"]
    (tmp_path / "api.py").write_text("x = 2\n")
    git("add", "-A")
    git("commit", "-qm", "code")
    assert not ci_docs_only.docs_only(ci_docs_only.changed_paths(tmp_path, base, "HEAD"))


def test_doc_tests_selection_includes_doc_readers():
    selected = ci_docs_only.doc_tests(ROOT)
    assert "tests/test_agents_contract.py" in selected
    assert all(path.startswith("tests/test_") for path in selected)


def test_link_checker_finds_only_unlisted_breaks(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("[ok](b.md) [web](https://x) [anc](#t) [bad](missing.md) ![img](nope.png)\n")
    (tmp_path / "b.md").write_text("[up](a.md#x) [sp](dir%20x/c.md)\n")
    (tmp_path / "dir x").mkdir()
    (tmp_path / "dir x" / "c.md").write_text("ok\n")
    found = check_md_links.broken_links(tmp_path, [tmp_path / "a.md", tmp_path / "b.md"])
    assert found == ["a.md -> missing.md"]


def test_repo_has_no_new_broken_links():
    baseline = ROOT / "scripts" / "md_links_baseline.txt"
    assert check_md_links.main(["--baseline", str(baseline)]) == 0


def test_workflows_wire_docs_only_without_touching_eval_gates():
    validate = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"))
    jobs = validate["jobs"]
    assert jobs["test"]["needs"] == "scope" and "docs_only != 'true'" in jobs["test"]["if"]
    assert "docs_only == 'true'" in jobs["docs-only"]["if"]
    assert "needs" not in jobs["secret-scan"], "secret scan must run on docs-only changes too"
    audit = yaml.safe_load((ROOT / ".github/workflows/audit-local.yml").read_text(encoding="utf-8"))
    assert "docs_only != 'true'" in audit["jobs"]["infra-browser"]["if"]
    gates = (ROOT / ".github/workflows/eval-gates.yml").read_text(encoding="utf-8")
    assert "ci_docs_only" not in gates, "deterministic-evals / project index check keep running always"


def test_dependabot_groups_minor_patch_and_leaves_majors_alone():
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {update["package-ecosystem"] for update in config["updates"]}
    assert ecosystems == {"github-actions", "pip", "npm"}
    for update in config["updates"]:
        groups = update["groups"].values()
        assert [g["update-types"] for g in groups] == [["minor", "patch"]]


def test_ci_pins_runner_image_and_node_from_nvmrc():
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        assert "runs-on: ubuntu-latest" not in text, workflow.name
        assert "node-version:" not in text, f"{workflow.name}: use node-version-file: web/.nvmrc"
    assert (ROOT / "web/.nvmrc").read_text(encoding="utf-8").strip() == "22"
