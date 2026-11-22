"""SPEC-421: narracao mediada com texto ao vivo, frase a frase, com o filtro de segredo.

O gate (`find_unrevealed` por frase fechada) e o MESMO filtro do texto final
(`_guard_mediation_secret`, SPEC-202 R11), no MESMO `scene_state`. Estes testes provam que
nada que o filtro final reprova sai ao vivo (I1..I10).
"""

from __future__ import annotations

import re

import pytest

import agents.storyteller as stt
from services import narrative_sink as sink
from services.secret_signatures import SECRET_SIGNATURES, find_unrevealed
from tests.spec319_helpers import slices
from tests.test_mediation_secret import _state

CLEAN = (
    "Magda desvia o olhar e ajeita o xale sobre os ombros magros. "
    "O fogo estala na lareira e o cheiro de ervas queimadas enche a pequena sala. "
    "Ela murmura algo ininteligivel para si mesma antes de voltar as cartas. "
    "La fora o vento arrasta folhas secas pela rua de pedra."
)
SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
ALL_SIGS = [p for phrases in SECRET_SIGNATURES.values() for p in phrases]


class _StreamLLM:
    """LLM falso: `stream_structured` entrega a narracao em fatias; marca o fim da chamada."""

    def __init__(self, narrative: str, size: int = 7, order: list | None = None) -> None:
        self.narrative = narrative
        self.size = size
        self.order = order if order is not None else []
        self.stream_calls = 0
        self.invokes = 0
        self._schema = None

    def with_structured_output(self, schema, *_a, **_k):
        self._schema = schema
        return self

    def invoke(self, messages, *_a, **_k):
        self.invokes += 1
        if self._schema is stt.StoryUpdate:
            return stt.StoryUpdate(narrative=self.narrative)
        from mock_llm import MockLLM

        return MockLLM().with_structured_output(self._schema).invoke(messages)

    def stream_structured(self, messages, schema, *, on_delta=None, on_reset=None, key=None):
        self.stream_calls += 1
        for piece in slices(self.narrative, self.size):
            on_delta(piece)
        self.order.append(("returned", ""))
        return schema(narrative=self.narrative)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("RPG_MEDIATED_STREAM", raising=False)


@pytest.fixture()
def seen(monkeypatch):
    import observability.telemetry as tel

    out: list[tuple[str, str, dict]] = []
    real = tel.log_event

    def spy(area, event, **fields):
        out.append((area, event, fields))
        return real(area, event, **fields)

    monkeypatch.setattr(tel, "log_event", spy)
    return out


def _run(monkeypatch, narrative, *, mode="on", size=7, state=None, bound=True):
    monkeypatch.setenv("RPG_MEDIATED_STREAM", mode)
    order: list[tuple[str, str]] = []
    llm = _StreamLLM(narrative, size, order)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    token = sink.bind(lambda kind, text: order.append((kind, text))) if bound else None
    try:
        out = stt.storyteller_node(state if state is not None else _state())
    finally:
        if token is not None:
            sink.unbind(token)
    return out, order, llm


def _shown(order) -> str:
    return "".join(t for k, t in order if k == "delta")


def _sentence_start(raw: str, idx: int) -> int:
    ends = [m.end() for m in SPLIT.finditer(raw) if m.end() <= idx]
    return max(ends, default=0)


def _no_signature(text: str) -> bool:
    low = text.lower()
    return not any(sig in low for sig in ALL_SIGS)


# --- R1 / flag ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "off"),
        ("off", "off"),
        ("shadow", "shadow"),
        ("ON", "on"),
        (" on ", "on"),
        ("talvez", "off"),
        ("", "off"),
    ],
)
def test_mediated_stream_mode(monkeypatch, raw, expected):
    from services import mediated_stream

    if raw is None:
        monkeypatch.delenv("RPG_MEDIATED_STREAM", raising=False)
    else:
        monkeypatch.setenv("RPG_MEDIATED_STREAM", raw)
    assert mediated_stream.mediated_stream_mode() == expected


