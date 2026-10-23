"""SPEC-297 - correcoes da revisao Sol (P1-1, P1-3, P2-*)."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import agents.bestiary as bst_mod
import agents.storyteller as st
from services import cron_internal
from services import shared_pool as sp
from services import shared_pool_validators as v
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import NOW, FakeJudge, all_ok, entry, make_store, npc_doc, seed
from workers import shared_pool_jobs as jobs

ATTEMPTS = [
    {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "outcome": "success",
        "network_attempted": True,
        "usage": {"input_tokens": 120, "output_tokens": 30},
    }
]


class FakeConn:
    def __init__(self):
        self.sql: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        conn = self

        class _R:
            def fetchone(self):
                if "auth.users" in sql:
                    return {
                        "email": "dona.real@example.com",
                        "meta": {"full_name": "Guilhermina Souza Ramos"},
                    }
                return None

        del conn
        return _R()

    @contextmanager
    def transaction(self):
        yield


class FakePool:
    def __init__(self):
        self.conn = FakeConn()

    @contextmanager
    def connection(self):
        yield self.conn


def test_cron_route_wires_usage_sink_and_owner_values(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    monkeypatch.setenv("RPG_CRON_SECRET", "s" * 40)
    store = make_store(tmp_path)
    pool = FakePool()
    monkeypatch.setattr(
        cron_internal,
        "_runtime",
        lambda: SimpleNamespace(shared_pool=store, game_store=SimpleNamespace(pool=pool)),
    )
    captured = {}

    def fake_promote(store_, **kw):
        captured.update(kw)
        return {"promoted": 0, "rejected": 0, "held": 0, "failed": 0}

    monkeypatch.setattr(jobs, "promote_due", fake_promote)
    app = FastAPI()
    app.include_router(cron_internal.router)
    resp = TestClient(app).post(
        "/internal/cron/shared-pool", headers={"Authorization": "Bearer " + "s" * 40}
    )
    assert resp.status_code == 200
    assert callable(captured["usage_sink"]) and callable(captured["owner_values"])
    # owner_values resolve e-mail e nome do dono de origem pela conexao admin
    values = captured["owner_values"](entry())
    assert "dona.real@example.com" in values and "Guilhermina Souza Ramos" in values


def test_usage_sink_writes_operation_and_usage_under_system_owner(monkeypatch):
    pool = FakePool()
    seen = {}
    monkeypatch.setattr(
        "infrastructure.usage_events.append_usage_events",
        lambda connection, **kw: seen.update(kw),
    )
    jobs.make_usage_sink(pool)(entry(), ATTEMPTS)
    sql, params = pool.conn.sql[0]
    assert "pool_evaluation" in sql and params[1] == jobs.SYSTEM_OWNER_ID
    assert seen["owner_id"] == jobs.SYSTEM_OWNER_ID and seen["game_id"] is None
    assert len(seen["events"]) == 1 and seen["events"][0].component == "pool_eval"
    # nada chegou a provider -> nada gravado
    pool2 = FakePool()
    jobs.make_usage_sink(pool2)(
        entry(), [{"provider": "mock", "outcome": "build_error", "network_attempted": False}]
    )
    assert pool2.conn.sql == []


def test_job_with_pool_rejects_owner_email_as_pii_and_records_usage(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    store.insert(entry(doc=npc_doc(persona="Conhecida como Guilhermina Souza Ramos na vila")))
    pool = FakePool()
    recorded = []
    monkeypatch.setattr(
        "infrastructure.usage_events.append_usage_events", lambda c, **kw: recorded.append(kw)
    )
    judge = FakeJudge()
    out = jobs.promote_due_job(
        store, llm=judge, now=NOW, pool=pool, embedder=None, embedding_profile="x"
    )
    assert out["rejected"] == 1 and judge.calls == 0
    assert store.get(entry().entry_id).evaluation["code"] == "pii"
    # e uma entrada limpa promove E grava custo (usage_sink real, evaluate fake nao gera tentativas)
    store.insert(
        entry(name="Outra Pessoa", entry_id="pool_npc_clean", sd=seed(desire_id="des_cura"))
    )
    monkeypatch.setattr(
        sp, "evaluate", lambda e, **kw: (kw["usage_sink"](e, ATTEMPTS), all_ok())[1]
    )
    out = jobs.promote_due_job(
        store, llm=judge, now=NOW, pool=pool, embedder=None, embedding_profile="x"
    )
    assert out["promoted"] == 1 and len(recorded) == 1


# ---------------- P1-3 / P2-6 ----------------
def test_name_typed_by_player_detection():
    assert sp.name_typed_by_player("Carlos Mendes", ["falo com Carlos Mendes"])
    assert sp.name_typed_by_player("Carlos Mendes", ["procuro o tal de mendes"])
    assert not sp.name_typed_by_player("Brunhilda Cobreira", ["entro na taverna"])
    assert not sp.name_typed_by_player("Ada Li", ["falo com ada"])  # tokens < 4 letras


def test_narrator_laundering_player_name_is_local_only(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    sp.reset_default_store()
    captured = {}

    def fake_gen(name, **kw):
        captured.update(kw)
        return {"name": name, "role": "x", "persona": "p"}

    monkeypatch.setattr(st, "generate_new_npc", fake_gen)
    st._with_new_npc(
        {},
        "Carlos Mendes",
        "Praça",
        "cena",
        game_id="g",
        home_id="na_anel_lama",
        turn=2,
        player_inputs=("falo com Carlos Mendes",),
    )
    assert captured["name_origin"] == "player"
    captured.clear()
    st._with_new_npc(
        {},
        "Brunhilda Cobreira",
        "Praça",
        "cena",
        game_id="g",
        home_id="na_anel_lama",
        turn=2,
        player_inputs=("entro na taverna",),
    )
    assert captured["name_origin"] == "narrator"


def test_player_inputs_are_last_three_human_messages():
    import inspect

    src = inspect.getsource(st.storyteller_node)
    assert "[m for m in messages if isinstance(m, HumanMessage)][-3:]" in src


# ---------------- P2-2 tipos/faixas ----------------
@pytest.mark.parametrize(
    "over",
    [
        {"attributes": {"str": 9999}},
        {"attributes": {"forca": 10}},
        {"attributes": {"str": "10"}},
        {"attributes": ["x"]},
        {"initial_relationship": 500},
        {"initial_relationship": "5"},
    ],
)
def test_typed_fields_rejected(over):
    assert v.validate_schema(entry(doc=npc_doc(**over)))


def test_artifact_bool_fields_rejected():
    e = entry(ns=PoolNamespace.ARTIFACT, sd=None, doc={"id": "a_1", "name": "X", "unique": "yes"})
    assert any(f.field == "unique" for f in v.validate_schema(e))


def test_materialize_clamps_relationship_and_attributes():
    e = entry(
        status=PoolStatus.PROMOTED,
        doc=npc_doc(initial_relationship=900, attributes={"str": 9999, "xx": 3}),
    )
    out = sp.materialize_npc(e, game_id="g")
    assert out["initial_relationship"] == 100 and out["attributes"]["str"] == 30
    assert set(out["attributes"]) == set(sp.ATTRIBUTE_KEYS)


# ---------------- P2-3/4/5/7 ----------------
def test_promotion_clears_input_shingles(tmp_path):
    store = make_store(tmp_path)
    sh = v.input_shingles(["uma frase longa o bastante para gerar shingles reais aqui"])
    store.insert(entry(shingles=sh))
    sp.promote_due(store, now=NOW, llm=FakeJudge(), embedder=None, embedding_profile="x")
    got = store.get(entry().entry_id)
    assert got.status == PoolStatus.PROMOTED and got.input_shingles == []


def test_get_store_fails_closed_outside_legacy(monkeypatch):
    import infrastructure.runtime as rt

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(rt, "get_runtime", boom)
    sp.reset_default_store()
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted-supabase")
    with pytest.raises(RuntimeError):
        sp.get_store()
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    assert sp.get_store() is not None


def test_submit_requires_principal_outside_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted")
    with pytest.raises(ValueError):
        sp.submit(
            PoolNamespace.NPC,
            npc_doc(),
            game_id="g",
            region_id="nova_arcadia",
            name_origin="narrator",
            seed=seed(),
            store=make_store(tmp_path),
        )


def test_mock_provider_in_attempts_blocks_promotion(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    store.insert(entry())

    def fake_eval(e, **kw):
        kw["attempts_out"].append({"provider": "mock", "model": "m", "outcome": "success"})
        return all_ok()

    monkeypatch.setattr(sp, "evaluate", fake_eval)
    out = sp.promote_due(store, now=NOW, llm=FakeJudge(), embedder=None, embedding_profile="x")
    assert out["promoted"] == 0 and store.get(entry().entry_id).status == PoolStatus.HELD


# ---------------- P2-10 / P2-1 ----------------
def test_bestiary_pool_view_filters_by_region(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    sp.reset_default_store()
    store = sp.get_store()
    for region, eid in (("nova_arcadia", "pool_bst_a"), ("brekmar", "pool_bst_b")):
        store.insert(
            entry(
                ns=PoolNamespace.CREATURE,
                status=PoolStatus.PROMOTED,
                game="game-z",
                name=f"Fera {region}",
                entry_id=eid,
                sd=None,
                region=region,
                doc={
                    "id": f"c_{region}",
                    "name": f"Fera {region}",
                    "description": "d",
                    "categoria": "padrao",
                    "arquetipo": "bruto",
                },
            )
        )
    view = bst_mod.load_bestiary("game-b", "nova_arcadia")
    ids = {v_.get("pool_entry_id") for v_ in view.values() if v_.get("pool_entry_id")}
    assert ids == {"pool_bst_a"}
    assert not [x for x in bst_mod.load_bestiary("game-b", "").values() if x.get("pool_entry_id")]


def test_cast_block_text_empty_is_empty_string():
    assert sp.cast_block_text([]) == ""
    assert sp.cast_block_text([entry()]).endswith("\n\n    ")
