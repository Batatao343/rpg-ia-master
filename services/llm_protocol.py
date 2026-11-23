"""SPEC-426: contrato minimo do cliente LLM, so para o checador de tipos.

`get_llm()` devolve MockLLM | FallbackLLM | RoutedLLM. O caminho estruturado devolve `object`
(nao `AIMessage | BaseModel`): `object` nao tem campo, entao `resultado.campo` sem
`isinstance(resultado, Schema)` reprova no gate (guard de FallbackLLM, AGENTS.md), e todo
implementador satisfaz o protocolo sem anotar `llm_setup.py`/`mock_llm.py`.
Sem `runtime_checkable` e sem import de runtime alem de `typing`.
"""

from __future__ import annotations

from typing import Any, Protocol


class StructuredInvoker(Protocol):
    def invoke(self, input: Any, /) -> object: ...


class LLMClient(Protocol):
    def invoke(self, input: Any, /) -> Any: ...

    def with_structured_output(
        self, schema: Any, /, *args: Any, **kwargs: Any
    ) -> StructuredInvoker: ...