# --- evidencia: falhava antes da mudanca ---------------------------------------------------


def test_mediated_turn_streams_before_end(monkeypatch):
    out, order, llm = _run(monkeypatch, CLEAN, mode="on")
    assert llm.stream_calls == 1 and llm.invokes >= 0
    names = [k for k, _ in order]
    assert "delta" in names[: names.index("returned")]  # >= 1 delta antes do fim da chamada
    assert out["messages"][-1].content.strip().startswith("Magda desvia o olhar")


# --- I1: nada que o filtro final reprova sai ao vivo ---------------------------------------

SECRET_CASES = {
    "primeira_frase": (
        "Ela carrega o pacto com Daruun em silencio absoluto. " + CLEAN,
        "pacto com daruun",
    ),
    "ultima_do_paragrafo": (
        "Magda desvia o olhar e ajeita o xale sobre os ombros magros. "
        "O fogo estala na lareira e o cheiro de ervas queimadas enche a sala. "
        "Ela sussurra que carrega o pacto com Daruun desde muito cedo.",
        "pacto com daruun",
    ),
    "segundo_paragrafo": (
        "Magda desvia o olhar.\n\nEla carrega o peso do pacto com Daruun, "
        "feito em troca de imortalidade.\n\n— Pergunte outra coisa.",
        "pacto com daruun",
    ),
    "caixa_alta": (
        CLEAN + " Dizem que PACTO COM VALERIUS explica tudo. " + CLEAN,
        "pacto com valerius",
    ),
    "caixa_titulo": (
        CLEAN + " Dizem que o Pacto Com Valerius explica tudo. " + CLEAN,
        "pacto com valerius",
    ),
    "dois_segredos": (
        CLEAN + " Falam do pacto com Valerius ao pe do fogo. A rede carmesim pode despertar logo. ",
        "pacto com valerius",
    ),
    "aspas_travessao": (
        CLEAN + ' "— O pacto com Daruun nunca foi esquecido", diz ela. ' + CLEAN,
        "pacto com daruun",
    ),
    "primeira_frase_longa_sem_ponto": (
        "Ela carrega o pacto com Daruun e nao diz mais nada a ninguem naquela sala escura",
        "pacto com daruun",
    ),
}


@pytest.mark.parametrize("size", [1, 3, 7, 100000])
@pytest.mark.parametrize("name", sorted(SECRET_CASES))
def test_mediated_stream_never_shows_secret_sentence(monkeypatch, seen, name, size):
    raw, sig = SECRET_CASES[name]
    out, order, _ = _run(monkeypatch, raw, mode="on", size=size)
    shown = _shown(order)
    assert _no_signature(shown)
    assert all(_no_signature(t) for k, t in order if k == "delta")
    assert len(shown) <= _sentence_start(raw, raw.lower().find(sig))
    final = out["messages"][-1].content
    assert sig not in final.lower() or find_unrevealed(final, _state()) is None
    assert any(
        ev == "stream_risk_hold" and f.get("rule") == "mediation_secret" for _a, ev, f in seen
    )


def test_secret_in_first_sentence_has_no_deltas_and_final_extends(monkeypatch):
    raw, _ = SECRET_CASES["primeira_frase"]
    out, order, _ = _run(monkeypatch, raw, mode="on", size=5)
    assert _shown(order) == ""
    assert "não deixa transparecer" in out["messages"][-1].content


def test_secret_second_paragraph_final_extends_shown(monkeypatch):
    raw, _ = SECRET_CASES["segundo_paragrafo"]
    out, order, _ = _run(monkeypatch, raw, mode="on", size=3)
    shown = _shown(order)
    assert shown.strip() == "Magda desvia o olhar."
    assert out["messages"][-1].content.startswith(shown)  # sufixo, sem replace
    assert any(str(r).startswith("mediation_secret") for r in out.get("narrative_rejections") or [])


