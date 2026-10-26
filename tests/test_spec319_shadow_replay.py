"""SPEC-319 follow-up D1: replay de narracoes canned no caminho do stream e no final.

Criterio do dono para ligar `RPG_TOKEN_STREAM=on`: `would_replace` < 5 % no shadow. Aqui o
nó REAL (storyteller / npc) roda com um LLM que streama fatias de um texto canned; o que o
sink emitiu tem de ser prefixo da mensagem final (a mesma regra de `api.py`).
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.npc as npc
import agents.storyteller as stt
from services import narrative_sink as sink
from services.turn_outcome import render_player_message

MAX_REPLACE_RATE = 0.05


class _StreamLLM:
    """Fatia o campo narrativo em pedacos pequenos e devolve o schema pronto."""

    is_fallback = False

    def __init__(self, response, field: str, size: int = 7):
        self._response = response
        self._field = field
        self._size = size

    def with_structured_output(self, *_a, **_k):
        outer = self

        class _S:
            def invoke(self, _msgs):
                return outer._response

        return _S()

    def stream_structured(self, _messages, _schema, *, on_delta=None, on_reset=None, key=None):
        text = str(getattr(self._response, self._field))
        for pos in range(0, len(text), self._size):
            if on_delta:
                on_delta(text[pos : pos + self._size])
        return self._response


def _story_state(prior: str | None, gold: int) -> dict:
    messages: list = []
    if prior:
        messages.append(AIMessage(content=prior))
    messages.append(HumanMessage(content="Observo ao redor"))
    return {
        "game_id": "replay319",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": messages,
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "campaign_plan": {},
        "player": {
            "name": "T",
            "class_name": "Guerreiro",
            "level": 1,
            "vitalidade": 10,
            "max_vitalidade": 10,
            "gold": gold,
        },
        "world": {
            "current_location": "Skallgard",
            "current_location_id": "skallgard",
            "turn_count": 5,
            "time_of_day": "Manhã",
            "danger_level": 2,
            "world_clock": {"day": 2, "period": "Manhã"},
            "quest_plan": [],
        },
    }


_BODY = (
    " O vento corta as vielas de Skallgard e o cheiro de fumaça pesa sobre os telhados. "
    "Dois guardas observam você de longe, sem pressa, enquanto um sino distante marca a hora.\n\n"
    "O que você faz?"
)

# (texto do LLM, narracao anterior (abertura repetida), ouro do jogador)
_STORY_CASES: list[tuple[str, str | None, int]] = []
for _i, _op in enumerate(
    [
        "A neblina desce sobre o porto",
        "Você ergue os olhos para a torre",
        "Passos ecoam no corredor vazio",
        "A taverna cheira a cerveja velha",
        "Um corvo grasna no alto do muro",
        "O mercador ajusta o capuz",
        "As tochas tremem com a corrente de ar",
        "Ninguém responde ao seu chamado",
        "A estrada segue entre campos queimados",
        "Uma sombra cruza o beco à sua frente",
    ]
):
    _STORY_CASES.append((_op + "." + _BODY, None, 10))  # simples
    _STORY_CASES.append(
        (_op + "." + _BODY, _op + ". Antes disso, tudo estava calmo.", 10)
    )  # repete
for _gold in (3, 40, 250):  # alegacao de saldo errada (o final corrige)
    _STORY_CASES.append(
        (
            f"A bolsa pesa na cintura. Você possui 999 moedas de ouro quando abre o cinto.{_BODY}",
            None,
            _gold,
        )
    )
    _STORY_CASES.append(
        (f"Você olha a bolsa: 77 moedas de ouro na bolsa, nada mais.{_BODY}", None, _gold)
    )
_STORY_CASES += [
    ("Aqui está a narração:\n\nA chuva fina molha o calçamento." + _BODY, None, 5),
    ("Claro. Aqui está a narrativa da cena:\n\nO fogo estala na lareira." + _BODY, None, 5),
    ("Como solicitado:\nUm cão late ao longe, depois silêncio." + _BODY, None, 5),
    ("A porta range.  Algo  se move  na sombra , e você hesita ." + _BODY, None, 5),
    ("O corredor é longo.\n[RESULTADO] +10 XP\nVocê avança devagar." + _BODY, None, 5),
    ("[RESULTADO] ouro +5\nA noite chega devagar sobre as muralhas." + _BODY, None, 5),
    ("Curto.", None, 5),
    (
        "Ao amanhecer, os sinos de Skallgard tocam três vezes.\n\nEscolhas:\n1. Entrar\n2. Esperar",
        None,
        5,
    ),
]


def _run_story(text: str, prior: str | None, gold: int, monkeypatch) -> tuple[str, str]:
    llm = _StreamLLM(stt.StoryUpdate(narrative=text), "narrative")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    deltas: list[str] = []

    def _sink(kind: str, piece: str) -> None:
        if kind == "delta":
            deltas.append(piece)
        else:
            deltas.clear()

    token = sink.bind(_sink)
    try:
        out = stt.storyteller_node(_story_state(prior, gold))
    finally:
        sink.unbind(token)
    # o recibo `[RESULTADO]` e removido na entrega (turn_outcome), nao no no
    return "".join(deltas), render_player_message(out["messages"][-1].content, {})


def test_story_stream_is_prefix_of_final(monkeypatch):
    assert len(_STORY_CASES) >= 30
    misses = []
    for text, prior, gold in _STORY_CASES:
        shown, final = _run_story(text, prior, gold, monkeypatch)
        assert shown, f"nada foi ao vivo: {text[:40]!r}"
        if not final.startswith(shown):
            misses.append((sink.replace_reason(shown, final), text[:50], shown[:60], final[:60]))
    rate = len(misses) / len(_STORY_CASES)
    assert rate < MAX_REPLACE_RATE, (rate, misses)


_LONG_A = (
    "O vento corta as vielas de Skallgard e o cheiro de fumaça pesa sobre os telhados. "
    "Dois guardas observam de longe, sem pressa, enquanto um sino distante marca a hora. "
    "As janelas altas refletem um céu cor de chumbo e as vozes do mercado chegam abafadas. "
    "Uma criança corre entre as barracas, perseguida por um cão magro e barulhento. "
    "O padeiro empilha pães escuros sobre o balcão e conta as moedas com cuidado. "
)
_LONG_B = "Ao longe, os sinos tocam de novo.\n\nO que você faz?"


def _final_with_guards(state: dict, out: dict) -> str:
    """Texto que o jogador recebe: guard de evidencia + render (mesmo caminho do SSE)."""
    from services.turn_delivery import early_narrative

    return early_narrative(state, out, "storyteller") or ""


def _run_story_update(update, monkeypatch) -> tuple[str, str]:
    llm = _StreamLLM(update, "narrative")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)
    deltas: list[str] = []
    token = sink.bind(
        lambda kind, piece: deltas.append(piece) if kind == "delta" else deltas.clear()
    )
    state = _story_state(None, 10)
    try:
        out = stt.storyteller_node(state)
    finally:
        sink.unbind(token)
    return "".join(deltas), _final_with_guards(state, out)


# classes de divergencia do `tail` no staging (stream MAIOR que o final, depois de 400+ chars)
_TAIL_CASES = {
    "unknown_item": stt.StoryUpdate(
        narrative=(
            _LONG_A + "Você pega o Amuleto Inexistente de Zorn da prateleira empoeirada. "
            "Nada mais chama a atenção." + _LONG_B
        ),
        items_gained=["Amuleto Inexistente de Zorn"],
    ),
    "false_death_claim": stt.StoryUpdate(
        narrative=_LONG_A + "Você morreu com o golpe do guarda. A cena escurece." + _LONG_B
    ),
    "acquire_without_item": stt.StoryUpdate(
        narrative=_LONG_A + "Você recebe a Runa Que Nao Existe do mercador. O sino toca." + _LONG_B,
        items_gained=["Runa Que Nao Existe"],
    ),
}


@pytest.mark.parametrize("case", sorted(_TAIL_CASES))
def test_story_tail_divergence_classes_stream_is_prefix(case, monkeypatch):
    shown, final = _run_story_update(_TAIL_CASES[case], monkeypatch)
    assert shown, "o inicio seguro ainda vai ao vivo"
    assert len(shown) > 200, "so a frase de risco e o resto ficam para o final"
    assert final.startswith(shown), (sink.replace_reason(shown, final), shown[-80:], final[-80:])


def test_story_without_risky_sentence_streams_everything(monkeypatch):
    update = stt.StoryUpdate(narrative=_LONG_A + _LONG_B)
    shown, final = _run_story_update(update, monkeypatch)
    assert shown.strip() == final.strip()


def test_stream_guard_risk_freezes_before_risky_sentence():
    g = sink.StreamGuard(risk=lambda s: "perigo" in s)
    text = (
        "Primeira frase calma e longa o bastante para passar da janela de espera inicial. "
        "Segunda frase também tranquila e descritiva do ambiente ao redor do herói. "
        "Aqui há perigo declarado. Quarta frase depois do perigo continua normalmente."
    )
    out = "".join(g.feed(text[i : i + 5]) for i in range(0, len(text), 5)) + g.finish()
    assert out.endswith("do herói.")
    assert "perigo" not in out


def test_stream_guard_risk_none_is_unchanged():
    g = sink.StreamGuard()
    text = "Uma frase simples e completa que cresce sem nenhum guard de risco ativo aqui. " * 3
    out = "".join(g.feed(text[i : i + 9]) for i in range(0, len(text), 9)) + g.finish()
    assert out == text.strip()


def _npc_state(prior: str | None) -> dict:
    messages: list = []
    if prior:
        messages.append(AIMessage(content=prior))
    messages.append(HumanMessage(content="quem manda aqui?"))
    st = _story_state(None, 10)
    st.update(
        active_npc_name="Guarda",
        npcs={
            "Guarda": {
                "name": "Guarda",
                "role": "guarda",
                "persona": "rude",
                "location": "skallgard",
                "in_scene": True,
                "memory": [],
                "relationship": 5,
            }
        },
        messages=messages,
    )
    return st


_NPC_CASES: list[tuple[str, str | None]] = [
    ("Quem pergunta é quem não devia estar aqui a esta hora da noite.", None),
    ('"Quem pergunta é quem não devia estar aqui a esta hora."', None),
    ("“Aqui manda o capitão, e ele não gosta de forasteiros curiosos.”", None),
    (
        "Aqui manda o capitão, e ele não gosta de forasteiros curiosos.",
        "Guarda: Aqui manda o capitão, e tudo mais",
    ),
    (
        '"Passe adiante antes que eu mude de ideia, forasteiro teimoso."',
        '**Guarda:** "Passe adiante antes que eu mude de ideia, forasteiro."',
    ),
    ("Aqui está a resposta:\n\nSeguimos as ordens do capitão e nada mais, entendeu?", None),
    ("Pouco. Fala menos.", None),
    ("Não tenho nada a dizer a você, viajante, e muito menos sobre o capitão.", None),
]


def _run_npc(text: str, prior: str | None, monkeypatch) -> tuple[str, str]:
    response = npc.NPCResponse(
        dialogue=text,
        action_description="cruza os braços",
        memory_update="",
        relationship_change=0,
        faction_reveals=[],
    )
    llm = _StreamLLM(response, "dialogue")
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: llm)
    deltas: list[str] = []
    token = sink.bind(
        lambda kind, piece: deltas.append(piece) if kind == "delta" else deltas.clear()
    )
    try:
        out = npc.npc_actor_node(_npc_state(prior))
    finally:
        sink.unbind(token)
    return "".join(deltas), out["messages"][-1].content


def test_npc_stream_is_prefix_of_final(monkeypatch):
    misses = []
    for text, prior in _NPC_CASES:
        shown, final = _run_npc(text, prior, monkeypatch)
        assert shown, f"nada foi ao vivo: {text[:40]!r}"
        if not final.startswith(shown):
            misses.append((sink.replace_reason(shown, final), text[:50], shown[:60], final[:60]))
    assert not misses, misses


@pytest.mark.parametrize(
    ("shown", "final", "reason"),
    [
        ("abc", "abcdef", "none"),
        ("abc", "xyz", "start"),
        ("A" * 60 + "BBB", "A" * 60 + "CCC", "tail"),
        ("abcdef", "abc", "shorter"),
    ],
)
def test_replace_reason(shown, final, reason):
    assert sink.replace_reason(shown, final) == reason
