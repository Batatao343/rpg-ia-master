"""SPEC-374 Etapa 4 — prazo do job dentro da janela do cron (R14)."""

from __future__ import annotations

import inspect

import pytest

from infrastructure.contracts import JobDeferred, JobRequest
from infrastructure.local_adapters import InlineJobQueue
from services import creature_gen as cg
from services import creature_gen_jobs as jobs
from workers import drain
from workers.job_worker import JobWorker


class Relogio:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


PAYLOAD = {
    "pedido": "algo que vive nos odres de água estragada",
    "regiao": "deserto_zhur",
    "location_id": "deserto_zhur",
    "encounter_level": 1,
    "game_id": "g-374",
    "turn": 4,
}


@pytest.fixture()
def capturar(monkeypatch):
    """Troca o LLM por um que falha se chamado e captura o prazo passado a ``gerar_nova``."""
    visto: dict = {"prazos": [], "llm": 0}

    def gerar_falso(p, dec, **kw):
        visto["prazos"].append(kw.get("prazo", "ausente"))
        return None, {"tentativas": 0, "codigos": ["FALSO"]}

    monkeypatch.setattr(cg, "gerar_nova", gerar_falso)
    return visto


def test_sem_janela_usa_prazo_cheio(capturar):
    assert drain.job_window_remaining() is None
    assert jobs.prazo_na_janela() is None
    out = jobs.handler(dict(PAYLOAD))
    assert out["status"] == "fallback"
    assert capturar["prazos"] == [None]  # None = prazo_s() inteiro (30 s)


def test_janela_curta_adia_sem_llm(capturar, monkeypatch):
    import llm_setup

    def proibido(*a, **k):
        raise AssertionError("LLM chamado com janela curta")

    monkeypatch.setattr(llm_setup, "get_llm", proibido)
    clock = Relogio(0.0)
    with drain.job_window_scope(11.0, clock):  # restam 11 s < 12 s
        with pytest.raises(JobDeferred) as ei:
            jobs.handler(dict(PAYLOAD))
    assert ei.value.reason == "janela_curta" and ei.value.delay_seconds == 60.0
    assert capturar["prazos"] == []  # nem chegou a gerar


def test_janela_minima_configuravel(capturar, monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_GEN_MIN_WINDOW_S", "5")
    with drain.job_window_scope(8.0, Relogio(0.0)):
        assert jobs.prazo_na_janela() == 5.0  # 8 - 3 s de folga


def test_prazo_efetivo_menor_que_janela(capturar):
    clock = Relogio(0.0)
    with drain.job_window_scope(20.0, clock):
        assert drain.job_window_remaining() == 20.0
        assert jobs.prazo_na_janela() == 17.0  # janela - 3 s < 30 s
        jobs.handler(dict(PAYLOAD))
        clock.t = 5.0  # o relógio anda: o restante encolhe
        assert drain.job_window_remaining() == 15.0
        assert jobs.prazo_na_janela() == 12.0
    with drain.job_window_scope(200.0, clock):
        assert jobs.prazo_na_janela() == cg.prazo_s() == 30.0  # nunca passa do prazo
    assert capturar["prazos"] == [17.0]
    assert drain.job_window_remaining() is None  # o escopo termina com o dreno


def test_gerar_nova_respeita_prazo_menor(monkeypatch):
    """O prazo da janela entra de verdade no relógio da geração (não só no argumento)."""
    relogio = iter([0.0, 0.0, 9.0, 9.0, 9.0, 9.0])
    monkeypatch.setattr(cg, "_relogio", lambda: next(relogio, 20.0))
    import llm_setup

    class _L:
        def with_structured_output(self, *a, **k):
            class _B:
                def invoke(self, m):
                    return cg.FichaCriaturaGerada(
                        **{"nome": "X Y", "familia": "besta_entropia", "origem_fonte": "abismo"}
                    )

            return _B()

    monkeypatch.setattr(llm_setup, "get_llm", lambda *a, **k: _L())
    p = jobs.pedido_de(PAYLOAD)
    _f, info = cg.gerar_nova(p, cg.Decisao("nova"), bestiary={}, runtime=[], lore="", prazo=6.0)
    assert "PRAZO" in info["codigos"]  # 9 s de relógio > prazo de 6 s


def _fila_com_job(max_attempts: int = 2):
    q = InlineJobQueue()
    q.enqueue(
        JobRequest(jobs.JOB_KIND, "creature:g-374:x", dict(PAYLOAD), max_attempts=max_attempts)
    )
    return q


def test_adiado_nao_vira_dead(capturar):
    q = _fila_com_job(max_attempts=2)
    worker = JobWorker(q, {jobs.JOB_KIND: jobs.handler}, worker_id="t")
    clock = Relogio(0.0)
    # janela curta 3x (mais que max_attempts): o job segue na fila, nunca vai a dead
    for _ in range(3):
        out = drain.drain_jobs(
            12.0, 5, "t", worker=worker, clock=clock, min_job_window_s=0.0, safety_margin_s=3.0
        )
        assert out["deferred"] == 5
        row = next(iter(q._jobs.values()))
        assert row.status == "queued" and row.attempt == 0 and row.error_code == "janela_curta"
    # janela boa: roda de verdade (fallback do gate termina o job normalmente)
    out = drain.drain_jobs(
        60.0, 1, "t", worker=worker, clock=clock, min_job_window_s=0.0, safety_margin_s=3.0
    )
    assert out["processed"] == 1 and out["dead"] == 0
    assert next(iter(q._jobs.values())).status == "succeeded"
    assert capturar["prazos"] == [30.0]  # 60 - 3 - 3 = 54 > 30


def test_postgres_defer_nao_gasta_tentativa():
    from infrastructure.postgres_jobs import PostgresJobQueue

    sql = inspect.getsource(PostgresJobQueue.defer)
    assert "attempts=greatest(attempts-1,0)" in sql and "status='queued'" in sql


def test_outros_jobs_janela_inalterada():
    assert drain.MIN_JOB_WINDOW_S == 15.0 and drain.SAFETY_MARGIN_S == 3.0
    visto: list = []
    q = InlineJobQueue()
    q.enqueue(JobRequest("outro", "k1", {}))

    def outro(_payload):
        visto.append(drain.job_window_remaining())
        return {"ok": True}

    worker = JobWorker(q, {"outro": outro}, worker_id="t")
    clock = Relogio(0.0)
    # 17 s de orçamento - 3 s de margem = 14 s < 15 s: o dreno nem começa (regra de sempre)
    out = drain.drain_jobs(17.0, 5, "t", worker=worker, clock=clock)
    assert out["processed"] == 0 and out["stopped_reason"] == "deadline"
    out = drain.drain_jobs(30.0, 5, "t", worker=worker, clock=clock)
    assert out["processed"] == 1 and visto == [27.0]
    assert drain.job_window_remaining() is None