def test_secret_last_sentence_of_paragraph_needs_replace(monkeypatch):
    from services.narrative_sink import replace_reason

    raw, _ = SECRET_CASES["ultima_do_paragrafo"]
    out, order, _ = _run(monkeypatch, raw, mode="on", size=4)
    shown = _shown(order)
    assert shown.startswith("Magda desvia o olhar")
    assert replace_reason(shown, out["messages"][-1].content) in {"tail", "shorter", "start"}


def test_concealed_name_gate_sees_pre_veil(monkeypatch, seen):
    # O nome oculto esta DENTRO da assinatura: so o texto pre-veu casa "pacto com valerius".
    monkeypatch.setattr(sink, "_conceal_map", lambda state: {"Valerius": "o Regente"})
    raw = (
        "A Ordem vigia a praca e ninguem ousa falar alto perto dela hoje. "
        "Magda diz que o velho fez um pacto com Valerius em troca de ouro."
    )
    for size in (1, 7, 100000):
        seen.clear()
        _out, order, _ = _run(monkeypatch, raw, mode="on", size=size)
        deltas = [t for k, t in order if k == "delta"]
        assert any(
            ev == "stream_risk_hold" and f.get("rule") == "mediation_secret" for _a, ev, f in seen
        )
        shown = "".join(deltas)
        assert "Regente" not in shown and "Valerius" not in shown and "pacto com" not in shown
        assert "A Ordem vigia" in shown


# --- F-1: lacunas conhecidas do filtro final (paridade, nao correcao) ---------------------------


@pytest.mark.parametrize(
    "gap",
    [
        "consumiu a familia",  # sem acento
        "pacto  com valerius",  # espaco duplo: o final colapsa e reprova (ramo "final reprovou")
        "pacto com\nvalerius",  # quebra de linha no meio
        "o pacto com. Valerius",  # partida por ponto
    ],
)
def test_mediated_stream_parity_known_gaps(monkeypatch, gap):
    raw = f"{CLEAN} Dizem que ele {gap} desde cedo, mas ninguem sabe. {CLEAN}"
    out, order, _ = _run(monkeypatch, raw, mode="on", size=5)
    final = out["messages"][-1].content
    if not any(
        str(r).startswith("mediation_secret") for r in out.get("narrative_rejections") or []
    ):
        # o final entregou: o stream nao pode ter mostrado nada que o final nao tenha
        assert final.startswith(_shown(order).rstrip()[:60])
    else:  # o final reprovou: o stream nao passou do inicio da frase reprovada
        assert _no_signature(_shown(order))


# --- I4 / I5 ------------------------------------------------------------------------------


def test_secret_signatures_fit_in_one_sentence():
    for sig in ALL_SIGS:
        assert not any(c in sig for c in ".!?\n\r"), sig
        assert sig == sig.strip(), sig


@pytest.mark.parametrize("sig", ALL_SIGS)
def test_gate_holds_every_sentence_final_rejects(sig):
    from services.mediated_stream import secret_gate

    st = _state()
    scene = {**st, "world": st["world"], "npcs": st["npcs"]}
    gate = secret_gate(scene)
    for variant in (sig, sig.upper(), sig.title()):
        sentence = f"Ela diz que {variant} sempre existiu."
        texts = {
            "primeira": f"{sentence} {CLEAN}",
            "meio": f"{CLEAN} {sentence} {CLEAN}",
            "ultima": f"{CLEAN} {sentence}",
            "segundo_paragrafo": f"{CLEAN}\n\n{sentence}\n\nFim.",
        }
        for text in texts.values():
            _guarded, rejections = stt._guard_mediation_secret(text, scene)
            if rejections:
                held = [s for s in SPLIT.split(text) if s.strip() and gate(s)]
                assert held and any(variant.lower() in s.lower() for s in held)


# --- I2 / I3 / I8 -------------------------------------------------------------------------


