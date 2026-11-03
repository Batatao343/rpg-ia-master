"""SPEC-379 R3: um fake de LLM roteirizado para a suite.

Nao substitui o `MockLLM` do produto (`mock_llm.py`), que gera conteudo plausivel
para jogar offline. O `ScriptedLLM` devolve SO o que o teste roteirizou e falha
alto (`AssertionError`) quando falta roteiro. Contrato de `invoke` identico ao do
`FallbackLLM`/`RoutedLLM`: um unico argumento posicional, nenhum kwarg.

Por default NAO expoe `stream_structured`/`stream_text` nem `is_mock`: os consumidores
(`services/narrative_sink.py`, `services/prologue.py`) seguem o caminho de `invoke`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import BaseModel

_PLAIN = None  # chave de roteiro para `invoke` sem schema


def _schema_name(schema: Any) -> str:
    return getattr(schema, "__name__", str(schema))


class _Bound:
    """Resultado de `with_structured_output(schema)`."""

    def __init__(self, owner: ScriptedLLM, schema: Any) -> None:
        self._owner = owner
        self._schema = schema

    def invoke(self, input, /):  # noqa: A002 - mesmo nome do produto
        return self._owner._respond(_schema_name(self._schema), self._schema, input)


class ScriptedLLM:
    is_fallback: bool

    def __init__(
        self,
        responses: Mapping[type | str, object] | None = None,
        *,
        text: str | Sequence[str] = "",
        repeat_last: bool = False,
        streaming: bool = False,
        is_fallback: bool = False,
    ) -> None:
        self.is_fallback = is_fallback
        self.calls: list[tuple[str | None, object]] = []
        self.get_llm_calls: list[tuple[float | None, object | None]] = []
        self._repeat_last = repeat_last
        self._fail_text: str | None = None
        self._scripts: dict[str, list[object]] = {}
        for key, value in (responses or {}).items():
            self._scripts[_schema_name(key)] = list(value) if isinstance(value, list) else [value]
        if text != "" and not isinstance(text, str):
            self._scripts["__text__"] = list(text)
        elif text != "":
            self._scripts["__text__"] = [text]
        if streaming:
            self.stream_structured = self._stream_structured
            self.stream_text = self._stream_text

    @classmethod
    def failing(
        cls, text: str = "", *, is_fallback: bool = False, streaming: bool = False
    ) -> ScriptedLLM:
        """Todo invoke (estruturado ou nao) devolve `AIMessage(text)`, como o `FallbackLLM`."""
        llm = cls(is_fallback=is_fallback, streaming=streaming)
        llm._fail_text = text
        return llm

    # --- API que os nos usam -------------------------------------------------
    def with_structured_output(self, schema, *args, **kwargs) -> _Bound:
        if kwargs.get("include_raw"):
            raise NotImplementedError("ScriptedLLM nao suporta include_raw=True")
        return _Bound(self, schema)

    def with_retry(self, *args, **kwargs) -> ScriptedLLM:
        return self

    def bind_tools(self, *args, **kwargs) -> ScriptedLLM:
        return self

    def invoke(self, input, /) -> AIMessage:  # noqa: A002
        return self._respond(_PLAIN, None, input)

    def stream(self, input, /) -> Iterator[AIMessageChunk]:  # noqa: A002
        text = str(self.invoke(input).content)
        for pos in range(0, len(text), 8):
            yield AIMessageChunk(content=text[pos : pos + 8])

    # --- streaming opcional (so com streaming=True) ----------------------------
    def _stream_structured(self, messages, schema, *, on_delta=None, on_reset=None, key=None):
        result = self._respond(_schema_name(schema), schema, messages)
        if (
            on_delta is not None
            and isinstance(result, BaseModel)
            and not isinstance(result, AIMessage)
        ):
            on_delta(result.model_dump_json())
        return result

    def _stream_text(self, messages, *, on_delta=None, on_reset=None):
        result = self._respond(_PLAIN, None, messages)
        if on_delta is not None and self._fail_text is None:
            on_delta(str(result.content))
        return result

    # --- nucleo ------------------------------------------------------------
    def _respond(self, name: str | None, schema: Any, messages: object):
        self.calls.append((name, messages))
        if self._fail_text is not None:
            return AIMessage(content=self._fail_text)
        key = "__text__" if name is _PLAIN else name
        queue = self._scripts.get(key)
        if not queue:
            raise AssertionError(f"ScriptedLLM: sem roteiro para {name or 'texto livre'!r}")
        if len(queue) > 1:
            item = queue.pop(0)
        elif self._repeat_last:
            item = queue[0]
        else:
            item = queue.pop(0)
            queue.append(_Exhausted(name))
        return self._materialize(item, name, schema, messages)

    @staticmethod
    def _materialize(item: object, name: str | None, schema: Any, messages: object):
        if isinstance(item, _Exhausted):
            raise AssertionError(f"ScriptedLLM: roteiro esgotado para {name or 'texto livre'!r}")
        if isinstance(item, BaseException) or (
            isinstance(item, type) and issubclass(item, BaseException)
        ):
            raise item  # type: ignore[misc]
        if callable(item) and not isinstance(item, (BaseModel, AIMessage, type)):
            item = item(messages, schema)  # type: ignore[operator]
            if isinstance(item, BaseException):
                raise item
        if name is _PLAIN:
            return item if isinstance(item, AIMessage) else AIMessage(content=str(item))
        if isinstance(item, dict) and hasattr(schema, "model_validate"):
            return schema.model_validate(item)
        return item


class _Exhausted:
    def __init__(self, name: str | None) -> None:
        self.name = name


def patch_get_llm(monkeypatch, llm: ScriptedLLM, *modules: Any) -> ScriptedLLM:
    """Troca `get_llm` em cada modulo e registra `(temperature, tier)` em `llm.get_llm_calls`."""

    def _get_llm(temperature: float | None = None, tier: object | None = None, *a, **k):
        llm.get_llm_calls.append((temperature, tier))
        return llm

    for module in modules:
        monkeypatch.setattr(module, "get_llm", _get_llm)
    return llm


def story_update_llm(**fields: Any) -> ScriptedLLM:
    """ScriptedLLM do storyteller: responde com qualquer variante de `StoryUpdate` pedida,
    preenchida com `fields` (a variante usada depende de flags do turno)."""
    import agents.storyteller as stt

    def build(_messages, schema):
        return schema(**fields)

    variants = (stt.StoryUpdate, stt.StoryUpdateWithRumors, stt.StoryUpdateWithRumorClaims)
    return ScriptedLLM({v: build for v in variants}, repeat_last=True)


__all__ = ["ScriptedLLM", "patch_get_llm", "story_update_llm"]
