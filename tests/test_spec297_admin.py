"""SPEC-297 Etapa 10 - admin e observabilidade (R21, R32)."""

import json
import logging

import pytest

from scripts import pool_admin
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import NOW, FakeJudge, entry, make_store, npc_doc, seed
from workers.shared_pool_jobs import promote_due_job

NAME = "Brunhilda Cobreira"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "on")


def test_veto_removes_from_candidates_keeps_materialized_copy(tmp_path, on):
    store = make_store(tmp_path)
    store.insert(entry(status=PoolStatus.PROMOTED, entry_id="pool_npc_v"))
    pooled = store.get("pool_npc_v")
    copy = sp.materialize_npc(pooled, game_id="game-b")  # cópia no save de B
    assert pooled.name_fold == "brunhilda cobreira"
    args = dict(
        region_id="nova_arcadia", exclude_ids=set(), exclude_names=set(), limit=5, store=store
    )
    assert sp.candidates(PoolNamespace.NPC, **args)
    pool_admin.main(["veto", "pool_npc_v", "--reason", "smoke"], store=store)
    assert sp.candidates(PoolNamespace.NPC, **args) == []
    assert store.get("pool_npc_v").status == PoolStatus.VETOED
    assert copy["name"] == pooled.name  # D2: cópia já materializada permanece


def test_restore_reenters_hold(tmp_path):
    store = make_store(tmp_path)
    store.insert(entry(status=PoolStatus.PROMOTED, entry_id="pool_npc_r"))
    sp.admin_veto(store, "pool_npc_r", "x")
    restored = sp.admin_restore(store, "pool_npc_r", now=NOW)
    assert (
        restored.status == PoolStatus.HELD
        and restored.attempts == 0
        and restored.promote_after == NOW
    )
    assert (
        promote_due_job(store, llm=FakeJudge(), now=NOW, embedder=None, embedding_profile="x")[
            "promoted"
        ]
        == 1
    )


def test_retire_and_list_show(tmp_path, capsys):
    store = make_store(tmp_path)
    store.insert(entry(entry_id="pool_npc_a"))
    assert pool_admin.main(["list", "--status", "held"], store=store) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["entry_id"] == "pool_npc_a"
    assert pool_admin.main(["show", "pool_npc_a"], store=store) == 0
    assert "input_shingles" not in capsys.readouterr().out
    pool_admin.main(["retire", "pool_npc_a"], store=store)
    assert store.get("pool_npc_a").status == PoolStatus.RETIRED
    assert pool_admin.main(["show", "nope"], store=store) == 1


def _log_text(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def test_admin_logs_have_no_content(tmp_path, caplog):
    store = make_store(tmp_path)
    store.insert(entry(entry_id="pool_npc_l"))
    with caplog.at_level(logging.DEBUG):
        sp.admin_veto(store, "pool_npc_l", "motivo-secreto-123")
    text = _log_text(caplog)
    assert "pool.admin_action" in text and "pool_npc_l" in text
    assert "motivo-secreto-123" not in text and NAME not in text


def test_pool_events_have_no_name_or_persona(tmp_path, monkeypatch, caplog, on):
    store = make_store(tmp_path)
    persona = "Persona única INCONFUNDÍVEL zxqw"
    with caplog.at_level(logging.DEBUG):
        e = sp.submit(
            PoolNamespace.NPC,
            npc_doc(NAME, persona=persona),
            game_id="game-a",
            region_id="nova_arcadia",
            name_origin="narrator",
            seed=seed(),
            store=store,
        )
        store.update(e.entry_id, {"promote_after": NOW.isoformat()})
        promote_due_job(store, llm=FakeJudge(), now=NOW, embedder=None, embedding_profile="x")
        sp.cast_block(
            {"game_id": "g", "world": {"turn_count": 1, "current_location_id": "na_anel_lama"}},
            store=store,
        )
    text = _log_text(caplog)
    for event in ("pool.submitted", "pool.promoted"):
        assert event in text
    assert NAME not in text and "INCONFUNDÍVEL" not in text and "@" not in text
