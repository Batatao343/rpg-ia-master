"""Build a bounded, deterministic repository graph from source files."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


GENERATOR_VERSION = "1.0.0"
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
ARTIFACT_NAMES = {"pyproject.toml", "package.json", "vite.config.ts", "Procfile"}
EXCLUDED_PREFIXES = (
    ".agents",
    ".claude",
    ".git",
    ".venv",
    ".pytest_cache",
    ".pytest-spec-index",
    ".ruff_cache",
    ".tmp",
    ".uv-cache",
    "__pycache__",
    "assets",
    "data",
    "faiss_lore_index",
    "faiss_rules_index",
    "frontend",
    "lore_nova",
    "node_modules",
    "playtest_runs",
    "saves",
    "saves_playtest",
    "web/dist",
    "web/node_modules",
    "web/public/art",
)
GENERATED_PATHS = {
    "project_index/manifest.json",
    "project_index/repo_graph.json",
    "project_index/repo_graph.schema.json",
}


class ProjectIndexError(RuntimeError):
    """The repository index cannot be trusted or generated."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    if result.returncode:
        raise ProjectIndexError(f"cannot resolve git HEAD: {result.stderr.strip()}")
    return result.stdout.strip()


def _git_visible_files(root: Path) -> list[str]:
    """Return tracked and non-ignored untracked files, never private ignored files."""

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    if result.returncode:
        raise ProjectIndexError("cannot enumerate git-visible files")
    return sorted(
        (item.decode("utf-8", errors="replace") for item in result.stdout.split(b"\0") if item),
        key=str.casefold,
    )


def _excluded(relative: str) -> bool:
    folded = relative.casefold()
    return any(folded == prefix.casefold() or folded.startswith(f"{prefix.casefold()}/") for prefix in EXCLUDED_PREFIXES)


def discover_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in _git_visible_files(root):
        path = root / PurePosixPath(relative)
        if not path.is_file():
            continue
        if relative in GENERATED_PATHS or _excluded(relative):
            continue
        if path.suffix.casefold() in SOURCE_SUFFIXES or path.name in ARTIFACT_NAMES:
            files.append(path)
        elif relative.startswith(".github/workflows/") and path.suffix.casefold() in {".yml", ".yaml"}:
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold())


def _source_tree_hash(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def _module_name(relative: str) -> str:
    path = PurePosixPath(relative)
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _absolute_import_from(
    module: str, relative: str, *, is_package: bool, level: int
) -> str:
    if level <= 0:
        return relative
    package = module.split(".") if is_package else module.split(".")[:-1]
    ascend = level - 1
    if ascend > len(package):
        return relative
    prefix = package[: len(package) - ascend]
    return ".".join([*prefix, *relative.split(".")]) if relative else ".".join(prefix)


def _node(
    node_id: str,
    kind: str,
    path: str,
    line: int | None,
    qualified_name: str | None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": kind,
        "path": path,
        "line": line,
        "qualified_name": qualified_name,
    }


def _edge(
    source: str,
    target: str,
    kind: str,
    path: str,
    line: int | None,
    confidence: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "type": kind,
        "confidence": confidence,
        "provenance": {"file": path, "line": line, "extractor": "python_ast"},
    }


@dataclass
class PythonUnit:
    path: str
    module: str
    tree: ast.Module
    file_id: str
    module_id: str
    aliases: dict[str, str]
    definitions: dict[str, str]
    symbol_nodes: list[dict[str, Any]]
    structural_edges: list[dict[str, Any]]
    endpoint_nodes: list[dict[str, Any]]


def _bound_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for child in target.elts for name in _bound_names(child)}
    return set()


