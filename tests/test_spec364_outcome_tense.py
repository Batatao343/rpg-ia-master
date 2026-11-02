"""SPEC-364 R10-R13: o resumo final conta a queda antiga no passado (e V6 rejeita o presente)."""

from __future__ import annotations

import pytest

from services import conflict_summary as cs
from services import round_log
from tests.fixtures import spec364_smoke as fx


def _facts(last_out=fx.LAST_OUT):
    enemies = [{"id": "enemy_mino", "name": "Minotauro Esqueleto"}, {"id": "enemy_goblin", "name": "Goblin"}]
    return round_log.outcome_facts("victory", fx.SUMMARY, fx.PLAYER, enemies, last_out, names=fx.NAMES)


def test_facts_split_final_and_earlier():
    facts = _facts()
    assert "Na rodada final, Minotauro Esqueleto morreu." in facts
    assert "Antes do fim, Goblin já tinha morrido." in facts


def test_facts_old_save_unchanged():
    facts = _facts(last_out={})
    assert "Goblin, Minotauro Esqueleto morreu." in facts
    assert not any(f.startswith("Antes do fim") for f in facts)


def test_prompt_mentions_past(monkeypatch):
    import agents.combat as combat

    seen = []

    def fake_fast(system, *a, **k):
        seen.append(system.content)
        return ""

    monkeypatch.setattr(combat, "_fast_text", fake_fast)
    enemies = [{"id": "enemy_mino", "name": "Minotauro Esqueleto"}]
    combat._narrate_outcome(
        "victory", fx.SUMMARY, fx.PLAYER, enemies, fx.LAST_OUT, "ataco", "", manifest=None, names=fx.NAMES
    )
    assert seen and "conte no passado" in seen[0]


def _auth():
    return round_log.authorship(fx.LAST_OUT, {"player": "Você", **fx.NAMES}, fx.PLAYER, fx.SUMMARY)


def test_authorship_earlier_fallen():
    assert _auth()["earlier_fallen"] == ["Goblin"]


def test_v6_rejects_staging_text():
    assert "V6" in cs.validate_attribution(fx.REAL_BAD, _auth())


def test_v6_accepts_correct_text():
    assert "V6" not in cs.validate_attribution(fx.GOOD, _auth())


BENIGN = [
    "O Minotauro Esqueleto desaba em pedaços.",
    "Você respira fundo enquanto o Minotauro Esqueleto tomba.",
    "O Goblin já tinha caído antes; o silêncio pesa.",
    "Ao seu lado, o corpo do Goblin jaz imóvel.",
    "Havia um Goblin caído, e agora o Minotauro cai de joelhos e depois desaba.",
    "O Goblin, que antes tombara, não se move.",
    "Um corvo cai do telhado e foge.",
    "A poeira cai sobre o Goblin morto.",
    "O Minotauro Esqueleto sucumbe ao seu golpe final.",
    "Você sente o chão tremer quando o gigante tomba.",
    "O Goblin estava caído desde o começo.",
    "Seu golpe cai certeiro e o Minotauro Esqueleto morre.",
]


@pytest.mark.parametrize("text", BENIGN)
def test_v6_benign_corpus(text):
    assert "V6" not in cs.validate_attribution(text, _auth())


def test_v6_no_earlier_no_violation():
    auth = round_log.authorship(fx.LAST_OUT, {"player": "Você", **fx.NAMES}, fx.PLAYER)
    assert auth.get("earlier_fallen", []) == []
    assert "V6" not in cs.validate_attribution(fx.REAL_BAD, auth)
