"""SPEC-319 R1: extrator incremental do campo `narrative`."""

from __future__ import annotations

import json
import random

import pytest

from services.partial_narrative import NarrativeExtractor

BS = "\\"  # uma barra invertida


def _feed_all(raw: str, step: int = 1, key: str | None = None) -> str:
    ex = NarrativeExtractor(key)
    out = []
    for i in range(0, len(raw), step):
        out.append(ex.feed(raw[i : i + step]))
    return "".join(out)


def test_plain_string():
    ex = NarrativeExtractor()
    assert ex.feed('{"narrative": "Olá, viajante.", "x": 1}') == "Olá, viajante."
    assert ex.done and ex.found


def test_escapes_split_across_deltas():
    pieces = [
        '{"narra',
        'tive": "Ele disse ' + BS,
        '"não' + BS,
        '" e ' + BS + "u00",
        "e7 " + BS,
        BS + " fim" + BS + 'n"',
        ', "x": 1}',
    ]
    ex = NarrativeExtractor()
    out = [ex.feed(p) for p in pieces]
    assert "".join(out) == 'Ele disse "não" e ç ' + BS + " fim\n"
    assert out[1] == "Ele disse "  # a barra pendente nao emite
    assert "ç" not in out[3]  # `\u00` incompleto nao emite


def test_surrogate_pair():
    raw = json.dumps({"narrative": "Fogo 🔥 e 🐉!"}, ensure_ascii=True)
    assert BS + "ud83d" in raw.lower()
    for step in (1, 2, 5):
        assert _feed_all(raw, step) == "Fogo 🔥 e 🐉!"


def test_stops_at_closing_quote_and_ignores_rest():
    ex = NarrativeExtractor()
    assert ex.feed('{"narrative":"abc"') == "abc"
    assert ex.done
    assert ex.feed(', "other": "zzz"}') == ""


def test_missing_key_emits_nothing():
    ex = NarrativeExtractor()
    assert ex.feed('{"other": "x", "y": 2}') == ""
    assert ex.done and not ex.found
    assert NarrativeExtractor().feed("texto solto sem json") == ""


def test_key_not_first_emits_nothing():
    ex = NarrativeExtractor()
    assert ex.feed('{"introduced_npcs": [], "narrative": "tarde demais"}') == ""
    assert not ex.found


def test_non_string_value_emits_nothing():
    assert NarrativeExtractor().feed('{"narrative": null}') == ""
    assert NarrativeExtractor().feed('{"narrative": 3}') == ""


def test_custom_key():
    assert _feed_all('{"dialogue": "Fale baixo.", "a": "b"}', 3, key="dialogue") == "Fale baixo."


_BASE = [
    "A névoa cobre o vale; você ouve passos.",
    'O velho sussurra: "Cuidado com a ponte".',
    "Linha um.\nLinha dois.\n\nO que você faz?",
    "Ação: " + BS + " barra invertida e / barra.",
    "Çedilha, ão, õe, ü, ñ — travessão e “aspas” curvas.",
    "Tab\taqui e emoji 🗡️ no fim.",
    "",
]


def _fixtures() -> list[str]:
    rng = random.Random(319)
    out = list(_BASE)
    words = "sombra ferro cinza sino rachado Valoria Abismo corvo ponte névoa coração".split()
    while len(out) < 50:
        body = " ".join(rng.choice(words) for _ in range(rng.randint(3, 40)))
        out.append(body + rng.choice([".", "!", "?", '"', "\n"]))
    return out


@pytest.mark.parametrize("ensure_ascii", [True, False])
def test_one_char_deltas_equal_whole(ensure_ascii):
    fixtures = _fixtures()
    assert len(fixtures) == 50
    for text in fixtures:
        raw = json.dumps({"narrative": text, "tail": [1, 2]}, ensure_ascii=ensure_ascii)
        expected = json.loads(raw)["narrative"]
        assert _feed_all(raw, 1) == expected
        assert _feed_all(raw, 7) == expected
