"""SPEC-213 Etapa 5 — projeção derivada em perfil com banco (Postgres local real).

Outbox `project_archive` na transação do commit, CAS de versão no apply, cerca do
job, retry em conflito, cancelamento por época e fallback do turno (modo A na
cerca). Executor do derivado é fake (sem LLM); o fluxo de banco é real.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from infrastructure.contracts import LeaseHeld, MemoryDocument, MemoryWriteIntent, Principal
from services import projections
from tests.test_postgres_jobs_local import _state, infra  # noqa: F401

pytestmark = pytest.mark.infra_local


def _principal():
    owner = uuid4()
    return Principal(owner, "test", str(owner), local=True)


def _pending_state(game, *, action="a" * 8, epoch=0):
    state = _state(game)
    state["continuity"] = {"session_action_count": 1, "timeline_epoch": epoch}
    state["narrative_summary"] = "resumo antigo"
    state["pending_derived"] = projections.make_plan(
        new_event_ids=[], new_rejections=False, turn=1, epoch=epoch)
    return projections.stamp_commit(state, action)


def _commit(coordinator, principal, game, version, state):
    claim = coordinator.claim(principal, uuid4(), game_id=game, kind="turn",
                              request_hash="a" * 64, base_version=version)
    committed, _ = coordinator.commit_game(
        principal, claim, state, receipt={"ok": True}, input_sha256="b" * 64,
        latency_ms=1, llm_cost_usd=0)
    return committed


def _job(pool, game):
    with pool.connection() as connection:
        return connection.execute(
            "select * from app.jobs where game_id=%s and kind=%s",
            (game, projections.JOB_KIND),
        ).fetchall()


def _game(pool, game):
    from services.game_serialization import deserialize_game_state
    with pool.connection() as connection:
        row = connection.execute("select version,state from app.games where id=%s",
                                 (game,)).fetchone()
    return int(row["version"]), deserialize_game_state(row["state"])


def _summary_executor(text="resumo novo", calls=None):
    def run(state, plan):
        if calls is not None:
            calls.append(plan["action_id"])
        return {"narrative_summary": text}
    return run


def test_commit_enqueues_project_archive_in_same_tx(infra, monkeypatch):
    store, queue, coordinator, _ = infra
    from infrastructure import postgres_turns
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        state = _pending_state(game)
        version = _commit(coordinator, principal, game, created.version, state)
        rows = _job(coordinator.pool, game)
        assert len(rows) == 1
        assert rows[0]["status"] == "queued"
        assert rows[0]["dedupe_key"] == projections.dedupe_key(game, 0, "a" * 8)
        assert rows[0]["payload"]["owner_id"] == str(principal.user_id)
        assert "narrative_summary" not in str(rows[0]["payload"])  # só ids

        # Mesmo commit falhando DEPOIS do enqueue: o job some junto (mesma transação).
        real = postgres_turns.enqueue_projection_outbox

        def explode(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("crash depois do outbox")

        monkeypatch.setattr(postgres_turns, "enqueue_projection_outbox", explode)
        with pytest.raises(RuntimeError):
            _commit(coordinator, principal, game, version, _pending_state(game, action="b" * 8))
        assert [r["dedupe_key"] for r in _job(coordinator.pool, game)] == [
            projections.dedupe_key(game, 0, "a" * 8)]
        assert _game(coordinator.pool, game)[0] == version
    finally:
        store.delete(principal, game)


def test_job_applies_with_cas_and_is_idempotent(infra):
    from services.job_fence import job_scope
    from workers.projection_jobs import apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))
        job = queue.lease("w1", {projections.JOB_KIND}, 10)
        job = next(j for j in job if j.request.game_id == game)
        calls: list = []
        staged: list = []

        class Memory:
            def stage_on(self, connection, intent):
                staged.append(intent.document.document_id)

        def executor(state, plan):
            from infrastructure.request_context import current_principal
            from services.turn_effects import current_effects
            current_effects().memory.add(MemoryWriteIntent(   # como add_memory_to_session
                document=MemoryDocument("session:x", "fato", "session", {}),
                principal=current_principal(), game_id=game))
            calls.append(plan["action_id"])
            return {"narrative_summary": "resumo novo"}

        with job_scope(job):
            out = apply_projection(coordinator.pool, job.request.payload,
                                   executor=executor, memory_store=Memory())
        queue.complete(job.job_id, job.lease_token, out)
        assert out["status"] == "completed"
        new_version, saved = _game(coordinator.pool, game)
        assert new_version == version + 1
        assert saved["narrative_summary"] == "resumo novo"
        assert saved["pending_derived"] is None
        ps = saved["projection_state"]
        assert ps["summary"]["projected_version"] == ps["canonical_version"]
        assert staged == ["session:x:epoch:0"]
        # R8: reexecutar o mesmo payload é no-op (já drenado), sem LLM nem memória.
        again = apply_projection(coordinator.pool, job.request.payload,
                                 executor=executor, memory_store=Memory())
        assert again == {"status": "superseded"}
        assert calls == ["a" * 8] and staged == ["session:x:epoch:0"]
    finally:
        store.delete(principal, game)


def test_job_apply_cas_conflict_marks_stale(infra):
    from workers.job_worker import JobWorker
    from workers.projection_jobs import apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))

        def racing_executor(state, plan):
            # Um turno/mutação mais novo commita enquanto o derivado roda.
            current = store.get(principal, game)
            store.save(principal, game, current.version, copy.deepcopy(current.state))
            return {"narrative_summary": "derivado velho"}

        worker = JobWorker(queue, {projections.JOB_KIND: lambda payload: apply_projection(
            coordinator.pool, payload, executor=racing_executor)}, worker_id="w-cas")
        job = queue.lease_key("w-cas", projections.JOB_KIND,
                              projections.dedupe_key(game, 0, "a" * 8))
        worker.run_leased(job)
        row = _job(coordinator.pool, game)[0]
        assert row["status"] == "retry"
        assert row["last_error_code"] == "projection_stale"
        bumped, saved = _game(coordinator.pool, game)
        assert bumped == version + 1                       # só a mutação concorrente
        assert saved["narrative_summary"] == "resumo antigo"
        assert saved["pending_derived"]["action_id"] == "a" * 8   # segue pendente
    finally:
        store.delete(principal, game)


def test_stale_fence_rejected(infra):
    from services.job_fence import job_scope
    from workers.projection_jobs import apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))
        key = projections.dedupe_key(game, 0, "a" * 8)
        old = queue.lease_key("w-old", projections.JOB_KIND, key)
        with coordinator.pool.connection() as connection, connection.transaction():
            connection.execute("update app.jobs set lease_until=now()-interval '1 minute' "
                               "where id=%s", (old.job_id,))
        new = next(j for j in queue.lease("w-new", {projections.JOB_KIND}, 50)
                   if j.job_id == old.job_id)
        assert new.lease_token != old.lease_token
        with job_scope(old), pytest.raises(LeaseHeld):
            apply_projection(coordinator.pool, old.request.payload,
                             executor=_summary_executor("de fence velho"))
        assert _game(coordinator.pool, game)[0] == version  # nada publicado
        with job_scope(new):
            out = apply_projection(coordinator.pool, new.request.payload,
                                   executor=_summary_executor("de fence novo"))
        assert out["status"] == "completed"
        assert _game(coordinator.pool, game)[1]["narrative_summary"] == "de fence novo"
    finally:
        store.delete(principal, game)


def test_two_clients_active_turn_blocks_projection(infra):
    """R14 (perfil DB): com um turno com lease vigente no jogo, o apply não gasta
    LLM nem publica — o turno drena a pendência na própria cerca."""
    from workers.projection_jobs import ProjectionStale, apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))
        coordinator.claim(principal, uuid4(), game_id=game, kind="turn",
                          request_hash="c" * 64, base_version=version)
        calls: list = []
        payload = {"owner_id": str(principal.user_id), "game_id": str(game),
                   "action_id": "a" * 8, "epoch": 0, "canonical_version": 1}
        with pytest.raises(ProjectionStale):
            apply_projection(coordinator.pool, payload, executor=_summary_executor(calls=calls))
        assert calls == []
        assert _game(coordinator.pool, game)[0] == version
    finally:
        store.delete(principal, game)


def test_restore_epoch_cancels_queued_projection_jobs(infra):
    """R7b: commit de restore (época nova) cancela `project_archive` da época antiga."""
    from workers.projection_jobs import apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))
        restored = _state(game)
        restored["continuity"] = {"session_action_count": 1, "timeline_epoch": 1}
        _commit(coordinator, principal, game, version, restored)
        row = _job(coordinator.pool, game)[0]
        assert row["status"] == "cancelled"
        assert row["last_error_code"] == "epoch_mismatch"
        # Mesmo se executado por engano, payload de época antiga é no-op.
        out = apply_projection(coordinator.pool, row["payload"], executor=_summary_executor())
        assert out == {"status": "superseded"}
    finally:
        store.delete(principal, game)


def test_worker_down_falls_back_to_mode_a(infra, monkeypatch):
    """Fila parada: o próximo turno não espera job que ninguém roda e drena a
    pendência DENTRO da sua cerca; o job atrasado depois é no-op."""
    import api
    from infrastructure import runtime as runtime_mod
    from services.turn_effects import effect_scope
    from workers.projection_jobs import apply_projection
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))
    monkeypatch.setattr(runtime_mod, "get_runtime", lambda: SimpleNamespace(
        job_queue=queue, resources=(coordinator.pool,), turn_coordinator=coordinator))
    monkeypatch.setenv(projections.WAIT_ENV, "5")
    try:
        version = _commit(coordinator, principal, game, created.version, _pending_state(game))
        _, state = _game(coordinator.pool, game)
        state["_storage_version"] = version
        import time
        started = time.monotonic()
        assert api._await_projection_db(state, str(game)) is state     # job só queued
        assert time.monotonic() - started < 1.0
        import agents.archivist as archive
        monkeypatch.setattr(archive, "run_derived_projection",
                            _summary_executor("drenado no turno"))
        claim = coordinator.claim(principal, uuid4(), game_id=game, kind="turn",
                                  request_hash="d" * 64, base_version=version)
        with effect_scope():
            drained = api._pre_drain_in_turn(state)
            drained = projections.stamp_commit(drained, "e" * 8)
            coordinator.commit_game(principal, claim, drained, receipt={"ok": True},
                                    input_sha256="d" * 64, latency_ms=1, llm_cost_usd=0)
        _, saved = _game(coordinator.pool, game)
        assert saved["narrative_summary"] == "drenado no turno"
        assert saved["projection_state"]["summary"]["status"] == "completed"
        late = _job(coordinator.pool, game)[0]
        assert apply_projection(coordinator.pool, late["payload"],
                                executor=_summary_executor("atrasado")) == {"status": "superseded"}
    finally:
        store.delete(principal, game)


def test_api_post_response_runs_own_outbox_job_and_meters_usage(infra, monkeypatch):
    """Modo A em perfil DB: a API arrenda o PRÓPRIO job após responder; uso de LLM
    vai para uma operação `archive_projection` (migration SPEC-213)."""
    import api
    from infrastructure import runtime as runtime_mod
    from infrastructure.usage_events import append_projection_job_attempt
    store, queue, coordinator, _ = infra
    principal, game = _principal(), uuid4()
    created = store.create(principal, _state(game))

    class Memory:
        def stage_on(self, connection, intent):
            raise AssertionError("sem memória neste derivado")

    monkeypatch.setattr(runtime_mod, "get_runtime", lambda: SimpleNamespace(
        job_queue=queue, resources=(coordinator.pool,), memory_store=Memory()))
    seen: list = []

    def executor(state, plan):
        from services.job_fence import current_job
        job = current_job()
        append_projection_job_attempt(coordinator.pool, job, [{
            "provider": "deepseek", "model": "deepseek-v4-flash", "outcome": "success",
            "network_attempted": True,
            "usage": {"input_tokens": 10, "output_tokens": 5}}])
        seen.append(job.job_id)
        return {"narrative_summary": "pós-resposta"}

    import agents.archivist as archive
    monkeypatch.setattr(archive, "run_derived_projection", executor)
    try:
        state = _pending_state(game)
        _commit(coordinator, principal, game, created.version, state)
        api._drain_projection_db(state)
        row = _job(coordinator.pool, game)[0]
        assert row["status"] == "succeeded" and row["lease_owner"] is None
        assert _game(coordinator.pool, game)[1]["narrative_summary"] == "pós-resposta"
        with coordinator.pool.connection() as connection:
            op = connection.execute("select kind,status from app.operations where id=%s",
                                    (seen[0],)).fetchone()
            usage = connection.execute(
                "select count(*) as n from app.usage_events where operation_id=%s",
                (seen[0],)).fetchone()["n"]
        assert op["kind"] == "archive_projection" and op["status"] == "completed"
        assert usage == 1
        api._drain_projection_db(state)      # job já concluído: nada a arrendar
        assert _job(coordinator.pool, game)[0]["status"] == "succeeded"
    finally:
        store.delete(principal, game)


def test_http_stream_post_response_db_e2e(infra):
    """Ponta a ponta no perfil `local` (Auth+Postgres reais, MockLLM): servidor
    com RPG_PROJECTION_MODE=post_response. Opt-in: RPG_AUDIT_BROWSER_URL +
    RPG_AUDIT_PROJECTION_MODE=post_response (o servidor sobe fora do pytest)."""
    import json
    import os
    import time
    from urllib.parse import urlsplit

    import httpx

    from tests.fakes.local_auth import create_confirmed_user, delete_confirmed_user

    base = os.getenv("RPG_AUDIT_BROWSER_URL")
    if not base or os.getenv("RPG_AUDIT_PROJECTION_MODE") != "post_response":
        pytest.skip("servidor local em post_response não informado")
    assert urlsplit(base).hostname in {"127.0.0.1", "localhost"}
    store, _, coordinator, _ = infra
    email = f"proj213-{uuid4().hex}@example.test"
    owner = create_confirmed_user(email, "LocalAuditOnly-2026!")
    game = None
    try:
        with httpx.Client(base_url=base, timeout=60, trust_env=False) as client:
            login = client.post("/auth/login", headers={"Origin": base},
                                json={"email": email, "password": "LocalAuditOnly-2026!"})
            assert login.status_code == 200, login.text
            client.headers.update({"Origin": base, "X-CSRF-Token": login.json()["csrf_token"]})
            options = client.get("/data/options").json()
            created = client.post("/game/new", json={
                "name": "Projetor DB", "race": options["races"][0],
                "class_name": options["classes"][0], "region": options["regions"][0],
                "action_id": str(uuid4())})
            assert created.status_code == 200, created.text
            game = created.json()["game_id"]
            versions = []
            for text in ("Observo a praça.", "Converso com o taverneiro.", "Sigo pela estrada."):
                events, name = [], None
                with client.stream("POST", "/game/action/stream", json={
                        "input_text": text, "game_id": game, "action_id": str(uuid4())}) as r:
                    assert r.status_code == 200
                    for line in r.iter_lines():
                        if line.startswith("event: "):
                            name = line[7:].strip()
                        elif line.startswith("data: ") and name:
                            events.append((name, json.loads(line[6:])))
                            name = None
                kinds = [k for k, _ in events]
                assert "error" not in kinds, events
                assert kinds.index("narrative") < kinds.index("state")
                final = dict(events)["state"]
                versions.append(final["projections"]["canonical_version"])
            assert versions == sorted(versions) and len(set(versions)) == 3
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                state = client.get("/game/state", params={"game_id": game}).json()
                ps = state["projections"]
                if all(ps[n]["status"] == "completed" for n in projections.PROJECTIONS):
                    break
                time.sleep(0.3)
            assert ps["canonical_version"] == versions[-1]
            assert all(ps[n]["projected_version"] == versions[-1] for n in projections.PROJECTIONS)
        rows = _job(coordinator.pool, UUID(game))
        assert rows, "nenhum job project_archive enfileirado"
        assert {r["status"] for r in rows} == {"succeeded"}
        assert len({r["dedupe_key"] for r in rows}) == len(rows)
        with coordinator.pool.connection() as connection:
            turns = connection.execute(
                "select count(*) as n from app.turns where game_id=%s", (UUID(game),)).fetchone()["n"]
        assert turns == 3
    finally:
        if game:
            store.delete(Principal(owner, "test", str(owner), local=True), UUID(game))
        delete_confirmed_user(owner)
