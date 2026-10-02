"""Determinism, freshness and bounded-query contracts for SPEC-166."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from project_index.generator import (
    ProjectIndexError,
    build_index,
    check_index,
    freshness_status,
    validate_graph,
)
from project_index.query import MAX_RESULTS, lookup_tests, query, state, symbol


ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "project_index").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "data/codex").mkdir(parents=True)
    (repo / "assets").mkdir()
    (repo / "pkg").mkdir()
    (repo / "mod.py").write_text(
        "def target(value: int) -> int:\n    return value + 1\n",
        encoding="utf-8",
    )
    (repo / "consumer.py").write_text(
        "from mod import target\n\ndef use() -> int:\n    return target(1)\n",
        encoding="utf-8",
    )
    (repo / "tests/test_mod.py").write_text(
        "from mod import target\n\ndef test_target():\n    assert target(1) == 2\n",
        encoding="utf-8",
    )
    (repo / "data/codex/should_not_index.py").write_text("SECRET = True\n", encoding="utf-8")
    (repo / "assets/should_not_index.py").write_text("ASSET = True\n", encoding="utf-8")
    (repo / "pkg/__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg/a.py").write_text("from .b import f\n\ndef call():\n    return f()\n", encoding="utf-8")
    (repo / "pkg/b.py").write_text("def f():\n    return 'package'\n", encoding="utf-8")
    (repo / "pkg/c.py").write_text(
        "from . import b\n\ndef call():\n    return b.f()\n", encoding="utf-8"
    )
    (repo / "b.py").write_text("def f():\n    return 'root'\n", encoding="utf-8")
    (repo / "api_routes.py").write_text(
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "@app.get('/ok')\n"
        "def ok():\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    (repo / "fake_routes.py").write_text(
        "from fastapi import FastAPI\n\n"
        "class Fake:\n"
        "    pass\n\n"
        "router = FastAPI()\n"
        "def helper(value=(router := Fake())):\n"
        "    return value\n\n"
        "@router.get('/not-http')\n"
        "def fake():\n"
        "    return None\n",
        encoding="utf-8",
    )
    (repo / "fake_match_routes.py").write_text(
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n"
        "match []:\n"
        "    case [*app]:\n"
        "        pass\n\n"
        "@app.get('/match-fake')\n"
        "def fake():\n"
        "    return None\n",
        encoding="utf-8",
    )
    (repo / "frontend.ts").write_text("export const value = 1\n", encoding="utf-8")
    (repo / ".gitignore").write_text("local_secret.py\n", encoding="utf-8")
    (repo / "local_secret.py").write_text("TOKEN = 'private'\n", encoding="utf-8")
    (repo / "project_index/domains.yaml").write_text(
        "schema_version: 1\ndomains:\n  sample:\n    entrypoints: [mod.py]\n"
        "    core: [consumer.py]\n    tests: [tests/test_mod.py]\n",
        encoding="utf-8",
    )
    (repo / "project_index/state_ownership.yaml").write_text(
        "schema_version: 1\nstate:\n  sample.value:\n    intended_writers: [mod.py]\n"
        "    important_readers: [consumer.py]\n",
        encoding="utf-8",
    )
    (repo / "project_index/eval_map.yaml").write_text(
        "schema_version: 1\ncoverage:\n  sample:\n    product_paths: [mod.py]\n"
        "    regression_tests: [tests/test_mod.py]\n    datasets: []\n",
        encoding="utf-8",
    )
    (repo / "project_index/repo_graph.schema.json").write_text(
        '{"title":"Valoria Repository Graph","type":"object"}\n', encoding="utf-8"
    )
    _git(repo, "init")
    _git(repo, "config", "user.name", "Project index fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo


def test_build_is_deterministic_and_preserves_curated_ownership(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ownership = (repo / "project_index/state_ownership.yaml").read_bytes()

    graph, manifest = build_index(repo)
    graph_bytes = (repo / "project_index/repo_graph.json").read_bytes()
    manifest_bytes = (repo / "project_index/manifest.json").read_bytes()
    build_index(repo)

    assert (repo / "project_index/repo_graph.json").read_bytes() == graph_bytes
    assert (repo / "project_index/manifest.json").read_bytes() == manifest_bytes
    assert (repo / "project_index/state_ownership.yaml").read_bytes() == ownership
    assert manifest["source_tree_hash"] == graph["source_tree_hash"]
    assert all("data/codex" not in path for path in manifest["included_files"])
    assert all("assets/" not in path for path in manifest["included_files"])
    assert "local_secret.py" not in manifest["included_files"]


def test_graph_has_provenance_confidence_and_static_relationships(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    graph, _ = build_index(repo)
    node_ids = {node["id"] for node in graph["nodes"]}

    assert "symbol:mod.target" in node_ids
    assert "symbol:consumer.use" in node_ids
    assert any(
        edge["type"] == "imports"
        and edge["source"] == "module:consumer"
        and edge["target"] == "module:mod"
        for edge in graph["edges"]
    )
    assert any(edge["type"] == "likely_test_for" for edge in graph["edges"])
    assert any(
        edge["type"] == "imports"
        and edge["source"] == "module:pkg.a"
        and edge["target"] == "module:pkg.b"
        for edge in graph["edges"]
    )
    assert not any(
        edge["type"] == "imports"
        and edge["source"] == "module:pkg.a"
        and edge["target"] == "module:b"
        for edge in graph["edges"]
    )
    assert any(
        edge["type"] == "imports"
        and edge["source"] == "module:pkg.c"
        and edge["target"] == "module:pkg.b"
        for edge in graph["edges"]
    )
    assert any(
        node["kind"] == "endpoint" and node["qualified_name"] == "GET /ok"
        for node in graph["nodes"]
    )
    assert any(
        edge["type"] == "route_to" and edge["confidence"] == "static_best_effort"
        for edge in graph["edges"]
    )
    assert not any(
        node["kind"] == "endpoint"
        and node["qualified_name"] in {"GET /not-http", "GET /match-fake"}
        for node in graph["nodes"]
    )
    assert any(node["id"] == "file:frontend.ts" and node["kind"] == "file" for node in graph["nodes"])
    assert all(edge["provenance"]["file"] for edge in graph["edges"])
    assert all(edge["confidence"] in {"static_exact", "static_best_effort"} for edge in graph["edges"])


def test_graph_validation_rejects_schema_drift(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    graph, _ = build_index(repo)
    graph["nodes"][0]["kind"] = "made_up"

    with pytest.raises(ProjectIndexError, match="invalid field values"):
        validate_graph(graph)

    graph, _ = build_index(repo)
    graph["edges"][0]["type"] = []

    with pytest.raises(ProjectIndexError, match="invalid field values"):
        validate_graph(graph)

    graph, _ = build_index(repo)
    graph["source_tree_hash"] = "sha256:" + ("z" * 64)

    with pytest.raises(ProjectIndexError, match="invalid source tree hash"):
        validate_graph(graph)

    graph, _ = build_index(repo)
    graph["nodes"][0]["line"] = True

    with pytest.raises(ProjectIndexError, match="invalid field values"):
        validate_graph(graph)


def test_check_rejects_dirty_source_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    build_index(repo)
    check_index(repo)
    (repo / "mod.py").write_text("def target(value):\n    return value + 2\n", encoding="utf-8")

    with pytest.raises(ProjectIndexError, match="stale"):
        check_index(repo)


def test_committing_generated_artifacts_warns_without_infinite_staleness(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    _, manifest = build_index(repo)
    indexed_commit = manifest["commit_sha"]
    _git(repo, "add", "project_index/manifest.json", "project_index/repo_graph.json")
    _git(repo, "commit", "-m", "version generated index")

    _, checked_manifest = check_index(repo)

    assert checked_manifest["commit_sha"] == indexed_commit
    assert freshness_status(repo, checked_manifest) == "fresh_commit_drift"


def test_real_index_excludes_content_and_queries_are_bounded() -> None:
    _, manifest = check_index(ROOT)
    included = manifest["included_files"]

    assert not any(path.startswith(("data/", "assets/", "lore_nova/", "saves/")) for path in included)
    assert not any(path.startswith((".claude/", ".agents/")) for path in included)
    result = query(ROOT, "memory context", limit=999)
    assert result["count"] <= MAX_RESULTS
    assert any(
        item.get("name") == "memory"
        or item.get("path") in {"rag.py", "services/context_builder.py"}
        for item in result["results"]
    )
    assert "Open the referenced source" in result["instruction"]


def test_real_index_locates_symbols_tests_and_curated_state() -> None:
    symbols = symbol(ROOT, "services.context_builder.build_context_pack")
    related_tests = lookup_tests(ROOT, "services/context_builder.py")
    ownership = state(ROOT, "player.gold")

    assert any(item["path"] == "services/context_builder.py" for item in symbols["results"])
    assert "tests/test_npc_memory.py" in related_tests["tests"]
    assert "memory_recall_at_5" in related_tests["metrics"]
    assert ownership["authority"] == "curated"
    assert ownership["results"][0]["canonical_domain"] == "economy"
