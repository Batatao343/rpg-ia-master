"""SPEC-381 R3/R4/R5/R9/R10/R13/R21: estrutura permanente do fatiamento de ``api.py``.

``docs/spec381/patch_lars.json`` congela o modulo-lar de cada nome que algum teste faz patch
(``monkeypatch.setattr``). O patch so vale se o nome mora no lar e em nenhum outro modulo da API.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LARS: dict[str, str] = json.loads(
    (ROOT / "docs/spec381/patch_lars.json").read_text(encoding="utf-8")
)
NEW_FILES = [ROOT / "api_core.py", ROOT / "api_models.py", ROOT / "api_presenters.py"] + sorted(
    (ROOT / "routes").glob("*.py")
)
MODULES = ["api_core", "api_models", "api_presenters"] + [
    f"routes.{p.stem}" for p in sorted((ROOT / "routes").glob("*.py")) if p.stem != "__init__"
]


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _defined(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
    return out


@pytest.mark.parametrize("path", NEW_FILES, ids=lambda p: p.name)
def test_new_modules_never_import_api(path):
    """R3: direcao unica api -> routes -> presenters -> models; ninguem importa ``api``."""
    for n in ast.walk(_tree(path)):
        if isinstance(n, ast.Import):
            assert all(a.name.split(".")[0] != "api" for a in n.names), path.name
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] != "api" or n.level, path.name


@pytest.mark.parametrize(
    "path", [p for p in NEW_FILES if p.parent.name == "routes"], ids=lambda p: p.name
)
def test_routers_do_not_read_env_at_import(path):
    """R4/§3.4: ``importlib.reload(api)`` nao recarrega ``routes/*``; env so dentro de funcao."""
    for stmt in _tree(path).body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(stmt):
            if isinstance(n, ast.Attribute) and n.attr in {"getenv", "environ"}:
                pytest.fail(f"{path.name}:{n.lineno} le env no nivel do modulo")


def test_import_side_effects_stay_in_api():
    """R4: os efeitos colaterais de import ficam em ``api.py``."""
    calls = {
        getattr(n.value.func, "id", None)
        for n in _tree(ROOT / "api.py").body
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
    }
    assert {
        "assert_boot_policy",
        "configure_logging",
        "log_boot_once",
        "set_llm_telemetry_hook",
        "set_llm_attempt_telemetry_hook",
    } <= calls


@pytest.mark.parametrize("name", sorted(LARS))
def test_patch_targets_live(name):
    """R13: o nome patchado mora so no lar; ``api`` nao o reexporta (patch esquecido falha alto)."""
    import api  # noqa: PLC0415

    lar = LARS[name]
    lar_mod = importlib.import_module(lar)
    assert hasattr(lar_mod, name), f"{lar} nao define {name}"
    if lar != "api":
        assert not hasattr(api, name), f"api ainda expoe {name}"
    for mod in ["api", *MODULES]:
        if mod == lar:
            continue
        defined = _defined(_tree(ROOT / (mod.replace(".", "/") + ".py")))
        assert name not in defined, f"{mod} tambem liga {name}"


def test_reexports_are_identical_and_not_rebound():
    """R5/R9: reexport = mesmo objeto do lar; nome religado por ``global`` nunca e reexportado."""
    import api  # noqa: PLC0415

    src = (ROOT / "api.py").read_text(encoding="utf-8")
    start = src.index("# --- reexports (SPEC-381 R9)")
    end = src.index("# --- fim dos reexports ---")
    block = ast.parse(src[start:end])
    rebound: dict[str, set[str]] = {}
    for mod in MODULES:
        names = {
            g
            for n in ast.walk(_tree(ROOT / (mod.replace(".", "/") + ".py")))
            if isinstance(n, ast.Global)
            for g in n.names
        }
        rebound[mod] = names
    checked = 0
    for n in block.body:
        assert isinstance(n, ast.ImportFrom)
        home = importlib.import_module(n.module)
        for a in n.names:
            assert getattr(api, a.name) is getattr(home, a.name), a.name
            assert a.name not in rebound[n.module], f"{a.name} e religado por global"
            assert a.name not in LARS, f"{a.name} e patchado e nao pode ser reexportado"
            checked += 1
    assert checked > 10


def test_no_included_router_besides_cron():
    """R21: montagem plana; so o cron segue com ``include_router``."""
    import api  # noqa: PLC0415

    opaque = [r for r in api.app.routes if type(r).__name__ == "_IncludedRouter"]
    assert len(opaque) == 1
    paths = [getattr(x, "path", "") for x in opaque[0].original_router.routes]
    assert paths and all(p.startswith("/internal/cron") for p in paths)
