"""SPEC-381 R13b: plugin pytest TEMPORARIO que prova que cada patch de nome da API esta vivo.

Carregue com ``-p patch_liveness`` e ``PYTHONPATH=scripts/dev`` (nao entra na suite default).
Embrulha ``MonkeyPatch.setattr``: para os nomes de ``docs/spec381/patch_lars.json`` troca cada valor
chamavel por um proxy que registra se foi chamado; grava ``{nodeid::nome: chamado}`` em
``$LIVENESS_OUT``. Rodar no commit-base (alvo ``api``) e na ponta (alvo ``<lar>``): os dois JSON
tem de ser iguais (um True que vira False = patch inocuo).

Com ``LIVENESS_MUTATE=1`` os valores NAO chamaveis (``_DOCS_PATHS``, ``game_graph`` ...) viram um
sentinela invalido: os testes desses nomes tem de FALHAR, antes e depois. ``$LIVENESS_OUT`` guarda
o desfecho (passed/failed) por teste.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]
NAMES = set(json.loads((ROOT / "docs/spec381/patch_lars.json").read_text(encoding="utf-8")))
MUTATE = os.environ.get("LIVENESS_MUTATE") == "1"
_NOTSET = object()
_orig = MonkeyPatch.setattr
CUR: list[str] = [""]
CALLED: dict[str, bool] = {}
OUTCOME: dict[str, str] = {}
MUTATED_TESTS: set[str] = set()


class _Sentinel:
    """Valor invalido de proposito (nao chamavel, sem atributos)."""


def _wrap(attr: str, value):
    key = f"{CUR[0]}::{attr}"
    if callable(value) and not isinstance(value, type):
        CALLED.setdefault(key, False)

        def proxy(*a, **k):
            CALLED[key] = True
            return value(*a, **k)

        try:
            return functools.wraps(value)(proxy)
        except (AttributeError, TypeError):
            return proxy
    if MUTATE:
        MUTATED_TESTS.add(CUR[0])
        return _Sentinel()
    CALLED.setdefault(key + "::noncallable", True)
    return value


def _setattr(self, target, name, value=_NOTSET, raising=True):
    if isinstance(target, str) and value is _NOTSET:
        attr = target.rsplit(".", 1)[-1]
        if attr in NAMES:
            name = _wrap(attr, name)
        return _orig(self, target, name, raising=raising)
    if isinstance(name, str) and name in NAMES:
        value = _wrap(name, value)
    return _orig(self, target, name, value, raising=raising)


MonkeyPatch.setattr = _setattr


def pytest_runtest_setup(item):
    CUR[0] = item.nodeid


def pytest_runtest_logreport(report):
    if report.when == "call":
        OUTCOME[report.nodeid] = report.outcome


def pytest_sessionfinish(session):
    out = os.environ.get("LIVENESS_OUT")
    if not out:
        return
    if MUTATE:
        data = {n: OUTCOME.get(n, "missing") for n in sorted(MUTATED_TESTS)}
    else:
        data = dict(sorted(CALLED.items()))
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
