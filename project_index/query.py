"""Bounded, evidence-backed queries over the generated project index."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from project_index.generator import ProjectIndexError, check_index


MAX_RESULTS = 50


def _normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return text.casefold()


def _strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for key, nested in value.items() for item in [str(key), *_strings(nested)]]
    if isinstance(value, list):
        return [item for nested in value for item in _strings(nested)]
    return [str(value)]


def _load_yaml(path: Path, key: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProjectIndexError(f"cannot read curated query file {path}") from error
    if not isinstance(data, dict) or not isinstance(data.get(key), dict):
        raise ProjectIndexError(f"invalid curated query file {path}")
    return data[key]


def _limit(value: int) -> int:
    return max(1, min(int(value), MAX_RESULTS))


def _bounded(value: Any, limit: int) -> Any:
    """Bound nested curated payloads as well as the outer result list."""

    if isinstance(value, list):
        return [_bounded(item, limit) for item in value[:limit]]
    if isinstance(value, dict):
        return {key: _bounded(nested, limit) for key, nested in value.items()}
    return value


def query(root: Path, text: str, limit: int = 12) -> dict[str, Any]:
    graph, _ = check_index(root)
    tokens = [token for token in _normalized(text).split() if token]
    if not tokens:
        raise ProjectIndexError("query cannot be empty")
    domains = _load_yaml(root / "project_index/domains.yaml", "domains")
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for name, payload in domains.items():
        haystack = " ".join(_normalized(item) for item in _strings({name: payload}))
        score = sum(haystack.count(token) for token in tokens)
        if score:
            ranked.append(
                (
                    score + 10,
                    f"domain:{name}",
                    {"kind": "domain", "name": name, "evidence": payload},
                )
            )
    for node in graph["nodes"]:
        haystack = _normalized(
            " ".join(str(node.get(key) or "") for key in ("id", "path", "qualified_name", "kind"))
        )
        score = sum(haystack.count(token) for token in tokens)
        if score:
            ranked.append((score, str(node["id"]), {"kind": "node", **node}))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    bounded_limit = _limit(limit)
    results = [_bounded(payload, bounded_limit) for _, _, payload in ranked[:bounded_limit]]
    return {
        "query": text,
        "count": len(results),
        "results": results,
        "instruction": "Open the referenced source at the indexed SHA before editing.",
    }


def symbol(root: Path, name: str, limit: int = 12) -> dict[str, Any]:
    graph, _ = check_index(root)
    needle = _normalized(name)
    matches = [
        node
        for node in graph["nodes"]
        if needle in _normalized(node.get("qualified_name") or node.get("id") or "")
    ]
    matches.sort(key=lambda row: (0 if _normalized(row.get("qualified_name")) == needle else 1, row["id"]))
    results = matches[: _limit(limit)]
    return {"symbol": name, "count": len(results), "results": _bounded(results, _limit(limit))}


def impact(root: Path, name: str, limit: int = 20) -> dict[str, Any]:
    graph, _ = check_index(root)
    matches = symbol(root, name, limit=_limit(limit))["results"]
    ids = {node["id"] for node in matches}
    related = [
        edge for edge in graph["edges"] if edge["source"] in ids or edge["target"] in ids
    ]
    related.sort(key=lambda row: (row["source"], row["target"], row["type"]))
    results = related[: _limit(limit)]
    return {"symbol": name, "matched_nodes": matches, "count": len(results), "edges": results}


def lookup_tests(root: Path, product_path: str, limit: int = 20) -> dict[str, Any]:
    graph, _ = check_index(root)
    normalized_path = PurePath(product_path)
    coverage = _load_yaml(root / "project_index/eval_map.yaml", "coverage")
    tests: set[str] = set()
    evals: set[str] = set()
    datasets: set[str] = set()
    for payload in coverage.values():
        if normalized_path in {PurePath(path) for path in payload.get("product_paths", [])}:
            tests.update(payload.get("regression_tests", []))
            evals.update(payload.get("metrics", []))
            datasets.update(payload.get("datasets", []))
    target_id = f"file:{normalized_path}"
    node_by_id = {node["id"]: node for node in graph["nodes"]}
    for edge in graph["edges"]:
        if edge["type"] == "likely_test_for" and edge["target"] == target_id:
            node = node_by_id.get(edge["source"])
            if node:
                tests.add(node["path"])
    bounded_limit = _limit(limit)
    bounded_tests = sorted(tests)[:bounded_limit]
    return {
        "path": normalized_path,
        "tests": bounded_tests,
        "metrics": sorted(evals)[:bounded_limit],
        "datasets": sorted(datasets)[:bounded_limit],
    }


def state(root: Path, field: str, limit: int = 12) -> dict[str, Any]:
    check_index(root)
    ownership = _load_yaml(root / "project_index/state_ownership.yaml", "state")
    needle = _normalized(field)
    matches = [
        {"field": name, **payload}
        for name, payload in ownership.items()
        if needle in _normalized(name)
    ]
    matches.sort(key=lambda row: row["field"])
    bounded_limit = _limit(limit)
    results = _bounded(matches[:bounded_limit], bounded_limit)
    return {"state": field, "count": len(results), "results": results, "authority": "curated"}


class PurePath(str):
    """Normalize repo paths without touching the filesystem."""

    def __new__(cls, value: str) -> "PurePath":
        return str.__new__(cls, value.replace("\\", "/").removeprefix("./"))


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
