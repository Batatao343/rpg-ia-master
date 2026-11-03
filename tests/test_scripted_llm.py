"""SPEC-379 R3: ScriptedLLM, o fake unico de LLM da suite."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

import character_creator
from llm_setup import FallbackLLM, ModelTier
from services import narrative_sink
from tests.fakes.scripted_llm import ScriptedLLM, patch_get_llm


class Foo(BaseModel):
    a: int = 0


class Bar(BaseModel):
    b: str = ""


def test_dict_response_is_validated_by_schema():
    llm = ScriptedLLM({Foo: {"a": 3}})
    out = llm.with_structured_output(Foo).invoke(["m"])
    assert isinstance(out, Foo) and out.a == 3


def test_sequence_is_consumed_in_order_and_fails_loud_when_exhausted():
    llm = ScriptedLLM({Foo: [Foo(a=1), {"a": 2}]})
    bound = llm.with_structured_output(Foo)
    assert [bound.invoke("x").a, bound.invoke("x").a] == [1, 2]
    with pytest.raises(AssertionError, match="Foo"):
        bound.invoke("x")


def test_repeat_last_keeps_answering():
    bound = ScriptedLLM({Foo: [Foo(a=1), Foo(a=2)]}, repeat_last=True).with_structured_output(Foo)
    assert [bound.invoke("x").a for _ in range(4)] == [1, 2, 2, 2]


def test_unscripted_schema_fails_loud():
    with pytest.raises(AssertionError, match="Bar"):
        ScriptedLLM({Foo: {}}).with_structured_output(Bar).invoke("x")


def test_callable_receives_messages_and_schema():
    seen = []

    def fn(messages, schema):
        seen.append((messages, schema))
        return Foo(a=9)

    out = ScriptedLLM({"Foo": fn}).with_structured_output(Foo).invoke(["hi"])
    assert out.a == 9 and seen == [(["hi"], Foo)]


def test_exception_response_is_raised():
    llm = ScriptedLLM({Foo: RuntimeError("boom")})
    with pytest.raises(RuntimeError, match="boom"):
        llm.with_structured_output(Foo).invoke("x")


def test_aimessage_response_is_returned_as_is():
    msg = AIMessage(content="erro")
    assert ScriptedLLM({Foo: msg}).with_structured_output(Foo).invoke("x") is msg


def test_text_script_for_plain_invoke():
    llm = ScriptedLLM(text=["um", "dois"])
    assert [llm.invoke("m").content, llm.invoke("m").content] == ["um", "dois"]
    with pytest.raises(AssertionError):
        llm.invoke("m")


def test_failing_returns_aimessage_for_structured_and_plain():
    llm = ScriptedLLM.failing("falhou")
    assert llm.with_structured_output(Foo).invoke("x").content == "falhou"
    assert llm.invoke("x").content == "falhou"
    assert llm.is_fallback is False


def test_failing_matches_fallback_llm_in_product_guard(monkeypatch):
    sheets = []
    scripted = ScriptedLLM.failing()
    for llm in (scripted, FallbackLLM("x")):
        monkeypatch.setattr(character_creator, "get_llm", lambda *a, _l=llm, **k: _l)
        sheets.append(
            character_creator.create_player_character(
                {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano", "region": "Nova Arcádia"}
            )
        )
    assert sheets[0] == sheets[1]
    assert isinstance(scripted.with_structured_output(Foo).invoke("m"), AIMessage)
    assert len(scripted.calls) == 2  # 1 da criacao + 1 desta asserção


def test_failing_streaming_mimics_exhausted_routed_llm():
    llm = ScriptedLLM.failing("", streaming=True)
    emitted: list[str] = []
    token = narrative_sink.bind(emitted.append)
    try:
        out = narrative_sink.narrate_structured(llm, Foo, ["m"])
        txt = narrative_sink.narrate_text(llm, ["m"])
    finally:
        narrative_sink.unbind(token)
    assert isinstance(out, AIMessage) and isinstance(txt, AIMessage)
    assert not any(emitted)  # nada vai ao vivo, como no RoutedLLM esgotado
    assert [c[0] for c in llm.calls] == ["Foo", None]


def test_invoke_rejects_kwargs_like_product():
    llm = ScriptedLLM(text="x")
    with pytest.raises(TypeError):
        llm.invoke("m", config={})  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ScriptedLLM({Foo: {}}).with_structured_output(Foo).invoke("m", config={})  # type: ignore[call-arg]


def test_no_stream_structured_unless_streaming_and_no_is_mock():
    plain = ScriptedLLM()
    assert not hasattr(plain, "stream_structured") and not hasattr(plain, "stream_text")
    assert getattr(plain, "is_mock", False) is False
    assert hasattr(ScriptedLLM(streaming=True), "stream_structured")


def test_stream_concatenates_to_text():
    text = "uma narração com mais de oito caracteres"
    chunks = list(ScriptedLLM(text=text).stream("m"))
    assert len(chunks) > 1 and "".join(c.content for c in chunks) == text


def test_calls_are_recorded():
    llm = ScriptedLLM({Foo: {}}, text="t")
    llm.with_structured_output(Foo).invoke("a")
    llm.invoke("b")
    assert llm.calls == [("Foo", "a"), (None, "b")]


def test_patch_get_llm_records_tier(monkeypatch):
    llm = ScriptedLLM()
    patch_get_llm(monkeypatch, llm, character_creator)
    assert character_creator.get_llm(temperature=0.3, tier=ModelTier.FAST) is llm
    assert llm.get_llm_calls == [(0.3, ModelTier.FAST)]


def test_include_raw_is_refused():
    with pytest.raises(NotImplementedError):
        ScriptedLLM().with_structured_output(Foo, include_raw=True)
