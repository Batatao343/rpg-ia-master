"""SPEC-317 R6 — cache de índice FAISS em processo (mtime + invalidação no save)."""

from __future__ import annotations

import hashlib

import pytest
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

import rag


class _Emb(Embeddings):
    def _vec(self, text: str):
        h = hashlib.sha256(text.encode()).digest()
        return [h[i] / 255.0 for i in range(8)]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture()
def index(tmp_path, monkeypatch):
    monkeypatch.delenv("RPG_INDEX_CACHE", raising=False)
    rag._INDEX_CACHE.clear()
    emb = _Emb()
    path = str(tmp_path / "idx")
    db = FAISS.from_texts(["um", "dois"], emb)
    rag._save_index(db, path, "fake")
    calls = {"n": 0}
    real = FAISS.load_local

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(FAISS, "load_local", staticmethod(counting))
    return path, emb, calls


def test_load_index_hits_cache_same_mtime(index):
    path, emb, calls = index
    first = rag._load_index(path, emb)
    second = rag._load_index(path, emb)
    assert calls["n"] == 1 and first is second


def test_save_invalidates_cache(index):
    path, emb, calls = index
    rag._load_index(path, emb)
    db = FAISS.from_texts(["tres"], emb)
    rag._save_index(db, path, "fake")
    reloaded = rag._load_index(path, emb)
    assert calls["n"] == 2
    assert [d.page_content for d in reloaded.docstore._dict.values()] == ["tres"]


def test_external_write_invalidates_by_stamp(index):
    path, emb, calls = index
    rag._load_index(path, emb)
    # Outra instância serverless gravou: troca de arquivo sem passar por _save_index.
    FAISS.from_texts(["quatro", "cinco", "seis"], emb).save_local(path)
    rag._load_index(path, emb)
    assert calls["n"] == 2


def test_cache_off_flag_loads_every_time(index, monkeypatch):
    path, emb, calls = index
    monkeypatch.setenv("RPG_INDEX_CACHE", "off")
    rag._load_index(path, emb)
    rag._load_index(path, emb)
    assert calls["n"] == 2