def _comparable(out: dict) -> dict:
    """Retorno do no inteiro, com mensagens por conteudo (objetos de mensagem tem id proprio)."""
    return {
        k: [(type(m).__name__, m.content) for m in v] if k == "messages" else v
        for k, v in out.items()
    }


@pytest.mark.parametrize("case", ["segundo_paragrafo", "ultima_do_paragrafo", "primeira_frase"])
def test_mediated_final_identical_across_modes(monkeypatch, case):
    raw, _ = SECRET_CASES[case]
    results = {}
    for mode in ("off", "shadow", "on"):
        out, _order, _ = _run(monkeypatch, raw, mode=mode, size=9)
        msgs = [m.content for m in out["messages"]]
        results[mode] = (msgs, out.get("narrative_rejections"), _comparable(out))
    assert results["off"] == results["shadow"] == results["on"]


def test_mediated_off_uses_invoke(monkeypatch):
    out, order, llm = _run(monkeypatch, CLEAN, mode="off")
    assert llm.stream_calls == 0 and llm.invokes >= 1
    assert order == []


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_mediated_without_sink_is_invoke(monkeypatch, mode):
    out, order, llm = _run(monkeypatch, CLEAN, mode=mode, bound=False)
    assert llm.stream_calls == 0 and llm.invokes >= 1
    assert out["messages"][-1].content.strip().startswith("Magda")


# --- I6 -----------------------------------------------------------------------------------


def test_gate_uses_final_guard_state(monkeypatch):
    from services import mediated_stream

    gate_ids: list[int] = []
    final_ids: list[int] = []
    real_gate = mediated_stream.secret_gate
    real_guard = stt._guard_mediation_secret

    def spy_gate(scene_state):
        gate_ids.append(id(scene_state))
        return real_gate(scene_state)

    def spy_guard(text, state):
        final_ids.append(id(state))
        return real_guard(text, state)

    monkeypatch.setattr(mediated_stream, "secret_gate", spy_gate)
    monkeypatch.setattr(stt, "_guard_mediation_secret", spy_guard)
    _run(monkeypatch, CLEAN, mode="on")
    assert gate_ids and final_ids and gate_ids[0] == final_ids[0]


# --- I7: fail-closed ------------------------------------------------------------------------


def test_gate_exception_holds_rest(monkeypatch):
    import services.mediated_stream as ms
    import services.secret_signatures as ss

    def boom(text, state):
        raise RuntimeError("boom")

    monkeypatch.setattr(ss, "find_unrevealed", boom)
    gate = ms.secret_gate({"x": 1})
    assert gate("Qualquer frase.") == "check_error"
    guard = sink.StreamGuard(risk=sink._compose_risk(gate, None))
    out = guard.feed(CLEAN) + guard.finish()
    assert out == ""  # nada sai depois da excecao: o final entrega


def test_mediated_without_scene_state_does_not_stream():
    from services import mediated_stream

    for scene in ({}, None):
        plan = mediated_stream.stream_plan(
            {"interlocutor_reason": "meta_to_narrator"}, scene, rumor_nothing=False
        )
        assert plan.stream is False and plan.extra_risk is None


# --- I9 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_rumor_nothing_never_streams_even_with_flag_on(monkeypatch, mode):
    import services.rumor_adoption as ra

    monkeypatch.setattr(ra, "nothing_found", lambda *a, **k: True)
    out, order, llm = _run(monkeypatch, CLEAN, mode=mode)
    assert llm.stream_calls == 0 and order == []


def test_plan_unmediated_is_unchanged(monkeypatch):
    from services import mediated_stream

    monkeypatch.setenv("RPG_MEDIATED_STREAM", "off")
    plan = mediated_stream.stream_plan({}, {"a": 1}, rumor_nothing=False)
    assert (plan.stream, plan.extra_risk, plan.shadow) == (True, None, False)
    plan = mediated_stream.stream_plan({}, {"a": 1}, rumor_nothing=True)
    assert plan.stream is False


