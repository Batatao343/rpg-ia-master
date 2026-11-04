"""SPEC-378 E5: golden da memoria de sessao/NPC do ``rag.py`` (add_* e query_*_by_vector).

Gravado com o codigo anterior a ``_add_memory``/``_query_by_vector``. Regrave so com
``RPG_SPEC378_RECORD=1`` e justifique no commit. ``SAVES_DIR`` fica em ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

import rag

GOLDEN = Path(__file__).parent / "fixtures" / "spec378" / "rag_memory.json"
GID = str(uuid.UUID(int=7))


class _Boom(Exception):
    pass


class _FakeDB:
    def __init__(self, log, kind):
        self.log, self.kind = log, kind

    def add_texts(self, texts, **kw):
        self.log.append(["add_texts", list(texts), sorted(kw)])


class _FakeFAISS:
    def __init__(self, log, fail):
        self.log, self.fail = log, fail

    def load_local(self, path, emb, **kw):
        self.log.append(["load_local", path, sorted(kw)])
        if self.fail:
            raise _Boom("faiss")
        return _FakeDB(self.log, "loaded")

    def from_texts(self, texts, emb, **kw):
        self.log.append(["from_texts", list(texts), sorted(kw)])
        if self.fail:
            raise _Boom("faiss")
        return _FakeDB(self.log, "new")


class _Store:
    def __init__(self, log, fail):
        self.log, self.fail = log, fail

    def stage(self, intent):
        self.log.append(["stage", repr(intent)])
        if self.fail:
            raise _Boom("stage")

    def query(self, q):
        self.log.append(["query", repr(q)])
        if self.fail:
            raise _Boom("query")
        return []


@pytest.fixture
def env(monkeypatch, tmp_path):
    log: list = []
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path / "mem"))
    monkeypatch.setattr(rag, "_log_event", lambda *a, **k: log.append(["log", list(a), k]))
    monkeypatch.setattr(rag, "_note_degraded", lambda s: log.append(["degraded", s]))
    monkeypatch.setattr(rag, "embedding_profile_id", lambda *a, **k: "EP")
    monkeypatch.setattr(rag, "_save_index", lambda db, p, prov: log.append(["save", p, prov]))
    monkeypatch.setattr(rag, "_read_meta", lambda p: {"provider": "prov"})
    monkeypatch.setattr(rag, "active_provider", lambda: "act")
    monkeypatch.setattr(rag, "_resolve_provider", lambda: "res")
    monkeypatch.setattr(rag, "_format_memory_documents", lambda d: f"FMT{len(list(d))}")
    monkeypatch.setattr(rag, "_load_index", lambda p, e: log.append(["load_index", p]) or "DB")

    def rop(op, ok, **kw):
        log.append(["result", op, ok, kw])
        return ok

    monkeypatch.setattr(rag, "_rag_operation_result", rop)
    monkeypatch.setattr(os, "makedirs", lambda p, **kw: log.append(["makedirs", str(p)]))
    import infrastructure.request_context as rc
    import infrastructure.runtime as rt

    monkeypatch.setattr(rc, "current_principal", lambda: "P")

    def setup(
        *, profile=False, store_fail=False, index=False, emb=True, faiss_fail=False, evid_fail=False
    ):
        monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted" if profile else "legacy")
        monkeypatch.setattr(
            rt, "get_runtime", lambda: type("R", (), {"memory_store": _Store(log, store_fail)})()
        )
        monkeypatch.setattr(rag, "_has_faiss_index", lambda p: index)
        e = object() if emb else None
        monkeypatch.setattr(rag, "_embeddings_for_index", lambda p: e)
        monkeypatch.setattr(rag, "get_embeddings", lambda: e)
        monkeypatch.setattr(rag, "FAISS", _FakeFAISS(log, faiss_fail))

        def evidence(db, v, k, source):
            if evid_fail:
                raise _Boom("q")
            log.append(["evidence", list(v), k, source])
            return [1, 2]

        monkeypatch.setattr(rag, "query_faiss_evidence", evidence)

    return log, setup, str(tmp_path)


def _add(scope, **kw):
    if scope == "session":
        return rag.add_memory_to_session(GID, **kw)
    return rag.add_npc_memory(GID, "npc1", **kw)


ADD_CASES = {
    "invalid_empty": {"texts": []},
    "invalid_none_gid": None,
    "profile_ok": {
        "profile": True,
        "texts": ["a", "b"],
        "metadatas": [{"timeline_epoch": 3}, None],
    },
    "profile_ok_nometa": {"profile": True, "texts": ["a"]},
    "profile_exc": {"profile": True, "store_fail": True, "texts": ["a"]},
    "existing_ok_meta": {"index": True, "texts": ["a"], "metadatas": [{"k": 1}]},
    "existing_ok": {"index": True, "texts": ["a"]},
    "existing_noemb": {"index": True, "emb": False, "texts": ["a"]},
    "new_ok_meta": {"texts": ["a"], "metadatas": [{"k": 1}]},
    "new_ok": {"texts": ["a", "b"]},
    "new_noemb": {"emb": False, "texts": ["a"]},
    "faiss_exc_existing": {"index": True, "faiss_fail": True, "texts": ["a"]},
    "faiss_exc_new": {"faiss_fail": True, "texts": ["a"]},
}
QUERY_CASES = {
    "profile": {"profile": True},
    "novec": {"vec": []},
    "noindex": {},
    "noemb": {"index": True, "emb": False},
    "ok": {"index": True},
}


def _norm(obj, tmp):
    text = json.dumps(obj, default=repr).replace(tmp.replace("\\", "\\\\"), "<TMP>")
    return json.loads(text.replace("\\\\", "/"))


def _snapshot(env) -> dict:
    log, setup, tmp = env
    out: dict = {}
    for scope in ("session", "npc"):
        for name, case in ADD_CASES.items():
            log.clear()
            case = dict(case or {"texts": ["a"]})
            opts = {
                k: case.pop(k)
                for k in ("profile", "store_fail", "index", "emb", "faiss_fail")
                if k in case
            }
            setup(**opts)
            if name == "invalid_none_gid":
                res = (
                    rag.add_memory_to_session("", ["a"])
                    if scope == "session"
                    else rag.add_npc_memory(GID, "", ["a"])
                )
            else:
                res = _add(scope, **case)
            out[f"add.{scope}.{name}"] = [res, list(log)]
        for name, case in QUERY_CASES.items():
            log.clear()
            case = dict(case)
            vec = case.pop("vec", [0.5, 0.25])
            setup(**case)
            if scope == "session":
                res = rag.query_session_by_vector(vec, GID)
                res2 = rag.query_session_by_vector(vec, GID, k=2)
            else:
                res = rag.query_npc_by_vector(vec, GID, "npc1")
                res2 = rag.query_npc_by_vector(vec, GID, "npc1", k=5)
            out[f"query.{scope}.{name}"] = [res, res2, list(log)]
        log.clear()
        setup(index=True, evid_fail=True)
        # excecao no FAISS dentro da consulta
        import rag as r

        r.query_faiss_evidence = lambda *a, **k: (_ for _ in ()).throw(_Boom("q"))
        res = (
            rag.query_session_by_vector([1.0], GID)
            if scope == "session"
            else rag.query_npc_by_vector([1.0], GID, "npc1")
        )
        out[f"query.{scope}.exc"] = [res, list(log)]
    assert not os.path.exists(os.path.join(tmp, "mem")), "nada deve ser criado fora do tmp"
    return _norm(out, tmp)


def test_rag_memory_matches_golden(env):
    got = _snapshot(env)
    if os.environ.get("RPG_SPEC378_RECORD") == "1":
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True), encoding="utf-8")
    assert got == json.loads(GOLDEN.read_text(encoding="utf-8"))
