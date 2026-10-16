"""SPEC-235 R1/R3 contra Postgres real: reclaim de op ``failed`` e gate ``pending_operation``."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from infrastructure.contracts import Conflict, LeaseHeld, NotFound, Principal
from tests.test_postgres_jobs_local import _state, infra  # noqa: F401

pytestmark = pytest.mark.infra_local


def _principal():
    owner = uuid4()
    return Principal(owner, "test", str(owner), local=True)


def _op_row(coordinator, op):
    with coordinator.pool.connection() as connection:
        return connection.execute(
            "select status,base_game_version,request_sha256,owner_id from app.operations where id=%s",
            (op,),
        ).fetchone()


def test_failed_reclaim_after_version_bump_and_strict_cases(infra):
    store, _, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        op = uuid4()
        claim = coordinator.claim(principal, op, game_id=game, kind="turn",
                                  request_hash="a" * 64, base_version=created.version)
        coordinator.fail(claim, "llm_timeout")
        # Equip/levelup avançam a versão sem tocar na operação falha.
        bumped = store.save(principal, game, created.version, _state(game))
        assert bumped.version == created.version + 1

        # Hash divergente nunca reaproveita, mesmo falha.
        with pytest.raises(Conflict):
            coordinator.claim(principal, op, game_id=game, kind="turn",
                              request_hash="b" * 64, base_version=bumped.version)
        # Outro dono: jogo invisível (NotFound) e chave indisponível sem jogo.
        intruder = _principal()
        with pytest.raises(NotFound):
            coordinator.claim(intruder, op, game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=bumped.version)
        with pytest.raises(Conflict):
            coordinator.claim(intruder, op, game_id=None, kind="turn",
                              request_hash="a" * 64, base_version=None)
        # Outro kind com a mesma chave é divergente.
        with pytest.raises(Conflict):
            coordinator.claim(principal, op, game_id=game, kind="equip",
                              request_hash="a" * 64, base_version=bumped.version)
        assert _op_row(coordinator, op)["status"] == "failed"

        # Mesmo dono/hash/kind: reclaim legítimo na versão nova.
        again = coordinator.claim(principal, op, game_id=game, kind="turn",
                                  request_hash="a" * 64, base_version=bumped.version)
        row = _op_row(coordinator, op)
        assert row["status"] == "running" and row["base_game_version"] == bumped.version
        assert again.base_version == bumped.version and again.lease_token != claim.lease_token
        # O token antigo está cercado: um worker atrasado não confirma nada.
        with pytest.raises(LeaseHeld):
            coordinator.complete(claim, committed_version=bumped.version, receipt={})
        # Enquanto roda, a mesma chave é estrita (lease fresco).
        with pytest.raises(LeaseHeld):
            coordinator.claim(principal, op, game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=bumped.version)

        committed, _ = coordinator.commit_game(
            principal, again, _state(game), receipt={"ok": True},
            input_sha256="c" * 64, latency_ms=1, llm_cost_usd=0)
        assert committed == bumped.version + 1
        assert coordinator.receipt(principal, op)["ok"] is True
        # Efeito confirmado nunca reexecuta: completed é estrito em qualquer versão.
        with pytest.raises(Conflict):  # divergente (base gravada != atual)
            coordinator.claim(principal, op, game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=committed)
        with pytest.raises(Conflict):  # versão antiga: StaleVersion (subclasse de Conflict)
            coordinator.claim(principal, op, game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=bumped.version)
        with coordinator.pool.connection() as connection:
            turns = connection.execute(
                "select count(*) as n from app.turns where operation_id=%s", (op,)).fetchone()["n"]
        assert turns == 1
        assert store.get(principal, game).version == committed
    finally:
        store.delete(principal, game)


def test_running_operation_with_changed_version_stays_strict(infra):
    store, _, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        op = uuid4()
        coordinator.claim(principal, op, game_id=game, kind="turn",
                          request_hash="a" * 64, base_version=created.version)
        # Simula lease expirado + versão alterada: running nunca relaxa a versão.
        with coordinator.pool.connection() as connection, connection.transaction():
            connection.execute("update app.operations set lease_until=now()-interval '1 minute' "
                               "where id=%s", (op,))
            connection.execute("update app.games set version=version+1,active_operation_id=null,"
                               "active_lease_token=null,active_lease_until=null where id=%s", (game,))
        with pytest.raises(Conflict, match="divergente"):
            coordinator.claim(principal, op, game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=created.version + 1)
    finally:
        store.delete(principal, game)


def test_equip_and_levelup_gate_pending_operation_against_real_operations(infra, monkeypatch):
    import api
    from fastapi import HTTPException
    from infrastructure import request_context, runtime

    store, _, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(request_context, "current_principal", lambda: principal)
    monkeypatch.setattr(runtime, "get_runtime", lambda: SimpleNamespace(
        turn_coordinator=coordinator, resources=(coordinator.pool,)))
    try:
        state = {"game_id": str(game), "_storage_version": created.version}
        assert api._failed_pending_operation(state) is None
        failed_op = uuid4()
        claim = coordinator.claim(principal, failed_op, game_id=game, kind="turn",
                                  request_hash="a" * 64, base_version=created.version)
        coordinator.fail(claim, "llm_timeout")
        for kind in ("equip", "levelup"):
            with pytest.raises(HTTPException) as err:
                api._begin_state_mutation(state, action_id=str(uuid4()), kind=kind,
                                          payload={"kind": kind})
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "pending_operation"
            assert err.value.detail["operation_id"] == str(failed_op)
        # Morte não é bloqueada (evita deadlock com death_pending).
        death, _, _ = api._begin_state_mutation(state, action_id=str(uuid4()), kind="death",
                                                payload={"choice": "accept"})
        assert death is not None
        coordinator.fail(death, "test_release")
        # Outro dono não enxerga a falha alheia.
        monkeypatch.setattr(request_context, "current_principal", _principal)
        assert api._failed_pending_operation(state) is None
        monkeypatch.setattr(request_context, "current_principal", lambda: principal)
        # Um turno posterior concluído supera a falha e libera equip.
        later = coordinator.claim(principal, uuid4(), game_id=game, kind="turn",
                                  request_hash="b" * 64, base_version=created.version)
        coordinator.complete(later, committed_version=created.version, receipt={})
        assert api._failed_pending_operation(state) is None
        ok, _, receipt = api._begin_state_mutation(state, action_id=str(uuid4()), kind="equip",
                                                   payload={"kind": "equip"})
        assert ok is not None and receipt is None
        coordinator.fail(ok, "test_release")
    finally:
        store.delete(principal, game)