# --- I10: shadow ----------------------------------------------------------------------------


def test_mediated_shadow_emits_nothing_and_logs(monkeypatch, seen):
    raw, _ = SECRET_CASES["segundo_paragrafo"]
    out, order, llm = _run(monkeypatch, raw, mode="shadow", size=3)
    assert llm.stream_calls == 1
    assert [k for k, _ in order if k in ("delta", "reset")] == []
    evs = [f for _a, ev, f in seen if ev == "mediated_stream"]
    assert len(evs) == 1
    ev = evs[0]
    assert ev["mode"] == "shadow" and ev["reason"] == "meta_to_narrator"
    assert ev["leak"] is False and ev["shown_len"] > 0 and ev["held_rule"] == "mediation_secret"
    assert ev["would_replace"] is False
    assert not any(isinstance(v, str) and "Magda" in v for v in ev.values())


def test_mediated_on_logs_event_with_replace(monkeypatch, seen):
    raw, _ = SECRET_CASES["ultima_do_paragrafo"]
    _run(monkeypatch, raw, mode="on", size=3)
    ev = next(f for _a, e, f in seen if e == "mediated_stream")
    assert ev["mode"] == "on" and ev["would_replace"] is True and ev["leak"] is False
    assert ev["final_len"] > 0


def test_first_delta_ms_uses_injected_clock(monkeypatch, seen):
    from services import mediated_stream

    ticks = iter([10.0, 10.25] + [11.0] * 50)
    monkeypatch.setattr(mediated_stream, "_clock", lambda: next(ticks))
    _run(monkeypatch, CLEAN, mode="on", size=4)
    ev = next(f for _a, e, f in seen if e == "mediated_stream")
    assert ev["first_delta_ms"] == 250


def test_off_and_unmediated_log_no_mediated_event(monkeypatch, seen):
    _run(monkeypatch, CLEAN, mode="off")
    _run(monkeypatch, CLEAN, mode="on", state=_state(interlocutor_reason="direct_address"))
    assert not [e for _a, e, _f in seen if e == "mediated_stream"]


# --- segredo ja revelado ----------------------------------------------------------------------


def test_secret_already_revealed_by_summary(monkeypatch):
    raw = (
        "Ela carrega o peso do pacto com Daruun, como todos sabem desde a noite da vigilia. "
        "Magda desvia o olhar e ajeita o xale sobre os ombros magros agora."
    )
    st = _state(
        player={
            "name": "T",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "vitalidade": 20,
            "max_vitalidade": 20,
            "known_secrets": ["O pacto com Daruun"],
        }
    )
    out, order, _ = _run(monkeypatch, raw, mode="on", size=6, state=st)
    final = out["messages"][-1].content
    assert not any(
        str(r).startswith("mediation_secret") for r in out.get("narrative_rejections") or []
    )
    assert final.startswith(_shown(order).rstrip())  # sufixo, sem replace


# --- reset no meio --------------------------------------------------------------------------


def test_mediated_reset_mid_stream(monkeypatch):
    class _Reset(_StreamLLM):
        def stream_structured(self, messages, schema, *, on_delta=None, on_reset=None, key=None):
            self.stream_calls += 1
            for piece in slices(self.narrative, 6)[:25]:
                on_delta(piece)
            on_reset()
            for piece in slices(self.narrative, 6):
                on_delta(piece)
            self.order.append(("returned", ""))
            return schema(narrative=self.narrative)

    monkeypatch.setenv("RPG_MEDIATED_STREAM", "on")
    order: list = []
    llm = _Reset(CLEAN, order=order)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    token = sink.bind(lambda kind, text: order.append((kind, text)))
    try:
        stt.storyteller_node(_state())
    finally:
        sink.unbind(token)
    kinds = [k for k, _ in order]
    assert "reset" in kinds
    after = "".join(t for k, t in order[kinds.index("reset") :] if k == "delta")
    assert after.startswith("Magda desvia")  # o guard recomecou limpo


