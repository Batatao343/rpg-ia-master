"""SPEC-419 — prazo curto e disjuntor do embedding da consulta interativa do turno.

Jina real sobre ``httpx.MockTransport``; nenhuma rede. O handler "travado" dorme
``min(read timeout da requisição, 3 s)`` e levanta ``ReadTimeout``.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx
import pytest

import rag
from services import context_sources, embedding_guard
from services.embedding_guard import EmbeddingSkipped

VEC = [0.5] * 1024


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in (
        "RPG_EMBEDDING_QUERY_DEADLINE",
        "RPG_EMBEDDING_QUERY_TIMEOUT_S",
        "RPG_EMBEDDING_BREAKER_S",
    ):
        monkeypatch.delenv(name, raising=False)
    embedding_guard.reset_for_tests()
    yield
    embedding_guard.reset_for_tests()


class Provider:
    """Jina falsa: ``mode`` = 'hang' | 'ok' | '503-then-ok'."""

    def __init__(self, mode="hang", *, real_sleep=True):
        self.mode = mode
        self.real_sleep = real_sleep
        self.reads: list[float] = []
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        read = request.extensions["timeout"]["read"]
        self.reads.append(read)
        if self.mode == "hang":
            if self.real_sleep:
                time.sleep(min(read, 3.0))
            raise httpx.ReadTimeout("travado", request=request)
        if self.mode == "503-then-ok" and self.calls == 1:
            return httpx.Response(503, request=request)
        body = {"data": [{"index": 0, "embedding": VEC}], "usage": {"total_tokens": 3}}
        return httpx.Response(200, json=body, request=request)

    def embeddings(self) -> rag._JinaEmbeddingsHTTPX:
        client = httpx.Client(
            transport=httpx.MockTransport(self.handler), timeout=httpx.Timeout(30.0)
        )
        return rag._JinaEmbeddingsHTTPX(
            api_key="k", model_name="jina-test", client=client, max_attempts=2
        )


def _wire(monkeypatch, emb):
    monkeypatch.setattr(rag, "is_database_profile", lambda: True)
    monkeypatch.setattr(rag, "get_embeddings", lambda: emb)
    monkeypatch.setattr(rag, "active_provider", lambda: "jina")


def test_contexto_passa_dentro_do_prazo_com_provedor_travado(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.3")
    prov = Provider("hang")
    _wire(monkeypatch, prov.embeddings())
    start = time.monotonic()
    query = context_sources.embed_context_query_uncached("a estrada", game_id="g1")
    results = context_sources.acquire_context_sources(
        query, game_id="g1", npc_id=None, readers=None
    )
    assert time.monotonic() - start < 1.0
    assert query.vector is None and query.embedding_provider == "jina"
    assert all(r.text == "" for r in results)
    assert prov.calls == 1


def test_consulta_interativa_usa_prazo_curto(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.3")
    prov = Provider("hang")
    emb = prov.embeddings()
    with embedding_guard.interactive_query(), pytest.raises(httpx.ReadTimeout):
        emb.embed_query("x")
    assert prov.calls == 1 and prov.reads[0] <= 0.3


def test_consulta_interativa_preserva_retry_rapido_de_5xx():
    prov = Provider("503-then-ok")
    with embedding_guard.interactive_query():
        assert prov.embeddings().embed_query("x") == VEC
    assert prov.calls == 2


def test_disjuntor_pula_sem_rede_depois_de_timeout(monkeypatch, caplog):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.2")
    prov = Provider("hang")
    emb = prov.embeddings()
    with embedding_guard.interactive_query():
        with pytest.raises(httpx.ReadTimeout):
            emb.embed_query("x")
        calls = prov.calls
        events: list[str] = []
        monkeypatch.setattr(rag, "_emit_embedding_attempt", lambda *a, **k: events.append("use"))
        with caplog.at_level(logging.DEBUG), pytest.raises(EmbeddingSkipped):
            emb.embed_query("x")
    assert prov.calls == calls and events == []
    assert "circuit_open" in caplog.text
    assert "breaker_open" in caplog.text and "query_degraded" in caplog.text
    now = time.monotonic()
    monkeypatch.setattr(embedding_guard.time, "monotonic", lambda: now + 61)
    prov.mode = "ok"
    with embedding_guard.interactive_query():
        assert emb.embed_query("x") == VEC


def test_dois_timeouts_simultaneos_abrem_uma_janela(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.3")
    prov = Provider("hang")
    emb = prov.embeddings()
    errors: list[BaseException] = []

    def run():
        try:
            with embedding_guard.interactive_query():
                emb.embed_query("x")
        except httpx.ReadTimeout:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert errors == [] and embedding_guard._open_until > time.monotonic()


def test_disjuntor_nao_afeta_job_nem_escrita(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.2")
    prov = Provider("hang")
    emb = prov.embeddings()
    with embedding_guard.interactive_query(), pytest.raises(httpx.ReadTimeout):
        emb.embed_query("x")
    prov.calls, prov.reads, prov.real_sleep = 0, [], False  # sem dormir 30 s
    with pytest.raises(httpx.ReadTimeout):
        emb.embed_query("job")
    with pytest.raises(httpx.ReadTimeout):
        emb.embed_documents(["escrita"])
    assert prov.calls == 4 and all(r == 30 for r in prov.reads)


def test_resposta_normal_identica_com_e_sem_prazo(monkeypatch):
    out = {}
    for mode in ("on", "off"):
        monkeypatch.setenv("RPG_EMBEDDING_QUERY_DEADLINE", mode)
        prov = Provider("ok")
        with embedding_guard.interactive_query():
            out[mode] = (prov.embeddings().embed_query("x"), prov.calls)
    assert out["on"] == out["off"] == (VEC, 1)


def test_kill_switch_off_volta_ao_comportamento_antigo(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_DEADLINE", "off")
    prov = Provider("hang", real_sleep=False)
    with embedding_guard.interactive_query():
        assert embedding_guard.deadline() is None
        with pytest.raises(httpx.ReadTimeout):
            prov.embeddings().embed_query("x")
        with pytest.raises(httpx.ReadTimeout):
            prov.embeddings().embed_query("y")  # sem disjuntor
    assert prov.calls == 4 and all(r == 30 for r in prov.reads)
    assert embedding_guard.prefetch_wait(2.0) == 2.0


def test_breaker_zero_desliga_so_o_disjuntor(monkeypatch):
    monkeypatch.setenv("RPG_EMBEDDING_BREAKER_S", "0")
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.2")
    prov = Provider("hang")
    emb = prov.embeddings()
    for _ in range(2):
        with embedding_guard.interactive_query(), pytest.raises(httpx.ReadTimeout):
            emb.embed_query("x")
    assert prov.calls == 2 and prov.reads[0] <= 0.2


@pytest.mark.parametrize("raw", ["abc", "0", "999", " 6 "])
def test_env_invalido_ou_fora_da_faixa_cai_no_default(monkeypatch, raw):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", raw)
    assert embedding_guard.query_timeout_s() == 6.0


def test_logs_sem_texto_da_consulta(monkeypatch, caplog):
    monkeypatch.setenv("RPG_EMBEDDING_QUERY_TIMEOUT_S", "0.2")
    prov = Provider("hang")
    emb = prov.embeddings()
    with caplog.at_level(logging.DEBUG), embedding_guard.interactive_query():
        with pytest.raises(httpx.ReadTimeout):
            emb.embed_query("SEGREDO_X")
        with pytest.raises(EmbeddingSkipped):
            emb.embed_query("SEGREDO_X")
    assert caplog.text and "SEGREDO_X" not in caplog.text
