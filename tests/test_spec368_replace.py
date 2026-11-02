"""SPEC-368 R11 / SPEC-355 item 19 - `replace` do stream na narracao de combate (SPEC-319 P2-1).

Medicao OFFLINE (sem LLM real): o caminho do Baralho `on` nao streama tokens por rodada
(SPEC-346) e a narracao de desfecho usa `stream=False`; o caminho que ainda streama
(`_narrate`, Baralho `off`/shadow) reaproveita o MESMO texto no final, a menos que o guard de
espécie (`species_drift`) o troque pelo texto deterministico. O replay conta quantos casos
canned divergem do que foi ao vivo. O numero em producao (LLM real) e do `would_replace` do
shadow no staging.
"""

from __future__ import annotations

import agents.combat as combat
from services import narrative_sink as sink
from services import prose_guard

MANIFEST = {"participants": [{"species_label": "Goblin"}]}
_BODY = (
    " A lâmina corta o ar e o goblin recua um passo, os olhos fixos em você, enquanto o eco do"
    " golpe se perde entre as paredes úmidas do túnel.\n\nO que você faz?"
)
_OPENINGS = [
    "O aço canta",
    "Você avança",
    "A poeira sobe",
    "Um grito rasga a escuridão",
    "O chão treme",
    "Sangue pinga na pedra",
    "A tocha vacila",
    "Os passos ecoam",
    "O ar fica pesado",
    "Uma sombra salta",
]


class _StreamTextLLM:
    is_fallback = False

    def __init__(self, text: str, size: int = 9):
        self._text, self._size = text, size

    def invoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self._text)

    def stream_text(self, _messages, *, on_delta=None, on_reset=None):
        from langchain_core.messages import AIMessage

        for pos in range(0, len(self._text), self._size):
            if on_delta:
                on_delta(self._text[pos : pos + self._size])
        return AIMessage(content=self._text)


def _drift_head() -> str:
    heads = prose_guard._species_heads()
    return next(h for h in sorted(heads) if h not in ("goblin", "goblins"))


def _run(text: str, monkeypatch) -> tuple[str, str]:
    llm = _StreamTextLLM(text)
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: llm)
    deltas: list[str] = []
    token = sink.bind(
        lambda kind, piece: deltas.append(piece) if kind == "delta" else deltas.clear()
    )
    try:
        final = combat._narrate(
            {"name": "T", "vitalidade": 10, "max_vitalidade": 10},
            [{"name": "Goblin", "vitalidade": 5, "max_vitalidade": 8}],
            ["Você acerta o Goblin."],
            None,
            "Ataco o goblin.",
            False,
            "",
            manifest=MANIFEST,
        )
    finally:
        sink.unbind(token)
    return "".join(deltas), final


def test_combat_stream_replace_rate_offline(monkeypatch):
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    clean = [f"{op}, e o goblin ruge." + _BODY for op in _OPENINGS * 3]  # 30 narrações sem deriva
    body = _BODY.replace("o goblin", "a criatura")
    drift = [f"{op}; um {_drift_head()} surge no túnel." + body for op in _OPENINGS[:3]]
    replaced_clean = 0
    for text in clean:
        shown, final = _run(text, monkeypatch)
        assert shown, "nada foi ao vivo"
        if not final.startswith(shown):
            replaced_clean += 1
    assert replaced_clean == 0, f"{replaced_clean}/{len(clean)} narrações limpas reescritas"
    # deriva de espécie: o final vira texto determinístico (replace por desenho, medido no staging)
    replaced_drift = 0
    for text in drift:
        shown, final = _run(text, monkeypatch)
        if shown and not final.startswith(shown):
            replaced_drift += 1
    assert replaced_drift == len(drift)
    print(f"R11 replay: limpas {replaced_clean}/{len(clean)}; deriva {replaced_drift}/{len(drift)}")


def test_deck_on_outcome_narration_never_streams():
    import inspect

    src = inspect.getsource(combat._narrate_outcome)
    assert "stream=False" in src


def test_outcome_is_not_streamed_by_the_sink(monkeypatch):
    # com sink ligado, a narração de desfecho não emite nenhum delta (texto final = registro + resumo)
    monkeypatch.setenv("RPG_TOKEN_STREAM", "on")
    llm = _StreamTextLLM("Fim da luta. O goblin cai." + _BODY)
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: llm)
    deltas: list[str] = []
    token = sink.bind(lambda kind, piece: deltas.append(piece))
    try:
        sink.narrate_text(llm, [], stream=False)
    finally:
        sink.unbind(token)
    assert deltas == []
