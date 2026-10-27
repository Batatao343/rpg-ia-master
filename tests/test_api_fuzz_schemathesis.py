"""SPEC-338: fuzz da API com Schemathesis in-process (legacy + DB offline).

Fora do pytest default (marker ``api_fuzz``); rodar com ``uv sync --group fuzz`` e
``pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz``.
Oráculo próprio (``check_response``): conformidade de resposta fica desligada porque a
API não documenta 400/401/404/409/503; o Schemathesis só gera as entradas.
"""

from __future__ import annotations

import os

import pytest

if os.getenv("RPG_API_FUZZ_REQUIRED") == "1":
    import schemathesis  # ausência no CI é erro de coleta, nunca skip
else:
    schemathesis = pytest.importorskip("schemathesis")

from fastapi.testclient import TestClient

import api
from tests.fakes.api_fuzz import (
    fuzz_operation,
    network_blocked,
)
from tests.fakes.two_principals import two_principals  # noqa: F401  (fixture)

pytestmark = [pytest.mark.api_fuzz, pytest.mark.timeout(180)]

# R7: exclusões fixas.
#   webhook: assinatura sobre corpo cru; transcriptions: upload cru; stream: streaming;
#   art confirm/quality: wallet + worker; checkout e google verify: rede.
EXCLUDED_RE = (
    r"^/(payments/stripe/webhook|account/transcriptions|game/action/stream"
    r"|game/\{[^}]+\}/art/(confirm|player/confirm|\{[^}]+\}/quality)"
    r"|account/checkout|account/purchases/google/verify)$"
)
# R8: rotas caras (grafo + MockLLM) com orçamento menor.
GRAPH_RE = r"^/game/(new|prologue|combat-simulator|art/brief)$"

# R10: allowlist do runtime fake. Fora: rotas que dependem de ``runtime.resources[0]``
# (Postgres: operations/{id}/cost usa game_store.pool), wallet/arte/compra/conta e as que o fake não atende.
DB_ALLOWED_RE = (
    r"^/(game/(state|map|codex|codex/dossiers|history|saves|chronicle/export"
    r"|chronicle/search|equip|cards/prepare|levelup|death|action"
    r"|save/\{game_id\}"
    r"|\{game_id\}/operations/\{operation_id\})"
    r"|data/map|auth/(config|login|signup|logout))$"
)

# R14: checks de status não documentado / schema / content-type ficam desligados (só o
# nosso oráculo roda), porque a API não documenta os 4xx/503 que devolve.


_SCHEMA = schemathesis.openapi.from_dict(api.app.openapi())
_BASE = _SCHEMA.exclude(path_regex=EXCLUDED_RE)


def _labels(schema) -> list[tuple[str, str]]:
    return sorted((o.ok().method.upper(), o.ok().path) for o in schema.get_all_operations())


LEGACY_FAST = _labels(_BASE.exclude(path_regex=GRAPH_RE))
LEGACY_GRAPH = _labels(_BASE.include(path_regex=GRAPH_RE))
DB_OPS = _labels(_BASE.include(path_regex=DB_ALLOWED_RE))


def _op(method: str, path: str):
    return _SCHEMA.find_operation_by_path(method, path)


def _ids(items):
    return [f"{m} {p}" for m, p in items]


@pytest.fixture(autouse=True)
def _block_network():
    with network_blocked():
        yield


@pytest.fixture
def legacy_client(monkeypatch):
    # Servidor configurado: sem segredo de sessão as rotas /auth/* respondem 503 por desenho.
    monkeypatch.setenv("RPG_SESSION_SECRET", "s" * 32)
    return TestClient(api.app, raise_server_exceptions=False)


@pytest.mark.parametrize(("method", "path"), LEGACY_FAST, ids=_ids(LEGACY_FAST))
def test_fuzz_legacy_fast(method, path, legacy_client):
    fuzz_operation(_op(method, path), legacy_client, max_examples=25)


@pytest.mark.parametrize(("method", "path"), LEGACY_GRAPH, ids=_ids(LEGACY_GRAPH))
def test_fuzz_legacy_graph(method, path, legacy_client):
    fuzz_operation(_op(method, path), legacy_client, max_examples=5)


@pytest.mark.parametrize(("method", "path"), DB_OPS, ids=_ids(DB_OPS))
def test_fuzz_db_offline(method, path, two_principals):  # noqa: F811
    seed = str(two_principals.game_a)
    fuzz_operation(_op(method, path), two_principals.client_a, max_examples=25, seed=seed)
