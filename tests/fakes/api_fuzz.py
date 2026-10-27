"""SPEC-338: helpers do fuzz de API (oráculo, execução de case, bloqueio de rede).

Sem testes aqui. Reutilizado por ``test_api_fuzz_schemathesis.py`` e
``test_api_fuzz_harness.py``. Não importa ``schemathesis`` no topo, para o módulo
carregar sem o grupo ``fuzz``.
"""

from __future__ import annotations

import contextlib
import os
import socket
import uuid
import zlib
from collections import Counter
from collections.abc import Iterator
from typing import Any

import httpx

from tests.fakes.two_principals import assert_security_headers, forbidden_leak

# 503 de desligamento intencional (feature off / sem config). Qualquer outro >= 500 falha.
INTENTIONAL_503: frozenset[str] = frozenset(
    {
        "captcha_unavailable",
        "stripe_disabled",
        "stripe_catalog_unavailable",
        "new_purchases_disabled",
        "stripe_checkout_unavailable",
        "google_play_disabled",
        "google_play_unconfigured",
        "image_generation_disabled",
        "image_pricing_unavailable",
        "image_quotes_unavailable",
        "speech_disabled",
        "speech_pricing_unavailable",
    }
)
# Só alcançável pela rota de upload cru, excluída do fuzz (R7).
EXCLUDED_503: frozenset[str] = frozenset({"speech_internal_error"})

# Erros do cliente httpx por entrada malformada gerada (negativa): não são bug da API.
CLIENT_SIDE_ERRORS: tuple[type[BaseException], ...] = (
    UnicodeError,
    httpx.InvalidURL,
    httpx.LocalProtocolError,
    httpx.UnsupportedProtocol,
)


def _detail(response: Any) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    detail = body.get("detail") if isinstance(body, dict) else None
    return detail if isinstance(detail, str) else None


def check_response(response: Any, path: str, *, headers: bool = True, hsts: bool = False) -> None:
    """R12 + R13: sem 5xx inesperado, headers de segurança e nada vazado."""
    status = response.status_code
    if status >= 500:
        assert status == 503 and _detail(response) in INTENTIONAL_503, (
            f"{path}: {status} inesperado: {response.text[:200]!r}"
        )
    if headers:
        assert_security_headers(response, path=path, hsts=hsts)
    leaks = forbidden_leak(response.text)
    assert leaks == [], f"{path}: vazamento {leaks} em {response.text[:200]!r}"


# Rotas de escrita cujo corpo carrega ``action_id`` (gate de idempotência por perfil).
ACTION_ID_PATHS = frozenset(
    {"/game/equip", "/game/levelup", "/game/death", "/game/cards/prepare", "/game/action"}
)
# Valores válidos do catálogo (os mesmos do ``two_principals``) para passar do validador Pydantic.
VALID_CATALOG = {
    "race": "Humano",
    "class_name": "Devoto do Abismo",
    "region": "Nova Arcádia",
}


def seed_game_id(case: Any, game_id: str) -> None:
    """R11: troca ``game_id`` (path/query/body) pelo id real da campanha semeada."""
    for bag in (case.path_parameters, case.query):
        if isinstance(bag, dict) and "game_id" in bag:
            bag["game_id"] = game_id
    if isinstance(case.body, dict) and "game_id" in case.body:
        case.body["game_id"] = game_id


def seed_idempotency(case: Any, digest: int) -> None:
    """P1-1: ``action_id`` (body) e ``Idempotency-Key`` (header) com UUID determinístico."""
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"api-fuzz/{digest}"))
    if isinstance(case.body, dict) and (
        case.operation.path in ACTION_ID_PATHS or "action_id" in case.body
    ):
        case.body["action_id"] = key
    if case.method.upper() == "DELETE":
        case.headers = {**(case.headers or {}), "Idempotency-Key": key}


def seed_catalog(case: Any) -> None:
    """P1-2: ``race``/``class_name``/``region``/``enemy_id`` válidos nas rotas de grafo."""
    import gamedata

    if not isinstance(case.body, dict):
        return
    for key, value in VALID_CATALOG.items():
        if key in case.body:
            case.body[key] = value
    if "enemy_id" in case.body:
        case.body["enemy_id"] = next(iter(gamedata.BESTIARY))
    if "level" in case.body and case.operation.path == "/game/combat-simulator":
        case.body["level"] = 1


