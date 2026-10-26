"""SPEC-319 R1: extrator incremental do campo `narrative` de um JSON em streaming.

Recebe os deltas de texto dos argumentos da tool call (``{"narrative": "Ola...``) e
devolve, a cada ``feed``, so o trecho NOVO da string ja desescapado. Maquina de estados
O(n) por caractere, sem regex sobre texto acumulado.

Contrato conservador: se a chave pedida NAO for o primeiro campo do objeto (ou o valor
nao for uma string), o extrator morre em silencio (``found=False``) e nao emite nada — o
chamador cai no pseudo-streaming da SPEC-316. Nao valida o JSON inteiro: o Pydantic
completo valida no fim, como sempre.
"""

from __future__ import annotations

_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}
_WS = " \t\r\n"
_HEX = "0123456789abcdefABCDEF"

# estados
_START, _SEEK_KEY, _IN_KEY, _SEEK_COLON, _SEEK_QUOTE, _IN_STRING, _CLOSED, _DEAD = range(8)
_ESC, _UNI = 100, 101  # sub-estados dentro da string


class NarrativeExtractor:
    """``feed(delta) -> str`` com o trecho novo (desescapado) do campo ``key``."""

    KEY = "narrative"

    def __init__(self, key: str | None = None) -> None:
        self.key = key or self.KEY
        self._state = _START
        self._sub = 0  # 0 = normal, _ESC, _UNI
        self._key_buf: list[str] = []
        self._hex: list[str] = []
        self._high: int | None = None  # surrogate alto aguardando o baixo

    @property
    def found(self) -> bool:
        """A chave pedida abriu a string (mesmo que ainda nao tenha fechado)."""
        return self._state in (_IN_STRING, _CLOSED)

    @property
    def done(self) -> bool:
        """A string fechou (ou o extrator desistiu): nada mais sera emitido."""
        return self._state in (_CLOSED, _DEAD)

    def feed(self, delta: str) -> str:
        if not delta or self.done:
            return ""
        out: list[str] = []
        for ch in delta:
            st = self._state
            if st == _IN_STRING:
                self._string_char(ch, out)
            elif st == _START:
                if ch in _WS:
                    continue
                self._state = _SEEK_KEY if ch == "{" else _DEAD
            elif st == _SEEK_KEY:
                if ch in _WS:
                    continue
                if ch == '"':
                    self._state = _IN_KEY
                    self._key_buf = []
                else:
                    self._state = _DEAD
            elif st == _IN_KEY:
                if ch == '"':
                    self._state = _SEEK_COLON if "".join(self._key_buf) == self.key else _DEAD
                elif ch == "\\" or len(self._key_buf) > 64:
                    self._state = _DEAD  # chave de verdade nao tem escape
                else:
                    self._key_buf.append(ch)
            elif st == _SEEK_COLON:
                if ch in _WS:
                    continue
                self._state = _SEEK_QUOTE if ch == ":" else _DEAD
            elif st == _SEEK_QUOTE:
                if ch in _WS:
                    continue
                self._state = _IN_STRING if ch == '"' else _DEAD
            if self.done:
                break
        return "".join(out)

    # -- string -----------------------------------------------------------
    def _string_char(self, ch: str, out: list[str]) -> None:
        if self._sub == _UNI:
            if ch not in _HEX:
                self._flush_high(out)
                self._state = _DEAD
                return
            self._hex.append(ch)
            if len(self._hex) == 4:
                self._sub = 0
                self._emit_code(int("".join(self._hex), 16), out)
                self._hex = []
            return
        if self._sub == _ESC:
            self._sub = 0
            if ch == "u":
                self._sub = _UNI
                self._hex = []
                return
            mapped = _SIMPLE_ESCAPES.get(ch)
            if mapped is None:
                self._flush_high(out)
                self._state = _DEAD
                return
            self._flush_high(out)
            out.append(mapped)
            return
        if ch == "\\":
            self._sub = _ESC
            return
        if ch == '"':
            self._flush_high(out)
            self._state = _CLOSED
            return
        self._flush_high(out)
        out.append(ch)

    def _flush_high(self, out: list[str]) -> None:
        if self._high is not None:
            out.append("�")  # surrogate alto orfao
            self._high = None

    def _emit_code(self, code: int, out: list[str]) -> None:
        if 0xD800 <= code <= 0xDBFF:
            self._flush_high(out)
            self._high = code
            return
        if 0xDC00 <= code <= 0xDFFF:
            if self._high is not None:
                out.append(chr(0x10000 + ((self._high - 0xD800) << 10) + (code - 0xDC00)))
                self._high = None
            else:
                out.append("�")
            return
        self._flush_high(out)
        out.append(chr(code))
