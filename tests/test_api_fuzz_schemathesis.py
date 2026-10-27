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
# (Postgres: operations/{id} usa resources[0].connection(); operations/{id}/cost usa
# game_store.pool; o legacy cobre as duas), wallet/arte/compra/conta e as que o fake não atende.
DB_ALLOWED_RE = (
    r"^/(game/(state|map|codex|codex/dossiers|history|saves|chronicle/export"
    r"|chronicle/search|equip|cards/prepare|levelup|death|action"
    r"|save/\{game_id\})"
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


@pytest.fixture
def legacy_seed(legacy_client):
    """P2-2: campanha real no legacy para as rotas com ``game_id`` chegarem ao handler."""
    response = legacy_client.post(
        "/game/new",
        json={
            "name": "Heroi-Fuzz",
            "race": "Humano",
            "class_name": "Devoto do Abismo",
            "region": "Nova Arcádia",
            "level": 1,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["game_id"]


# Rotas que mudam estado ou rodam o grafo: pelo menos um exemplo precisa passar da
# validação (status fora de 400/422), senão o fuzz só testou o validador.
MUST_REACH_HANDLER = {
    ("POST", "/game/equip"),
    ("POST", "/game/levelup"),
    ("POST", "/game/death"),
    ("POST", "/game/cards/prepare"),
    ("POST", "/game/action"),
    ("DELETE", "/game/save/{game_id}"),
    ("POST", "/game/new"),
    ("POST", "/game/prologue"),
    ("POST", "/game/combat-simulator"),
    ("POST", "/game/art/brief"),
}


# Respostas de gate (validação/idempotência/id), ainda antes da regra de negócio.
GATE_CODES = {
    "400:None",
    "400:game_id_invalid",
    "400:action_id_required",
    "400:action_id_invalid",
    "400:idempotency_key_required",
}


def _assert_reached(method: str, path: str, statuses) -> None:
    print(f"STATUS {method} {path}: {dict(sorted(statuses.items()))}")
    if (method, path) in MUST_REACH_HANDLER:
        reached = {k for k in statuses if k.split(":")[0] not in {"422"} and k not in GATE_CODES}
        assert reached, f"{method} {path} nunca passou da validação: {dict(statuses)}"


def test_scope_is_locked():
    """P2-1: exclusões (R7) e allowlist DB (R10) não mudam em silêncio."""
    all_ops = _labels(_SCHEMA)
    kept = set(LEGACY_FAST) | set(LEGACY_GRAPH)
    assert sorted(set(all_ops) - kept) == [
        ("POST", "/account/checkout"),
        ("POST", "/account/purchases/google/verify"),
        ("POST", "/account/transcriptions"),
        ("POST", "/game/action/stream"),
        ("POST", "/game/{game_id}/art/confirm"),
        ("POST", "/game/{game_id}/art/player/confirm"),
        ("POST", "/game/{game_id}/art/{generation_id}/quality"),
        ("POST", "/payments/stripe/webhook"),
    ]
    assert len(LEGACY_GRAPH) == 4
    assert DB_OPS == sorted(
        [
            ("GET", "/auth/config"),
            ("POST", "/auth/login"),
            ("POST", "/auth/logout"),
            ("POST", "/auth/signup"),
            ("GET", "/data/map"),
            ("POST", "/game/action"),
            ("POST", "/game/cards/prepare"),
            ("GET", "/game/chronicle/export"),
            ("POST", "/game/chronicle/search"),
            ("GET", "/game/codex"),
            ("GET", "/game/codex/dossiers"),
            ("POST", "/game/death"),
            ("POST", "/game/equip"),
            ("GET", "/game/history"),
            ("POST", "/game/levelup"),
            ("GET", "/game/map"),
            ("DELETE", "/game/save/{game_id}"),
            ("GET", "/game/saves"),
            ("GET", "/game/state"),
        ]
    )


@pytest.mark.parametrize(("method", "path"), LEGACY_FAST, ids=_ids(LEGACY_FAST))
def test_fuzz_legacy_fast(method, path, legacy_client, legacy_seed):
    statuses = fuzz_operation(_op(method, path), legacy_client, max_examples=25, seed=legacy_seed)
    _assert_reached(method, path, statuses)


@pytest.mark.parametrize(("method", "path"), LEGACY_GRAPH, ids=_ids(LEGACY_GRAPH))
def test_fuzz_legacy_graph(method, path, legacy_client):
    statuses = fuzz_operation(_op(method, path), legacy_client, max_examples=5, catalog=True)
    _assert_reached(method, path, statuses)


@pytest.mark.parametrize(("method", "path"), DB_OPS, ids=_ids(DB_OPS))
def test_fuzz_db_offline(method, path, two_principals):  # noqa: F811
    seed = str(two_principals.game_a)
    statuses = fuzz_operation(
        _op(method, path), two_principals.client_a, max_examples=25, seed=seed
    )
    _assert_reached(method, path, statuses)
