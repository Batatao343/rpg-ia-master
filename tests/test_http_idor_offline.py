"""SPEC-337: IDOR offline (dois principals), controle positivo e correções L1/L2.

Matriz R14 (principal B contra o ``game_id`` de A). Rotas que dependem de Postgres
(``runtime.resources[0]``) recebem repositório fake; ``/account/checkout/{order_id}`` fica
fora (exige pedido real) e é omissão documentada em ``test_http_idor_local.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.fakes.two_principals import two_principals  # noqa: F401  (fixture)


def _a_state(tp):
    stored = tp.store.get(tp.a, tp.game_a)
    assert stored is not None
    return stored


# --- Etapa 0: controle positivo (R15) ----------------------------------------


def test_fixture_is_database_profile(two_principals):
    import api

    assert api._database_profile()
    from fastapi.testclient import TestClient

    anon = TestClient(api.app, raise_server_exceptions=False)
    assert (
        anon.get("/game/state", params={"game_id": str(two_principals.game_a)}).status_code == 401
    )


def test_owner_reads_own_game_through_swapped_store(two_principals):
    tp = two_principals
    gid = str(tp.game_a)
    state = tp.client_a.get("/game/state", params={"game_id": gid})
    assert state.status_code == 200, state.text
    assert tp.seed_name in state.text
    assert tp.client_a.get("/game/history", params={"game_id": gid}).status_code == 200
    saves = tp.client_a.get("/game/saves")
    assert saves.status_code == 200 and gid in saves.text


# --- Etapa 1: L1 (DELETE reaproveitando Idempotency-Key) ---------------------


def _complete_turn_with_key(tp, key):
    claim = tp.coordinator.claim(
        tp.a,
        key,
        game_id=tp.game_a,
        kind="turn",
        request_hash="turn-hash",
        base_version=1,
    )
    tp.coordinator.complete(claim, committed_version=2, receipt={"narrative": "turno de A"})


def test_delete_rejects_idempotency_key_of_other_operation(two_principals):
    tp = two_principals
    key = uuid4()
    _complete_turn_with_key(tp, key)
    out = tp.client_a.delete(f"/game/save/{tp.game_a}", headers={"Idempotency-Key": str(key)})
    assert out.status_code == 409, out.text
    assert out.json()["detail"] == "operation_request_mismatch"
    assert tp.store.get(tp.a, tp.game_a) is not None


def test_delete_rejects_key_reused_for_other_game(two_principals):
    tp = two_principals
    other = uuid4()
    key = uuid4()
    clone = dict(tp.store.get(tp.a, tp.game_a).state)
    clone["game_id"] = str(other)
    tp.store.create(tp.a, clone)
    # delete CONCLUÍDO de outra campanha com a mesma key
    first = tp.client_a.delete(f"/game/save/{other}", headers={"Idempotency-Key": str(key)})
    assert first.status_code == 200
    out = tp.client_a.delete(f"/game/save/{tp.game_a}", headers={"Idempotency-Key": str(key)})
    assert out.status_code == 409, out.text
    assert tp.store.get(tp.a, tp.game_a) is not None


def test_delete_retry_same_key_is_idempotent(two_principals):
    tp = two_principals
    key = str(uuid4())
    url = f"/game/save/{tp.game_a}"
    first = tp.client_a.delete(url, headers={"Idempotency-Key": key})
    assert first.status_code == 200 and first.json() == {"ok": True}
    assert tp.store.get(tp.a, tp.game_a) is None
    again = tp.client_a.delete(url, headers={"Idempotency-Key": key})
    assert again.status_code == 200 and again.json() == {"ok": True}
    assert sum(1 for name, _ in tp.coordinator.calls if name == "commit_delete") == 1


# --- Etapa 1: L2 (quality com geração de outra campanha) ---------------------


class _FakeArtRepo:
    """Replica o filtro de ``DynamicArtRepository.set_quality`` (dono + campanha)."""

    rows: dict = {}

    def __init__(self, *_a, **_k):
        pass

    def set_quality(self, principal, generation_id, *, game_id, approved):
        from infrastructure.contracts import Conflict

        row = self.rows.get(generation_id)
        if not row or row["owner"] != principal.user_id or row["game_id"] != game_id:
            raise Conflict("quality_not_available")
        row["status"] = "ready" if approved else "rejected_quality"


def test_art_quality_rejects_generation_of_other_game(two_principals, monkeypatch):
    tp = two_principals
    gen, other_game = uuid4(), uuid4()
    rows = {gen: {"owner": tp.a.user_id, "game_id": other_game, "status": "ready"}}
    _FakeArtRepo.rows = rows
    monkeypatch.setattr("services.dynamic_art.DynamicArtRepository", _FakeArtRepo)
    monkeypatch.setattr(tp.runtime, "resources", (object(),))
    out = tp.client_a.post(f"/game/{tp.game_a}/art/{gen}/quality", json={"approved": False})
    assert out.status_code == 409, out.text
    assert out.json()["detail"] == "Arte não disponível para avaliação."
    assert rows[gen]["status"] == "ready"


# --- Etapa 7: matriz R14 ------------------------------------------------------

_ART_GEN = "00000000-0000-4000-8000-000000000001"
_OP = "00000000-0000-4000-8000-000000000002"

# (método, caminho com {g}, query?, body?)
_ROUTES = [
    ("GET", "/game/state?game_id={g}", None),
    ("GET", "/game/map?game_id={g}", None),
    ("GET", "/game/codex?game_id={g}", None),
    ("GET", "/game/codex/dossiers?game_id={g}", None),
    ("GET", "/game/history?game_id={g}", None),
    ("GET", "/game/chronicle/export?game_id={g}", None),
    ("GET", "/data/map?game_id={g}", None),
    ("POST", "/game/action", {"input_text": "olho ao redor", "game_id": "{g}"}),
    ("POST", "/game/action/stream", {"input_text": "olho ao redor", "game_id": "{g}"}),
    ("POST", "/game/equip", {"unequip_slot": "weapon", "game_id": "{g}"}),
    ("POST", "/game/cards/prepare", {"game_id": "{g}", "card_ids": []}),
    ("POST", "/game/levelup", {"choice_id": "x", "game_id": "{g}"}),
    ("POST", "/game/death", {"choice": "accept", "game_id": "{g}"}),
    ("POST", "/game/chronicle/search", {"query": "teste", "game_id": "{g}"}),
    ("DELETE", "/game/save/{g}", None),
    ("POST", "/game/{g}/audit-export", {}),
    ("GET", f"/game/{{g}}/operations/{_OP}", None),
    ("GET", f"/game/{{g}}/operations/{_OP}/cost", None),
    ("POST", "/game/{g}/art/quote", {"image_type": "scene"}),
    ("GET", f"/game/{{g}}/art/{_ART_GEN}", None),
    ("POST", f"/game/{{g}}/art/{_ART_GEN}/quality", {"approved": True}),
]


# 404 em tudo; exceções explícitas por rota (hoje nenhuma: B tem sessão recente abaixo).
_EXPECTED_STATUS: dict[str, int] = {}


class _EmptyArtRepo:
    def __init__(self, *_a, **_k):
        pass

    def get(self, *_a, **_k):
        return None

    def set_quality(self, *_a, **_k):
        from infrastructure.contracts import Conflict

        raise Conflict("none")


@pytest.mark.parametrize(
    "method,path,body", _ROUTES, ids=[f"{m} {p.split('?')[0]}" for m, p, _ in _ROUTES]
)
def test_principal_b_cannot_touch_game_a(two_principals, monkeypatch, method, path, body):
    tp = two_principals
    gid = str(tp.game_a)
    monkeypatch.setattr("services.dynamic_art.DynamicArtRepository", _EmptyArtRepo)
    monkeypatch.setattr(tp.runtime, "resources", (object(),))
    from infrastructure.request_context import current_principal

    monkeypatch.setattr("api._image_finance", lambda: (tp.runtime, current_principal(), object()))
    from services.account_security import proof

    class _NoRowsAuditSource:  # o filtro de dono do Postgres devolve None para outro principal
        def __init__(self, *_a, **_k):
            pass

        def load(self, _game):
            return None

    monkeypatch.setattr("infrastructure.audit_source.PostgresAuditSource", _NoRowsAuditSource)

    # audit-export exige sessão recente; com ela o 404 vem da checagem de dono.
    tp.client_b.cookies.set("rpg_recent", proof(tp.b.user_id, "recent", "b"))
    url = path.replace("{g}", gid)
    payload = (
        None
        if body is None
        else {k: (v.replace("{g}", gid) if isinstance(v, str) else v) for k, v in body.items()}
    )
    headers = {"Idempotency-Key": str(uuid4())}
    before = _a_state(tp).version
    kwargs = {"json": payload} if payload is not None else {}
    response = tp.client_b.request(method, url, headers=headers, **kwargs)
    assert response.status_code == _EXPECTED_STATUS.get(path.split("?")[0], 404), (
        f"{method} {path}: {response.status_code} {response.text[:200]}"
    )
    assert tp.seed_name not in response.text
    after = _a_state(tp)
    assert after.version == before
    assert tp.seed_name in str(after.state.get("player", {}).get("name"))