# --- FallbackLLM: AIMessage do structured output cai no guard do storyteller -----------------


def test_mediated_aimessage_result_falls_into_isinstance_guard(monkeypatch):
    from langchain_core.messages import AIMessage

    class _Err(_StreamLLM):
        def stream_structured(self, messages, schema, *, on_delta=None, on_reset=None, key=None):
            self.stream_calls += 1
            return AIMessage(content="erro")

    monkeypatch.setenv("RPG_MEDIATED_STREAM", "on")
    llm = _Err(CLEAN)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    token = sink.bind(lambda kind, text: None)
    try:
        out = stt.storyteller_node(_state())
    finally:
        sink.unbind(token)
    assert out["messages"][-1].content.strip()
    assert llm.stream_calls == 1 and llm.invokes == 0


def test_stream_guard_risk_none_is_unchanged():
    g = sink.StreamGuard()
    out = g.feed(CLEAN[:150]) + g.feed(CLEAN[150:]) + g.finish()
    assert out.strip() == CLEAN.strip()


# --- SSE ponta a ponta -------------------------------------------------------------------------
from tests.test_streaming import _new_game, _read_sse, client  # noqa: E402,F401


def _mediated_sse(client, monkeypatch, narrative, *, size=5):
    import persistence

    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    monkeypatch.setenv("RPG_MEDIATED_STREAM", "on")
    llm = _StreamLLM(narrative, size)
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    gid = _new_game(client)
    state = persistence.load_game_state(persistence.save_path(gid))
    state["npcs"] = {
        "Velha Magda": {
            "name": "Velha Magda",
            "in_scene": True,
            "home_location_id": state["world"].get("current_location_id"),
            "relationship": 6,
        }
    }
    persistence.save_game_state(state)
    body = {"input_text": "Narrador, o que a Velha Magda sente?", "game_id": gid}
    with client.stream("POST", "/game/action/stream", json=body) as r:
        assert r.status_code == 200
        return _read_sse(r), llm


def test_sse_mediated_live_chunks_before_done(client, monkeypatch):
    events, llm = _mediated_sse(client, monkeypatch, CLEAN)
    assert llm.stream_calls == 1
    narr = [d for e, d in events if e == "narrative"]
    live = [d for d in narr if d.get("live")]
    assert live and narr[-1]["done"] is True
    assert not [d for d in narr if d.get("replace")]


def test_sse_mediated_secret_mid_paragraph_one_replace_no_live_leak(client, monkeypatch):
    raw, _ = SECRET_CASES["ultima_do_paragrafo"]
    events, _llm = _mediated_sse(client, monkeypatch, raw)
    narr = [d for e, d in events if e == "narrative"]
    assert len([d for d in narr if d.get("replace")]) == 1
    live_text = "".join(d["chunk"] for d in narr if d.get("live"))
    assert live_text and _no_signature(live_text)


# --- P3-4: turno que falha no meio nao contamina a telemetria do seguinte ----------------------


def test_failed_turn_does_not_leak_run_into_next_after_final(monkeypatch, seen):
    from services import mediated_stream

    class _Boom(_StreamLLM):
        def stream_structured(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setenv("RPG_MEDIATED_STREAM", "on")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Boom(CLEAN))
    token = sink.bind(lambda kind, text: None)
    try:
        stt.storyteller_node(_state())  # o no engole a falha; o `_Run` nao pode sobrar
    finally:
        sink.unbind(token)
    assert mediated_stream._RUN.get() is None
    # um `_Run` velho (turno que lancou fora do except) e descartado pelo turno seguinte
    mediated_stream._RUN.set(mediated_stream._Run("on"))
    seen.clear()
    _run(monkeypatch, CLEAN, mode="off")
    assert not any(ev == "mediated_stream" for _a, ev, _f in seen)
