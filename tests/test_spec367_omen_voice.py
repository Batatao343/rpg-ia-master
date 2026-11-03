"""SPEC-367 R7-R9: presságio na voz do jogador ("você"), catálogo legível com nome e com "você"."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import api
from services import enemy_intent as ei
from tests.test_enemy_intent_node import _rounds

CATALOG = Path(__file__).resolve().parents[1] / "data" / "combat" / "pressagio_sinais.json"
HERO = "Smoke5A"


def _actors():
    return {
        "g1": {"id": "g1", "name": "Goblin", "family": "fera"},
        "h": {"id": "h", "name": HERO, "is_player": True},
        "a": {"id": "a", "name": "Bram"},
    }


def _intent(alvo):
    return {"actor_id": "g1", "tipo": "ataque", "alvo_id": alvo, "carta_id": None}


def test_hero_target_is_voce():
    row = ei.public_intent(_intent("h"), "desconhecida", actors_by_id=_actors())
    assert HERO not in row["sinal"]
    assert "você" in row["sinal"]


def test_ally_and_enemy_keep_name():
    row = ei.public_intent(_intent("a"), "desconhecida", actors_by_id=_actors())
    assert "Bram" in row["sinal"] and "você" not in row["sinal"]


def _phrases():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for tipo, fams in data.items():
        if tipo.startswith("_"):
            continue
        for fam, frases in fams.items():
            for f in frases:
                yield tipo, fam, f


def test_catalog_lint_no_de_alvo():
    bad = re.compile(
        r"\b(?:de|do|da) \{alvo\}|\{alvo\}-(?:lo|la|los|las)\b|\{alvo\}[^.;:,]*?\w+-(?:lo|la|los|las)\b"
    )
    for tipo, fam, f in _phrases():
        assert not bad.search(f), (tipo, fam, f)
        assert not f.lstrip().startswith("{alvo}"), (tipo, fam, f)
        assert not re.search(r"\{alvo\}[^.]*-(?:lo|la|los|las)\b", f), (tipo, fam, f)


@pytest.mark.parametrize("alvo", ["Mirela5", "você"])
def test_every_phrase_formats_with_name_and_voce(alvo):
    n = 0
    for _tipo, _fam, f in _phrases():
        out = f.format(nome="Goblin", alvo=alvo)
        assert "{" not in out and alvo in out if "{alvo}" in f else "{" not in out
        n += 1
    assert n > 20


@pytest.mark.parametrize("fam", ["fera", "morto_inquieto"])
def test_state_view_omens_without_hero_name(monkeypatch, fam):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    state, metas = _rounds(monkeypatch, 2)
    hero = state["player"]["name"]
    for meta in metas:
        view = api._combat_block({"combat": meta, "enemies": [], "player": {}})
        for row in view.get("pressagios_publicos", []):
            assert hero not in row["sinal"], row
            assert hero not in str(row.get("prenuncio") or "")
    # a família é exercida pelo unitário: ambas leem "você" sem o nome
    for tipo in ("ataque", "controle", "dreno"):
        s = ei.sinal_for(tipo, {"id": "x", "name": "X", "family": fam}, "você", key=tipo)
        assert HERO not in s


def test_real_round_sinal_says_voce(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    _state, metas = _rounds(monkeypatch, 2)
    sinais = [r["sinal"] for m in metas for r in m.get("pressagios_publicos", [])]
    assert sinais and any("você" in s for s in sinais), sinais
