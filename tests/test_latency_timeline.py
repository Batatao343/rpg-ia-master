"""SPEC-200 Etapa 1 — nucleo de timeline e fases exclusivas (puro, sem rede)."""

from __future__ import annotations

import threading

from observability import latency as lat
from observability.latency import FakeClock, TurnPhase, TurnTimeline


def test_phases_exclusive_no_double_count():
    clock = FakeClock()
    tl = TurnTimeline(clock)
    clock.advance(1.0)  # carga do save etc. (sem no ainda)
    with tl.phase(TurnPhase.CONTEXT):  # contexto aninhado no narrador
        clock.advance(2.0)
    clock.advance(3.0)  # resto do narrador
    tl.node_done("storyteller")
    tl.finish()
    ms = tl.phase_ms()
    assert ms["context"] == 2000
    assert ms["narrator"] == 4000  # 1.0 + 3.0; contexto NAO conta em dobro
    assert sum(ms.values()) == tl.total_ms() == 6000


def test_sum_phases_equals_total():
    clock = FakeClock()
    tl = TurnTimeline(clock)
    for node, spent in (
        ("turn_prepare", 0.0004),
        ("dm_router", 0.4113),
        ("storyteller", 2.5017),
        ("archivist", 1.9),
        ("turn_finalizer", 0.0006),
    ):
        clock.advance(spent)
        tl.node_done(node)
    tl.settle()
    with tl.phase(TurnPhase.PERSISTENCE):
        clock.advance(0.2403)
    clock.advance(0.0007)
    tl.finish()
    assert abs(sum(tl.phase_ms().values()) - tl.total_ms()) <= 1
    assert tl.phase_ms()["router"] == 411
    assert tl.phase_ms()["persistence"] == 240


def test_noop_when_no_timeline():
    assert lat.current_timeline() is None
    with lat.phase(TurnPhase.CONTEXT):  # nao levanta
        pass
    with lat.accumulate("archivist_validate_ms"):
        pass


def test_accumulate_and_scope():
    clock = FakeClock()
    tl = TurnTimeline(clock)
    token = lat.bind(tl)
    try:
        with lat.accumulate("archivist_validate_ms"):
            clock.advance(0.05)
        with lat.accumulate("archivist_validate_ms"):
            clock.advance(0.03)
        with lat.phase(TurnPhase.CONTEXT):
            clock.advance(0.1)
    finally:
        lat.unbind(token)
    assert tl.extra["archivist_validate_ms"] == 80
    assert lat.current_timeline() is None


def test_marks_thread_safe():
    clock = FakeClock()
    tl = TurnTimeline(clock, transport="stream")
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        for _ in range(200):
            clock.advance(0.001)
            with tl.phase(TurnPhase.CONTEXT):
                pass
            tl.node_done("storyteller")

    def generator():
        barrier.wait()
        for name in ("accepted", "ttfmc", "ttlt", "state"):
            tl.mark(name)

    threads = [threading.Thread(target=worker), threading.Thread(target=generator)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    tl.finish()
    assert tl.mark_ms("accepted") is not None and tl.mark_ms("state") is not None
    assert abs(sum(tl.phase_ms().values()) - tl.total_ms()) <= 1


def test_marks_are_first_occurrence():
    clock = FakeClock()
    tl = TurnTimeline(clock)
    clock.advance(0.5)
    tl.mark("ttfmc")
    clock.advance(0.5)
    tl.mark("ttfmc")
    assert tl.mark_ms("ttfmc") == 500


def test_client_gone_leaves_nulls():
    clock = FakeClock()
    tl = TurnTimeline(clock, transport="stream")
    clock.advance(0.01)
    tl.mark("accepted")  # desconectou antes de qualquer conteudo
    fields = tl.fields()
    assert fields["ack_server_ms"] == 10
    assert fields["ttfmc_server_ms"] is None and fields["ttlt_server_ms"] is None
    assert fields["pseudo_streaming"] is True


def test_real_token_mark_turns_off_pseudo_streaming():
    """SPEC-319 R6: o 1o delta real marca `first_token`; TTFT deixa de ser igual ao TTFMC."""
    clock = FakeClock()
    tl = TurnTimeline(clock, transport="stream")
    assert tl.fields()["pseudo_streaming"] is True
    assert tl.fields()["first_token_server_ms"] is None
    clock.advance(0.7)
    tl.mark("first_token")
    clock.advance(0.3)
    tl.mark("ttfmc")
    fields = tl.fields()
    assert fields["pseudo_streaming"] is False
    assert fields["first_token_server_ms"] == 700 and fields["ttfmc_server_ms"] == 1000


def test_attempts_attributed_to_current_phase():
    clock = FakeClock()
    tl = TurnTimeline(clock)
    with tl.phase(TurnPhase.CONTEXT):
        tl.note_attempt("classify")  # dentro do contexto
    tl.note_attempt("fast")  # pendente ate o no terminar
    tl.note_attempt("fast")
    tl.node_done("storyteller")
    assert tl.llm_by_phase() == {"context": 1, "narrator": 2}


def test_input_size_thresholds():
    assert lat.input_size(10) == "short"
    assert lat.input_size(100) == "medium"
    assert lat.input_size(500) == "long"


def test_percentile_nearest_rank_matches_playtest():
    from playtest.telemetry import _percentile

    values = [5, 1, 9, 3, 7, 2, 8]
    for pct in (50, 95):
        assert lat.percentile(values, pct) == _percentile(values, pct)