def run_case(
    case: Any, client: Any, *, seed: str | None = None, catalog: bool = False
) -> Any | None:
    """Executa um case no ``TestClient``; ``None`` = rejeitado pelo próprio cliente.

    Em ~1/3 dos exemplos (decisão determinística pelo conteúdo) o case é semeado com o
    ``game_id`` real, ``action_id``/``Idempotency-Key`` e, nas rotas de grafo, o catálogo.
    """
    digest = zlib.crc32(repr((case.path_parameters, case.query, case.body)).encode())
    if digest % 3 == 0:
        if seed is not None:
            seed_game_id(case, seed)
            seed_idempotency(case, digest)
        if catalog:
            seed_catalog(case)
    try:
        kwargs = case.as_transport_kwargs(base_url="http://testserver")
        return client.request(**kwargs)
    except CLIENT_SIDE_ERRORS:
        return None


def _status_key(response: Any) -> str:
    """``200`` ou ``400:<code>``: separa o 400 do gate do 400 de regra de negócio."""
    if response.status_code < 400:
        return str(response.status_code)
    try:
        code = response.json().get("code")
    except (ValueError, AttributeError):
        code = None
    return f"{response.status_code}:{code}"


def fuzz_settings(max_examples: int) -> Any:
    """R16: determinístico, sem banco de exemplos e sem deadline."""
    from hypothesis import HealthCheck, settings

    cap = os.getenv("RPG_API_FUZZ_MAX_EXAMPLES")
    if cap:
        max_examples = min(max_examples, int(cap))
    return settings(
        max_examples=max_examples,
        derandomize=True,
        database=None,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
            HealthCheck.filter_too_much,
        ],
    )


def fuzz_operation(
    operation: Any,
    client: Any,
    *,
    max_examples: int,
    seed: str | None = None,
    catalog: bool = False,
    headers: bool = True,
) -> Counter[str]:
    """Fuzza uma operação (``APIOperation``); levanta ``AssertionError`` no primeiro achado.

    Devolve a contagem de status por resposta (prova de que o fuzz passou da validação).
    """
    from hypothesis import given

    statuses: Counter[str] = Counter()

    @given(case=operation.as_strategy())
    @fuzz_settings(max_examples)
    def probe(case: Any) -> None:
        response = run_case(case, client, seed=seed, catalog=catalog)
        if response is not None:
            statuses[_status_key(response)] += 1
            try:
                check_response(response, operation.path, headers=headers)
            except AssertionError as exc:
                raise AssertionError(
                    f"{exc} | path={case.path_parameters!r} query={case.query!r} body={case.body!r}"
                ) from None

    probe()
    return statuses


def fuzz_failures(
    schema: Any, client: Any, *, max_examples: int = 5, headers: bool = True
) -> dict[str, str]:
    """Fuzza cada operação do schema; devolve ``{operação: erro}`` (usado no R15)."""
    failures: dict[str, str] = {}
    for result in schema.get_all_operations():
        operation = result.ok()
        try:
            fuzz_operation(operation, client, max_examples=max_examples, headers=headers)
        except AssertionError as exc:
            failures[f"{operation.method.upper()} {operation.path}"] = str(exc)
    return failures


@contextlib.contextmanager
def network_blocked() -> Iterator[None]:
    """R17: httpx externo levanta e ``socket.connect`` só aceita loopback."""
    real_connect = socket.socket.connect

    def blocked(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("network blocked in api_fuzz")

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1"):
            raise RuntimeError("network blocked in api_fuzz")
        return real_connect(self, address)

    saved = (httpx.HTTPTransport.handle_request, httpx.AsyncHTTPTransport.handle_async_request)
    httpx.HTTPTransport.handle_request = blocked  # type: ignore[method-assign]
    httpx.AsyncHTTPTransport.handle_async_request = blocked  # type: ignore[method-assign]
    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    try:
        yield
    finally:
        httpx.HTTPTransport.handle_request, httpx.AsyncHTTPTransport.handle_async_request = saved  # type: ignore[method-assign]
        socket.socket.connect = real_connect  # type: ignore[method-assign]