class _WriteCollector(ast.NodeVisitor):
    """Collect possible writes without descending into deferred function bodies."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.mutated_roots: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802 - AST visitor API
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802 - AST visitor API
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            root: ast.expr = node.value
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if isinstance(root, ast.Name):
                self.mutated_roots.add(root.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - AST visitor API
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"setattr", "delattr"}
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            self.mutated_roots.add(node.args[0].id)
        self.generic_visit(node)

    def _visit_function_header(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for argument in arguments:
            if argument.annotation:
                self.visit(argument.annotation)
        if node.returns:
            self.visit(node.returns)
        for type_param in getattr(node, "type_params", []):
            self.visit(type_param)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        for expression in [*node.decorator_list, *node.bases]:
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for type_param in getattr(node, "type_params", []):
            self.visit(type_param)
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        return

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self.names.update(alias.asname or alias.name for alias in node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:  # noqa: N802
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:  # noqa: N802
        if node.name:
            self.names.add(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:  # noqa: N802
        if node.rest:
            self.names.add(node.rest)
        self.generic_visit(node)


def _possible_writes(statement: ast.stmt) -> tuple[set[str], set[str]]:
    collector = _WriteCollector()
    collector.visit(statement)
    return collector.names, collector.mutated_roots


def _fastapi_bindings(tree: ast.Module) -> dict[int, set[str]]:
    """Snapshot proven FastAPI/APIRouter instances at each top-level function."""

    constructors: set[str] = set()
    namespaces: set[str] = set()
    bindings: set[str] = set()
    snapshots: dict[int, set[str]] = {}

    def shadow(names: set[str]) -> None:
        constructors.difference_update(names)
        namespaces.difference_update(names)
        bindings.difference_update(names)

    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names, mutated_roots = _possible_writes(statement)
            immediate_writes = (names - {statement.name}) | mutated_roots
            snapshots[id(statement)] = bindings - immediate_writes
            shadow(names | mutated_roots)
            continue
        if isinstance(statement, ast.ClassDef):
            names, mutated_roots = _possible_writes(statement)
            shadow(names | mutated_roots)
            continue
        if isinstance(statement, ast.ImportFrom):
            imported_names = {alias.asname or alias.name for alias in statement.names}
            shadow(imported_names)
            if statement.module == "fastapi":
                constructors.update(
                    alias.asname or alias.name
                    for alias in statement.names
                    if alias.name in {"FastAPI", "APIRouter"}
                )
            continue
        if isinstance(statement, ast.Import):
            imported_names = {
                alias.asname or alias.name.split(".")[0] for alias in statement.names
            }
            shadow(imported_names)
            namespaces.update(
                alias.asname or alias.name
                for alias in statement.names
                if alias.name == "fastapi"
            )
            continue
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        else:
            names, mutated_roots = _possible_writes(statement)
            shadow(names | mutated_roots)
            continue
        names, mutated_roots = _possible_writes(statement)
        is_fastapi_constructor = False
        if isinstance(value, ast.Call):
            constructor = value.func
            is_fastapi_constructor = (
                isinstance(constructor, ast.Name) and constructor.id in constructors
            ) or (
                isinstance(constructor, ast.Attribute)
                and isinstance(constructor.value, ast.Name)
                and constructor.value.id in namespaces
                and constructor.attr in {"FastAPI", "APIRouter"}
            )
        shadow(names | mutated_roots)
        if is_fastapi_constructor:
            bindings.update(name for target in targets for name in _bound_names(target))
    return snapshots


def _endpoint_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef, http_bindings: set[str]
) -> list[tuple[str, str, int]]:
    endpoints: list[tuple[str, str, int]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id not in http_bindings:
            continue
        method = decorator.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            continue
        if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            continue
        route = decorator.args[0].value
        if isinstance(route, str):
            endpoints.append((method, route, decorator.lineno))
    return endpoints


def _parse_python(root: Path, path: Path) -> PythonUnit:
    relative = path.relative_to(root).as_posix()
    module = _module_name(relative)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        raise ProjectIndexError(f"cannot parse {relative}: {error}") from error
    file_id = f"file:{relative}"
    module_id = f"module:{module}"
    aliases: dict[str, str] = {}
    is_package = path.name == "__init__.py"
    http_bindings = _fastapi_bindings(tree)
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(statement, ast.ImportFrom):
            imported_from = _absolute_import_from(
                module, statement.module or "", is_package=is_package, level=statement.level
            )
            for alias in statement.names:
                aliases[alias.asname or alias.name] = f"{imported_from}.{alias.name}"

    definitions: dict[str, str] = {}
    symbols: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []

    def visit_def(
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        scope: list[str],
        parent_id: str,
        in_class: bool,
    ) -> None:
        qualified = ".".join([module, *scope, node.name])
        symbol_id = f"symbol:{qualified}"
        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif relative.startswith("tests/") or node.name.startswith("test_"):
            kind = "test"
        elif in_class:
            kind = "method"
        else:
            kind = "function"
        symbols.append(_node(symbol_id, kind, relative, node.lineno, qualified))
        edges.append(_edge(parent_id, symbol_id, "defines", relative, node.lineno, "static_exact"))
        if not scope:
            definitions[node.name] = symbol_id
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not scope:
            for method, route, line in _endpoint_decorators(
                node, http_bindings.get(id(node), set())
            ):
                endpoint_id = f"endpoint:{method}:{route}:{relative}:{node.lineno}"
                endpoints.append(_node(endpoint_id, "endpoint", relative, line, f"{method} {route}"))
                edges.append(
                    _edge(
                        endpoint_id,
                        symbol_id,
                        "route_to",
                        relative,
                        line,
                        "static_best_effort",
                    )
                )
        child_scope = [*scope, node.name]
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                visit_def(child, child_scope, symbol_id, isinstance(node, ast.ClassDef) or in_class)

    for statement in tree.body:
        if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            visit_def(statement, [], module_id, False)
    return PythonUnit(
        path=relative,
        module=module,
        tree=tree,
        file_id=file_id,
        module_id=module_id,
        aliases=aliases,
        definitions=definitions,
        symbol_nodes=symbols,
        structural_edges=edges,
        endpoint_nodes=endpoints,
    )


class _CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - AST visitor API
        self.calls.append(node)
        self.generic_visit(node)


def _function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _graph_schema_hash(root: Path) -> str:
    path = root / "project_index/repo_graph.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectIndexError("repo graph JSON schema is missing or invalid") from error
    if not isinstance(schema, dict) or schema.get("title") != "Valoria Repository Graph":
        raise ProjectIndexError("repo graph JSON schema has an unexpected identity")
    return _sha256(_canonical_json(schema))


def generate(root: Path, *, indexed_commit: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    files = discover_files(root)
    commit_sha = indexed_commit or _git_head(root)
    tree_hash = _source_tree_hash(root, files)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    units: list[PythonUnit] = []

    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.casefold() == ".py":
            unit = _parse_python(root, path)
            units.append(unit)
            nodes.append(_node(unit.file_id, "file", relative, 1, None))
            nodes.append(_node(unit.module_id, "module", relative, 1, unit.module))
            nodes.extend(unit.symbol_nodes)
            nodes.extend(unit.endpoint_nodes)
            edges.append(_edge(unit.file_id, unit.module_id, "contains", relative, 1, "static_exact"))
            edges.extend(unit.structural_edges)
        elif path.suffix.casefold() in SOURCE_SUFFIXES:
            nodes.append(_node(f"file:{relative}", "file", relative, 1, None))
        else:
            nodes.append(_node(f"artifact:{relative}", "artifact", relative, 1, None))

    modules = {unit.module: unit for unit in units}
    symbol_by_qualified = {
        str(node["qualified_name"]): str(node["id"])
        for unit in units
        for node in unit.symbol_nodes
        if node["qualified_name"]
    }
    for unit in units:
        for statement in unit.tree.body:
            imported: list[tuple[str, int]] = []
            if isinstance(statement, ast.Import):
                imported.extend((alias.name, statement.lineno) for alias in statement.names)
            elif isinstance(statement, ast.ImportFrom):
                imported_from = _absolute_import_from(
                    unit.module,
                    statement.module or "",
                    is_package=PurePosixPath(unit.path).name == "__init__.py",
                    level=statement.level,
                )
                if statement.module:
                    imported.append((imported_from, statement.lineno))
                else:
                    imported.extend(
                        (f"{imported_from}.{alias.name}", statement.lineno)
                        for alias in statement.names
                    )
            for imported_module, line in imported:
                candidate = imported_module
                while candidate and candidate not in modules:
                    candidate = candidate.rpartition(".")[0]
                if not candidate:
                    continue
                target = modules[candidate]
                edges.append(
                    _edge(unit.module_id, target.module_id, "imports", unit.path, line, "static_exact")
                )
                if unit.path.startswith("tests/"):
                    edges.append(
                        _edge(
                            unit.file_id,
                            target.file_id,
                            "likely_test_for",
                            unit.path,
                            line,
                            "static_best_effort",
                        )
                    )

        for function in _function_nodes(unit.tree):
            candidates = [
                node
                for node in unit.symbol_nodes
                if node["line"] == function.lineno and str(node["qualified_name"]).endswith(f".{function.name}")
            ]
            if not candidates:
                continue
            source_id = str(candidates[0]["id"])
            collector = _CallCollector()
            for statement in function.body:
                collector.visit(statement)
            for call in collector.calls:
                target_id: str | None = None
                if isinstance(call.func, ast.Name):
                    target_id = unit.definitions.get(call.func.id)
                    imported = unit.aliases.get(call.func.id)
                    if target_id is None and imported:
                        target_id = symbol_by_qualified.get(imported)
                elif isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                    prefix = unit.aliases.get(call.func.value.id)
                    if prefix:
                        target_id = symbol_by_qualified.get(f"{prefix}.{call.func.attr}")
                if target_id:
                    edges.append(
                        _edge(source_id, target_id, "calls", unit.path, call.lineno, "static_best_effort")
                    )

    unique_nodes = {str(node["id"]): node for node in nodes}
    unique_edges = {_canonical_json(edge): edge for edge in edges}
    graph = {
        "schema_version": 1,
        "commit_sha": commit_sha,
        "source_tree_hash": tree_hash,
        "nodes": sorted(unique_nodes.values(), key=lambda row: str(row["id"])),
        "edges": sorted(
            unique_edges.values(),
            key=lambda row: (
                str(row["source"]),
                str(row["target"]),
                str(row["type"]),
                int(row["provenance"]["line"] or 0),
            ),
        ),
    }
    validate_graph(graph)
    node_counts = Counter(str(node["kind"]) for node in graph["nodes"])
    edge_counts = Counter(str(edge["type"]) for edge in graph["edges"])
    manifest = {
        "schema_version": 1,
        "generator_version": GENERATOR_VERSION,
        "commit_sha": commit_sha,
        "source_tree_hash": tree_hash,
        "graph_hash": _sha256(_canonical_json(graph)),
        "graph_schema_hash": _graph_schema_hash(root),
        "commit_policy": "warn_on_commit_drift_when_source_tree_hash_matches",
        "languages": {"python": "ast", "typescript_javascript": "file_only"},
        "included_files": [path.relative_to(root).as_posix() for path in files],
        "excluded_prefixes": list(EXCLUDED_PREFIXES),
        "node_counts": dict(sorted(node_counts.items())),
        "edge_counts": dict(sorted(edge_counts.items())),
    }
    return graph, manifest


def validate_graph(graph: dict[str, Any]) -> None:
    allowed_node_kinds = {
        "file",
        "module",
        "class",
        "function",
        "method",
        "test",
        "endpoint",
        "artifact",
    }
    allowed_edge_kinds = {
        "imports",
        "defines",
        "contains",
        "references",
        "calls",
        "route_to",
        "likely_test_for",
    }
    if set(graph) != {"schema_version", "commit_sha", "source_tree_hash", "nodes", "edges"}:
        raise ProjectIndexError("repo graph has unexpected top-level fields")
    if type(graph.get("schema_version")) is not int or graph["schema_version"] != 1:
        raise ProjectIndexError("unsupported repo graph schema")
    if not isinstance(graph.get("commit_sha"), str) or len(graph["commit_sha"]) < 7:
        raise ProjectIndexError("repo graph has invalid commit SHA")
    tree_hash = graph.get("source_tree_hash")
    if not isinstance(tree_hash, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", tree_hash) is None:
        raise ProjectIndexError("repo graph has invalid source tree hash")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProjectIndexError("repo graph nodes/edges must be lists")
    node_fields = {"id", "kind", "path", "line", "qualified_name"}
    for node in nodes:
        if not isinstance(node, dict) or set(node) != node_fields:
            raise ProjectIndexError("repo graph node does not match schema")
        if (
            not isinstance(node["id"], str)
            or not isinstance(node["path"], str)
            or not isinstance(node["kind"], str)
            or node["kind"] not in allowed_node_kinds
            or not (node["line"] is None or type(node["line"]) is int)
            or not (
                node["qualified_name"] is None
                or isinstance(node["qualified_name"], str)
            )
        ):
            raise ProjectIndexError("repo graph node has invalid field values")
    ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(ids) != len(nodes) or len(ids) != len(set(ids)):
        raise ProjectIndexError("repo graph node IDs must be unique strings")
    valid = set(ids)
    edge_fields = {"source", "target", "type", "confidence", "provenance"}
    provenance_fields = {"file", "line", "extractor"}
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) != edge_fields:
            raise ProjectIndexError("repo graph edge does not match schema")
        if (
            not isinstance(edge["source"], str)
            or not isinstance(edge["target"], str)
            or not isinstance(edge["type"], str)
            or not isinstance(edge["confidence"], str)
        ):
            raise ProjectIndexError("repo graph edge has invalid field values")
        if edge.get("source") not in valid or edge.get("target") not in valid:
            raise ProjectIndexError("repo graph edge points to a missing node")
        if edge.get("type") not in allowed_edge_kinds:
            raise ProjectIndexError("repo graph edge has invalid type")
        provenance = edge.get("provenance")
        if (
            not isinstance(provenance, dict)
            or set(provenance) != provenance_fields
            or not isinstance(provenance.get("file"), str)
            or not provenance.get("file")
            or not (
                provenance.get("line") is None
                or type(provenance.get("line")) is int
            )
            or not (
                provenance.get("extractor") is None
                or isinstance(provenance.get("extractor"), str)
            )
        ):
            raise ProjectIndexError("repo graph edge lacks provenance")
        if edge.get("confidence") not in {"static_exact", "static_best_effort", "curated"}:
            raise ProjectIndexError("repo graph edge has invalid confidence")


def _load_curated(path: Path, top_key: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProjectIndexError(f"invalid curated index file {path}: {error}") from error
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get(top_key), dict):
        raise ProjectIndexError(f"invalid curated index schema in {path}")
    return data


def validate_curated_files(root: Path) -> None:
    index_root = root / "project_index"
    domains = _load_curated(index_root / "domains.yaml", "domains")
    ownership = _load_curated(index_root / "state_ownership.yaml", "state")
    eval_map = _load_curated(index_root / "eval_map.yaml", "coverage")
    referenced_paths: set[str] = set()
    for domain in domains["domains"].values():
        for key in ("entrypoints", "core", "tests"):
            referenced_paths.update(domain.get(key, []))
    for item in ownership["state"].values():
        referenced_paths.update(item.get("intended_writers", []))
        referenced_paths.update(item.get("important_readers", []))
    for item in eval_map["coverage"].values():
        referenced_paths.update(item.get("product_paths", []))
        referenced_paths.update(item.get("regression_tests", []))
        referenced_paths.update(item.get("datasets", []))
    missing = sorted(path for path in referenced_paths if not (root / path).is_file())
    if missing:
        raise ProjectIndexError("curated index references missing files: " + ", ".join(missing))


def build_index(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    validate_curated_files(root)
    graph, manifest = generate(root)
    index_root = root / "project_index"
    index_root.mkdir(parents=True, exist_ok=True)
    (index_root / "repo_graph.json").write_bytes(
        json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    (index_root / "manifest.json").write_bytes(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    return graph, manifest


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectIndexError(f"cannot read index artifact {path}") from error
    if not isinstance(data, dict):
        raise ProjectIndexError(f"index artifact must be an object: {path}")
    return data


def check_index(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    validate_curated_files(root)
    actual_graph = _read_json(root / "project_index/repo_graph.json")
    actual_manifest = _read_json(root / "project_index/manifest.json")
    indexed_commit = actual_manifest.get("commit_sha")
    if not isinstance(indexed_commit, str) or len(indexed_commit) < 7:
        raise ProjectIndexError("project index has invalid commit SHA")
    expected_graph, expected_manifest = generate(root, indexed_commit=indexed_commit)
    if actual_graph != expected_graph or actual_manifest != expected_manifest:
        raise ProjectIndexError("project index is stale: source tree or generated artifacts changed")
    return actual_graph, actual_manifest


def freshness_status(root: Path, manifest: dict[str, Any]) -> str:
    """Commit drift warns; byte-identical indexed source remains usable."""

    return "fresh" if manifest.get("commit_sha") == _git_head(root.resolve()) else "fresh_commit_drift"
