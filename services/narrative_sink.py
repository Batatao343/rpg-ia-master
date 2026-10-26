"""SPEC-319: canal de narracao token-a-token entre o no narrador e o SSE.

O ``sink`` e um contextvar ligado pela API so no stream (POST, CLI e playtest nao ligam:
sem sink o narrador faz ``invoke`` como antes). O no narrador usa ``narrate_structured`` /
``narrate_text``: o LLM streama, o ``StreamGuard`` limpa o que da para limpar em fluxo
(recibo ``[RESULTADO]``, veu de nomes ocultos da SPEC-293) e so o texto limpo vai ao sink.
O texto FINAL (prose guard, evidencia, regra de ouro) continua mandando: a API compara e,
se divergir, manda ``replace`` (SPEC-316 R2). O parcial nunca entra em messages/save.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any, Literal

TokenStreamMode = Literal["off", "shadow", "on"]

Sink = Callable[[str, str], None]  # (kind: "delta"|"reset", text)


def token_stream_mode() -> TokenStreamMode:
    """`RPG_TOKEN_STREAM=off|shadow|on` (default `shadow`; valor invalido = `off`)."""
    raw = os.getenv("RPG_TOKEN_STREAM", "shadow").strip().lower()
    if raw in ("off", "shadow", "on"):
        return raw  # type: ignore[return-value]
    return "off"


class _Binding:
    __slots__ = ("sink", "emitted", "state_getter")

    def __init__(self, sink: Sink, state_getter: Callable[[], Any] | None = None) -> None:
        self.sink = sink
        self.emitted = False
        self.state_getter = state_getter


_SINK: ContextVar[_Binding | None] = ContextVar("rpg_narrative_sink", default=None)


def bind(sink: Sink, state_getter: Callable[[], Any] | None = None) -> Token:
    """Liga o sink ao contexto atual. `state_getter` devolve o estado vivo do turno (para o
    veu de nomes ocultos nos nos que nao recebem `state`, ex.: narracao de combate/loot)."""
    return _SINK.set(_Binding(sink, state_getter))


def unbind(token: Token) -> None:
    try:
        _SINK.reset(token)
    except ValueError:  # token de outro contexto: apenas desliga
        _SINK.set(None)


def active() -> bool:
    return _SINK.get() is not None


def emit(text: str) -> None:
    binding = _SINK.get()
    if binding is None or not text:
        return
    binding.emitted = True
    try:
        binding.sink("delta", text)
    except Exception:  # silent-ok: o canal de exibicao nunca derruba o turno
        pass


def reset() -> None:
    """Pede ao cliente que descarte o parcial (so se algo foi emitido desde o ultimo reset)."""
    binding = _SINK.get()
    if binding is None or not binding.emitted:
        return
    binding.emitted = False
    try:
        binding.sink("reset", "")
    except Exception:  # silent-ok: o canal de exibicao nunca derruba o turno
        pass


def replace_reason(shown: str, final: str) -> str:
    """Por que o stream nao e prefixo do final: `start` (divergiu na abertura: abertura repetida,
    rotulo, aspas), `tail` (divergiu depois: saldo de ouro, guard de conteudo), `shorter`
    (o final e menor que o ja mostrado) ou `none` (final estende o mostrado)."""
    if final.startswith(shown):
        return "none"
    common = len(os.path.commonprefix([shown, final]))
    if common >= len(final):
        return "shorter"
    return "start" if common < min(len(shown), 40) else "tail"


_RECEIPT = re.compile(r"[ \t]*\[RESULTADO\][^\r\n]*")


class StreamGuard:
    """Limpeza em fluxo: so devolve texto ja estavel (sem receber de volta o que mudaria).

    - remove blocos ``[RESULTADO] ...`` (recibo e do Python, nunca da LLM);
    - aplica o veu da SPEC-293 (``conceal_text``) segurando uma janela do tamanho do maior
      nome oculto, para que um nome partido entre deltas nao vaze;
    - segura a palavra parcial final e qualquer ``[`` ainda aberto na linha.
    Se o texto limpo deixar de ser extensao do que ja saiu, para de emitir (``broken``); o
    ``replace`` final corrige.
    """

    HOLD_CHARS = 120  # segura o inicio ate o preambulo meta nao poder mais casar

    def __init__(
        self,
        mapping: dict[str, str] | None = None,
        prefix: str = "",
        normalize: str = "player_facing",
        finalize: Callable[[str], str] | None = None,
        hold_extra: int = 0,
        min_words: int = 0,
    ) -> None:
        # F-2: cada no normaliza como o seu texto final (`meta` = so `sanitize_meta_preamble`).
        self.normalize = normalize
        self.mapping = dict(mapping or {})
        self.hold = (max(len(k) for k in self.mapping) + 8) if self.mapping else 0
        # SPEC-319 (follow-up D1): `finalize` aplica em fluxo as mesmas transformacoes do texto
        # final (abertura repetida, saldo de ouro, aspas externas, rotulo do NPC) para o stream
        # ser prefixo do final. `hold_extra` segura o fim para padroes que so fecham depois;
        # `min_words` segura o inicio ate a abertura (6 palavras) estar completa.
        self.finalize = finalize
        self.hold = max(self.hold, hold_extra)
        self.min_words = min_words
        self.prefix = prefix
        self.reset()

    def reset(self) -> None:
        self.raw = ""
        self.sent = ""
        self.broken = False

    def _cleaned(self) -> str:
        from services import prose_guard

        sanitize = (
            prose_guard.sanitize_meta_preamble
            if self.normalize == "meta"
            else prose_guard.sanitize_player_facing
        )

        # Mesmas normalizacoes baratas do texto final (preambulo meta, marcadores do motor,
        # espacos/pontuacao): evita `replace` falso so por formatacao (revisao P2-3).
        text = sanitize(_RECEIPT.sub("", self.raw))
        if not text:
            return ""
        text = self.finalize(text) if self.finalize else self.prefix + text
        if self.mapping:
            from services.faction_display import conceal_text

            text = conceal_text(text, self.mapping)
        return text

    def _advance(self, *, final: bool) -> str:
        if self.broken:
            return ""
        cleaned = self._cleaned()
        if final:
            safe = len(cleaned.rstrip())
        else:
            if len(self.raw) < self.HOLD_CHARS and "\n" not in self.raw:
                return ""  # segura o inicio: o preambulo meta ainda pode casar
            if self.min_words and len(self.raw.split()) < self.min_words:
                return ""  # a abertura repetida so e decidida com as 6 primeiras palavras
            limit = len(cleaned) - self.hold
            if limit <= len(self.sent):
                return ""
            # corta ANTES do espaco: o espaco antes de pontuacao some no texto final
            safe = max((cleaned.rfind(c, 0, limit) for c in (" ", "\n", "\t")), default=-1)
            bracket = cleaned.rfind("[")
            if bracket != -1 and "\n" not in cleaned[bracket:]:
                safe = min(safe, bracket)
        if safe <= len(self.sent):
            return ""
        if not cleaned.startswith(self.sent):
            self.broken = True
            return ""
        piece = cleaned[len(self.sent) : safe]
        self.sent += piece
        return piece

    def feed(self, delta: str) -> str:
        self.raw += delta or ""
        return self._advance(final=False)

    def finish(self) -> str:
        return self._advance(final=True)


def _conceal_map(state: Any) -> dict[str, str]:
    binding = _SINK.get()
    if not state and binding is not None and binding.state_getter is not None:
        try:
            state = binding.state_getter()
        except Exception:  # silent-ok: sem estado, so o filtro de recibo vale
            state = None
    if not state:
        return {}
    try:
        from services.faction_display import concealed_name_map

        return concealed_name_map(state)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("sse", "stream_conceal_map_failed", exc)
        return {}


def narrate_structured(
    llm: Any,
    schema: type,
    messages: list,
    *,
    state: Any = None,
    key: str | None = None,
    prefix: str = "",
    stream: bool = True,
    normalize: str = "player_facing",
    finalize: Callable[[str], str] | None = None,
    hold_extra: int = 0,
    min_words: int = 0,
):
    """`with_structured_output(schema).invoke(messages)`, com tokens ao vivo quando ha sink.

    Sem sink, ou LLM sem `stream_structured` (FallbackLLM), e exatamente o invoke de antes.
    O retorno pode ser `AIMessage` (guard do chamador continua obrigatorio)."""
    streamer = getattr(llm, "stream_structured", None)
    if streamer is None or not active() or not stream:
        return llm.with_structured_output(schema).invoke(messages)
    guard = StreamGuard(
        _conceal_map(state),
        prefix=prefix,
        normalize=normalize,
        finalize=finalize,
        hold_extra=hold_extra,
        min_words=min_words,
    )
    reset()  # outro no narrador no mesmo turno: recomeca limpo

    def on_delta(text: str) -> None:
        piece = guard.feed(text)
        if piece:
            emit(piece)

    def on_reset() -> None:
        guard.reset()
        reset()

    result = streamer(messages, schema, on_delta=on_delta, on_reset=on_reset, key=key)
    if isinstance(result, schema):
        tail = guard.finish()
        if tail:
            emit(tail)
    else:
        on_reset()
    return result


def narrate_text(llm: Any, messages: list, *, state: Any = None, stream: bool = True):
    """`llm.invoke(messages)` com tokens ao vivo quando ha sink (narracao plain de combate/loot).

    `stream=False`: o chamador sabe que o texto final sera substituido por um guard de
    conteudo (ex.: loot canonico), entao nada vai ao vivo."""
    streamer = getattr(llm, "stream_text", None)
    if streamer is None or not active() or not stream:
        return llm.invoke(messages)
    guard = StreamGuard(_conceal_map(state), normalize="meta")
    reset()

    def on_delta(text: str) -> None:
        piece = guard.feed(text)
        if piece:
            emit(piece)

    def on_reset() -> None:
        guard.reset()
        reset()

    result = streamer(messages, on_delta=on_delta, on_reset=on_reset)
    if str(getattr(result, "content", "") or "").strip():
        tail = guard.finish()
        if tail:
            emit(tail)
    else:
        on_reset()
    return result
